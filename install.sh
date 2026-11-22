#!/usr/bin/env bash
# One-shot installer for the autocad-mcp server on a Mac.
#
#   curl -fsSL https://raw.githubusercontent.com/DenysKulemza/autocad-mcp/main/install.sh | bash
#
# What it does:
#   1. installs uv (Python package runner) if missing
#   2. registers the server in Claude Desktop (claude_desktop_config.json)
#   3. registers the server in Claude Code too, if the `claude` CLI is installed
# The server itself is fetched and cached by uvx on first launch; nothing else is installed.
# Drawings are saved to ~/Documents/autocad-mcp (override with AUTOCAD_MCP_ROOT).
set -euo pipefail

REPO="${AUTOCAD_MCP_REPO:-https://github.com/DenysKulemza/autocad-mcp}"
DESKTOP_CONFIG="${CLAUDE_DESKTOP_CONFIG:-$HOME/Library/Application Support/Claude/claude_desktop_config.json}"
ROOT="${AUTOCAD_MCP_ROOT:-$HOME/Documents/autocad-mcp}"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

# 1. uv --------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
  say "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
UV="$(command -v uv || echo "$HOME/.local/bin/uv")"
say "uv: $UV ($("$UV" --version))"

# 2. Claude Desktop ---------------------------------------------------------
say "Registering in Claude Desktop: $DESKTOP_CONFIG"
mkdir -p "$(dirname "$DESKTOP_CONFIG")"
mkdir -p "$ROOT"
UV="$UV" REPO="$REPO" ROOT="$ROOT" DESKTOP_CONFIG="$DESKTOP_CONFIG" /usr/bin/python3 - <<'PY'
import json, os, pathlib
path = pathlib.Path(os.environ["DESKTOP_CONFIG"])
try:
    config = json.loads(path.read_text()) if path.exists() and path.read_text().strip() else {}
except json.JSONDecodeError as exc:
    raise SystemExit(f"{path} is not valid JSON ({exc}); fix or remove it and rerun") from exc
servers = config.setdefault("mcpServers", {})
servers["autocad"] = {
    "command": os.environ["UV"],
    "args": ["tool", "run", "--from", f"git+{os.environ['REPO']}", "autocad-mcp"],
    "env": {"AUTOCAD_MCP_ROOT": os.environ["ROOT"]},
}
path.write_text(json.dumps(config, indent=2) + "\n")
print(f"    wrote mcpServers.autocad -> {path}")
PY

# 3. Claude Code (optional) -------------------------------------------------
if command -v claude >/dev/null 2>&1; then
  say "Registering in Claude Code (user scope)"
  claude mcp remove autocad -s user >/dev/null 2>&1 || true
  claude mcp add --scope user -e "AUTOCAD_MCP_ROOT=$ROOT" autocad -- "$UV" tool run --from "git+$REPO" autocad-mcp
fi

# 4. Warm the cache so the first Claude launch is fast -----------------------
say "Fetching the server (first run only, ~1 min)"
"$UV" tool run --from "git+$REPO" python -c "import autocad_mcp; print('    autocad-mcp', autocad_mcp.__version__, 'ready')"

say "Done. Restart Claude Desktop, then ask Claude to draw something."
say "DXF files land in: $ROOT"
