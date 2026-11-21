"""Environment diagnostics & 1-click AI customization installer for Antigravity, Claude Code & Cursor."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import PLUGIN_SRC_DIR, REPO_ROOT


def find_blender_exe() -> str | None:
    env_b = os.environ.get("VELUM_BLENDER_EXE")
    if env_b and os.path.isfile(env_b):
        return env_b

    candidates: list[str] = []
    if platform.system() == "Windows":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        bf = Path(pf) / "Blender Foundation"
        if bf.is_dir():
            for sub in sorted(bf.iterdir(), key=lambda p: p.name, reverse=True):
                exe = sub / "blender.exe"
                if exe.is_file():
                    candidates.append(str(exe))
    elif platform.system() == "Darwin":
        mac_app = "/Applications/Blender.app/Contents/MacOS/Blender"
        if os.path.isfile(mac_app):
            candidates.append(mac_app)

    which_b = shutil.which("blender")
    if which_b:
        candidates.append(which_b)
    return candidates[0] if candidates else None


def find_venv_python() -> str:
    if platform.system() == "Windows":
        cand = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        cand = REPO_ROOT / ".venv" / "bin" / "python"
    if cand.is_file():
        return str(cand)
    return sys.executable


def _probe_blender_version(exe: str | None) -> str | None:
    if not exe:
        return None
    try:
        cp = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=8, check=False)
        first = (cp.stdout or "").splitlines()
        return first[0].strip() if first else "Blender (detected)"
    except Exception:
        return None


def _probe_cad_packages(py_exe: str) -> dict[str, bool]:
    code = (
        "import importlib.util, json; "
        "mods=['build123d','trimesh','pymeshlab','PIL','numpy']; "
        "print(json.dumps({m: importlib.util.find_spec(m) is not None for m in mods}))"
    )
    try:
        cp = subprocess.run([py_exe, "-c", code], capture_output=True, text=True, timeout=10, check=False)
        if cp.returncode == 0 and cp.stdout.strip():
            return json.loads(cp.stdout.strip().splitlines()[-1])
    except Exception:
        pass
    return {m: False for m in ("build123d", "trimesh", "pymeshlab", "PIL", "numpy")}


def get_design_output_dir() -> Path:
    env_d = os.environ.get("VELUM_DESIGN_OUTPUT_DIR")
    if env_d:
        return Path(env_d)
    home = Path.home()
    od = home / "OneDrive" / "Desktop"
    if od.is_dir():
        return od / "Design Model Output"
    return home / "Desktop" / "Design Model Output"


def run_doctor() -> dict[str, Any]:
    """Return comprehensive health report for Blender, CAD venv, GPU tools, and AI agent plugins."""
    blender_exe = find_blender_exe()
    blender_ver = _probe_blender_version(blender_exe)
    venv_py = find_venv_python()
    has_venv = (REPO_ROOT / ".venv").is_dir()
    cad_mods = _probe_cad_packages(venv_py)
    uv_exe = shutil.which("uv")
    gh_exe = shutil.which("gh")

    home = Path.home()
    agy_plugin_dir = home / ".gemini" / "config" / "plugins" / "velum-forge"
    claude_skills_dir = home / ".claude" / "skills"
    claude_installed = (claude_skills_dir / "velum-3d-workflow" / "SKILL.md").is_file()
    agy_installed = (agy_plugin_dir / "plugin.json").is_file()
    dmo = get_design_output_dir()

    checks = [
        {
            "id": "blender",
            "label": "Blender 5.2+ LTS Engine",
            "ok": blender_exe is not None,
            "detail": f"{blender_ver} ({blender_exe})" if blender_exe else "Not found — install Blender 5.2 LTS+",
        },
        {
            "id": "venv",
            "label": "Velum Forge Python .venv",
            "ok": has_venv and all(cad_mods.values()),
            "detail": f"{venv_py} | modules: " + ", ".join(f"{k}={'OK' if v else 'MISSING'}" for k, v in cad_mods.items()),
        },
        {
            "id": "uv",
            "label": "uv Fast Python Manager",
            "ok": uv_exe is not None,
            "detail": uv_exe or "Optional (pip fallback available)",
        },
        {
            "id": "antigravity",
            "label": "Antigravity Plugin (velum-forge)",
            "ok": agy_installed,
            "detail": str(agy_plugin_dir) if agy_installed else "Not installed yet (click 'Sync AI Skills')",
        },
        {
            "id": "claude",
            "label": "Claude Code CLI Skills (~/.claude/skills)",
            "ok": claude_installed,
            "detail": str(claude_skills_dir) if claude_installed else "Not installed yet (click 'Sync AI Skills')",
        },
        {
            "id": "output_dir",
            "label": "Design Model Output Showcase Folder",
            "ok": dmo.is_dir(),
            "detail": str(dmo),
        },
    ]

    all_core_ok = bool(blender_exe) and all(cad_mods.values())
    return {
        "ok": all_core_ok,
        "repo_root": str(REPO_ROOT),
        "blender_exe": blender_exe,
        "blender_version": blender_ver,
        "venv_python": venv_py,
        "uv_exe": uv_exe,
        "gh_exe": gh_exe,
        "cad_modules": cad_mods,
        "antigravity_plugin_installed": agy_installed,
        "claude_skills_installed": claude_installed,
        "design_output_dir": str(dmo),
        "checks": checks,
    }


def install_ai_integrations(
    *,
    antigravity: bool = True,
    claude_code: bool = True,
    workspace_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Install Velum Forge plugin, skills & rules into Antigravity, Claude Code, and optional workspace."""
    home = Path.home()
    installed: dict[str, Any] = {}

    # Ensure Design Model Output directory exists
    dmo = get_design_output_dir()
    dmo.mkdir(parents=True, exist_ok=True)
    installed["design_output_dir"] = str(dmo)

    # 1. Google Antigravity Global Plugin (~/.gemini/config/plugins/velum-forge)
    # Note: Never mutate ~/.gemini/config/config.json directly; Antigravity discovers plugins/ automatically!
    if antigravity:
        dst_plugin = home / ".gemini" / "config" / "plugins" / "velum-forge"
        if dst_plugin.exists():
            shutil.rmtree(dst_plugin)
        dst_plugin.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PLUGIN_SRC_DIR, dst_plugin)
        # Stamp absolute engine path helper into plugin for cross-workspace CLI discovery
        (dst_plugin / ".velum_forge_root").write_text(str(REPO_ROOT), encoding="utf-8")
        installed["antigravity_plugin"] = str(dst_plugin)

    # 2. Claude Code CLI Global Skills (~/.claude/skills/velum-*)
    if claude_code:
        claude_skills = home / ".claude" / "skills"
        claude_skills.mkdir(parents=True, exist_ok=True)
        copied_skills: list[str] = []
        src_skills = PLUGIN_SRC_DIR / "skills"
        for sk_dir in sorted(src_skills.iterdir()):
            if sk_dir.is_dir() and (sk_dir / "SKILL.md").is_file():
                dst_sk = claude_skills / sk_dir.name
                if dst_sk.exists():
                    shutil.rmtree(dst_sk)
                shutil.copytree(sk_dir, dst_sk)
                copied_skills.append(sk_dir.name)
        installed["claude_skills"] = copied_skills

    # 3. Optional Project Workspace (.agents/skills + .cursor/rules/velum-forge.mdc)
    if workspace_dir:
        ws = Path(workspace_dir).resolve()
        ws_agents = ws / ".agents" / "skills"
        ws_agents.mkdir(parents=True, exist_ok=True)
        for sk_dir in sorted((PLUGIN_SRC_DIR / "skills").iterdir()):
            if sk_dir.is_dir():
                dst_sk = ws_agents / sk_dir.name
                if dst_sk.exists():
                    shutil.rmtree(dst_sk)
                shutil.copytree(sk_dir, dst_sk)
        cursor_rules = ws / ".cursor" / "rules"
        cursor_rules.mkdir(parents=True, exist_ok=True)
        rules_body = (PLUGIN_SRC_DIR / "rules" / "AGENTS.md").read_text(encoding="utf-8")
        mdc = (
            "---\n"
            "description: Velum Forge 3D CAD, Blender 5.2+ PBR Baking, QA & LOD Rules\n"
            "globs: **/*.py, **/*.blend, **/*.glb, **/*.step\n"
            "alwaysApply: false\n"
            "---\n\n"
            + rules_body
        )
        (cursor_rules / "velum-forge.mdc").write_text(mdc, encoding="utf-8")
        installed["workspace_configured"] = str(ws)

    return installed
