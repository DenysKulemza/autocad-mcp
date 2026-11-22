# autocad-mcp

Headless MCP server that creates and inspects AutoCAD-compatible **DXF** drawings on macOS
(or anywhere) without AutoCAD installed. Built on [ezdxf](https://ezdxf.mozman.at/) and the
official `mcp` Python SDK (2.x). Saved files open directly in AutoCAD (R2013 format by default).

Why not drive AutoCAD directly? AutoCAD for Mac has no COM/.NET automation, so the Windows-style
`pyautocad` servers cannot work there. See `docs/adr/001-headless-dxf-server.md`.

## Tools

| Tool | Purpose |
|------|---------|
| `new_drawing(name, dxf_version="R2013", units="mm")` | Create an empty drawing in memory |
| `open_drawing(name)` | Load `<root>/<name>.dxf` |
| `save_drawing(name)` | Write `<root>/<name>.dxf`, returns the path |
| `drawing_info(name)` | Version, units, entity count, layers, path |
| `add_line(name, start, end, layer?)` | LINE between two `[x, y]` points |
| `add_circle(name, center, radius, layer?)` | CIRCLE |
| `add_polyline(name, points, closed?, layer?)` | Lightweight POLYLINE |
| `add_text(name, text, insert, height?, rotation?, layer?)` | Single-line TEXT |
| `list_entities(name, layer?, entity_type?, limit?)` | Handles, types, layers, geometry |
| `delete_entity(name, handle)` | Remove one entity |
| `render_preview(name, width_px?, height_px?)` | PNG image of the modelspace |

Layers are created on first use. Coordinates are 2D `[x, y]` in the drawing's units.

## Install on a Mac (Claude Desktop)

One line, no AutoCAD or Python knowledge needed:

```bash
curl -fsSL https://raw.githubusercontent.com/DenysKulemza/autocad-mcp/main/install.sh | bash
```

Then restart Claude Desktop. The server appears as **autocad** under Settings → Developer, and
Claude can draw on request, for example:

> Make a new drawing "garage" in metres, draw a 6 by 4 rectangle on layer WALLS, add a door
> 0.9 wide on the bottom wall, label it, show me a preview, then save it.

Saved files land in `~/Documents/autocad-mcp/<name>.dxf`. Open them with AutoCAD (File → Open,
file type DXF) or drag them onto the AutoCAD icon.

What the installer does: installs [uv](https://docs.astral.sh/uv/) if missing, adds an
`autocad` entry to `~/Library/Application Support/Claude/claude_desktop_config.json`, registers
the server in Claude Code too if the `claude` CLI exists, and pre-fetches the code. Updates:
`uv cache clean autocad-mcp` then restart Claude Desktop.

The entry it writes, if you prefer to add it by hand:

```json
{
  "mcpServers": {
    "autocad": {
      "command": "/Users/you/.local/bin/uv",
      "args": ["tool", "run", "--from", "git+https://github.com/DenysKulemza/autocad-mcp", "autocad-mcp"],
      "env": { "AUTOCAD_MCP_ROOT": "/Users/you/Documents/autocad-mcp" }
    }
  }
}
```

## Development setup

```bash
brew install uv
cd ~/PycharmProjects/autocad-mcp
uv sync
uv run pytest
```

Register with Claude Code (user scope, available in every project):

```bash
claude mcp add --scope user autocad -- uv run --directory ~/PycharmProjects/autocad-mcp autocad-mcp
```

Optional: set where drawings are stored (default `~/Documents/autocad-mcp`):

```bash
claude mcp add --scope user -e AUTOCAD_MCP_ROOT=~/Drawings autocad -- uv run --directory ~/PycharmProjects/autocad-mcp autocad-mcp
```

## Development

```bash
uv run pytest          # unit tests + end-to-end stdio tests
uv run ruff check .    # lint
uv run mypy            # types (strict)
```

## Roadmap

- `apply_with_autocad`: run generated AutoLISP on a DWG via `AutoCAD -b` on a Mac that has AutoCAD.
- DWG import/export through ODA File Converter (`ezdxf.addons.odafc`).
- Layers, blocks, dimensions, hatches.
