#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== Velum Forge 1.0 Installer (macOS / Linux) ==="

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "[1/4] uv/Python bootstrapper not found — installing standalone uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

echo "[1/4] Provisioning standalone Python 3.12 CAD environment via uv..."
uv python install 3.12
uv venv "$REPO_ROOT/.venv" --python 3.12 --allow-existing
uv pip install --python "$REPO_ROOT/.venv/bin/python" -e "$REPO_ROOT"

echo "[2/4] Installing AI Agent Plugins & Skills..."
PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" "$REPO_ROOT/.venv/bin/python" -m velum_forge.cli install-ai

echo "[3/4] Installing 'vforge' CLI symlink..."
mkdir -p "$HOME/.local/bin"
ln -sf "$REPO_ROOT/.venv/bin/vforge" "$HOME/.local/bin/vforge"

echo "[4/4] Running Environment Doctor..."
PYTHONPATH="$REPO_ROOT:${PYTHONPATH:-}" "$REPO_ROOT/.venv/bin/python" -m velum_forge.cli doctor
echo "[DONE] Run 'vforge studio' to open Velum Forge Studio!"
