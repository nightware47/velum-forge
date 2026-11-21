"""Blender 3D Viewport Reference Image Plane Loader (`vflib.refs`).

Places orthographic Front / Side / Top reference blueprint planes in a `VF_References_ref` collection
scaled to exact real-world meters (`target_length_m`) — automatically excluded from exports and QA counts!
"""
from __future__ import annotations

import json
import math
import os

import bpy

from . import core


def load_reference_planes(asset_dir: str) -> bpy.types.Collection | None:
    """Load `<asset_dir>/asset_spec.json` or `<asset_dir>/references/*.png` into `VF_References_ref`."""
    spec_path = os.path.join(asset_dir, "asset_spec.json")
    target_len = 1.20
    refs = []
    if os.path.isfile(spec_path):
        try:
            with open(spec_path, "r", encoding="utf-8-sig") as fh:
                spec = json.load(fh)
            target_len = float(spec.get("target_length_m", 1.20))
            refs = spec.get("references", [])
        except Exception:
            pass

    if not refs:
        ref_dir = os.path.join(asset_dir, "references")
        if os.path.isdir(ref_dir):
            for fn in sorted(os.listdir(ref_dir)):
                if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    refs.append({"path": os.path.join(ref_dir, fn), "view": "side" if "side" in fn.lower() else "hero"})

    if not refs:
        return None

    # Suffix `_ref` ensures `qa_pipeline.py` automatically excludes reference empties from mesh checks!
    ref_col = core.fresh_collection("VF_References_ref")
    for idx, item in enumerate(refs[:4]):
        img_p = item.get("path") or ""
        if not os.path.isfile(img_p):
            continue
        try:
            img = bpy.data.images.load(img_p, check_existing=True)
        except Exception:
            continue

        emp = bpy.data.objects.new(f"RefPlane_{item.get('view', 'ref')}_{idx}", None)
        emp.empty_display_type = "IMAGE"
        emp.data = img
        emp.empty_display_size = target_len
        emp.use_empty_image_alpha = True
        emp.color = (1.0, 1.0, 1.0, 0.42)

        view = item.get("view", "side")
        if view == "front":
            emp.location = (0.0, -target_len * 0.75, target_len * 0.25)
            emp.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        elif view == "top":
            emp.location = (0.0, 0.0, -0.02)
            emp.rotation_euler = (0.0, 0.0, math.radians(90.0))
        else:
            # Side / hero reference parked slightly to port (-X) facing +X so side ortho aligns 1:1!
            emp.location = (-target_len * 0.45, 0.0, target_len * 0.22)
            emp.rotation_euler = (math.radians(90.0), 0.0, math.radians(90.0))

        emp.hide_render = True
        ref_col.objects.link(emp)

    return ref_col
