"""Velum Forge Studio — Local Desktop App Backend, Reference Manager & Live Generation Runner."""
from __future__ import annotations

import json
import mimetypes
import os
import platform
import shutil
import subprocess
import threading
import time
import urllib.parse
import uuid
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import CAD_ENGINE_DIR, EXAMPLES_DIR, PLUGIN_SRC_DIR, REPO_ROOT, UI_DIR
from .doctor import (
    find_blender_exe,
    find_venv_python,
    get_design_output_dir,
    install_ai_integrations,
    run_doctor,
    set_custom_blender_exe,
)
from .generator import (
    build_agent_handoff_prompt,
    build_ai_cli_invocation,
    detect_ai_clis,
    generate_parametric_scripts,
    slugify,
)
from .references import analyze_reference_image, save_uploaded_reference
from .scaffold import scaffold_asset

_JOBS_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _default_scan_roots() -> list[Path]:
    roots = [EXAMPLES_DIR]
    vf_assets = REPO_ROOT / "assets" / "models"
    if vf_assets.is_dir() and vf_assets not in roots:
        roots.append(vf_assets)
    for desk in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop"):
        if desk.is_dir():
            try:
                for proj in desk.iterdir():
                    if proj.is_dir():
                        cand = proj / "assets" / "models"
                        if cand.is_dir() and cand not in roots:
                            roots.append(cand)
            except OSError:
                pass
    extra = os.environ.get("VELUM_ASSET_ROOTS", "")
    for item in extra.split(os.pathsep):
        if item.strip() and Path(item).is_dir():
            roots.append(Path(item).resolve())
    return roots


def _allowed_roots() -> list[Path]:
    roots = _default_scan_roots() + [REPO_ROOT, get_design_output_dir()]
    for r in list(roots):
        qa_parent = r.parent.parent / ".qa-out" if r.name == "models" else r.parent / ".qa-out"
        if qa_parent.is_dir():
            roots.append(qa_parent)
    return [p.resolve() for p in roots if p.exists()]


def _is_safe_local_file(p: Path) -> bool:
    try:
        rp = p.resolve()
        if not rp.is_file():
            return False
        return any(rp == root or root in rp.parents for root in _allowed_roots())
    except Exception:
        return False


