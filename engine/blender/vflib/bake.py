"""Hardware-Safe Cycles GPU (`OPTIX`/`CUDA`) 2K/4K PBR Texture Baker & Blender 5.2+ Helpers (`vflib.bake`).

Protects workstations against simultaneous GPU + all-core CPU power spikes by:
- Enabling STRICTLY GPU devices (`d.use = (d.type == dev_type)`) — NEVER Hybrid GPU + CPU!
- Enabling GPU denoising (`OPTIX` denoiser or `OPENIMAGEDENOISE` with `denoising_use_gpu = True`)
  so post-render denoising never fires an all-core AVX2 CPU spike on top of a hot GPU!
- Capping Blender CPU threads (`FIXED` <= 8 by default, configurable via `VELUM_BLENDER_THREADS`).
- Using safe tiled Cycles baking/rendering (`tile_size = 512`, `VELUM_CYCLES_TILE_SIZE`).
- Inserting a brief thermal/VRM cooldown pause (`VELUM_BAKE_COOLDOWN`, default 1.0s) between passes.
"""
from __future__ import annotations

import gc
import os
import shutil
import tempfile
import time

import bmesh
import bpy
import numpy as np

from . import core, mats

_LAST_COOLDOWN_TS = 0.0


def _safe_thread_count(threads: int | None = None) -> int:
    if threads is not None and int(threads) > 0:
        return int(threads)
    env_t = os.environ.get("VELUM_BLENDER_THREADS", "").strip()
    if env_t.isdigit() and int(env_t) > 0:
        return int(env_t)
    cpus = os.cpu_count() or 8
    return min(8, max(2, cpus // 2))


def _safe_tile_size(tile_size: int | None = None) -> int:
    if tile_size is not None and int(tile_size) >= 64:
        return int(tile_size)
    env_ts = os.environ.get("VELUM_CYCLES_TILE_SIZE", "").strip()
    if env_ts.isdigit() and int(env_ts) >= 64:
        return int(env_ts)
    return 512


def _safe_cooldown_sec(seconds: float | None = None) -> float:
    if seconds is not None:
        return max(0.0, float(seconds))
    raw = os.environ.get("VELUM_BAKE_COOLDOWN", "1.0").strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        return 1.0


def thermal_cooldown(seconds: float | None = None, *, min_gap: float = 0.45) -> None:
    """Brief GC + cooldown pause between heavy Cycles GPU passes to avoid back-to-back PSU transient spikes."""
    global _LAST_COOLDOWN_TS
    sec = _safe_cooldown_sec(seconds)
    now = time.monotonic()
    if sec <= 0.0:
        gc.collect()
        return
    if (now - _LAST_COOLDOWN_TS) < min_gap:
        return
    gc.collect()
    time.sleep(sec)
    _LAST_COOLDOWN_TS = time.monotonic()


def configure_safe_threads(sc: bpy.types.Scene, threads: int | None = None) -> int:
    """Cap Blender CPU thread count (`FIXED`) so CPU denoising / BVH builds never spike all cores."""
    t = _safe_thread_count(threads)
    try:
        sc.render.threads_mode = "FIXED"
        sc.render.threads = t
    except Exception:
        pass
    return t


def configure_safe_denoising(sc: bpy.types.Scene, backend: str, use_denoising: bool = True) -> None:
    """Configure GPU-accelerated Cycles denoising so OIDN never triggers an all-core CPU AVX2 spike."""
    sc.cycles.use_denoising = bool(use_denoising)
    if not use_denoising:
        return

    b = (backend or "CPU").upper()
    if b != "CPU":
        try:
            sc.cycles.denoising_use_gpu = True
        except (TypeError, AttributeError):
            pass
    if b == "OPTIX":
        # Prefer pure RT-core OptiX denoiser; fall back to GPU OpenImageDenoise
        try:
            sc.cycles.denoiser = "OPTIX"
            return
        except (TypeError, AttributeError):
            pass

    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except (TypeError, AttributeError):
        pass

    if b != "CPU":
        try:
            sc.cycles.denoising_use_gpu = True
        except (TypeError, AttributeError):
            pass
    else:
        try:
            sc.cycles.denoising_use_gpu = False
        except (TypeError, AttributeError):
            pass


def enable_cycles_gpu(
    sc: bpy.types.Scene,
    *,
    device: str | None = None,
    threads: int | None = None,
    tile_size: int | None = None,
    use_denoising: bool = True,
) -> str:
    """Activate Cycles strictly on GPU-only (never Hybrid GPU+CPU) with safe GPU denoising, tiling & thread caps."""
    try:
        import addon_utils

        if "cycles" not in bpy.context.preferences.addons:
            addon_utils.enable("cycles", default_set=False, persistent=False)
    except Exception:
        pass

    sc.render.engine = "CYCLES"
    configure_safe_threads(sc, threads=threads)

    ts = _safe_tile_size(tile_size)
    try:
        sc.cycles.use_auto_tile = True
        sc.cycles.tile_size = ts
    except (TypeError, AttributeError):
        pass

    req = (device or os.environ.get("VELUM_CYCLES_DEVICE", "auto")).strip().lower()
    if req == "cpu":
        try:
            prefs = bpy.context.preferences.addons["cycles"].preferences
            prefs.get_devices()
            for d in prefs.devices:
                d.use = (d.type == "CPU")
        except Exception:
            pass
        sc.cycles.device = "CPU"
        configure_safe_denoising(sc, "CPU", use_denoising=use_denoising)
        return "CPU"

    if req in ("optix", "cuda", "hip", "oneapi", "metal"):
        order = (req.upper(),)
    else:
        order = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")

    chosen = "CPU"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dev_type in order:
            try:
                prefs.compute_device_type = dev_type
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == dev_type]
                if devs:
                    # CRITICAL: STRICT GPU-ONLY! Never set d.use=True for CPU devices during GPU rendering!
                    for d in prefs.devices:
                        d.use = (d.type == dev_type)
                    sc.cycles.device = "GPU"
                    chosen = dev_type
                    break
            except Exception:
                continue
    except Exception:
        pass

    if chosen == "CPU":
        sc.cycles.device = "CPU"

    configure_safe_denoising(sc, chosen, use_denoising=use_denoising)
    return chosen


def lin_arr_to_srgb(arr: np.ndarray) -> np.ndarray:
    """Convert linear `[0, 1]` float buffer to sRGB before `Image.pixels.foreach_set` on 8-bit PNGs."""
    a = np.clip(arr, 0.0, 1.0)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(np.maximum(a, 1e-8), 1.0 / 2.4) - 0.055)


