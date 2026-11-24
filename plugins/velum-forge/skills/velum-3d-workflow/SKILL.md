---
name: velum-3d-workflow
description: Master 6-stage Velum Forge runbook for building production-grade, zero-clipping, Cycles-baked 2K PBR 3D assets (vehicles, boats, architecture/street scenes, props, wildlife/fish) with matched perspective reference cameras, optional Honest Rating Iteration Reviews, 4 variants, 4-tier LOD0-LOD3 chains, and automated 10-view Roblox/glTF QA. Activate first on any end-to-end 3D asset build or overhaul request.
---

# Velum Forge — Master 6-Stage 3D Asset Workflow (v1.2)

Use this skill whenever asked to create, overhaul, or productionize a 3D model. Every Velum Forge asset passes **6 deterministic engineering gates** plus an **optional Iterative Visual Critic & Honest Rating Review Loop**.

## Pipeline Architecture

```text
Stage 0: Reference Intake & Spec (`references/*` + `asset_spec.json` + Perspective Cams OR Ortho Blueprints)
   │
Stage 1: Precision CAD Hardware (build123d -> STEP + 1:1m watertight GLB)   [velum-cad-brep]
   │
Stage 2: Parametric / Organic / Arch BMesh Assembly in Meters (+Y fwd, Z=0) [velum-organic-species]
   │
Stage 3: Hard BVH Shell-Integrity & Signed-Volume Normal Gate (0 breaches)
   │
Stage 4: Automated 10-View QA + Multi-Angle `ref_comparison.png` (`PASS` 0E/0W)
   │
Stage 4B (OPTIONAL): Iterative Visual Critic & Honest Rating Loop (`vforge review`)
   │      Snapshot -> Honest X.X/10 Rating + Categorized Defects -> Fix -> Re-QA until >= Target
   │
Stage 5: Cycles GPU (OPTIX) 2048x2048 PBR Texture Bake + Multi-Variant Build [velum-pbr-bake-lods]
   │
Stage 6: Seam-Locked 4-Tier LOD0..LOD3 + Game Engine Export + Visual Review
```

## Stage-by-Stage Execution Checklist

### Stage 0 — Perspective Photos vs. Ortho Blueprints & `asset_spec.json`
- **Real Perspective Photos (`projection: "perspective"` — Street View, 3/4 shots, close-ups, aerials):**
  - Do **NOT** slap flat ortho blueprint planes or ortho grids onto perspective photos!
  - Call `refs.load_references(THIS_DIR, subject_objects=meshes)` (or register exact custom viewpoints with `refs.add_perspective_ref_camera("StreetCorner_01", img_path, location=(...), target=(...), lens_mm=28.0)`) so Blender mounts real matched perspective cameras (`VF_RefCam_*`) with camera background overlays.
  - `vforge qa` automatically renders EVERY `VF_RefCam_*` camera and builds a **multi-angle side-by-side `renders/ref_comparison.png`** pairing all reference photos 1-to-1 with their matched model renders!
- **Orthographic Blueprints (`projection: "ortho_blueprint"` — Side/Front/Back/Top elevations ONLY):**
  - `refs.load_references(THIS_DIR)` mounts `1:1 m` orthographic planes in `VF_References_ref`.
  - Pass `--ortho-grid` to `vforge qa` (or set `ortho_blueprint_grid: true` in `asset_spec.json`) ONLY when you want a calibrated metric ruler grid on `ORTHO` blueprint views — never on perspective shots!
- **Starting from CLI with optional Iterative Rating Mode:**
  ```powershell
  # Standard single-pass build:
  vforge generate red_snapper --kind fish --length 0.85 --ref path\to\snapper_photo.jpg --prompt "Northern Red Snapper"

  # Architecture / Street Scene with multiple Street View photos + Optional Iterative Honest Rating Loop:
  vforge generate ocean_dr_800 --kind arch --length 18.0 --ref gsv1.jpg --ref gsv2.jpg --iterate --target-score 9.0 --max-iterations 3
  ```

### Stage 1 — Precision Mechanical CAD Sub-Assemblies (`velum-cad-brep`)
- Whenever an asset includes machined, cast, or ergonomic hardware (steering wheels, cleats, throttles, propellers, door pulls, sconces, brackets), build them in `build123d` (`engine/cad/cad_bridge.py`) at `1.0 unit = 1.0 meter` (`+Z = Up`).
- Export via `export_cad_part()` / `export_cad_assembly()` and import `.glb` sub-parts into Blender (`bpy.ops.import_scene.gltf`) at exact `1:1` meter coordinates.

### Stage 2 — Parametric / Organic / Architectural Primary Forms (`vflib`)
- Add `<velum-forge>/engine/blender` to `sys.path` and import `from vflib import core, mats, gameready, integrity, bake, lod, export, render, refs`.
- **Coordinate standard:** `1 unit = 1.0 m`, `+X` = Right/Starboard, `+Y` = Forward (`vflib` convention; maps to Roblox `-Z` `LookVector`), `+Z` = Up.
- **Closed watertight manifolds (`S^2`):** Build hulls, bodies, and hydrofoil fins from ordered circumferential rings capped at both ends so Euler characteristic $\chi = V - E + F = 2$.
- **Ground exact lowest vertex to `Z = 0.0000 m`** while keeping object scale `(1, 1, 1)`.
- **Tag every mesh:** Set `ob["sc_part"] = "<MeshPartName>"` (`< 20,000` tris per `MeshPart` for Roblox) and `ob["sc_role"] = "solid" | "paint" | "glass" | "neon"`.

### Stage 3 — Hard BVH Shell-Integrity Gate
- Never extrude interior floors, bulkheads, lockers, or fin roots blindly through outer shells. Clamp interior coordinates strictly inside the inner wall (`vflib.integrity`).
- Run `integrity.ensure_positive_signed_volume(bm)` on every closed manifold and keep thin closed walls `>= 1.6 mm` thick (`half_thickness >= 0.80 mm`) so `qa_check.py` (`--eps 0.001`) never flags back-to-back faces.

### Stage 4 — 10-View Automated QA + Multi-Angle Reference Comparison (`0` Errors, `0` Warnings)
- Run:
  ```powershell
  vforge qa path\to\build_asset.py --profile roblox --forward-axis +Y
  # Add --ortho-grid ONLY for ortho blueprints; add --snapshot-iteration when Iterative Review is active:
  vforge qa path\to\build_asset.py --profile roblox --forward-axis +Y --snapshot-iteration
  ```
- **Always inspect visually** (`read_file`): `renders/qa_contact_material.png`, `renders/qa_contact_diagnostic.png`, `renders/ref_comparison.png`, and any individual `renders/refcam_*.png` shots.

### Stage 4B (OPTIONAL) — Iterative Visual Critic & Honest Rating Loop (`vforge review`)
Check `asset_spec.json["review_loop"]["enabled"]` (or whether the user requested iterative rating reviews).
- **If `enabled == false`** (default fast mode): skip straight to Stage 5 once Stage 4 passes (`0` errors, `0` warnings).
- **If `enabled == true`** (or explicitly requested by the user):
  1. Visually inspect ALL rendered views against ALL reference photos + `qa_report.json`.
  2. Be **brutally honest — NO grade inflation!** Explicitly call out icosphere/blob foliage, broomstick branches, buried windows, clipping umbrellas/props, blurry signage, curb overhang, floating parts, z-fighting, or UV overlaps.
  3. Score across the 6 rubric axes (`silhouette_proportions`, `reference_fidelity`, `detail_craft`, `materials_lighting`, `geometric_qa`, `scene_continuity`). Remember: `velum_forge.review` **automatically caps** the rating at `7.9/10` if `qa_report.json` has errors (or `8.9/10` if warnings remain when zero-warnings is enforced).
  4. Record each iteration via CLI (automatically archives snapshots, updates `reviews/REVIEW_LOG.md`, and renders `reviews/iteration_progression.png`!):
     ```powershell
     vforge review log path\to\asset_dir `
       --score 7.8 `
       --summary "Huge jump on glazing, signage, and palm fronds, but not 10/10 yet." `
       --strength "Dark reflective windows across all 3 stories and 100% outward blue face orientation" `
       --defect "Shade Trees|major|Straight branch cylinders radiate like broomsticks|Build gnarled curved boughs wrapped in full billowing broad-leaf canopy" `
       --defect "Geometric QA|critical|Floating breeze blocks (6mm gap) and chair backrests|Bridge mortar joints and seat backrests into frames"
     ```
  5. Fix every critical/major defect + every QA report issue, re-run `vforge qa ... --snapshot-iteration`, and log the next iteration until **`honest_rating >= target_score`** (default `9.0 / 10`) AND **`QA PASS (0E/0W)`**, or until `max_iterations` is reached.
  6. Use `vforge review status <dir>` to check score progression and `vforge review prompt <dir>` to generate a focused defect-fix prompt!

### Stage 5 — Cycles GPU `2048x2048` PBR Bake & Variants (`velum-pbr-bake-lods`)
- Author rich procedural Cycles materials and bake true `2048x2048` maps (`Color` w/ linear raytraced AO -> `sRGB`, OpenGL `Normal`, `Roughness`, `Metalness`, `AO`, `ORM` -> `Non-Color`).
- Build 3–4 distinct variants where appropriate.

### Stage 6 — Seam-Locked 4-Tier `LOD0`–`LOD3` & Live Delivery
- Generate `LOD0` (`100%`), `LOD1` (`~50%`), `LOD2` (`~25%`), and `LOD3` (`~10%`) via `vflib.lod.build_lod_chain()`.
- Visually inspect `variants_lineup.png`, `baked_closeup.png`, `lod_comparison_sheet.png`, and (when enabled) `reviews/iteration_progression.png`.
- Sync final `.blend`, `.glb`, and `blender-render-check.png` to `core.DESIGN_OUTPUT_DIR` and open visibly in Blender when working interactively with a user.
