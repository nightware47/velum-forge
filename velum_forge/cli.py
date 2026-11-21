"""Unified `vforge` CLI for Velum Forge."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from . import CAD_ENGINE_DIR, EXAMPLES_DIR, REPO_ROOT, __version__
from .doctor import find_blender_exe, find_venv_python, install_ai_integrations, run_doctor
from .scaffold import scaffold_asset
from .studio_server import launch_studio


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vforge",
        description="Velum Forge — AI-Driven B-Rep CAD, Blender 5.2+ Cycles PBR Baking, LOD & Game Asset Studio",
    )
    parser.add_argument("--version", action="version", version=f"velum-forge {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    p_doc = sub.add_parser("doctor", help="Check Blender 5.2+, CAD B-Rep venv, GPU & AI agent plugins")
    p_doc.add_argument("--json", action="store_true")

    p_ai = sub.add_parser("install-ai", help="Install Velum Forge plugin & skills into Antigravity, Claude Code & workspace")
    p_ai.add_argument("--workspace", default="", help="Optional project folder to populate .agents/skills & .cursor/rules")
    p_ai.add_argument("--no-antigravity", action="store_true")
    p_ai.add_argument("--no-claude", action="store_true")

    p_stu = sub.add_parser("studio", help="Launch the interactive Velum Forge Desktop Studio App")
    p_stu.add_argument("--port", type=int, default=8765)
    p_stu.add_argument("--no-open", action="store_true")

    sub.add_parser("setup-gui", help="Launch the native Windows Setup & Workflow Installer GUI")

    p_new = sub.add_parser("new", help="Scaffold a new 3D asset generator (`boat`, `fish`, `prop`, `cad`)")
    p_new.add_argument("kind", choices=["boat", "fish", "prop", "cad"])
    p_new.add_argument("name", help="Asset name or slug (e.g. yellowfin_tuna)")
    p_new.add_argument("--dir", default=str(EXAMPLES_DIR), help="Parent directory for the new asset folder")

    p_qa = sub.add_parser("qa", help="Run the 10-view automated visual & geometric QA gate on an asset")
    p_qa.add_argument("asset", help="Path to .py, .blend, .glb, .fbx, or .step asset")
    p_qa.add_argument("--profile", default="roblox", choices=["roblox", "game", "render", "print"])
    p_qa.add_argument("--forward-axis", default="+Y", choices=["+Y", "-Y"])
    p_qa.add_argument("--fast", action="store_true")

    p_bake = sub.add_parser("bake", help="Run headless Blender 5.2+ 2K Cycles PBR bake + variants + LODs script")
    p_bake.add_argument("script", help="Path to bake_lod_variants.py")

    p_ins = sub.add_parser("inspect", help="Inspect mesh watertightness, Euler number, m/studs size & 20k tri cap")
    p_ins.add_argument("mesh", help="Path to .glb/.stl/.obj/.ply")
    p_ins.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.cmd in (None, "studio"):
        port = getattr(args, "port", 8765)
        no_open = getattr(args, "no_open", False)
        launch_studio(port=port, open_window=not no_open)
        return 0

    if args.cmd == "setup-gui":
        from .installer_gui import run_installer_gui

        return run_installer_gui()

    if args.cmd == "doctor":
        rep = run_doctor()
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            print(f"=== Velum Forge Doctor (v{__version__}) ===")
            for chk in rep["checks"]:
                badge = "[OK]  " if chk["ok"] else "[WARN]"
                print(f"  {badge} {chk['label']:38s} -> {chk['detail']}")
        return 0 if rep["ok"] else 1

    if args.cmd == "install-ai":
        res = install_ai_integrations(
            antigravity=not args.no_antigravity,
            claude_code=not args.no_claude,
            workspace_dir=args.workspace or None,
        )
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "new":
        res = scaffold_asset(args.kind, args.name, args.dir)
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "qa":
        if platform.system() == "Windows":
            ps_exe = shutil.which("powershell") or "powershell.exe"
            cmd = [
                ps_exe,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(CAD_ENGINE_DIR / "run_qa.ps1"),
                "-Asset",
                args.asset,
                "-Profile",
                args.profile,
                "-ForwardAxis",
                args.forward_axis,
            ]
            if args.fast:
                cmd.append("-Fast")
            return subprocess.call(cmd, cwd=str(REPO_ROOT))
        blender_exe = find_blender_exe() or "blender"
        out_d = str(REPO_ROOT / ".qa-out" / Path(args.asset).stem)
        cmd = [
            blender_exe,
            "-b",
            "--python-exit-code",
            "1",
            "-P",
            str(REPO_ROOT / "engine" / "blender" / "qa_pipeline.py"),
            "--",
            "--input",
            args.asset,
            "--out-dir",
            out_d,
            "--profile",
            args.profile,
            "--forward-axis",
            args.forward_axis,
        ]
        return subprocess.call(cmd, cwd=str(REPO_ROOT))

    if args.cmd == "bake":
        blender_exe = find_blender_exe()
        if not blender_exe:
            print("ERROR: Blender 5.2+ executable not found.", file=sys.stderr)
            return 1
        return subprocess.call([blender_exe, "-b", "--python-exit-code", "1", "-P", os.path.abspath(args.script)])

    if args.cmd == "inspect":
        py = find_venv_python()
        cmd = [py, str(CAD_ENGINE_DIR / "cad_bridge.py"), "inspect", args.mesh]
        if args.json:
            cmd.append("--json")
        return subprocess.call(cmd)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
