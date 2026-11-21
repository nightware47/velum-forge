"""Seam-Locked 4-Tier Game LOD Chain Generator (`vflib.lod`)."""
from __future__ import annotations

import math
import os

import bmesh
import bpy

from . import core, gameready

DEFAULT_LOD_TIERS = [
    (1, 0.48, set(), 0.50),
    (2, 0.24, set(), 0.25),
    (3, 0.11, set(), 0.10),
]


def build_lod_chain(
    lod0_parts: dict[str, bpy.types.Object],
    out_lods_dir: str,
    asset_slug: str,
    *,
    collection_prefix: str = "Asset",
    tiers: list[tuple[int, float, set[str], float]] | None = None,
    planar_parts: set[str] | None = None,
    outboard_decal_parts: set[str] | None = None,
) -> dict[str, dict]:
    """Build `LOD1..LOD3` collections + standalone `.glb` files preserving baked UVs & silhouette."""
    use_tiers = tiers or DEFAULT_LOD_TIERS
    planar = planar_parts or set()
    decal_out = outboard_decal_parts or set()
    os.makedirs(out_lods_dir, exist_ok=True)

    summary: dict[str, dict] = {
        "LOD0": {
            "tris": sum(gameready.triangle_count(o, False) for o in lod0_parts.values()),
            "parts": len(lod0_parts),
            "screen_size": 1.0,
        }
    }

    for lvl, ratio, culled, scr_sz in use_tiers:
        l_col = core.fresh_collection(f"{collection_prefix}_LOD{lvl}")
        lvl_objs: list[bpy.types.Object] = []
        for pname, src in lod0_parts.items():
            if pname in culled:
                continue
            cp = src.copy()
            cp.data = src.data.copy()
            cp.name = f"{pname}_LOD{lvl}"
            cp.data.name = cp.name
            l_col.objects.link(cp)
            cp["sc_part"] = pname
            cp["sc_role"] = src.get("sc_role", "solid")

            dec = cp.modifiers.new("VF_LOD_Decimate", "DECIMATE")
            if pname in planar:
                dec.decimate_type = "DISSOLVE"
                dec.angle_limit = math.radians({1: 1.8, 2: 2.6, 3: 3.4}.get(lvl, 3.0))
                dec.delimit = {"UV", "SEAM", "SHARP", "MATERIAL"}
                dec.use_dissolve_boundaries = False
            else:
                dec.decimate_type = "COLLAPSE"
                dec.ratio = ratio
                dec.delimit = {"UV", "SEAM", "SHARP"}
                dec.use_collapse_triangulate = True

            with bpy.context.temp_override(
                object=cp,
                active_object=cp,
                selected_objects=[cp],
                selected_editable_objects=[cp],
            ):
                bpy.ops.object.modifier_apply(modifier=dec.name)

            if pname in planar or pname in decal_out:
                bm = bmesh.new()
                bm.from_mesh(cp.data)
                if pname in planar:
                    bmesh.ops.triangulate(bm, faces=bm.faces[:])
                if pname in decal_out:
                    mw = cp.matrix_world
                    dx = {1: 0.003, 2: 0.008, 3: 0.013}.get(lvl, 0.006)
                    for v in bm.verts:
                        wco = mw @ v.co
                        if abs(wco.x) > 0.02:
                            v.co.x += math.copysign(dx, wco.x)
                bm.to_mesh(cp.data)
                bm.free()
                cp.data.update()

            lvl_objs.append(cp)

        glb_lod = os.path.join(out_lods_dir, f"{asset_slug}_LOD{lvl}.glb")
        core.ensure_object_mode()
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in lvl_objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = lvl_objs[0]
        bpy.ops.export_scene.gltf(filepath=glb_lod, use_selection=True, export_format="GLB", export_apply=True)
        for o in lvl_objs:
            o.select_set(False)

        tris = sum(gameready.triangle_count(o, False) for o in lvl_objs)
        summary[f"LOD{lvl}"] = {
            "tris": tris,
            "parts": len(lvl_objs),
            "screen_size": scr_sz,
            "glb": f"lods/{asset_slug}_LOD{lvl}.glb",
        }
        core.log(f"[LOD{lvl}] {tris} tris across {len(lvl_objs)} parts -> {glb_lod}")

    return summary

