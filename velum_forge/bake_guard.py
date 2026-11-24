"""Hardware-safe Cycles GPU/CPU bake runner & cross-process sequential GPU lock (`velum_forge.bake_guard`).

Prevents simultaneous GPU + all-core CPU power spikes and overlapping GPU bakes by:
- Enforcing safe CPU thread caps (`-t` + `VELUM_BLENDER_THREADS` + `OMP_NUM_THREADS`).
- Exporting safe Cycles environment defaults (`VELUM_CYCLES_DEVICE`, `VELUM_CYCLES_TILE_SIZE`, `VELUM_BAKE_COOLDOWN`).
- Running headless Blender with `--factory-startup` by default (opt-in `--user-addons`) so heavy UI add-ons don't stall or destabilize batch jobs.
- Serializing concurrent GPU bakes via a stale-PID-safe lock file (`~/.velum-forge/gpu_bake.lock`, opt-out via `--no-lock`).
"""
from __future__ import annotations

import contextlib
import json
import os
import platform
import time
from pathlib import Path
from typing import Callable, Iterator

LOCK_PATH = Path.home() / ".velum-forge" / "gpu_bake.lock"


def default_safe_threads() -> int:
    """Return a conservative CPU thread budget (capped at 8) to prevent all-core AVX2 power spikes."""
    env_val = os.environ.get("VELUM_BLENDER_THREADS", "").strip()
    if env_val.isdigit() and int(env_val) > 0:
        return int(env_val)
    cpus = os.cpu_count() or 8
    return min(8, max(2, cpus // 2))


def build_safe_blender_bake_cmd(
    blender_exe: str,
    script_path: str,
    *,
    threads: int | None = None,
    user_addons: bool = False,
    extra_script_args: list[str] | None = None,
) -> list[str]:
    """Construct a safe headless Blender command for baking/rendering."""
    t_count = max(1, int(threads if threads is not None else default_safe_threads()))
    cmd = [blender_exe, "-b"]
    if not user_addons:
        cmd.append("--factory-startup")
    cmd.extend(["-t", str(t_count), "--python-exit-code", "1", "-P", os.path.abspath(script_path)])
    if extra_script_args:
        cmd.append("--")
        cmd.extend(extra_script_args)
    return cmd


def build_safe_cycles_env(
    *,
    threads: int | None = None,
    device: str = "auto",
    cooldown: float = 1.0,
    tile_size: int = 512,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Return environment dictionary carrying safe Cycles GPU/CPU guardrails into Blender."""
    env = dict(base_env if base_env is not None else os.environ)
    t_count = max(1, int(threads if threads is not None else default_safe_threads()))
    env["VELUM_BLENDER_THREADS"] = str(t_count)
    env["VELUM_CYCLES_DEVICE"] = str(device or "auto").strip().lower()
    env["VELUM_BAKE_COOLDOWN"] = str(max(0.0, float(cooldown)))
    env["VELUM_CYCLES_TILE_SIZE"] = str(max(64, int(tile_size)))
    # Cap OpenMP/TBB worker pools used by OpenImageDenoise & mesh ops
    env["OMP_NUM_THREADS"] = str(t_count)
    env["TBB_NUM_THREADS"] = str(t_count)
    return env


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if platform.system() == "Windows":
        try:
            import ctypes

            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == 259  # STILL_ACTIVE
                return True
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _try_clear_stale_lock(lock_file: Path) -> bool:
    try:
        raw = json.loads(lock_file.read_text(encoding="utf-8"))
        pid = int(raw.get("pid", 0))
        if pid > 0 and not _pid_is_alive(pid):
            lock_file.unlink(missing_ok=True)
            return True
    except Exception:
        try:
            # If lock file is unreadable and older than 10 seconds, clear it
            if lock_file.exists() and (time.time() - lock_file.stat().st_mtime) > 10.0:
                lock_file.unlink(missing_ok=True)
                return True
        except OSError:
            pass
    return False


@contextlib.contextmanager
def gpu_bake_lock(
    *,
    enabled: bool = True,
    lock_file: Path | None = None,
    label: str = "bake",
    poll_interval: float = 0.5,
    log_fn: Callable[[str], None] | None = None,
) -> Iterator[None]:
    """Acquire a cross-process sequential GPU bake lock so two GPU bakes never overlap."""
    if not enabled:
        yield
        return

    lf = lock_file or LOCK_PATH
    lf.parent.mkdir(parents=True, exist_ok=True)
    waited = False
    fd = None

    while True:
        try:
            fd = os.open(str(lf), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            payload = json.dumps({"pid": os.getpid(), "label": label, "started_at": time.time()}).encode("utf-8")
            os.write(fd, payload)
            os.close(fd)
            fd = None
            break
        except FileExistsError:
            if _try_clear_stale_lock(lf):
                continue
            if not waited:
                waited = True
                if log_fn:
                    log_fn(f"[Velum Forge] Another GPU bake is active ({lf}); waiting sequentially...")
            time.sleep(poll_interval)

    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            # Only remove if we own it
            if lf.exists():
                raw = json.loads(lf.read_text(encoding="utf-8"))
                if int(raw.get("pid", -1)) == os.getpid():
                    lf.unlink(missing_ok=True)
        except Exception:
            lf.unlink(missing_ok=True)
