# Velum Forge 3D Asset Engineering Rules

Whenever creating, refining, baking, optimizing, or exporting 3D models (`.blend`, `.glb`, `.fbx`, `.step`, `build123d`, or `bpy` scripts), follow the **Velum Forge 6-Gate Standard**:

1. **Activate the Relevant Velum Forge Skill First**:
   - Read `velum-3d-workflow` for any end-to-end 3D asset request.
   - Read `velum-cad-brep` for mechanical/hard-surface hardware (`build123d` B-Rep CAD).
   - Read `velum-organic-species` for creatures, fish, animals, or organic characters.
   - Read `velum-pbr-bake-lods` whenever baking procedural shaders to PBR textures, generating variants, or building LODs.
2. **Real-World Scale & Exact Grounding**:
   - Model strictly in **meters** (`1 unit = 1.0 m`, `+Z = Up`, lowest vertex grounded at `Z = 0.0000 m`, object transforms applied to `scale = (1, 1, 1)`, `rotation = (0, 0, 0)`).
3. **Zero Shell Clipping & Watertight Topology**:
   - Never extrude interior bulkheads, lockers, fins, or mounts blindly through curved outer shells. Clamp interior geometry to the inner hull/body envelope and run a **BVH shell-integrity check** (`0` breaches, `0` floating parts).
   - Enforce outward normals on closed concave/forked manifolds using **exact 3D signed volume** ($\sum \frac{1}{6} v_0 \cdot (v_1 \times v_2) > 0$), and keep thin hydrofoil/panel wall thickness `>= 1.6 mm` so opposite faces never trigger `< 1.0 mm` back-to-back warnings.
4. **Mandatory 10-View Visual & Geometric QA Gate (`PASS` with `0` Errors, `0` Warnings)**:
   - Run `vforge qa <asset>` (or `engine/cad/run_qa.ps1`) and **visually inspect** both `contact_sheet_material.png` (6 views) and `contact_sheet_diagnostic.png` (wireframe, part IDs, blue/red face orientation, underbody) before declaring geometry complete.
5. **True Cycles GPU (`OPTIX`/`CUDA`) PBR Texture Baking (Never Ship Raw Procedural Nodes to Engines)**:
   - Game engines (Roblox, glTF, Unity, Unreal) ignore procedural Blender nodes (`Noise`, `Voronoi`, `Wave`, `Bump`, `Mix`). Always bake onto a non-overlapping `2048x2048` UV atlas (`Color` in `sRGB` + `Normal` OpenGL `Y+`, `Roughness`, `Metalness`, `AO`, `ORM` in `Non-Color`).
   - **Blender 5.2+ Critical Guardrails**:
     - `ShaderNodeMix(data_type="RGBA")`: bind explicit socket indices `inputs[0]` (Factor), `inputs[6]` (A), `inputs[7]` (B), and `outputs[2]` (Result) — never look up `"A"`, `"B"`, or `"Result"` by name (matches `Float` socket `0`!).
     - `Image.pixels.foreach_set` on 8-bit `sRGB` PNGs (`float_buffer=False`): convert scene-linear float buffers with `lin_arr_to_srgb()` before `foreach_set`.
     - Headless `-b` Edit Mode: set `view_layer.objects.active = ob` and `ob.select_set(True)` directly on `view_layer` before `bpy.ops.object.mode_set(mode="EDIT")`.
     - Cloud/OneDrive sync folders: render and save PNGs to `tempfile.gettempdir()` first and copy with retry (`render_still_safe`).
6. **Multi-Variant & 4-Tier `LOD0`–`LOD3` Delivery**:
   - Ship `LOD0` (`1.0`), `LOD1` (`~50%`), `LOD2` (`~25%`), and `LOD3` (`~10%`) preserving `delimit={'UV', 'SEAM', 'SHARP'}` and articulated servo parts, visually verified on a 4-panel `lod_comparison_sheet.png`.