def mix_rgba(nt: bpy.types.NodeTree, fac, col_a, col_b) -> bpy.types.NodeSocket:
    """Blender 5.2-safe `ShaderNodeMix(data_type='RGBA')` binding explicit socket indices (0, 6, 7 -> out 2)."""
    mx = nt.nodes.new("ShaderNodeMix")
    mx.data_type = "RGBA"
    mx.clamp_factor = True
    if isinstance(fac, bpy.types.NodeSocket):
        nt.links.new(fac, mx.inputs[0])
    else:
        mx.inputs[0].default_value = float(fac)
    if isinstance(col_a, bpy.types.NodeSocket):
        nt.links.new(col_a, mx.inputs[6])
    else:
        mx.inputs[6].default_value = col_a
    if isinstance(col_b, bpy.types.NodeSocket):
        nt.links.new(col_b, mx.inputs[7])
    else:
        mx.inputs[7].default_value = col_b
    return mx.outputs[2]


def split_material_border_uv_islands(objs: list[bpy.types.Object], angle_deg: float = 58.0, margin: float = 0.006) -> None:
    """Split multi-material border edges prior to UV packing (then re-weld 3D verts) for zero-staircase stripes."""
    import math

    core.ensure_object_mode()
    for ob in objs:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        border_edges = [e for e in bm.edges if len({f.material_index for f in e.link_faces}) > 1]
        if border_edges:
            bmesh.ops.split_edges(bm, edges=border_edges)
        bm.to_mesh(ob.data)
        bm.free()

    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_deg), island_margin=margin, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin=margin)
    bpy.ops.uv.seams_from_islands()
    bpy.ops.object.mode_set(mode="OBJECT")
    for o in objs:
        o.select_set(False)

    for ob in objs:
        bm_w = bmesh.new()
        bm_w.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm_w, verts=bm_w.verts[:], dist=1e-6)
        bm_w.to_mesh(ob.data)
        bm_w.free()
        ob.data.update()