def discover_assets() -> list[dict[str, Any]]:
    """Scan configured asset roots and assemble rich metadata, references, renders, PBR maps & LODs."""
    assets: list[dict[str, Any]] = []
    seen_dirs: set[Path] = set()

    for root in _default_scan_roots():
        if not root.is_dir():
            continue
        source_label = (
            "Velum Forge Workspace"
            if root == EXAMPLES_DIR
            else root.parent.parent.name
            if root.name == "models"
            else root.name
        )
        for sub in sorted(root.iterdir()):
            if not sub.is_dir() or sub.name.startswith((".", "_")):
                continue
            rsub = sub.resolve()
            if rsub in seen_dirs:
                continue
            seen_dirs.add(rsub)

            py_files = sorted(sub.glob("*.py"))
            blends = sorted(sub.glob("*.blend"))
            spec_file = sub / "asset_spec.json"
            if not py_files and not blends and not spec_file.is_file():
                continue

            build_script = next(
                (p for p in py_files if p.name.startswith("build_") and "hardware" not in p.name),
                py_files[0] if py_files else None,
            )
            bake_script = next((p for p in py_files if "bake" in p.name), None)
            main_blend = next((p for p in blends if "variants_lods" in p.name), blends[0] if blends else None)

            spec_data: dict[str, Any] = {}
            if spec_file.is_file():
                try:
                    spec_data = json.loads(spec_file.read_text(encoding="utf-8-sig"))
                except Exception:
                    pass

            report_data: dict[str, Any] = {}
            rep_file = sub / "variants_and_lods_report.json"
            if rep_file.is_file():
                try:
                    report_data = json.loads(rep_file.read_text(encoding="utf-8-sig"))
                except Exception:
                    pass

            # Collect reference images
            ref_images: list[dict[str, Any]] = []
            ref_dir = sub / "references"
            if ref_dir.is_dir():
                for rf in sorted(ref_dir.iterdir()):
                    if rf.is_file() and rf.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                        ref_images.append({"label": f"Ref: {rf.stem}", "path": str(rf.resolve())})

            # Collect preview / render / QA / ref_comparison images (prioritize ref_comparison & lineup!)
            images: list[dict[str, str]] = []
            seen_imgs: set[Path] = set()
            for img_dir_name in ("renders", "previews"):
                idir = sub / img_dir_name
                if idir.is_dir():
                    for im in sorted(idir.glob("*.png")):
                        rim = im.resolve()
                        if rim not in seen_imgs:
                            seen_imgs.add(rim)
                            lbl = "Ref vs Model" if im.stem == "ref_comparison" else im.stem.replace("_", " ").title()
                            images.append({"label": lbl, "path": str(rim)})
            if not images and (sub / "preview.png").is_file():
                images.append({"label": "Preview", "path": str((sub / "preview.png").resolve())})

            # Put ref_comparison & variants_lineup at the front of thumbnails!
            images.sort(
                key=lambda item: (
                    0 if "ref vs model" in item["label"].lower() else (1 if "lineup" in item["label"].lower() else 2),
                    item["label"],
                )
            )

            pbr_maps: list[dict[str, str]] = []
            tex_root = sub / "textures"
            if tex_root.is_dir():
                sub_tex = sorted([d for d in tex_root.iterdir() if d.is_dir()])
                scan_t = sub_tex[0] if sub_tex else tex_root
                for mp in sorted(scan_t.glob("*.png")):
                    pbr_maps.append({"label": mp.stem.split("_")[-1], "path": str(mp.resolve())})

            hero_img = next(
                (i["path"] for i in images if "lineup" in i["label"].lower() or "ref vs model" in i["label"].lower()),
                images[0]["path"] if images else (ref_images[0]["path"] if ref_images else None),
            )

            assets.append(
                {
                    "id": f"{source_label}:{sub.name}",
                    "name": sub.name,
                    "title": spec_data.get("title") or sub.name.replace("_", " ").title(),
                    "prompt": spec_data.get("prompt") or "",
                    "extracted_palette": spec_data.get("extracted_palette") or [],
                    "source": source_label,
                    "dir": str(rsub),
                    "build_script": str(build_script.resolve()) if build_script else None,
                    "bake_script": str(bake_script.resolve()) if bake_script else None,
                    "blend_file": str(main_blend.resolve()) if main_blend else None,
                    "has_variants_report": bool(report_data),
                    "report": report_data,
                    "hero_image": hero_img,
                    "images": images,
                    "references": ref_images,
                    "pbr_maps": pbr_maps,
                    "handoff_prompt": build_agent_handoff_prompt(rsub),
                }
            )
    return assets


