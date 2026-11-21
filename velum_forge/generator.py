"""Reference-driven 3D Asset Generator & AI Agent Orchestrator (`velum_forge.generator`).

Supports three seamless generation modes:
  1. `parametric` — Instant offline reference-calibrated multi-part generator (uses reference aspect ratio,
     dominant hex palette, and real-world meters) + automatic 10-view QA & `ref_comparison.png`!
  2. `claude` / `codex` / `gemini` — Drives an installed local multimodal AI CLI (`claude`, `codex`, `gemini`)
     to inspect `<asset_dir>/references/*`, write bespoke `build_<slug>.py` + `bake_lod_variants.py`,
     pass the 10-view QA gate (`0` errors, `0` warnings), and bake 2K Cycles PBR textures + LOD0-LOD3.
  3. `handoff` — Stages `asset_spec.json` + `references/` and outputs a 1-click copyable prompt for
     interactive IDE agents (Google Antigravity, Cursor, Windsurf, Claude Code).
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
from pathlib import Path
from typing import Any

from . import BLENDER_ENGINE_DIR, CAD_ENGINE_DIR, EXAMPLES_DIR, REPO_ROOT
from .references import write_asset_spec


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", name.strip().lower()).strip("_")
    return s or "custom_asset"


def pascal_case(slug: str) -> str:
    return "".join(w.capitalize() for w in slug.split("_") if w)


def detect_ai_clis() -> list[dict[str, Any]]:
    """Detect installed local AI coding CLIs (`claude`, `codex`, `gemini`) on PATH or npm global bin."""
    appdata = os.environ.get("APPDATA", "")
    home = Path.home()

    specs = [
        ("claude", "Claude Code CLI (Multimodal Reference Vision + Code)", [
            shutil.which("claude"),
            str(Path(appdata) / "npm" / "claude.cmd") if appdata else None,
            str(home / ".local" / "bin" / ("claude.exe" if platform.system() == "Windows" else "claude")),
        ]),
        ("codex", "OpenAI Codex CLI", [
            shutil.which("codex"),
            str(Path(appdata) / "npm" / "codex.cmd") if appdata else None,
        ]),
        ("gemini", "Google Gemini CLI", [
            shutil.which("gemini"),
            str(Path(appdata) / "npm" / "gemini.cmd") if appdata else None,
        ]),
    ]

    found: list[dict[str, Any]] = []
    for cid, label, cands in specs:
        exe = next((c for c in cands if c and os.path.isfile(c)), None)
        found.append({"id": cid, "label": label, "installed": exe is not None, "exe": exe})
    return found


def build_agent_handoff_prompt(asset_dir: Path) -> str:
    """Build a crystal-clear, copy-paste-ready prompt for Antigravity, Cursor, Claude Code, or Codex."""
    spec_file = asset_dir / "asset_spec.json"
    spec = json.loads(spec_file.read_text(encoding="utf-8-sig")) if spec_file.is_file() else {}
    slug = spec.get("slug", asset_dir.name)
    title = spec.get("title", slug)
    kind = spec.get("kind", "prop")
    prompt = spec.get("prompt", title)
    length_m = spec.get("target_length_m", 1.2)
    refs = spec.get("references", [])
    pal = spec.get("extracted_palette", [])

    ref_lines = "\n".join(
        f"  - `{r['path']}` (view={r.get('view', 'hero')}, subject_aspect={r.get('subject_aspect_w_over_h')}, palette={r.get('dominant_palette')})"
        for r in refs
    ) or "  - (No reference images attached — research real-world dimensions & proportions first)"

    return (
        f"Build and refine the Velum Forge 3D asset **{title}** (`{slug}`, archetype=`{kind}`, target_length=`{length_m} m`) "
        f"in `{asset_dir}` following the Velum Forge 6-Gate Standard:\n\n"
        f"1. **Read Spec & Reference Images First:**\n"
        f"   - Spec JSON: `{spec_file}`\n"
        f"   - User Description: {prompt}\n"
        f"   - Extracted Reference Palette: {', '.join(pal)}\n"
        f"   - Reference Images (inspect every image visually before modeling!):\n{ref_lines}\n\n"
        f"2. **Read Velum Forge Skills & Guardrails (`{REPO_ROOT}`):**\n"
        f"   - Activate `velum-3d-workflow` (and `velum-cad-brep` / `velum-organic-species` / `velum-pbr-bake-lods`).\n"
        f"   - Engine imports: `sys.path.insert(0, r\"{BLENDER_ENGINE_DIR}\")` -> `from vflib import core, mats, gameready, integrity, bake, lod, export, refs`.\n"
        f"   - Load viewport reference planes via `refs.load_reference_planes(THIS_DIR)`.\n\n"
        f"3. **Author Bespoke Geometry & Shaders (`build_{slug}.py` + `bake_lod_variants.py`):**\n"
        f"   - Real-world meter scale (`+Y` forward, `+Z` up, `ground_z = 0.0000 m`), `< 20,000` tris per `MeshPart`, `>= 1.6 mm` wall thickness, positive signed volume normals, and `0` BVH shell breaches.\n\n"
        f"4. **Verify 10-View QA + Side-by-Side Reference Comparison (`PASS` 0 Errors, 0 Warnings):**\n"
        f"   - Run: `vforge qa \"{asset_dir / f'build_{slug}.py'}\" --profile {spec.get('qa_profile', 'roblox')} --forward-axis +Y`\n"
        f"   - Visually inspect `renders/qa_contact_material.png`, `renders/qa_contact_diagnostic.png`, and `renders/ref_comparison.png`!\n\n"
        f"5. **Bake `2048x2048` Cycles GPU PBR Maps, 4 Variants & `LOD0`–`LOD3`:**\n"
        f"   - Run: `vforge bake \"{asset_dir / 'bake_lod_variants.py'}\"` and inspect `renders/variants_lineup.png` and `renders/lod_comparison_sheet.png`."
    )


def generate_parametric_scripts(
    asset_dir: Path,
    *,
    slug: str,
    title: str,
    kind: str,
    prompt: str,
    length_m: float,
    references: list[dict[str, Any]],
    profile: str = "roblox",
) -> dict[str, str]:
    """Write reference-calibrated multi-part `build_<slug>.py` + `bake_lod_variants.py` + `asset_spec.json`."""
    asset_dir.mkdir(parents=True, exist_ok=True)
    spec_path = write_asset_spec(
        asset_dir,
        slug=slug,
        title=title,
        kind=kind,
        prompt=prompt,
        length_m=length_m,
        profile=profile,
        references=references,
    )
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    pal = spec["extracted_palette"]
    c_primary = pal[0] if len(pal) > 0 else "#0E7490"
    c_secondary = pal[1] if len(pal) > 1 else "#EAB308"
    c_belly = pal[2] if len(pal) > 2 else "#F1F5F9"
    c_accent = pal[3] if len(pal) > 3 else "#1E293B"

    # Extract aspect ratio hint from side/hero reference if provided!
    ref_aspect = next((r["subject_aspect_w_over_h"] for r in references if r.get("subject_aspect_w_over_h")), None)
    pascal = pascal_case(slug)
    bl_engine = str(BLENDER_ENGINE_DIR).replace("\\", "\\\\")
    cad_engine = str(CAD_ENGINE_DIR).replace("\\", "\\\\")

    build_py = asset_dir / f"build_{slug}.py"
    bake_py = asset_dir / "bake_lod_variants.py"

    if kind == "fish":
        # Calibrate body depth ratio from reference aspect ratio if available!
        depth_ratio = round(max(0.16, min(0.42, 0.82 / ref_aspect)), 3) if ref_aspect and ref_aspect > 1.2 else 0.24
        build_py.write_text(
            f'''"""Velum Forge Reference-Calibrated Organic Species — {title} (`{length_m} m` LOA).

