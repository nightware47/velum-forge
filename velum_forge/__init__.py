"""Velum Forge — AI-Driven B-Rep CAD, Blender 5.2+ PBR Baking, LOD & Game Asset Studio."""
from __future__ import annotations

from pathlib import Path

__version__ = "1.0.0"

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parent
ENGINE_DIR = REPO_ROOT / "engine"
BLENDER_ENGINE_DIR = ENGINE_DIR / "blender"
CAD_ENGINE_DIR = ENGINE_DIR / "cad"
PLUGIN_SRC_DIR = REPO_ROOT / "plugins" / "velum-forge"
EXAMPLES_DIR = REPO_ROOT / "examples"
UI_DIR = PKG_DIR / "ui"