def _start_chained_job(title: str, steps: list[tuple[str, list[str], str]]) -> str:
    """Run one or more sequential pipeline commands in a background thread with live log streaming."""
    jid = uuid.uuid4().hex[:10]
    job = {
        "id": jid,
        "title": title,
        "status": "running",
        "started_at": time.time(),
        "exit_code": None,
        "logs": f"[Velum Forge] Starting pipeline: {title}\n",
    }
    with _JOBS_LOCK:
        _JOBS[jid] = job

    def _worker() -> None:
        rc = 0
        try:
            for idx, (step_name, cmd, cwd) in enumerate(steps, 1):
                with _JOBS_LOCK:
                    _JOBS[jid]["logs"] += f"\n--- Step {idx}/{len(steps)}: {step_name} ---\n$ {' '.join(cmd)}\n\n"
                proc = subprocess.Popen(
                    cmd,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    with _JOBS_LOCK:
                        _JOBS[jid]["logs"] += line
                rc = proc.wait()
                if rc != 0:
                    with _JOBS_LOCK:
                        _JOBS[jid]["exit_code"] = rc
                        _JOBS[jid]["status"] = "failed"
                        _JOBS[jid]["logs"] += f"\n[Velum Forge] Step '{step_name}' exited with code {rc}.\n"
                    return
            with _JOBS_LOCK:
                _JOBS[jid]["exit_code"] = 0
                _JOBS[jid]["status"] = "done"
                _JOBS[jid]["logs"] += f"\n[Velum Forge] All {len(steps)} step(s) completed successfully!\n"
        except Exception as exc:
            with _JOBS_LOCK:
                _JOBS[jid]["exit_code"] = -1
                _JOBS[jid]["status"] = "failed"
                _JOBS[jid]["logs"] += f"\n[Velum Forge ERROR] {exc}\n"

    threading.Thread(target=_worker, daemon=True).start()
    return jid


def _build_qa_cmd(asset_path: str, profile: str = "roblox", fwd: str = "+Y") -> list[str]:
    if platform.system() == "Windows":
        ps_exe = shutil.which("powershell") or "powershell.exe"
        return [
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
            fwd,
        ]
    blender_exe = find_blender_exe() or "blender"
    out_d = str(REPO_ROOT / ".qa-out" / Path(asset_path).stem)
    return [
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
        fwd,
    ]


def _load_skills_catalog() -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    skills_dir = PLUGIN_SRC_DIR / "skills"
    if skills_dir.is_dir():
        for sk in sorted(skills_dir.iterdir()):
            md = sk / "SKILL.md"
            if md.is_file():
                out.append({"name": sk.name, "path": str(md), "content": md.read_text(encoding="utf-8")})
    rules_md = PLUGIN_SRC_DIR / "rules" / "AGENTS.md"
    if rules_md.is_file():
        out.append({"name": "rules/AGENTS.md (Always-On)", "path": str(rules_md), "content": rules_md.read_text(encoding="utf-8")})
    return out


class StudioHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send_json(self, data: Any, status: int = 200) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        route = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if route in ("/", "/index.html"):
            html = (UI_DIR / "index.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return

        if route == "/api/doctor":
            doc = run_doctor()
            doc["ai_clis"] = detect_ai_clis()
            self._send_json(doc)
            return

        if route == "/api/assets":
            self._send_json({"assets": discover_assets()})
            return

        if route == "/api/skills":
            self._send_json({"skills": _load_skills_catalog()})
            return

        if route == "/api/jobs":
            jid = (qs.get("id") or [""])[0]
            with _JOBS_LOCK:
                if jid and jid in _JOBS:
                    self._send_json(_JOBS[jid])
                else:
                    self._send_json({"jobs": list(_JOBS.values())[-12:]})
            return

        if route == "/api/file":
            raw_p = (qs.get("path") or [""])[0]
            p = Path(raw_p)
            if not raw_p or not _is_safe_local_file(p):
                self._send_json({"error": "File access denied or not found"}, status=404)
                return
            data = p.read_bytes()
            mime, _ = mimetypes.guess_type(str(p))
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        route = urllib.parse.urlparse(self.path).path
        body = self._read_body()

        if route == "/api/generate":
            raw_name = str(body.get("name") or "custom_asset").strip()
            slug = slugify(raw_name)
            title = str(body.get("title") or raw_name.replace("_", " ").title()).strip()
            kind = str(body.get("kind") or "fish")
            prompt = str(body.get("prompt") or title).strip()
            length_m = float(body.get("length_m") or 1.20)
            engine = str(body.get("engine") or "parametric")
            parent_dir = Path(str(body.get("parent_dir") or EXAMPLES_DIR)).resolve()
            asset_dir = parent_dir / slug
            asset_dir.mkdir(parents=True, exist_ok=True)

            # 1. Stage & analyze uploaded reference images!
            staged_refs: list[dict[str, Any]] = []
            for r_item in body.get("references") or []:
                fn = str(r_item.get("filename") or "ref.png")
                vw = str(r_item.get("view") or "auto")
                durl = str(r_item.get("data_url") or "")
                if durl:
                    staged_refs.append(save_uploaded_reference(asset_dir, fn, durl, view=vw))

            # Also keep any existing references already in `<asset_dir>/references/`
            ref_sub = asset_dir / "references"
            if ref_sub.is_dir() and not staged_refs:
                for rf in sorted(ref_sub.iterdir()):
                    if rf.is_file() and rf.suffix.lower() in (".png", ".jpg", ".jpeg"):
                        staged_refs.append(analyze_reference_image(rf))

            # 2. Generate reference-calibrated baseline scripts + asset_spec.json
            created = generate_parametric_scripts(
                asset_dir,
                slug=slug,
                title=title,
                kind=kind,
                prompt=prompt,
                length_m=length_m,
                references=staged_refs,
            )
            handoff = build_agent_handoff_prompt(asset_dir)

            if engine == "handoff":
                self._send_json({"ok": True, "mode": "handoff", "created": created, "handoff_prompt": handoff})
                return

            steps: list[tuple[str, list[str], str]] = []
            if engine in ("claude", "codex", "gemini", "auto_ai"):
                ai_cmd = build_ai_cli_invocation("auto" if engine == "auto_ai" else engine, asset_dir)
                if ai_cmd:
                    steps.append((f"AI Agent Synthesis ({engine})", ai_cmd, str(asset_dir)))
                else:
                    self._send_json(
                        {
                            "ok": False,
                            "error": f"AI CLI '{engine}' was not detected on this PC. Use 'Instant Parametric Generator' or copy the AI Handoff Prompt into Antigravity / Cursor!",
                            "handoff_prompt": handoff,
                        },
                        status=400,
                    )
                    return
            else:
                blender_exe = find_blender_exe()
                if not blender_exe and kind != "cad":
                    self._send_json(
                        {"ok": False, "error": "Blender 5.2+ not detected yet — click 'Locate blender.exe' in Environment Doctor first."},
                        status=400,
                    )
                    return
                build_script = created["build_script"]
                steps.append(("10-View Visual & Reference Comparison QA Gate", _build_qa_cmd(build_script, "roblox", "+Y"), str(REPO_ROOT)))
                if created.get("bake_script") and blender_exe:
                    steps.append(
                        ("4-Variant Showcase + LOD0-LOD3 Build", [blender_exe, "-b", "--python-exit-code", "1", "-P", created["bake_script"]], str(asset_dir))
                    )

            jid = _start_chained_job(f"Generate 3D Asset: {title}", steps)
            self._send_json({"ok": True, "job_id": jid, "slug": slug, "created": created, "handoff_prompt": handoff})
            return

        if route == "/api/upload-reference":
            target_dir = Path(str(body.get("asset_dir") or "")).resolve()
            if not target_dir.is_dir():
                self._send_json({"ok": False, "error": "Asset directory not found"}, status=404)
                return
            added = []
            for r_item in body.get("references") or []:
                fn = str(r_item.get("filename") or "ref.png")
                vw = str(r_item.get("view") or "auto")
                durl = str(r_item.get("data_url") or "")
                if durl:
                    added.append(save_uploaded_reference(target_dir, fn, durl, view=vw))
            self._send_json({"ok": True, "added": added, "handoff_prompt": build_agent_handoff_prompt(target_dir)})
            return

        if route == "/api/install-ai":
            res = install_ai_integrations(
                antigravity=bool(body.get("antigravity", True)),
                claude_code=bool(body.get("claude_code", True)),
                workspace_dir=body.get("workspace_dir") or None,
            )
            self._send_json({"ok": True, "installed": res, "doctor": run_doctor()})
            return

        if route == "/api/set-blender":
            raw_exe = str(body.get("blender_exe") or "").strip()
            res = set_custom_blender_exe(raw_exe)
            status = 200 if res.get("ok") else 400
            res["doctor"] = run_doctor()
            self._send_json(res, status=status)
            return

        if route == "/api/browse-blender":
            picked = ""
            if platform.system() == "Windows":
                ps_cmd = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "$f = New-Object System.Windows.Forms.OpenFileDialog; "
                    "$f.Title = 'Select blender.exe (Blender 5.2+ Recommended)'; "
                    "$f.Filter = 'Blender Executable (blender.exe)|blender.exe|Executables (*.exe)|*.exe|All Files (*.*)|*.*'; "
                    "if ($f.ShowDialog() -eq 'OK') { Write-Output $f.FileName }"
                )
                cp = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps_cmd], capture_output=True, text=True, check=False)
                picked = (cp.stdout or "").strip()
            if not picked:
                self._send_json({"ok": False, "cancelled": True})
                return
            res = set_custom_blender_exe(picked)
            res["doctor"] = run_doctor()
            self._send_json(res, status=200 if res.get("ok") else 400)
            return

        if route == "/api/scaffold":
            kind = str(body.get("kind") or "prop")
            name = str(body.get("name") or "new_asset")
            parent = str(body.get("parent_dir") or EXAMPLES_DIR)
            res = scaffold_asset(kind, name, parent)
            self._send_json({"ok": True, "created": res})
            return

        if route == "/api/open-blender":
            target = str(body.get("path") or "")
            blender_exe = find_blender_exe()
            if not blender_exe:
                self._send_json({"ok": False, "error": "Blender 5.2+ executable not found"}, status=400)
                return
            p = Path(target)
            if p.is_file() and p.suffix.lower() == ".blend":
                subprocess.Popen([blender_exe, str(p)])
                self._send_json({"ok": True, "launched": str(p)})
                return
            if p.is_file() and p.suffix.lower() == ".py":
                subprocess.Popen([blender_exe, "-P", str(p)])
                self._send_json({"ok": True, "launched": str(p)})
                return
            self._send_json({"ok": False, "error": f"Cannot open {target}"}, status=400)
            return

        if route == "/api/run-qa":
            asset_path = str(body.get("path") or "")
            profile = str(body.get("profile") or "roblox")
            fwd = str(body.get("forward_axis") or "+Y")
            jid = _start_chained_job(
                f"10-View QA + Ref Comparison ({Path(asset_path).name})",
                [("Run 10-View QA", _build_qa_cmd(asset_path, profile, fwd), str(REPO_ROOT))],
            )
            self._send_json({"ok": True, "job_id": jid})
            return

        if route == "/api/run-bake":
            bake_path = str(body.get("path") or "")
            blender_exe = find_blender_exe()
            if not blender_exe or not Path(bake_path).is_file():
                self._send_json({"ok": False, "error": "Blender 5.2+ or bake script not found"}, status=400)
                return
            jid = _start_chained_job(
                f"2K Cycles PBR Bake + Variants + LODs ({Path(bake_path).parent.name})",
                [("Cycles PBR Bake & LODs", [blender_exe, "-b", "--python-exit-code", "1", "-P", bake_path], str(Path(bake_path).parent))],
            )
            self._send_json({"ok": True, "job_id": jid})
            return

        self._send_json({"error": "Unknown endpoint"}, status=404)


def _open_native_app_window(url: str) -> None:
    if platform.system() == "Windows":
        app_browsers = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for exe in app_browsers:
            if exe.is_file():
                subprocess.Popen([str(exe), f"--app={url}", "--window-size=1480,940"])
                return
    webbrowser.open(url)


def launch_studio(host: str = "127.0.0.1", port: int = 8765, open_window: bool = True) -> None:
    srv = None
    chosen_port = port
    for candidate in range(port, port + 20):
        try:
            srv = ThreadingHTTPServer((host, candidate), StudioHandler)
            chosen_port = candidate
            break
        except OSError:
            continue
    if srv is None:
        raise RuntimeError(f"Could not bind Studio server near port {port}")

    url = f"http://{host}:{chosen_port}"
    print(f"[Velum Forge Studio] Running at {url} (Ctrl+C to stop)")
    if open_window:
        threading.Timer(0.45, _open_native_app_window, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[Velum Forge Studio] Shutting down.")
        srv.server_close()