Prompt: {prompt}
Reference Palette: {pal} | Calibrated Depth Ratio: {depth_ratio}
"""
from __future__ import annotations

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if "{bl_engine}" not in sys.path:
    sys.path.insert(0, "{bl_engine}")

from vflib import core, gameready, integrity, mats, refs  # noqa: E402

LOA = {float(length_m):.4f}
DEPTH_RATIO = {depth_ratio}
SNOUT_Y = LOA * 0.48
PEDUNCLE_Y = -LOA * 0.31
TAIL_Y = -LOA * 0.52


def clear_scene_and_setup_units() -> None:
    core.ensure_object_mode()
    for ob in list(bpy.data.objects):
        d = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        core._free_data(d)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def _unwrap_clean(ob: bpy.types.Object) -> None:
    core.ensure_object_mode()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(58.0), island_margin=0.012, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.010)
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)


def _tube_with_caps(rings: list[list[Vector]], cap_a: Vector, cap_b: Vector) -> bmesh.types.BMesh:
    bm = bmesh.new()
    va = bm.verts.new(cap_a)
    bm_r = [[bm.verts.new(p) for p in r] for r in rings]
    vb = bm.verts.new(cap_b)
    nc = len(bm_r[0])
    for j in range(nc):
        jn = (j + 1) % nc
        bm.faces.new((va, bm_r[0][jn], bm_r[0][j]))
    for i in range(len(bm_r) - 1):
        for j in range(nc):
            jn = (j + 1) % nc
            bm.faces.new((bm_r[i][j], bm_r[i][jn], bm_r[i + 1][jn], bm_r[i + 1][j]))
    for j in range(nc):
        jn = (j + 1) % nc
        bm.faces.new((bm_r[-1][j], bm_r[-1][jn], vb))
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    integrity.ensure_positive_signed_volume(bm)
    return bm


def _make_mesh_ob(bm: bmesh.types.BMesh, name: str, col: bpy.types.Collection, mat: bpy.types.Material) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob["sc_part"] = name
    ob["sc_role"] = "solid"
    _unwrap_clean(ob)
    return ob


def _contours(u: float) -> tuple[float, float, float]:
    max_h = LOA * DEPTH_RATIO
    env = math.sin(math.pi * math.pow(max(0.0, min(1.0, u)), 0.62))
    half_h = max(0.014 * LOA, 0.5 * max_h * env)
    half_w = max(0.010 * LOA, 0.22 * max_h * env)
    return -half_h, half_h, half_w


def build_all(collection_name: str = "{pascal}", clear_scene: bool = True, mat_override: dict | None = None):
    if clear_scene:
        clear_scene_and_setup_units()
    col = core.fresh_collection(collection_name)

    m_body = (mat_override or {{}}).get("Body") or mats.pbr("{pascal}_Body", color="{c_primary}", roughness=0.22, metallic=0.35)
    m_fin = (mat_override or {{}}).get("Fins") or mats.pbr("{pascal}_Fins", color="{c_secondary}", roughness=0.28, metallic=0.20)
    m_eye = (mat_override or {{}}).get("Eyes") or mats.pbr("{pascal}_Eyes", color="#090D16", roughness=0.04, metallic=0.10)

    # 1. Fuselage Body
    rings = []
    for i in range(1, 96):
        u = i / 96.0
        y = SNOUT_Y - u * (SNOUT_Y - PEDUNCLE_Y)
        zb, zt, hw = _contours(u)
        ring = []
        for j in range(48):
            th = (2.0 * math.pi * j) / 48.0
            zn = 0.5 * (1.0 + math.cos(th))
            z = zb + (zt - zb) * zn
            x = max(0.0012, hw * abs(math.sin(th))) * (1.0 if math.sin(th) >= 0 else -1.0)
            ring.append(Vector((x, y, z)))
        rings.append(ring)
    body = _make_mesh_ob(_tube_with_caps(rings, Vector((0, SNOUT_Y + 0.003, 0)), Vector((0, PEDUNCLE_Y - 0.003, 0))), "Body", col, m_body)

    # 2. Dorsal Fin
    d_rings = []
    for i in range(1, 56):
        s = i / 56.0
        u = 0.22 + s * 0.62
        y = SNOUT_Y - u * (SNOUT_Y - PEDUNCLE_Y)
        _, zt, _ = _contours(u)
        fh = LOA * 0.095 * math.sin(math.pi * math.pow(s, 0.7))
        d_rings.append([
            Vector((math.sin(2.0 * math.pi * j / 20.0) * max(0.001, 0.0025 * (1.0 - 0.6 * (0.5 * (1.0 - math.cos(2.0 * math.pi * j / 20.0))))),
                    y - 0.02 * s, zt - 0.004 + (0.5 * (1.0 - math.cos(2.0 * math.pi * j / 20.0))) * max(0.004, fh)))
            for j in range(20)
        ])
    y_d0 = SNOUT_Y - 0.22 * (SNOUT_Y - PEDUNCLE_Y)
    y_d1 = SNOUT_Y - 0.84 * (SNOUT_Y - PEDUNCLE_Y)
    dorsal = _make_mesh_ob(_tube_with_caps(d_rings, Vector((0, y_d0, _contours(0.22)[1] - 0.003)), Vector((0, y_d1, _contours(0.84)[1] - 0.003))), "DorsalFin", col, m_fin)

    # 3. Forked Caudal Tail Fin
    c_rings = []
    span_z = LOA * DEPTH_RATIO * 0.72
    for i in range(1, 64):
        s = i / 64.0
        v = 2.0 * s - 1.0
        av = abs(v)
        y_l = PEDUNCLE_Y + 0.014 * max(0.0, 1.0 - (av / 0.2) ** 2) - (LOA * 0.16) * (av ** 1.1)
        chord = max(0.012, LOA * 0.065 * (1.0 - 0.55 * av))
        c_rings.append([
            Vector((math.sin(2.0 * math.pi * j / 20.0) * 0.0018,
                    y_l - (0.5 * (1.0 - math.cos(2.0 * math.pi * j / 20.0))) * chord,
                    v * span_z))
            for j in range(20)
        ])
    caudal = _make_mesh_ob(_tube_with_caps(c_rings, Vector((0, TAIL_Y, -span_z)), Vector((0, TAIL_Y, span_z))), "CaudalFin", col, m_fin)

    # 4. Eyes
    bm_e = bmesh.new()
    ey = SNOUT_Y - 0.12 * (SNOUT_Y - PEDUNCLE_Y)
    _, _, hw_e = _contours(0.12)
    for side in (-1.0, 1.0):
        bmesh.ops.create_uvsphere(bm_e, u_segments=20, v_segments=14, radius=LOA * 0.016,
                                  matrix=Matrix.Translation((side * (hw_e * 0.88), ey, LOA * 0.018)))
    bmesh.ops.triangulate(bm_e, faces=bm_e.faces[:])
    integrity.ensure_positive_signed_volume(bm_e)
    eyes = _make_mesh_ob(bm_e, "Eyes", col, m_eye)

    meshes = [body, dorsal, caudal, eyes]
    lo, _ = core.world_bbox(meshes)
    if abs(lo.z) > 1e-7:
        for o in meshes:
            o.data.transform(Matrix.Translation((0, 0, -lo.z)))
            o.data.update()

    errs = integrity.verify_socket_contact(body, meshes, forbid_medial_cross_names={{"Eyes"}})
    if errs:
        raise RuntimeError("Integrity check failed: " + "; ".join(errs))

    refs.load_reference_planes(THIS_DIR)
    gameready.validate(meshes)
    return col, meshes


def main() -> int:
    _, meshes = build_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(THIS_DIR, "{slug}.blend"))
    bpy.ops.export_scene.gltf(filepath=os.path.join(THIS_DIR, "{slug}.glb"), export_format="GLB", export_apply=True)
    return 0


if __name__ == "__main__":
    main()
''',
            encoding="utf-8",
        )
    elif kind == "cad":
        build_py.write_text(
            f'''"""Velum Forge Reference-Calibrated B-Rep CAD Part — {title} (`{length_m} m`).

