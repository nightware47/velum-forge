"""Native Dark-Themed Windows Setup Wizard GUI for Velum Forge (`Setup-VelumForge.cmd`)."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from . import REPO_ROOT, __version__
from .doctor import find_blender_exe, install_ai_integrations


def _install_worker(
    *,
    setup_venv: bool,
    install_agy: bool,
    install_claude: bool,
    add_path_shim: bool,
    launch_after: bool,
    log_fn,
    done_fn,
) -> None:
    try:
        log_fn(f"=== Velum Forge v{__version__} Setup Wizard ===\n")
        blender = find_blender_exe()
        if blender:
            log_fn(f"[OK] Detected Blender 5.2+: {blender}\n")
        else:
            log_fn("[WARN] Blender 5.2+ not detected in standard paths. Install Blender 5.2 LTS for QA/Baking.\n")

        venv_dir = REPO_ROOT / ".venv"
        venv_py = venv_dir / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")

        if setup_venv:
            uv_exe = shutil.which("uv")
            if uv_exe:
                log_fn(f"\n[1/4] Creating/updating Python 3.12 CAD .venv with uv ({uv_exe})...\n")
                subprocess.run([uv_exe, "venv", str(venv_dir), "--python", "3.12", "--allow-existing"], cwd=str(REPO_ROOT), check=False)
                rc = subprocess.call(
                    [uv_exe, "pip", "install", "--python", str(venv_py), "-e", str(REPO_ROOT)],
                    cwd=str(REPO_ROOT),
                )
            else:
                log_fn("\n[1/4] Creating/updating Python .venv with standard venv + pip...\n")
                if not venv_py.is_file():
                    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)], cwd=str(REPO_ROOT))
                rc = subprocess.call([str(venv_py), "-m", "pip", "install", "-e", str(REPO_ROOT)], cwd=str(REPO_ROOT))
            if rc != 0:
                log_fn(f"[WARN] Editable CAD package install exited with code {rc} (Studio UI still works).\n")
            else:
                log_fn("[OK] Installed build123d, trimesh, pymeshlab, pillow, numpy & vforge CLI!\n")

        log_fn("\n[2/4] Installing AI Agent Plugins & Skills...\n")
        ai_res = install_ai_integrations(antigravity=install_agy, claude_code=install_claude)
        for k, v in ai_res.items():
            log_fn(f"  -> {k}: {v}\n")

        if add_path_shim and platform.system() == "Windows":
            log_fn("\n[3/4] Creating global `vforge.cmd` shim in ~/.local/bin...\n")
            bin_dir = Path.home() / ".local" / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            py_target = str(venv_py if venv_py.is_file() else Path(sys.executable))
            shim = bin_dir / "vforge.cmd"
            shim.write_text(
                f'@echo off\r\nset PYTHONPATH={REPO_ROOT};%PYTHONPATH%\r\n"{py_target}" -m velum_forge.cli %*\r\n',
                encoding="utf-8",
            )
            log_fn(f"[OK] Wrote {shim}\n")

        log_fn("\n[4/4] Setup complete! Velum Forge is ready.\n")
        done_fn(True, launch_after)
    except Exception as exc:
        log_fn(f"\n[ERROR] Setup failed: {exc}\n")
        done_fn(False, False)


def run_installer_gui() -> int:
    root = tk.Tk()
    root.title(f"Velum Forge v{__version__} — Workflow & Studio Installer")
    root.geometry("720x540")
    root.configure(bg="#0b1120")

    title_lbl = tk.Label(
        root,
        text="Velum Forge — 3D CAD, PBR & AI Workflow Installer",
        font=("Segoe UI", 16, "bold"),
        fg="#f8fafc",
        bg="#0b1120",
    )
    title_lbl.pack(anchor="w", padx=24, pady=(20, 4))

    sub_lbl = tk.Label(
        root,
        text="Configures OpenCascade build123d CAD, Blender 5.2+ QA/Bake Engine, Antigravity Plugin & Studio App.",
        font=("Segoe UI", 10),
        fg="#94a3b8",
        bg="#0b1120",
    )
    sub_lbl.pack(anchor="w", padx=24, pady=(0, 16))

    opts_frame = tk.Frame(root, bg="#111c33", highlightbackground="#1e293b", highlightthickness=1)
    opts_frame.pack(fill="x", padx=24, pady=(0, 14))

    v_venv = tk.BooleanVar(value=True)
    v_agy = tk.BooleanVar(value=True)
    v_claude = tk.BooleanVar(value=True)
    v_shim = tk.BooleanVar(value=True)
    v_launch = tk.BooleanVar(value=True)

    cb_cfg = dict(bg="#111c33", fg="#e2e8f0", selectcolor="#0f172a", activebackground="#111c33", activeforeground="#38bdf8", font=("Segoe UI", 10))
    tk.Checkbutton(opts_frame, text="Create / Update Python 3.12 CAD Virtual Environment (build123d, trimesh, pymeshlab)", variable=v_venv, **cb_cfg).pack(anchor="w", padx=14, pady=(10, 4))
    tk.Checkbutton(opts_frame, text="Install Official Google Antigravity Plugin (~/.gemini/config/plugins/velum-forge)", variable=v_agy, **cb_cfg).pack(anchor="w", padx=14, pady=4)
    tk.Checkbutton(opts_frame, text="Install Claude Code CLI Skills (~/.claude/skills/velum-*)", variable=v_claude, **cb_cfg).pack(anchor="w", padx=14, pady=4)
    tk.Checkbutton(opts_frame, text="Install `vforge` CLI launcher shim (~/.local/bin/vforge.cmd)", variable=v_shim, **cb_cfg).pack(anchor="w", padx=14, pady=4)
    tk.Checkbutton(opts_frame, text="Launch Velum Forge Studio App immediately after installation", variable=v_launch, **cb_cfg).pack(anchor="w", padx=14, pady=(4, 10))

    log_box = tk.Text(root, height=11, bg="#050811", fg="#67e8f9", font=("Consolas", 9), relief="flat", padx=10, pady=8)
    log_box.pack(fill="both", expand=True, padx=24, pady=(0, 14))
    log_box.insert("end", "Ready to install. Click 'Install & Setup Velum Forge' below.\n")

    btn_frame = tk.Frame(root, bg="#0b1120")
    btn_frame.pack(fill="x", padx=24, pady=(0, 18))

    install_btn = tk.Button(
        btn_frame,
        text="Install & Setup Velum Forge",
        font=("Segoe UI", 10, "bold"),
        bg="#0284c7",
        fg="#ffffff",
        activebackground="#0369a1",
        relief="flat",
        padx=18,
        pady=8,
    )
    install_btn.pack(side="right")

    def append_log(msg: str) -> None:
        root.after(0, lambda: (log_box.insert("end", msg), log_box.see("end")))

    def on_done(ok: bool, launch_studio_flag: bool) -> None:
        def _finish() -> None:
            install_btn.config(state="normal", text="Re-Run Setup")
            if ok and launch_studio_flag:
                root.destroy()
                subprocess.Popen([sys.executable, "-m", "velum_forge.cli", "studio"], cwd=str(REPO_ROOT))
            elif ok:
                messagebox.showinfo("Velum Forge", "Installation complete!")
        root.after(0, _finish)

    def on_click() -> None:
        install_btn.config(state="disabled", text="Installing...")
        threading.Thread(
            target=_install_worker,
            kwargs=dict(
                setup_venv=v_venv.get(),
                install_agy=v_agy.get(),
                install_claude=v_claude.get(),
                add_path_shim=v_shim.get(),
                launch_after=v_launch.get(),
                log_fn=append_log,
                done_fn=on_done,
            ),
            daemon=True,
        ).start()

    install_btn.config(command=on_click)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_installer_gui())
