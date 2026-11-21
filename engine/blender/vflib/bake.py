"""Cycles GPU (`OPTIX`/`CUDA`) 2K/4K PBR Texture Baker & Blender 5.2 Color-Space Helpers (`vflib.bake`)."""
from __future__ import annotations

import os
import shutil
import tempfile
import time

import bmesh
import bpy
import numpy as np

from . import core, mats


def enable_cycles_gpu(sc: bpy.types.Scene) -> str:
    """Activate Cycles GPU (`OPTIX` -> `CUDA` -> `HIP` -> `ONEAPI` -> `METAL`, fallback `CPU`)."""
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dev_type in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
            try:
                prefs.compute_device_type = dev_type
                prefs.get_devices()
                devs = [d for d in prefs.devices if d.type == dev_type]
                if devs:
                    for d in prefs.devices:
                        d.use = True
                    sc.cycles.device = "GPU"
                    return dev_type
            except Exception:
                continue
    except Exception:
        pass
    sc.cycles.device = "CPU"
    return "CPU"


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


def render_still_safe(sc: bpy.types.Scene, dst_path: str, retries: int = 6) -> str:
    """Render to local temp directory first, then copy with retry so cloud-synced folders never lock OpenImageIO."""
    os.makedirs(os.path.dirname(os.path.abspath(dst_path)), exist_ok=True)
    tmp_p = os.path.join(tempfile.gettempdir(), f"__vf_rnd_{os.getpid()}_{os.path.basename(dst_path)}")
    sc.render.filepath = tmp_p
    bpy.ops.render.render(write_still=True)
    for attempt in range(retries):
        try:
            shutil.copy2(tmp_p, dst_path)
            break
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(0.4)
    try:
        os.remove(tmp_p)
    except OSError:
        pass
    return dst_path


def save_png_8bit(rgba: np.ndarray, path: str, colorspace: str) -> bpy.types.Image:
    """Save a `[H, W, 4]` float32 array in `[0, 1]` to an 8-bit PNG safely via temp copy."""
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
    for attempt in range(6):
        try:
            shutil.copy2(tmp_p, path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.35)
    try:
        os.remove(tmp_p)
    except OSError:
        pass
    img.filepath = path
    img.reload()
    img.colorspace_settings.name = colorspace
    return img

