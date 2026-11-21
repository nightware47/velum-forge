"""Unified `vforge` CLI for Velum Forge (Generate with References, QA, Bake, Doctor & Studio)."""
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
from .doctor import find_blender_exe, find_venv_python, install_ai_integrations, run_doctor, set_custom_blender_exe
from .generator import build_agent_handoff_prompt, build_ai_cli_invocation, generate_parametric_scripts, slugify
from .references import stage_local_reference_files
from .scaffold import scaffold_asset
from .studio_server import launch_studio


def _run_qa_cli(asset_path: str, profile: str = "roblox", forward_axis: str = "+Y", ref_path: str = "", fast: bool = False) -> int:
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
            asset_path,
            "-Profile",
            profile,
            "-ForwardAxis",
            forward_axis,
        ]
        if ref_path:
            cmd.extend(["-Ref", ref_path])
        if fast:
            cmd.append("-Fast")
        return subprocess.call(cmd, cwd=str(REPO_ROOT))

    blender_exe = find_blender_exe() or "blender"
    out_d = str(REPO_ROOT / ".qa-out" / Path(asset_path).stem)
    cmd = [
        blender_exe,
        "-b",
        "--python-exit-code",
        "1",
        "-P",
        str(REPO_ROOT / "engine" / "blender" / "qa_pipeline.py"),
        "--",
        "--input",
        asset_path,
        "--out-dir",
        out_d,
        "--profile",
        profile,
        "--forward-axis",
        forward_axis,
    ]
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vforge",
        description="Velum Forge — Reference-Driven AI 3D CAD, Blender 5.2+ Cycles PBR Baking, LOD & Game Asset Studio",
    )
    parser.add_argument("--version", action="version", version=f"velum-forge {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    # 1. GENERATE (New primary command!)
    p_gen = sub.add_parser("generate", help="Generate a 3D asset from a prompt + optional reference images!")
    p_gen.add_argument("name", help="Asset name or slug (e.g. 'red_snapper' or 'patrol_rib_28')")
    p_gen.add_argument("--prompt", default="", help="Detailed natural-language description of proportions, parts & materials")
    p_gen.add_argument("--kind", default="fish", choices=["fish", "boat", "prop", "cad"], help="3D archetype")
    p_gen.add_argument("--length", type=float, default=1.20, help="Target real-world length/size in meters (default: 1.20)")
    p_gen.add_argument("--ref", action="append", default=[], help="Reference image path(s) — repeat --ref for front/side/hero photos")
    p_gen.add_argument("--engine", default="parametric", choices=["parametric", "claude", "codex", "gemini", "handoff"], help="Generation engine")
    p_gen.add_argument("--dir", default=str(EXAMPLES_DIR), help="Parent output directory")

    # 2. ADD-REF & BRIEF
    p_ref = sub.add_parser("add-ref", help="Attach reference image(s) to an asset folder and analyze palette/proportions")
    p_ref.add_argument("asset_dir", help="Target asset directory")
    p_ref.add_argument("images", nargs="+", help="One or more PNG/JPG/WebP reference images")

    p_brf = sub.add_parser("brief", help="Print the complete AI Agent Handoff Prompt for an asset folder")
    p_brf.add_argument("asset_dir", help="Target asset directory")

    p_doc = sub.add_parser("doctor", help="Check Blender 5.2+, CAD B-Rep venv, GPU & AI agent plugins")
    p_doc.add_argument("--json", action="store_true")

    p_sb = sub.add_parser("set-blender", help="Manually set & persist custom blender.exe path in ~/.velum-forge/config.json")
    p_sb.add_argument("path", help="Path to blender.exe (or its installation folder)")

    p_ai = sub.add_parser("install-ai", help="Install Velum Forge plugin & skills into Antigravity, Claude Code & workspace")
    p_ai.add_argument("--workspace", default="", help="Optional project folder to populate .agents/skills & .cursor/rules")
    p_ai.add_argument("--no-antigravity", action="store_true")
    p_ai.add_argument("--no-claude", action="store_true")

    p_stu = sub.add_parser("studio", help="Launch the interactive Velum Forge Desktop Studio App")
    p_stu.add_argument("--port", type=int, default=8765)
    p_stu.add_argument("--no-open", action="store_true")

    sub.add_parser("setup-gui", help="Launch the Setup & Workflow Installer GUI")

    p_new = sub.add_parser("new", help="Scaffold a blank 3D asset generator (`boat`, `fish`, `prop`, `cad`)")
    p_new.add_argument("kind", choices=["boat", "fish", "prop", "cad"])
    p_new.add_argument("name", help="Asset name or slug")
    p_new.add_argument("--dir", default=str(EXAMPLES_DIR))

    p_qa = sub.add_parser("qa", help="Run the 10-view visual & geometric QA gate (+ automatic side-by-side reference comparison)")
    p_qa.add_argument("asset", help="Path to .py, .blend, .glb, .fbx, or .step asset")
    p_qa.add_argument("--profile", default="roblox", choices=["roblox", "game", "render", "print"])
    p_qa.add_argument("--forward-axis", default="+Y", choices=["+Y", "-Y"])
    p_qa.add_argument("--ref", default="", help="Optional explicit reference image path for side-by-side comparison")
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

    if args.cmd == "generate":
        slug = slugify(args.name)
        title = args.name.replace("_", " ").title()
        asset_dir = Path(args.dir).resolve() / slug
        staged = stage_local_reference_files(asset_dir, args.ref) if args.ref else []
        created = generate_parametric_scripts(
            asset_dir,
            slug=slug,
            title=title,
            kind=args.kind,
            prompt=args.prompt or title,
            length_m=args.length,
            references=staged,
        )
        print(f"[Velum Forge] Staged spec & baseline generator at: {asset_dir}")
        if args.engine == "handoff":
            print("\n=== COPY & PASTE INTO ANTIGRAVITY / CURSOR / CLAUDE ===\n")
            print(build_agent_handoff_prompt(asset_dir))
            return 0
        if args.engine in ("claude", "codex", "gemini"):
            ai_cmd = build_ai_cli_invocation(args.engine, asset_dir)
            if not ai_cmd:
                print(f"ERROR: AI CLI '{args.engine}' not found on PATH. Printing AI Handoff Prompt instead:\n", file=sys.stderr)
                print(build_agent_handoff_prompt(asset_dir))
                return 1
            return subprocess.call(ai_cmd, cwd=str(asset_dir))

        # Default `parametric`: run QA (+ ref_comparison.png) then 4-variant + LOD build!
        rc = _run_qa_cli(created["build_script"], profile="roblox", forward_axis="+Y")
        if rc != 0:
            return rc
        if created.get("bake_script"):
            blender_exe = find_blender_exe()
            if blender_exe:
                return subprocess.call([blender_exe, "-b", "--python-exit-code", "1", "-P", created["bake_script"]])
        return 0

    if args.cmd == "add-ref":
        ad = Path(args.asset_dir).resolve()
        res = stage_local_reference_files(ad, args.images)
        print(json.dumps(res, indent=2))
        return 0

    if args.cmd == "brief":
        print(build_agent_handoff_prompt(Path(args.asset_dir).resolve()))
        return 0

    if args.cmd == "setup-gui":
        from .installer_gui import run_installer_gui

        return run_installer_gui()

    if args.cmd == "set-blender":
        res = set_custom_blender_exe(args.path)
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

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
        return _run_qa_cli(args.asset, profile=args.profile, forward_axis=args.forward_axis, ref_path=args.ref, fast=args.fast)

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
