"""End-to-end: launch the real server over stdio and drive it with the MCP client."""

import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import types
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

EXPECTED_TOOLS = {
    "new_drawing",
    "open_drawing",
    "save_drawing",
    "drawing_info",
    "add_line",
    "add_circle",
    "add_polyline",
    "add_text",
    "list_entities",
    "delete_entity",
    "render_preview",
}


@asynccontextmanager
async def connect(tmp_path: Path) -> AsyncIterator[tuple[ClientSession, Path]]:
    """Launch the real server as a subprocess over stdio.

    A context manager rather than an async fixture: anyio cancel scopes must be entered
    and exited in the same task, which pytest-asyncio fixtures do not guarantee.
    """
    root = tmp_path / "root"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "autocad_mcp.server"],
        env={**os.environ, "AUTOCAD_MCP_ROOT": str(root)},
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as s:
        await s.initialize()
        yield s, root


def _structured(result: types.CallToolResult | types.Result) -> object:
    assert isinstance(result, types.CallToolResult), result
    assert not result.is_error, result.content
    return result.structured_content


async def test_lists_expected_tools(tmp_path: Path) -> None:
    async with connect(tmp_path) as (s, _):
        tools = await s.list_tools()
        assert {t.name for t in tools.tools} == EXPECTED_TOOLS
        for tool in tools.tools:
            assert tool.description, f"{tool.name} has no description"


async def test_full_workflow_over_stdio(tmp_path: Path) -> None:
    async with connect(tmp_path) as (s, root):
        info = _structured(await s.call_tool("new_drawing", {"name": "e2e", "units": "mm"}))
        assert isinstance(info, dict) and info["name"] == "e2e"

        line = _structured(
            await s.call_tool(
                "add_line", {"name": "e2e", "start": [0, 0], "end": [100, 0], "layer": "L"}
            )
        )
        assert isinstance(line, dict) and line["type"] == "LINE"
        _structured(
            await s.call_tool("add_circle", {"name": "e2e", "center": [50, 50], "radius": 10})
        )
        _structured(
            await s.call_tool(
                "add_polyline",
                {"name": "e2e", "points": [[0, 0], [10, 0], [10, 10]], "closed": True},
            )
        )
        _structured(await s.call_tool("add_text", {"name": "e2e", "text": "hi", "insert": [1, 1]}))

        listed = _structured(await s.call_tool("list_entities", {"name": "e2e"}))
        assert isinstance(listed, dict)  # list results are wrapped as {"result": [...]}
        entities = listed["result"]
        assert sorted(e["type"] for e in entities) == ["CIRCLE", "LINE", "LWPOLYLINE", "TEXT"]

        _structured(await s.call_tool("delete_entity", {"name": "e2e", "handle": line["handle"]}))
        after = _structured(
            await s.call_tool("list_entities", {"name": "e2e", "entity_type": "LINE"})
        )
        assert isinstance(after, dict) and after["result"] == []

        saved = _structured(await s.call_tool("save_drawing", {"name": "e2e"}))
        assert isinstance(saved, dict)
        assert Path(saved["path"]) == root / "e2e.dxf"
        assert (root / "e2e.dxf").is_file()

        preview = await s.call_tool(
            "render_preview", {"name": "e2e", "width_px": 300, "height_px": 200}
        )
        assert isinstance(preview, types.CallToolResult) and not preview.is_error
        images = [c for c in preview.content if isinstance(c, types.ImageContent)]
        assert len(images) == 1 and images[0].mime_type == "image/png"


async def test_tool_errors_are_reported_not_swallowed(tmp_path: Path) -> None:
    async with connect(tmp_path) as (s, _):
        result = await s.call_tool("add_line", {"name": "missing", "start": [0, 0], "end": [1, 1]})
        assert isinstance(result, types.CallToolResult)
        assert result.is_error
        text = " ".join(c.text for c in result.content if isinstance(c, types.TextContent))
        assert "not open" in text
