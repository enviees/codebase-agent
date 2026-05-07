#!/bin/bash
# setup.sh — runs on SessionStart or when invoked by index command

# Resolve plugin root from script location if CLAUDE_PLUGIN_ROOT is not set
if [ -z "${CLAUDE_PLUGIN_ROOT}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
else
  PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
fi

VENV="${PLUGIN_ROOT}/.venv"
REQUIREMENTS="${PLUGIN_ROOT}/requirements.txt"
SETUP_DONE="${PLUGIN_ROOT}/.setup_done"

# Already set up — skip
if [ -f "$SETUP_DONE" ]; then
  exit 0
fi

echo ""
echo "[codebase-agent] First run — setting up dependencies..."
echo ""

# Check Python 3.10+
PYTHON=""
for cmd in python3.12 python3.11 python3.10 python3; do
  if command -v "$cmd" &>/dev/null; then
    VERSION=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
    MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
    if [ "$MAJOR" -ge 3 ] && [ "$VERSION" -ge 10 ]; then
      PYTHON="$cmd"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  echo "[codebase-agent] ❌ Python 3.10+ is required but not found."
  echo "   Install it with: brew install python@3.11"
  exit 0
fi

echo "[codebase-agent] Using $PYTHON"

# Create venv
"$PYTHON" -m venv "$VENV"
if [ $? -ne 0 ]; then
  echo "[codebase-agent] ❌ Failed to create virtual environment."
  exit 0
fi

# Install dependencies
echo "[codebase-agent] Installing dependencies (this takes ~30 seconds)..."
"$VENV/bin/pip" install -r "$REQUIREMENTS" -q
if [ $? -ne 0 ]; then
  echo "[codebase-agent] ❌ pip install failed. Check your internet connection."
  exit 0
fi

# Install mcp
"$VENV/bin/pip" install "mcp[cli]" -q

# Mark setup as done
touch "$SETUP_DONE"

echo ""
echo "[codebase-agent] ✅ Setup complete!"
echo ""
echo "   Next: Add your API keys to ~/.zshrc:"
echo "     export OPENAI_API_KEY=sk-..."
echo "     export DEEPSEEK_API_KEY=sk-..."
echo ""
echo "   Then open any project and say: index this project"
echo ""