#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Velum Forge 1.0 Installer (macOS / Linux) ==="

if command -v uv >/dev/null 2>&1; then
  uv venv "$REPO_ROOT/.venv" --python 3.12 --allow-existing
  uv pip install --python "$REPO_ROOT/.venv/bin/python" -e "$REPO_ROOT"
else
  python3 -m venv "$REPO_ROOT/.venv"
  "$REPO_ROOT/.venv/bin/pip" install --upgrade pip
  "$REPO_ROOT/.venv/bin/pip" install -e "$REPO_ROOT"
fi

PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" "$REPO_ROOT/.venv/bin/python" -m velum_forge.cli install-ai
mkdir -p "$HOME/.local/bin"
ln -sf "$REPO_ROOT/.venv/bin/vforge" "$HOME/.local/bin/vforge"

PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" "$REPO_ROOT/.venv/bin/python" -m velum_forge.cli doctor
echo "[DONE] Run 'vforge studio' to open Velum Forge Studio!"
