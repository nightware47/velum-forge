---
name: velum-pbr-bake-lods
description: Cycles GPU (OPTIX/CUDA) 2048x2048 PBR texture baking, Blender 5.2+ shader/color-space guardrails, zero-staircase UV stripe packing, multi-variant generation, and seam-locked 4-tier LOD0-LOD3 chains. Activate whenever baking textures, creating variants, or generating LODs.
---

# Velum Forge — 2K Cycles PBR Baking, Variants & 4-Tier LODs

Procedural Blender nodes (`TexNoise`, `TexVoronoi`, `TexWave`, `Bump`, `Mix`) render in Cycles but **export blank** to glTF, Roblox `SurfaceAppearance`, Unity, and Unreal. Always bake procedural shaders onto a single shared non-overlapping `2048x2048` UV atlas per variant, then build `LOD1`–`LOD3` from the baked `LOD0` parts.

## Five Hard-Won Blender 5.2+ Rules (Never Violate These!)

1. **`ShaderNodeMix(data_type="RGBA")` Socket Indices:**
   - In Blender 5.2+, `ShaderNodeMix` contains multiple sockets identically named `"A"`, `"B"`, and `"Result"` (`Float`, `Vector`, `RGBA`). Looking up `"A"` or `"Result"` by name binds the **scalar `Float` socket (`outputs[0]`)**, turning colored procedural wood/scales grayscale or white!
   - **Always use `vflib.bake.mix_rgba(nt, fac, col_a, col_b)`** (binds `inputs[0]` Factor, `inputs[6]` RGBA A, `inputs[7]` RGBA B, `outputs[2]` RGBA Result).
2. **`Image.pixels.foreach_set` on 8-bit `sRGB` Images (`float_buffer=False`):**
   - `foreach_set` writes `[0..1]` directly into raw 8-bit PNG bytes without linear-to-sRGB gamma encoding.
   - Always bake Base Color & AO into `float_buffer=True` `"Non-Color"` images, composite AO in linear space (`bc_lin * (0.70 + 0.30 * ao)`), then convert via **`vflib.bake.lin_arr_to_srgb()`** before calling `save_png_8bit(..., "sRGB")`.
3. **Zero-Staircase Painted Stripes on Shared UV Atlases:**
   - `bpy.ops.uv.smart_project` splits only by face angle, merging coplanar faces across painted waterline or livery stripes so diagonal UV rasterization staircases!
   - **Fix (`vflib.bake.split_material_border_uv_islands`):** Split `bmesh` edges where `len({f.material_index for f in e.link_faces}) > 1` BEFORE `smart_project` + `pack_islands` + `seams_from_islands()`, then re-weld 3D vertices via `bmesh.ops.remove_doubles(..., dist=1e-6)` afterward! The 3D mesh stays 100% watertight while every stripe sits on its own isolated UV island with `12–14 px` `EXTEND` dilation — laser-sharp at any angle!
4. **Headless (`-b`) Edit Mode Selection:**
   - In background mode (`-b`), `temp_override` alone does not satisfy `bpy.ops.object.mode_set(mode="EDIT")`. Set `ob.select_set(True)` and `bpy.context.view_layer.objects.active = ob` directly on `view_layer` first.
5. **Cloud / OneDrive Sync File-Lock Immunity:**
   - Writing Cycles renders or PNG textures directly into a synced folder (`OneDrive`, `Dropbox`) intermittently fails with `OpenImageIO write failed`. Always render/save to `tempfile.gettempdir()` first and copy with retry (`vflib.bake.render_still_safe` & `vflib.bake.save_png_8bit`).

## Standard 6-Map `2048x2048` Output Set
| Map | Filename | Color Space | Bake Pass |
| :--- | :--- | :---: | :--- |
| **Albedo + Cavity AO** | `T_<Asset>_<var>_Color.png` | `sRGB` | `EMIT` (Base Color) × linear `AO` -> `lin_arr_to_srgb` |
| **Tangent Normal (OpenGL)** | `T_<Asset>_<var>_Normal.png` | `Non-Color` | `NORMAL` (`TANGENT`, `+X / +Y / +Z`) |
| **Roughness** | `T_<Asset>_<var>_Roughness.png` | `Non-Color` | `ROUGHNESS` |
| **Metalness** | `T_<Asset>_<var>_Metalness.png` | `Non-Color` | `EMIT` (Metallic socket override) |
| **Ambient Occlusion** | `T_<Asset>_<var>_AO.png` | `Non-Color` | `AO` (`64` samples) |
| **Channel-Packed ORM** | `T_<Asset>_<var>_ORM.png` | `Non-Color` | `R = AO`, `G = Roughness`, `B = Metalness` |

> **Blender `ShaderNodeTexVoronoi` 5.2 API Note:** Use `vor.distance = "MANHATTAN"` (not `.metric`, which was removed in 5.x).

## Seam-Locked 4-Tier LOD Rules (`LOD0` -> `LOD1` -> `LOD2` -> `LOD3`)
- Always mark UV island borders as seams (`bpy.ops.uv.seams_from_islands()`) before replacing multi-slot procedural materials with the single baked material.
- On `COLLAPSE` decimation (`LOD1 ~0.48`, `LOD2 ~0.24`, `LOD3 ~0.11`), always set `dec.delimit = {"UV", "SEAM", "SHARP"}` so thin stripes and UV seams never tear into sawtooth triangles!
- **Double-walled shells (`Hull` with outer skin + inner liner):** Chord-flattening under `COLLAPSE` pulls curved outer walls inward into inner liners. Use `dec.decimate_type = "DISSOLVE"` (`angle_limit = 1.8° / 2.6° / 3.4°`, `delimit = {"UV", "SEAM", "SHARP"}`) on double-walled hulls, and push thin exterior decal ribbons (`PaintPrimary`) outboard by `+3..+13 mm` along `±X` (`vflib.lod.build_lod_chain`).
- Render a `2x2` `lod_comparison_sheet.png` and inspect it visually before shipping!
