# Velum Forge 3D Asset Engineering Rules

Whenever creating, refining, baking, optimizing, or exporting 3D models (`.blend`, `.glb`, `.fbx`, `.step`, `build123d`, or `bpy` scripts), follow the **Velum Forge 6-Gate Standard**:

1. **Activate the Relevant Velum Forge Skill First**:
   - Read `velum-3d-workflow` for any end-to-end 3D asset request.
   - Read `velum-cad-brep` for mechanical/hard-surface hardware (`build123d` B-Rep CAD).
   - Read `velum-organic-species` for creatures, fish, animals, or organic characters.
   - Read `velum-pbr-bake-lods` whenever baking procedural shaders to PBR textures, generating variants, or building LODs.
2. **Perspective-First Reference Matching (Use Ortho Grids Strictly for Ortho Blueprints)**:
   - Never force orthographic blueprint planes or ortho grids onto real-world perspective photos (Street View, 3/4 shots, close-ups, aerials).
   - For **perspective photos**, mount matched Blender perspective cameras (`vflib.refs.load_references()` or `refs.add_perspective_ref_camera()` with matching `lens_mm` and eye height) so `vforge qa` renders multi-angle side-by-side `ref_comparison.png` pairs through the exact matching lens.
   - Use `1:1 m` orthographic planes and optional `--ortho-grid` metric overlays **only** when the reference image is an actual orthographic blueprint (`ortho_side`, `ortho_front`, `ortho_back`, `ortho_top`).
3. **Real-World Scale & Exact Grounding**:
   - Model strictly in **meters** (`1 unit = 1.0 m`, `+Z = Up`, lowest vertex grounded at `Z = 0.0000 m`, object transforms applied to `scale = (1, 1, 1)`, `rotation = (0, 0, 0)`).
4. **Zero Shell Clipping & Watertight Topology**:
   - Never extrude interior bulkheads, lockers, fins, or mounts blindly through curved outer shells. Clamp interior geometry to the inner hull/body envelope and run a **BVH shell-integrity check** (`0` breaches, `0` floating parts).
   - Enforce outward normals on closed concave/forked manifolds using **exact 3D signed volume** ($\sum \frac{1}{6} v_0 \cdot (v_1 \times v_2) > 0$), and keep thin hydrofoil/panel wall thickness `>= 1.6 mm` so opposite faces never trigger `< 1.0 mm` back-to-back warnings.
5. **Mandatory 10-View Visual & Geometric QA Gate (`PASS` with `0` Errors, `0` Warnings)**:
   - Run `vforge qa <asset>` (or `engine/cad/run_qa.ps1`) and **visually inspect** `contact_sheet_material.png`, `contact_sheet_diagnostic.png`, and multi-angle `ref_comparison.png` before declaring geometry complete.
6. **Optional Iterative Critic & Honest Rating Loop (`review_loop.enabled` in `asset_spec.json` or when requested)**:
   - This core feature is **optional** (toggled via `--iterate`, `vforge review config <dir> --enable`, Studio UI toggle, or user request).
   - When **enabled**, archive each pass (`vforge qa ... --snapshot-iteration`), compare every render directly against all reference photos + `qa_report.json`, and log a brutally honest **Iteration N Review — Honest Rating: X.X / 10** via `vforge review log` (no grade inflation; list strengths + categorized defects; ratings are automatically capped if `qa_report.json` has errors/warnings). Iterate until `honest_rating >= target_score` (default `9.0 / 10`) with `0` QA errors/warnings, or until `max_iterations` is reached.
   - When **disabled**, run clean single-pass QA without extra iteration overhead.
7. **True Cycles GPU (`OPTIX`/`CUDA`) PBR Texture Baking (Never Ship Raw Procedural Nodes to Engines)**:
   - Game engines (Roblox, glTF, Unity, Unreal) ignore procedural Blender nodes (`Noise`, `Voronoi`, `Wave`, `Bump`, `Mix`). Always bake onto a non-overlapping `2048x2048` UV atlas (`Color` in `sRGB` + `Normal` OpenGL `Y+`, `Roughness`, `Metalness`, `AO`, `ORM` in `Non-Color`).
   - **Blender 5.2+ Critical Guardrails**:
     - `ShaderNodeMix(data_type="RGBA")`: bind explicit socket indices `inputs[0]` (Factor), `inputs[6]` (A), `inputs[7]` (B), and `outputs[2]` (Result) — never look up `"A"`, `"B"`, or `"Result"` by name (matches `Float` socket `0`!).
     - `Image.pixels.foreach_set` on 8-bit `sRGB` PNGs (`float_buffer=False`): convert scene-linear float buffers with `lin_arr_to_srgb()` before `foreach_set`.
     - Headless `-b` Edit Mode: set `view_layer.objects.active = ob` and `ob.select_set(True)` directly on `view_layer` before `bpy.ops.object.mode_set(mode="EDIT")`.
     - Cloud/OneDrive sync folders: render and save PNGs to `tempfile.gettempdir()` first and copy with retry (`render_still_safe`).
     - Hardware-safe Cycles GPU-only & GPU denoising: ALWAYS use `vflib.bake.enable_cycles_gpu(sc)` (`d.use = (d.type == dev_type)`, GPU `OPTIX`/`denoising_use_gpu=True`, `FIXED` <= 8 threads, `512 px` tiling, `1.0 s` cooldown) — never enable Hybrid GPU+CPU (`d.use = True`) or all-core CPU OIDN!
8. **Multi-Variant & 4-Tier `LOD0`–`LOD3` Delivery**:
   - Ship `LOD0` (`1.0`), `LOD1` (`~50%`), `LOD2` (`~25%`), and `LOD3` (`~10%`) preserving `delimit={'UV', 'SEAM', 'SHARP'}` and articulated servo parts, visually verified on a 4-panel `lod_comparison_sheet.png`.