Prompt: {prompt}
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, "{cad_engine}")
from build123d import Align, Box, BuildPart, BuildSketch, Cylinder, Locations, Mode, Plane, RectangleRounded, extrude, fillet
from cad_bridge import export_cad_part

L = {float(length_m):.4f}


def build_part():
    w = L * 0.62
    h = L * 0.14
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            RectangleRounded(L, w, radius=min(L, w) * 0.12)
        extrude(amount=h)
        with BuildSketch(Plane.XY.offset(h * 0.5)):
            RectangleRounded(L * 0.52, w * 0.48, radius=min(L, w) * 0.08)
        extrude(amount=h * 1.4)
        top_e = p.edges().filter_by(lambda e: e.center().Z > h * 0.8)
        if top_e:
            fillet(top_e, radius=max(0.001, h * 0.12))
        dx, dy = L * 0.36, w * 0.32
        with Locations([(-dx, -dy, h), (dx, -dy, h), (-dx, dy, h), (dx, dy, h)]):
            Cylinder(radius=max(0.002, L * 0.028), height=h * 2.0, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
        with Locations((0, 0, -0.5)):
            Box(L * 4, L * 4, 1.0, mode=Mode.SUBTRACT)
    return p.part


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "cad"))
    args = ap.parse_args()
    res = export_cad_part(build_part(), args.out_dir, "{slug}", color="{c_primary}", metallic=0.85, roughness=0.24)
    print(json.dumps(res, indent=2))
    return 0 if res["inspection"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
''',
            encoding="utf-8",
        )
        return {"slug": slug, "dir": str(asset_dir), "spec": str(spec_path), "build_script": str(build_py)}
    else:
        # `boat` or `prop` multi-part watertight generator calibrated to `length_m` & reference palette!
        beam_ratio = 0.34 if kind == "boat" else 0.58
        height_ratio = 0.28 if kind == "boat" else 0.48
        build_py.write_text(
            f'''"""Velum Forge Reference-Calibrated 3D Asset — {title} (`{length_m} m`, `kind={kind}`).

Prompt: {prompt}
Reference Palette: {pal}
"""
from __future__ import annotations

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if "{bl_engine}" not in sys.path:
    sys.path.insert(0, "{bl_engine}")

from vflib import core, gameready, integrity, mats, refs  # noqa: E402

LOA = {float(length_m):.4f}
BEAM = LOA * {beam_ratio}
HEIGHT = LOA * {height_ratio}


def clear_scene_and_setup_units() -> None:
    core.ensure_object_mode()
    for ob in list(bpy.data.objects):
        d = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        core._free_data(d)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def _unwrap_clean(ob: bpy.types.Object) -> None:
    core.ensure_object_mode()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(58.0), island_margin=0.012, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin=0.010)
    bpy.ops.object.mode_set(mode="OBJECT")
    ob.select_set(False)


