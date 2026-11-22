# ADR-001: Headless DXF server instead of a live AutoCAD bridge

Date: 2026-11-22. Status: accepted.

## Context

We want an MCP server that lets Claude create and inspect AutoCAD drawings from a Mac.
AutoCAD for Mac exposes no COM/ActiveX or .NET automation; only AutoLISP, a C++ ObjectARX
SDK, and a `-b <script>` startup switch exist. Almost every public "AutoCAD MCP" relies on
COM via pyautocad and therefore only works on Windows. AutoCAD (full) is available on a
second Mac, not on the development machine, so a live bridge could not be exercised here.

## Decision

Build a headless Python MCP server (stdio) that reads and writes DXF files with ezdxf:

- `mcp` 2.x `MCPServer` (FastMCP was renamed in 2.0); stdio transport; Python 3.12 via uv.
- Drawings are addressed by a short name and stored under one root directory
  (`AUTOCAD_MCP_ROOT`, default `~/Documents/autocad-mcp`). Names are validated so tools
  can never write outside the root.
- Default DXF version R2013 (opens in AutoCAD 2013 and later); R2000–R2018 selectable.
- Pure drawing logic lives in `drawings.py` with no MCP imports; `server.py` is a thin
  tool layer. Every saved file is checked with `ezdxf.audit()` in tests.

## Alternatives considered

1. **AutoLISP over AppleScript keystrokes**: real-time control of the open drawing, but
   needs Accessibility permission, breaks on focus changes, and cannot be tested in CI.
2. **AutoLISP batch via `AutoCAD -b script`**: robust, but one AutoCAD launch per job
   (tens of seconds) and requires a licensed install on the same machine. Kept as a future
   optional tool (`apply_with_autocad`) for the AutoCAD Mac.
3. **ObjectARX C++ plugin with a local socket**: the cleanest live bridge, but needs
   Xcode, the OARXMAC SDK, signing, and a rebuild per AutoCAD release.
4. **Pin `mcp<2` to keep FastMCP**: starts a new project on a deprecated API.

## Consequences

- No live editing of a drawing that is open in AutoCAD; the workflow is build → save →
  open the .dxf in AutoCAD.
- DWG is not produced natively. The ODA File Converter (free, has a macOS build) can be
  wired in later through `ezdxf.addons.odafc`.
- The server is fully unit- and end-to-end-testable without any Autodesk software.
