---
name: velum-3d-workflow
description: Master 6-stage Velum Forge runbook for building production-grade, zero-clipping, Cycles-baked 2K PBR 3D assets (vehicles, boats, props, wildlife/fish) with 4 variants, 4-tier LOD0-LOD3 chains, and automated 10-view Roblox/glTF QA. Activate first on any end-to-end 3D asset build or overhaul request.
---

# Velum Forge — Master 6-Stage 3D Asset Workflow

Use this skill whenever asked to create, overhaul, or productionize a 3D model. Every Velum Forge asset passes **6 deterministic engineering gates** — never skip straight from raw geometry to delivery without visual QA, BVH shell-integrity verification, real PBR texture baking, and LODs.

## Pipeline Architecture

```text
Stage 0: Reference Intake & Spec (`references/*` + `asset_spec.json` + 1:1m Viewport Planes)
   │
Stage 1: Precision CAD Hardware (build123d -> STEP + 1:1m watertight GLB)   [velum-cad-brep]
   │
Stage 2: Parametric / Organic BMesh Assembly in Meters (+Y fwd, Z=0 ground)  [velum-organic-species]
   │
Stage 3: Hard BVH Shell-Integrity & Signed-Volume Normal Gate (0 breaches)
   │
Stage 4: Automated 10-View QA + Side-by-Side `ref_comparison.png` (`PASS` 0E/0W)
   │
Stage 5: Cycles GPU (OPTIX) 2048x2048 PBR Texture Bake + Multi-Variant Build [velum-pbr-bake-lods]
   │
Stage 6: Seam-Locked 4-Tier LOD0..LOD3 + Game Engine Export + Visual Review
```

## Stage-by-Stage Execution Checklist

### Stage 0 — Reference Images, `asset_spec.json` & Starting a New Asset
- **Starting from scratch or reference photos:**
  ```powershell
  # Stages reference photos into <dir>/references/, extracts dominant hex palette & aspect ratio,
  # writes asset_spec.json, and generates a reference-calibrated baseline + Ref-vs-Model QA sheet:
  vforge generate red_snapper --kind fish --length 0.85 --ref path\to\snapper_side.jpg --prompt "Northern Red Snapper"
  ```
- **When refining an existing or Studio-staged asset folder:**
  1. Always check `<asset_dir>/asset_spec.json` first and **visually read every image inside `<asset_dir>/references/`** before writing geometry!
  2. Call `refs.load_reference_planes(THIS_DIR)` (`from vflib import refs`) inside `build_<slug>.py` so `1:1 m` orthographic reference planes are placed inside `VF_References_ref` (automatically ignored by QA triangle checks & game exports).
  3. Whenever `<asset_dir>/references/` contains at least one image, `vforge qa` **automatically generates `<asset_dir>/renders/ref_comparison.png`** placing `REFERENCE` side-by-side next to `MODEL` — always inspect `ref_comparison.png` visually and iterate until silhouette, proportions, and colors match!

### Stage 1 — Precision Mechanical CAD Sub-Assemblies (`velum-cad-brep`)
- Whenever an asset includes machined, cast, or ergonomic hardware (steering wheels, cleats, throttles, propellers, rod launchers, hinges, brackets), build them in `build123d` (`engine/cad/cad_bridge.py`) at `1.0 unit = 1.0 meter` (`+Z = Up`).
- Export via `export_cad_part()` / `export_cad_assembly()`, which cleans OpenCascade B-Reps, converts `Z-up -> glTF Y-up` once, welds vertices, verifies positive volume, and writes `.step` + `.glb`.
- Import those `.glb` sub-parts into Blender (`bpy.ops.import_scene.gltf`) at exact `1:1` meter coordinates.

### Stage 2 — Parametric / Organic Primary Forms (`vflib`)
- Add `<velum-forge>/engine/blender` to `sys.path` and import `from vflib import core, mats, gameready, integrity, bake, lod, export, render`.
- **Coordinate standard:** `1 unit = 1.0 m`, `+X` = Right/Starboard, `+Y` = Forward (`vflib` convention; maps to Roblox `-Z` `LookVector`), `+Z` = Up.
- **Closed watertight manifolds (`S^2`):** Build hulls, bodies, and hydrofoil fins from ordered circumferential rings capped at both ends (`_build_closed_tube_with_caps`) so Euler characteristic $\chi = V - E + F = 2$ (`0` boundary edges, `0` non-manifold edges).
- **Ground exact lowest vertex to `Z = 0.0000 m`:** Shift mesh vertex data (`ob.data.transform(Matrix.Translation((0, 0, -lo.z)))`) so object origins stay `(0, 0, 0)` and `scale = (1, 1, 1)`.
- **Tag every mesh:** Set `ob["sc_part"] = "<MeshPartName>"` (keeping each `MeshPart < 20,000` tris for Roblox) and `ob["sc_role"] = "solid" | "paint" | "glass" | "neon"`. Add `core.socket("Name", col, loc)` for functional attachments/hinges.

### Stage 3 — Hard BVH Shell-Integrity Gate
- **Never extrude interior floors, bulkheads, lockers, or fin roots blindly.** Clamp interior coordinates strictly inside the inner wall (`x_max = inner_hull_x(y, z) - clearance`).
- Run `BVHTree.FromBMesh` overlap & raycast checks (`vflib.integrity`) before saving:
  - `0` outer-shell breaches from interior parts.
  - `100%` positive root socket contact (`< 1.5 mm`) on attached fins, eyes, rails, or hardware (`0` floating parts).
  - Exact **signed-volume normal check** (`integrity.ensure_positive_signed_volume(bm)`) so concave V-forked tails or thin shells never invert normals.
  - Keep thin closed walls `>= 1.6 mm` thick (`half_thickness >= 0.80 mm`) so `qa_check.py` (`--eps 0.001`) never flags hidden `< 1 mm` back-to-back faces.

### Stage 4 — 10-View Automated QA Gate (`0` Errors, `0` Warnings)
- Run:
  ```powershell
  vforge qa path\to\build_asset.py --profile roblox --forward-axis +Y
  # or directly:
  .\engine\cad\run_qa.ps1 -Asset path\to\build_asset.py -Profile roblox -ForwardAxis "+Y"
  ```
- **Always inspect both rendered contact sheets visually** (`contact_sheet_material.png` + `contact_sheet_diagnostic.png`) plus `underbody` views. Fix every error AND every warning until the banner is green **`PASS (Errors: 0, Warnings: 0)`**.

### Stage 5 — Cycles GPU `2048x2048` PBR Bake & Variants (`velum-pbr-bake-lods`)
- Author rich procedural Cycles materials (wood planks + caulk grooves, diamond non-skid, imbricated scales, leather grain, sonar UI, weathered metal) and bake true `2048x2048` maps (`Color` w/ linear raytraced AO -> `sRGB`, OpenGL `Normal`, `Roughness`, `Metalness`, `AO`, `ORM` -> `Non-Color`).
- Build **3–4 distinct variants** (including genuine geometry/equipment variations where appropriate, such as patrol lightbars or sexual dimorphism).

### Stage 6 — Seam-Locked 4-Tier `LOD0`–`LOD3` & Live Delivery
- Generate `LOD0` (`100%`), `LOD1` (`~50%`), `LOD2` (`~25%`), and `LOD3` (`~10%`) via `vflib.lod.build_lod_chain()`.
- Render and **visually inspect**:
  1. `variants_lineup.png` (all variants un-cropped in studio echelon)
  2. `baked_closeup.png` (macro proof of baked normal/roughness/AO micro-detail)
  3. `lod_comparison_sheet.png` (2x2 grid verifying zero seam tearing or inner-wall poke across `LOD0`–`LOD3`)
  4. Baked `Color` and `Normal` PNG atlases
- Sync final `.blend`, `.glb`, and `blender-render-check.png` to `core.DESIGN_OUTPUT_DIR` and open visibly in Blender when working interactively with a user.

## Reference Flagships in Repo
- Hard-surface / Naval Vessel: `examples/sunrunner_24/` (`build_hardware_cad.py`, `build_sunrunner_24.py`, `bake_lod_variants.py`)
- Organic / Pelagic Wildlife + Swim Rig: `examples/mahi_mahi/` (`build_mahi_mahi.py`, `bake_lod_variants.py`)
