#!/bin/bash
# start_mcp.sh — resolves plugin root from script location and starts MCP server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/.venv"
MCP_SERVER="${SCRIPT_DIR}/mcp_server.py"

# If venv doesn't exist yet, exit gracefully
if [ ! -f "${VENV}/bin/python" ]; then
  echo "[codebase-agent] Run /codebase-agent:index to set up first." >&2
  exit 1
fi

export PYTHONPATH="${SCRIPT_DIR}"
exec "${VENV}/bin/python" "${MCP_SERVER}"