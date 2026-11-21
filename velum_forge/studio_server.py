"""Velum Forge Studio — Local Desktop App Backend & Native Chromeless App-Window Launcher."""
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
from .scaffold import scaffold_asset

_JOBS_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}


def _default_scan_roots() -> list[Path]:
    roots = [EXAMPLES_DIR]
    # Automatically discover sibling project asset folders if present on user's Desktop
    for desk in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop"):
        sc_models = desk / "Sun City RP" / "assets" / "models"
        if sc_models.is_dir() and sc_models not in roots:
            roots.append(sc_models)
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
    """Scan configured asset roots and assemble rich metadata, images, PBR maps, LODs & scripts."""
    assets: list[dict[str, Any]] = []
    seen_dirs: set[Path] = set()

    for root in _default_scan_roots():
        if not root.is_dir():
            continue
        source_label = "Velum Forge Examples" if root == EXAMPLES_DIR else root.parent.parent.name if root.name == "models" else root.name
        for sub in sorted(root.iterdir()):
            if not sub.is_dir() or sub.name.startswith((".", "_")):
                continue
            rsub = sub.resolve()
            if rsub in seen_dirs:
                continue
            seen_dirs.add(rsub)

            py_files = sorted(sub.glob("*.py"))
            blends = sorted(sub.glob("*.blend"))
            if not py_files and not blends:
                continue

            build_script = next((p for p in py_files if p.name.startswith("build_") and "hardware" not in p.name), py_files[0] if py_files else None)
            bake_script = next((p for p in py_files if "bake" in p.name), None)
            main_blend = next((p for p in blends if "variants_lods" in p.name), blends[0] if blends else None)

            report_data: dict[str, Any] = {}
            rep_file = sub / "variants_and_lods_report.json"
            if rep_file.is_file():
                try:
                    report_data = json.loads(rep_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            # Collect preview / render images
            images: list[dict[str, str]] = []
            for img_dir_name in ("renders", "previews"):
                idir = sub / img_dir_name
                if idir.is_dir():
                    for im in sorted(idir.glob("*.png")):
                        images.append({"label": im.stem.replace("_", " ").title(), "path": str(im.resolve())})
            if not images and (sub / "preview.png").is_file():
                images.append({"label": "Preview", "path": str((sub / "preview.png").resolve())})

            # Collect baked PBR texture maps (first variant or textures/)
            pbr_maps: list[dict[str, str]] = []
            tex_root = sub / "textures"
            if tex_root.is_dir():
                sub_tex = sorted([d for d in tex_root.iterdir() if d.is_dir()])
                scan_t = sub_tex[0] if sub_tex else tex_root
                for mp in sorted(scan_t.glob("*.png")):
                    pbr_maps.append({"label": mp.stem.split("_")[-1], "path": str(mp.resolve())})

            hero_img = next((i["path"] for i in images if "lineup" in i["label"].lower() or "hero" in i["label"].lower()), images[0]["path"] if images else None)

            assets.append(
                {
                    "id": f"{source_label}:{sub.name}",
                    "name": sub.name,
                    "title": sub.name.replace("_", " ").title(),
                    "source": source_label,
                    "dir": str(rsub),
                    "build_script": str(build_script.resolve()) if build_script else None,
                    "bake_script": str(bake_script.resolve()) if bake_script else None,
                    "blend_file": str(main_blend.resolve()) if main_blend else None,
                    "has_variants_report": bool(report_data),
                    "report": report_data,
                    "hero_image": hero_img,
                    "images": images,
                    "pbr_maps": pbr_maps,
                }
            )
    return assets


def _start_background_job(title: str, cmd: list[str], cwd: str) -> str:
    jid = uuid.uuid4().hex[:10]
    job = {
        "id": jid,
        "title": title,
        "cmd": " ".join(f'"{c}"' if " " in c else c for c in cmd),
        "status": "running",
        "started_at": time.time(),
        "exit_code": None,
        "logs": f"[Velum Forge] Starting: {title}\n$ {' '.join(cmd)}\n\n",
    }
    with _JOBS_LOCK:
        _JOBS[jid] = job

    def _worker() -> None:
        try:
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
            with _JOBS_LOCK:
                _JOBS[jid]["exit_code"] = rc
                _JOBS[jid]["status"] = "done" if rc == 0 else "failed"
                _JOBS[jid]["logs"] += f"\n[Velum Forge] Finished with exit code {rc}.\n"
        except Exception as exc:
            with _JOBS_LOCK:
                _JOBS[jid]["exit_code"] = -1
                _JOBS[jid]["status"] = "failed"
                _JOBS[jid]["logs"] += f"\n[Velum Forge ERROR] {exc}\n"

    threading.Thread(target=_worker, daemon=True).start()
    return jid


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
        return  # Keep terminal clean

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
            self._send_json(run_doctor())
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
            if platform.system() == "Windows":
                ps_exe = shutil.which("powershell") or "powershell.exe"
                qa_ps1 = str(CAD_ENGINE_DIR / "run_qa.ps1")
                cmd = [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", qa_ps1, "-Asset", asset_path, "-Profile", profile, "-ForwardAxis", fwd]
            else:
                blender_exe = find_blender_exe() or "blender"
                out_d = str(REPO_ROOT / ".qa-out" / Path(asset_path).stem)
                cmd = [blender_exe, "-b", "--python-exit-code", "1", "-P", str(REPO_ROOT / "engine" / "blender" / "qa_pipeline.py"), "--", "--input", asset_path, "--out-dir", out_d, "--profile", profile, "--forward-axis", fwd]
            jid = _start_background_job(f"10-View QA Gate ({Path(asset_path).name})", cmd, str(REPO_ROOT))
            self._send_json({"ok": True, "job_id": jid})
            return

        if route == "/api/run-bake":
            bake_path = str(body.get("path") or "")
            blender_exe = find_blender_exe()
            if not blender_exe or not Path(bake_path).is_file():
                self._send_json({"ok": False, "error": "Blender 5.2+ or bake script not found"}, status=400)
                return
            cmd = [blender_exe, "-b", "--python-exit-code", "1", "-P", bake_path]
            jid = _start_background_job(f"2K Cycles PBR Bake + Variants + LODs ({Path(bake_path).parent.name})", cmd, str(Path(bake_path).parent))
            self._send_json({"ok": True, "job_id": jid})
            return

        self._send_json({"error": "Unknown endpoint"}, status=404)


def _open_native_app_window(url: str) -> None:
    """Open Velum Forge Studio in a chromeless desktop window (Edge/Chrome --app mode) with browser fallback."""
    if platform.system() == "Windows":
        app_browsers = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for exe in app_browsers:
            if exe.is_file():
                subprocess.Popen([str(exe), f"--app={url}", "--window-size=1460,920"])
                return
    webbrowser.open(url)


def launch_studio(host: str = "127.0.0.1", port: int = 8765, open_window: bool = True) -> None:
    # Auto-pick free port if 8765 is already bound
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