def _atomic_copy_fsync(src_path: str, dst_path: str, retries: int = 6) -> None:
    """Copy `src_path` -> sibling temp file, fsync to disk, then atomically replace `dst_path` with retry.

    Prevents both OneDrive/cloud-sync `OpenImageIO` write locks and zero-filled (`0x00`) corrupted files
    if system power is unexpectedly interrupted before the OS NTFS write cache flushes.
    """
    abs_dst = os.path.abspath(dst_path)
    dst_dir = os.path.dirname(abs_dst)
    os.makedirs(dst_dir, exist_ok=True)
    staged = os.path.join(dst_dir, f".__vf_stage_{os.getpid()}_{os.path.basename(abs_dst)}")
    try:
        shutil.copy2(src_path, staged)
        try:
            with open(staged, "rb+") as fh:
                fh.flush()
                os.fsync(fh.fileno())
        except OSError:
            pass
        for attempt in range(retries):
            try:
                os.replace(staged, abs_dst)
                return
            except PermissionError:
                if attempt == retries - 1:
                    raise
                time.sleep(0.4)
    finally:
        if os.path.exists(staged):
            try:
                os.remove(staged)
            except OSError:
                pass


def render_still_safe(
    sc: bpy.types.Scene,
    dst_path: str,
    retries: int = 6,
    cooldown: float | None = None,
) -> str:
    """Render to local temp directory first, fsync + atomically replace destination, and apply thermal cooldown."""
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    if sc.render.engine == "CYCLES":
        enable_cycles_gpu(sc, use_denoising=bool(sc.cycles.use_denoising))
    else:
        configure_safe_threads(sc)
    tmp_p = os.path.join(tempfile.gettempdir(), f"__vf_rnd_{os.getpid()}_{os.path.basename(dst_path)}")
    sc.render.filepath = tmp_p
    bpy.ops.render.render(write_still=True)
    try:
        _atomic_copy_fsync(tmp_p, dst_path, retries=retries)
    finally:
        try:
            os.remove(tmp_p)
        except OSError:
            pass
    if sc.render.engine == "CYCLES":
        thermal_cooldown(cooldown)
    return dst_path


def save_png_8bit(rgba: np.ndarray, path: str, colorspace: str) -> bpy.types.Image:
    """Save a `[H, W, 4]` float32 array in `[0, 1]` to an 8-bit PNG safely via fsync'd atomic replace."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    h, w, _ = rgba.shape
    iname = os.path.basename(path)
    old = bpy.data.images.get(iname)
    if old is not None:
        bpy.data.images.remove(old)
    img = bpy.data.images.new(iname, width=w, height=h, alpha=False, float_buffer=False)
    img.colorspace_settings.name = colorspace
    img.pixels.foreach_set(np.clip(rgba, 0.0, 1.0).astype(np.float32).ravel())
    tmp_p = os.path.join(tempfile.gettempdir(), f"__vf_tex_{os.getpid()}_{iname}")
    img.filepath_raw = tmp_p
    img.file_format = "PNG"
    img.save()
    try:
        _atomic_copy_fsync(tmp_p, path, retries=6)
    finally:
        try:
            os.remove(tmp_p)
        except OSError:
            pass
    img.filepath = path
    img.reload()
    img.colorspace_settings.name = colorspace
    return img
