# AGENTS.md — Velum Forge Universal AI Operating Rules

This repository (**Velum Forge v1.2**) defines the standard AI-driven 3D engineering workflow used across **Google Antigravity**, **Claude Code**, **Codex**, and **Cursor**.

## Core Directives for AI Agents

1. **Read the Bundled Skills Before Writing 3D Code:**
   - [`plugins/velum-forge/skills/velum-3d-workflow/SKILL.md`](plugins/velum-forge/skills/velum-3d-workflow/SKILL.md) — Master 6-stage pipeline + optional Iterative Honest Rating Loop.
   - [`plugins/velum-forge/skills/velum-cad-brep/SKILL.md`](plugins/velum-forge/skills/velum-cad-brep/SKILL.md) — `build123d` OpenCascade B-Rep mechanical hardware -> `1:1 m` GLB.
   - [`plugins/velum-forge/skills/velum-organic-species/SKILL.md`](plugins/velum-forge/skills/velum-organic-species/SKILL.md) — Closed `S^2` organic/fish/creature manifolds, polar jewel eyes & swim rigs.
   - [`plugins/velum-forge/skills/velum-pbr-bake-lods/SKILL.md`](plugins/velum-forge/skills/velum-pbr-bake-lods/SKILL.md) — Cycles `OPTIX` `2048x2048` PBR baking, Blender 5.2+ traps & 4-tier LODs.
   - [`docs/BLENDER_52_GOTCHAS.md`](docs/BLENDER_52_GOTCHAS.md) — Critical API & color-space traps in Blender 5.2+.

2. **Match Reference Mode to Reference Type (Perspective vs. Ortho Blueprint):**
   - **Real Perspective Photos (Street View, 3/4, close-ups, aerials):** Mount matched Blender perspective cameras (`vflib.refs.load_references` / `refs.add_perspective_ref_camera`) with matching `lens_mm` so `vforge qa` generates a multi-angle paired `ref_comparison.png`. Never force ortho planes or ortho grids onto perspective photos!
   - **Orthographic Blueprints (`ortho_side`, `ortho_front`, `ortho_top`):** Use `1:1 m` orthographic planes and opt-in `--ortho-grid` strictly on orthographic elevation views.

3. **Never Skip the 6 Engineering Gates (+ Optional Gate 4B Critic Loop):**
   - **Gate 1 (Real Scale & Grounding):** `1.0 unit = 1.0 m`, `+Y` forward (`vflib` convention), `+Z` up, lowest vertex resting at `Z = 0.0000 m`, transforms `(1, 1, 1)` applied.
   - **Gate 2 (Hybrid CAD + Watertight `S^2` BMesh):** Use `build123d` (`engine/cad/cad_bridge.py`) for machined/cast hardware and closed circumferential `bmesh` lofts (`engine/blender/vflib/`) for hulls, bodies, architecture, and hydrofoils (`t_half >= 0.80 mm` -> `>= 1.6 mm` wall thickness).
   - **Gate 3 (BVH Shell-Integrity & Signed-Volume Normals):** Clamp interior structures strictly inside outer shells; verify `0` shell breaches, `0` floating parts, and positive signed volume (`vflib.integrity.ensure_positive_signed_volume`).
   - **Gate 4 (10-View Visual & Geometric QA):** Run `vforge qa <script_or_model> --profile roblox --forward-axis +Y` and visually inspect `contact_sheet_material.png`, `contact_sheet_diagnostic.png`, and multi-angle `ref_comparison.png` until **`PASS (Errors: 0, Warnings: 0)`**.
   - **Gate 4B (Optional Iterative Critic & Honest Rating Reviews):** When `review_loop.enabled` is `true` in `asset_spec.json` (or requested via `--iterate` / Studio toggle), snapshot each pass (`--snapshot-iteration`), rate honestly (`0.0–10.0` with no grade inflation + automatic QA gate caps) via `vforge review log`, and iterate on categorized defects until `honest_rating >= target_score` and `0` QA issues!
   - **Gate 5 (Cycles `OPTIX` `2048x2048` PBR Baking):** Bake `Color` (`sRGB` with linear raytraced AO + `lin_arr_to_srgb`), OpenGL `Normal`, `Roughness`, `Metalness`, `AO`, and `ORM` (`Non-Color`).
   - **Gate 6 (Variants + Seam-Locked `LOD0`–`LOD3`):** Deliver 3–4 variants + 4 LOD tiers (`100% / ~50% / ~25% / ~10%`) verified on a `2x2` `lod_comparison_sheet.png`.