def _make_part(bm: bmesh.types.BMesh, name: str, col: bpy.types.Collection, mat: bpy.types.Material) -> bpy.types.Object:
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    integrity.ensure_positive_signed_volume(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob["sc_part"] = name
    ob["sc_role"] = "solid"
    _unwrap_clean(ob)
    return ob


def build_all(collection_name: str = "{pascal}", clear_scene: bool = True, mat_override: dict | None = None):
    if clear_scene:
        clear_scene_and_setup_units()
    col = core.fresh_collection(collection_name)
    m_hull = (mat_override or {{}}).get("Hull") or mats.pbr("{pascal}_Primary", color="{c_primary}", roughness=0.18, metallic=0.12)
    m_deck = (mat_override or {{}}).get("Deck") or mats.pbr("{pascal}_Secondary", color="{c_belly}", roughness=0.35, metallic=0.05)
    m_acc = (mat_override or {{}}).get("Accent") or mats.pbr("{pascal}_Accent", color="{c_accent}", roughness=0.22, metallic=0.65)

    # Closed lofted primary hull / body
    bm_h = bmesh.new()
    rings = []
    for i in range(1, 56):
        t = i / 56.0
        y = -0.5 * LOA + t * LOA
        w_t = 0.5 * BEAM * math.pow(math.sin(math.pi * min(1.0, (1.0 - t) * 1.15 if t > 0.35 else 0.72 + 0.28 * (t / 0.35))), 0.65)
        w_t = max(0.01 * LOA, w_t)
        z_keel = HEIGHT * 0.28 * (max(0.0, (t - 0.55) / 0.45) ** 2.0)
        z_sheer = HEIGHT * (0.76 + 0.24 * (t ** 1.4))
        ring = []
        for j in range(32):
            th = (2.0 * math.pi * j) / 32.0
            zn = 0.5 * (1.0 + math.cos(th))
            x = w_t * math.sin(th) * (0.55 + 0.45 * zn)
            z = z_keel + (z_sheer - z_keel) * zn
            ring.append(bm_h.verts.new(Vector((x, y, z))))
        rings.append(ring)
    va = bm_h.verts.new(Vector((0, -0.5 * LOA - 0.01, HEIGHT * 0.45)))
    vb = bm_h.verts.new(Vector((0, 0.5 * LOA + 0.01, HEIGHT * 0.96)))
    for j in range(32):
        jn = (j + 1) % 32
        bm_h.faces.new((va, rings[0][jn], rings[0][j]))
        bm_h.faces.new((rings[-1][j], rings[-1][jn], vb))
    for i in range(len(rings) - 1):
        for j in range(32):
            jn = (j + 1) % 32
            bm_h.faces.new((rings[i][j], rings[i][jn], rings[i + 1][jn], rings[i + 1][j]))
    hull = _make_part(bm_h, "Hull", col, m_hull)

    # Superstructure / Console
    bm_c = bmesh.new()
    bmesh.ops.create_cube(bm_c, size=1.0)
    bmesh.ops.scale(bm_c, vec=Vector((BEAM * 0.42, LOA * 0.22, HEIGHT * 0.65)), verts=bm_c.verts[:])
    bmesh.ops.translate(bm_c, vec=Vector((0.0, LOA * 0.04, HEIGHT * 0.92)), verts=bm_c.verts[:])
    bmesh.ops.bevel(bm_c, geom=bm_c.edges[:], offset=min(BEAM, HEIGHT) * 0.05, segments=3, affect="EDGES")
    console = _make_part(bm_c, "Console", col, m_deck)

    # Accent Hardware / Motor
    bm_m = bmesh.new()
    bmesh.ops.create_cube(bm_m, size=1.0)
    bmesh.ops.scale(bm_m, vec=Vector((BEAM * 0.22, LOA * 0.10, HEIGHT * 0.58)), verts=bm_m.verts[:])
    bmesh.ops.translate(bm_m, vec=Vector((0.0, -0.5 * LOA - LOA * 0.03, HEIGHT * 0.65)), verts=bm_m.verts[:])
    bmesh.ops.bevel(bm_m, geom=bm_m.edges[:], offset=min(BEAM, HEIGHT) * 0.04, segments=3, affect="EDGES")
    motor = _make_part(bm_m, "Hardware", col, m_acc)

    meshes = [hull, console, motor]
    lo, _ = core.world_bbox(meshes)
    if abs(lo.z) > 1e-7:
        for o in meshes:
            o.data.transform(Matrix.Translation((0, 0, -lo.z)))
            o.data.update()

    refs.load_reference_planes(THIS_DIR)
    gameready.validate(meshes)
    return col, meshes


def main() -> int:
    _, meshes = build_all()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(THIS_DIR, "{slug}.blend"))
    bpy.ops.export_scene.gltf(filepath=os.path.join(THIS_DIR, "{slug}.glb"), export_format="GLB", export_apply=True)
    return 0


