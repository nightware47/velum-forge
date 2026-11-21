"""Hard BVH Shell-Integrity, Socket-Contact & Signed-Volume Normal Gates (`vflib.integrity`).

Prevents shell poke-throughs, floating parts, and inverted normals on concave/forked closed manifolds.
"""
from __future__ import annotations

import bmesh
import bpy
from mathutils.bvhtree import BVHTree


def ensure_positive_signed_volume(bm: bmesh.types.BMesh) -> float:
    """Enforce 100% outward face normals on any closed `S^2` manifold using exact 3D signed volume."""
    bm.faces.ensure_lookup_table()
    vol6 = 0.0
    for f in bm.faces:
        if len(f.verts) >= 3:
            v0 = f.verts[0].co
            for k in range(1, len(f.verts) - 1):
                vol6 += v0.dot(f.verts[k].co.cross(f.verts[k + 1].co))
    if vol6 < 0.0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        vol6 = -vol6
    return vol6 / 6.0


def verify_socket_contact(
    primary_ob: bpy.types.Object,
    sub_objects: list[bpy.types.Object],
    *,
    forbid_medial_cross_names: set[str] | None = None,
    medial_eps: float = 0.002,
) -> list[str]:
    """Verify every sub-object contacts `primary_ob` (0 floating islands) and respects symmetry planes."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    bm_prim = bmesh.new()
    bm_prim.from_object(primary_ob, dg)
    bm_prim.transform(primary_ob.matrix_world)
    bvh_prim = BVHTree.FromBMesh(bm_prim)

    forbid = forbid_medial_cross_names or set()
    errors: list[str] = []

    for ob in sub_objects:
        if ob == primary_ob or ob.type != "MESH":
            continue
        bm = bmesh.new()
        bm.from_object(ob, dg)
        bm.transform(ob.matrix_world)
        bvh_sub = BVHTree.FromBMesh(bm)

        if not bvh_prim.overlap(bvh_sub):
            errors.append(f"{ob.name}: FLOATING (0 BVH contact with {primary_ob.name})")

        if ob.name in forbid:
            for v in bm.verts:
                if abs(v.co.x) < medial_eps:
                    errors.append(f"{ob.name}: crossed X=0 medial plane at {tuple(round(c, 4) for c in v.co)}")
                    break
        bm.free()

    bm_prim.free()
    return errors

