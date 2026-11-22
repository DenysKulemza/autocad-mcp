"""MCP server exposing AutoCAD-compatible DXF drawing tools over stdio.

Run with ``autocad-mcp`` (console script) or ``python -m autocad_mcp.server``.
Set ``AUTOCAD_MCP_ROOT`` to choose where .dxf files are stored
(default: ``~/Documents/autocad-mcp``).
"""

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from autocad_mcp.drawings import DrawingError, DrawingStore

DEFAULT_ROOT = "~/Documents/autocad-mcp"

# ezdxf logs table/dictionary creation at INFO; keep stderr (the MCP log channel) quiet.
logging.getLogger("ezdxf").setLevel(logging.WARNING)

store = DrawingStore(Path(os.environ.get("AUTOCAD_MCP_ROOT", DEFAULT_ROOT)))

mcp = MCPServer(
    "autocad-mcp",
    instructions=(
        "Create and inspect AutoCAD-compatible DXF drawings without AutoCAD. "
        "Workflow: new_drawing or open_drawing, add entities, list_entities to verify, "
        "render_preview to look at it, then save_drawing. All coordinates are 2D [x, y] in the "
        f"drawing's units. Files are stored under {store.root}."
    ),
)


def drawing_errors[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Re-raise DrawingError as ToolError so its message reaches the model.

    mcp 2.x reports any other exception as a generic "Error executing tool" crash.
    """

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except DrawingError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


@mcp.tool()
@drawing_errors
def new_drawing(name: str, dxf_version: str = "R2013", units: str = "mm") -> dict[str, Any]:
    """Create a new empty drawing in memory.

    name: short file stem (letters, digits, space, '.', '_', '-'); '.dxf' is added on save.
    dxf_version: one of R2000, R2004, R2007, R2010, R2013, R2018 (R2013 opens in AutoCAD 2013+).
    units: unitless, mm, cm, m, in, ft.
    """
    return store.new(name, dxf_version, units)


@mcp.tool()
@drawing_errors
def open_drawing(name: str) -> dict[str, Any]:
    """Load an existing .dxf file from the drawings root into memory."""
    return store.open(name)


@mcp.tool()
@drawing_errors
def save_drawing(name: str) -> dict[str, Any]:
    """Write the drawing to <root>/<name>.dxf. Returns the path; open it in AutoCAD."""
    return store.save(name)


@mcp.tool()
@drawing_errors
def drawing_info(name: str) -> dict[str, Any]:
    """Summary of an open drawing: version, units, entity count, layers, saved path."""
    return store.info(name)


@mcp.tool()
@drawing_errors
def add_line(
    name: str, start: list[float], end: list[float], layer: str | None = None
) -> dict[str, Any]:
    """Add a LINE from start [x, y] to end [x, y]. Creates the layer if it does not exist."""
    return store.add_line(name, start, end, layer)


@mcp.tool()
@drawing_errors
def add_circle(
    name: str, center: list[float], radius: float, layer: str | None = None
) -> dict[str, Any]:
    """Add a CIRCLE with center [x, y] and positive radius."""
    return store.add_circle(name, center, radius, layer)


@mcp.tool()
@drawing_errors
def add_polyline(
    name: str, points: list[list[float]], closed: bool = False, layer: str | None = None
) -> dict[str, Any]:
    """Add a lightweight POLYLINE through points [[x, y], ...]; closed=True joins last to first."""
    return store.add_polyline(name, points, closed, layer)


@mcp.tool()
@drawing_errors
def add_text(
    name: str,
    text: str,
    insert: list[float],
    height: float = 2.5,
    rotation: float = 0.0,
    layer: str | None = None,
) -> dict[str, Any]:
    """Add single-line TEXT at insert [x, y] with the given height (drawing units) and rotation."""
    return store.add_text(name, text, insert, height, rotation, layer)


@mcp.tool()
@drawing_errors
def list_entities(
    name: str, layer: str | None = None, entity_type: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    """List modelspace entities with handle, type, layer and geometry.

    Filter by layer name and/or entity_type (LINE, CIRCLE, LWPOLYLINE, TEXT, ...).
    """
    return store.list_entities(name, layer, entity_type, limit)


@mcp.tool()
@drawing_errors
def delete_entity(name: str, handle: str) -> dict[str, Any]:
    """Delete one entity by its handle (see list_entities)."""
    return store.delete_entity(name, handle)


@mcp.tool()
@drawing_errors
def render_preview(name: str, width_px: int = 1200, height_px: int = 900) -> Image:
    """Render the modelspace to a PNG image so you can look at the drawing."""
    return Image(data=store.render_png(name, width_px, height_px), format="png")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
