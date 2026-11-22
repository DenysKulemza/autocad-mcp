"""Pure drawing operations over ezdxf documents.

No MCP imports live here so the whole module is unit-testable without a transport.
Drawings are addressed by a short name; files live under a single root directory.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf import units as ezunits
from ezdxf.document import Drawing
from ezdxf.entities import DXFGraphic

Point = tuple[float, float]

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,99}$")

_UNITS: dict[str, int] = {
    "unitless": 0,  # $INSUNITS 0 = unitless (no ezdxf constant)
    "mm": ezunits.MM,
    "cm": ezunits.CM,
    "m": ezunits.M,
    "in": ezunits.IN,
    "ft": ezunits.FT,
}

_DXF_VERSIONS: dict[str, str] = {
    "R2000": "R2000",
    "R2004": "R2004",
    "R2007": "R2007",
    "R2010": "R2010",
    "R2013": "R2013",
    "R2018": "R2018",
}


class DrawingError(ValueError):
    """Raised for invalid names, unknown drawings or bad geometry."""


def normalize_name(name: str) -> str:
    """Return a safe file stem for a drawing name, rejecting path tricks."""
    stem = name[:-4] if name.lower().endswith(".dxf") else name
    if not _NAME_RE.match(stem):
        raise DrawingError(
            f"Invalid drawing name {name!r}: use letters, digits, space, '.', '_' or '-' "
            "(no path separators), max 100 characters."
        )
    return stem


def _xy(point: Any, label: str) -> Point:
    try:
        x, y = point
        return float(x), float(y)
    except (TypeError, ValueError) as exc:
        raise DrawingError(f"{label} must be an [x, y] pair, got {point!r}") from exc


class DrawingStore:
    """Holds open ezdxf documents keyed by drawing name and persists them to ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()
        self._docs: dict[str, Drawing] = {}

    # -- lifecycle ---------------------------------------------------------

    def path_for(self, name: str) -> Path:
        return self.root / f"{normalize_name(name)}.dxf"

    def new(self, name: str, dxf_version: str = "R2013", units: str = "mm") -> dict[str, Any]:
        stem = normalize_name(name)
        if dxf_version not in _DXF_VERSIONS:
            raise DrawingError(
                f"Unsupported DXF version {dxf_version!r}; choose one of {sorted(_DXF_VERSIONS)}"
            )
        if units not in _UNITS:
            raise DrawingError(f"Unsupported units {units!r}; choose one of {sorted(_UNITS)}")
        doc = ezdxf.new(_DXF_VERSIONS[dxf_version], setup=True)
        doc.units = _UNITS[units]
        self._docs[stem] = doc
        return self.info(stem)

    def open(self, name: str) -> dict[str, Any]:
        stem = normalize_name(name)
        path = self.path_for(stem)
        if not path.is_file():
            raise DrawingError(f"No DXF file at {path}")
        doc = ezdxf.readfile(path)
        self._docs[stem] = doc
        return self.info(stem)

    def save(self, name: str) -> dict[str, Any]:
        stem, doc = self._get(name)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.path_for(stem)
        doc.saveas(path)
        result = self.info(stem)
        result["path"] = str(path)
        return result

    def info(self, name: str) -> dict[str, Any]:
        stem, doc = self._get(name)
        msp = doc.modelspace()
        unit_name = next((k for k, v in _UNITS.items() if v == doc.units), str(doc.units))
        return {
            "name": stem,
            "dxf_version": doc.acad_release,
            "units": unit_name,
            "entity_count": len(msp),
            "layers": sorted(layer.dxf.name for layer in doc.layers),
            "path": str(self.path_for(stem)) if self.path_for(stem).exists() else None,
        }

    def open_names(self) -> list[str]:
        return sorted(self._docs)

    def _get(self, name: str) -> tuple[str, Drawing]:
        stem = normalize_name(name)
        doc = self._docs.get(stem)
        if doc is None:
            raise DrawingError(
                f"Drawing {stem!r} is not open. Call new_drawing or open_drawing first. "
                f"Open drawings: {self.open_names()}"
            )
        return stem, doc

    def _layer_attribs(self, doc: Drawing, layer: str | None) -> dict[str, Any]:
        if layer is None:
            return {}
        if layer not in doc.layers:
            doc.layers.add(layer)
        return {"layer": layer}

    # -- entities ----------------------------------------------------------

    def add_line(self, name: str, start: Any, end: Any, layer: str | None = None) -> dict[str, Any]:
        _, doc = self._get(name)
        entity = doc.modelspace().add_line(
            _xy(start, "start"), _xy(end, "end"), dxfattribs=self._layer_attribs(doc, layer)
        )
        return describe(entity)

    def add_circle(
        self, name: str, center: Any, radius: float, layer: str | None = None
    ) -> dict[str, Any]:
        _, doc = self._get(name)
        if radius <= 0:
            raise DrawingError(f"radius must be positive, got {radius}")
        entity = doc.modelspace().add_circle(
            _xy(center, "center"), float(radius), dxfattribs=self._layer_attribs(doc, layer)
        )
        return describe(entity)

    def add_polyline(
        self, name: str, points: list[Any], closed: bool = False, layer: str | None = None
    ) -> dict[str, Any]:
        _, doc = self._get(name)
        if len(points) < 2:
            raise DrawingError("polyline needs at least two points")
        pts = [_xy(p, f"points[{i}]") for i, p in enumerate(points)]
        entity = doc.modelspace().add_lwpolyline(
            pts, close=closed, dxfattribs=self._layer_attribs(doc, layer)
        )
        return describe(entity)

    def add_text(
        self,
        name: str,
        text: str,
        insert: Any,
        height: float = 2.5,
        rotation: float = 0.0,
        layer: str | None = None,
    ) -> dict[str, Any]:
        _, doc = self._get(name)
        if height <= 0:
            raise DrawingError(f"height must be positive, got {height}")
        entity = doc.modelspace().add_text(
            text,
            height=float(height),
            rotation=float(rotation),
            dxfattribs=self._layer_attribs(doc, layer),
        )
        entity.set_placement(_xy(insert, "insert"))
        return describe(entity)

    def list_entities(
        self,
        name: str,
        layer: str | None = None,
        entity_type: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        _, doc = self._get(name)
        query = "*"
        conditions: list[str] = []
        if entity_type:
            query = entity_type.upper()
        if layer:
            conditions.append(f'layer=="{layer}"')
        if conditions:
            query += "[" + " & ".join(conditions) + "]"
        entities = doc.modelspace().query(query)
        return [describe(e) for e in list(entities)[: max(0, limit)]]

    def delete_entity(self, name: str, handle: str) -> dict[str, Any]:
        _, doc = self._get(name)
        entity = doc.entitydb.get(handle)
        if entity is None or not entity.is_alive:
            raise DrawingError(f"No entity with handle {handle!r}")
        summary = describe(entity) if isinstance(entity, DXFGraphic) else {"handle": handle}
        doc.modelspace().delete_entity(entity)  # type: ignore[arg-type]
        return summary

    # -- rendering ---------------------------------------------------------

    def render_png(self, name: str, width_px: int = 1200, height_px: int = 900) -> bytes:
        _, doc = self._get(name)
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.config import BackgroundPolicy, Configuration
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

        dpi = 100
        fig = plt.figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
        ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        config = Configuration(background_policy=BackgroundPolicy.WHITE)
        Frontend(ctx, backend, config=config).draw_layout(doc.modelspace(), finalize=True)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi)
        plt.close(fig)
        return buf.getvalue()


def describe(entity: DXFGraphic) -> dict[str, Any]:
    """Compact JSON-friendly summary of a modelspace entity."""
    kind = entity.dxftype()
    out: dict[str, Any] = {
        "handle": entity.dxf.handle,
        "type": kind,
        "layer": entity.dxf.layer,
    }
    if kind == "LINE":
        out["start"] = _round(entity.dxf.start)
        out["end"] = _round(entity.dxf.end)
    elif kind == "CIRCLE":
        out["center"] = _round(entity.dxf.center)
        out["radius"] = round(float(entity.dxf.radius), 6)
    elif kind == "LWPOLYLINE":
        out["points"] = [_round(p) for p in entity.get_points(format="xy")]  # type: ignore[attr-defined]
        out["closed"] = bool(entity.closed)  # type: ignore[attr-defined]
    elif kind == "TEXT":
        out["text"] = entity.dxf.text
        out["insert"] = _round(entity.dxf.insert)
        out["height"] = round(float(entity.dxf.height), 6)
        out["rotation"] = round(float(entity.dxf.rotation), 6)
    return out


def _round(vec: Any) -> list[float]:
    return [round(float(c), 6) for c in tuple(vec)[:2]]