if __name__ == "__main__":
    main()
''',
            encoding="utf-8",
        )

    # Write complete 4-Variant + 4-Tier LOD + Studio Showcase Renderer script (`bake_lod_variants.py`)!
    bake_py.write_text(
        f'''"""Velum Forge 4-Variant Showcase, LOD0-LOD3 & Render Generator for {title}."""
from __future__ import annotations

import json
import os
import shutil
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in (THIS_DIR, "{bl_engine}"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from vflib import bake, core, lod, mats, render  # noqa: E402
import build_{slug} as builder  # noqa: E402

VARIANTS = [
    ("reference_ match".replace(" ", ""), "{c_primary}", "{c_secondary}"),
    ("cobalt_edition", "#0F4C81", "#38BDF8"),
    ("crimson_sport", "#881337", "#F59E0B"),
    ("gold_legendary", "#D97706", "#FEF08A"),
]


def main() -> int:
    builder.clear_scene_and_setup_units()
    variant_cols = {{}}
    flagship_parts = {{}}
    lod_summary = {{}}

    for idx, (vid, c1, c2) in enumerate(VARIANTS):
        m_ov = {{
            "Body": mats.pbr(f"{{vid}}_body", color=c1, roughness=0.22, metallic=0.32),
            "Fins": mats.pbr(f"{{vid}}_fins", color=c2, roughness=0.28, metallic=0.22),
            "Hull": mats.pbr(f"{{vid}}_hull", color=c1, roughness=0.18, metallic=0.15),
            "Deck": mats.pbr(f"{{vid}}_deck", color="{c_belly}", roughness=0.34, metallic=0.05),
            "Accent": mats.pbr(f"{{vid}}_accent", color=c2, roughness=0.22, metallic=0.65),
        }}
        vcol, meshes = builder.build_all(collection_name=f"Variant_{{vid}}", clear_scene=False, mat_override=m_ov)
        for o in meshes:
            o.name = f"{pascal}_{{vid}}_{{o['sc_part']}}"
            o.data.name = o.name
        p_objs = {{o["sc_part"]: o for o in meshes}}
        variant_cols[vid] = vcol

        v_dir = os.path.join(THIS_DIR, "variants", vid)
        os.makedirs(v_dir, exist_ok=True)
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.export_scene.gltf(filepath=os.path.join(v_dir, f"{slug}_{{vid}}.glb"), use_selection=True, export_format="GLB", export_apply=True)
        for o in meshes:
            o.select_set(False)

        if idx == 0:
            flagship_parts = p_objs
            lod_summary = lod.build_lod_chain(flagship_parts, os.path.join(THIS_DIR, "lods"), "{slug}", collection_prefix="{pascal}")

    # Space variants neatly side-by-side & flush depsgraph so world_bbox sees all 4 translated models!
    lo, hi = core.world_bbox(list(flagship_parts.values()))
    span_x = max((hi.x - lo.x) * 2.25, (hi.y - lo.y) * 0.42, 0.25)
    all_m = []
    for idx, (vid, vcol) in enumerate(variant_cols.items()):
        dx = (idx - 1.5) * span_x
        for o in vcol.objects:
            o.location.x += dx
            if o.type == "MESH":
                all_m.append(o)
    bpy.context.view_layer.update()

    for l_idx in (1, 2, 3):
        lc = bpy.data.collections.get(f"{pascal}_LOD{{l_idx}}")
        if lc:
            lc.hide_render = True
            lc.hide_viewport = True

    sc = bpy.context.scene
    bake.enable_cycles_gpu(sc)
    sc.cycles.samples = 64
    sc.cycles.use_denoising = True
    st = render.setup_studio(all_m, backdrop="product")
    lo_all, hi_all = core.world_bbox(all_m)
    ctr = (lo_all + hi_all) * 0.5
    rad = max((hi_all - lo_all).length * 0.5, 0.3)
    cd = bpy.data.cameras.new("VF_LineupCam")
    cm = bpy.data.objects.new("VF_LineupCam", cd)
    st.objects.link(cm)
    sc.camera = cm
    sc.render.resolution_x = 1800
    sc.render.resolution_y = 1012
    cm.location = ctr + Vector((rad * 1.15, rad * 1.75, rad * 0.68))
    cm.data.lens = 35.0
    cm.rotation_euler = (ctr - cm.location).to_track_quat("-Z", "Y").to_euler()
    out_lineup = os.path.join(THIS_DIR, "renders", "variants_lineup.png")
    bake.render_still_safe(sc, out_lineup)
    core.clear_collection(st)
    bpy.data.collections.remove(st)

    master_blend = os.path.join(THIS_DIR, "{slug}_variants_lods.blend")
    bpy.ops.wm.save_as_mainfile(filepath=master_blend)
    os.makedirs(core.DESIGN_OUTPUT_DIR, exist_ok=True)
    shutil.copy2(master_blend, os.path.join(core.DESIGN_OUTPUT_DIR, "{slug}.blend"))
    shutil.copy2(out_lineup, os.path.join(core.DESIGN_OUTPUT_DIR, "blender-render-check.png"))

    rep = {{
        "ok": True,
        "asset": "{slug}",
        "bake_res": 2048,
        "lods": lod_summary,
        "variants": {{vid: {{"color": c1, "accent": c2}} for vid, c1, c2 in VARIANTS}},
    }}
    with open(os.path.join(THIS_DIR, "variants_and_lods_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
''',
        encoding="utf-8",
    )

    return {
        "slug": slug,
        "dir": str(asset_dir),
        "spec": str(spec_path),
        "build_script": str(build_py),
        "bake_script": str(bake_py),
    }


def build_ai_cli_invocation(engine_id: str, asset_dir: Path) -> list[str] | None:
    """Return non-interactive command line to run `claude`, `codex`, or `gemini` on `<asset_dir>`."""
    clis = {c["id"]: c for c in detect_ai_clis()}
    if engine_id == "auto":
        chosen = next((c for c in detect_ai_clis() if c["installed"]), None)
    else:
        c_item = clis.get(engine_id)
        chosen = c_item if (c_item and c_item["installed"]) else None

    if not chosen or not chosen["exe"]:
        return None

    brief = build_agent_handoff_prompt(asset_dir)
    exe = str(chosen["exe"])
    cid = chosen["id"]

    if cid == "claude":
        return [exe, "-p", brief, "--dangerously-skip-permissions"]
    if cid == "codex":
        return [exe, "exec", "--full-auto", brief]
    if cid == "gemini":
        return [exe, "-p", brief, "-y"]
    return None
