---
name: velum-organic-species
description: Closed S^2 manifold organic, wildlife, fish, and creature modeling in Blender 5.2+ with exact biological proportions, sculpted anatomical sockets/opercula, signed-volume outward normals, polar jewel-eye UVs, sexual/rarity dimorphism variants, and analytical swim/spine rigging.
---

# Velum Forge — Organic, Creature & Marine Species Engineering

When modeling organic species (fish, marine life, animals, stylized/realistic creatures), avoid boolean soup or open-boundary card fins that fail Roblox/print watertightness checks. Build **mathematically closed `S^2` manifolds** with analytical surface sculpting and procedural-to-baked micro-anatomy.

## 1. Closed `S^2` Tube-With-Caps Topology (`0` Boundary Edges, `0` Non-Manifold Edges)
- Represent the body fuselage and every fin (dorsal sail, deeply forked caudal tail, falcate pectorals, pelvics, anal fin) as ordered circumferential rings `rings[0..N-1]` (`n_circ` points around `phi in [0, 2*pi)`) closed with single apex triangle fans `cap_start` and `cap_end` (`V - E + F = 2`).
- **Minimum Hydrofoil Thickness Rule (`>= 1.6 mm`):**
  - `qa_check.py` flags opposite-facing faces closer than `1.0 mm` (`--eps 0.001`) as `hidden back-to-back faces`.
  - Keep fin half-thickness `t_half >= 0.00080` (`1.6 mm` total thickness) even at extreme trailing edges and fin tips!
- **Signed-Volume Outward Normal Guarantee:**
  - On thin concave shapes (like a V-forked scissor tail), `bmesh.ops.recalc_face_normals` can pick inward orientation. Always call `vflib.integrity.ensure_positive_signed_volume(bm)` after triangulation to guarantee **100% outward blue normals**.

## 2. Sculpted Anatomical Features Directly on the Continuous Body Grid
Instead of gluing floating primitives onto a smooth ellipsoid (which looks toy-like):
- **Blade Cross-Section, Not a Sausage:** Pelagic fish have an epaxial-heavy ovoid-lenticular cross-section (widest ~62% up from the belly, pinching into a crisp ventral keel, `height:width ~ 2.2–2.6:1`).
- **Sculpted Concave Orbital Eye Sockets:** Indent a smooth concave socket (`~4.5 mm` deep) surrounded by a `+1.3 mm` bony supraorbital rim, then seat a flattened eyeball (`Eyes`) `3–4 mm` into the socket (`0` floating gap, `> 25 mm` away from the medial `X = 0` plane).
- **Curved Gill Operculum & Recessed Gill Cleft:** Sculpt a C-curved `+2.5 mm` opercular plate step dropping sharply into a `-2.3 mm` recessed branchial groove — zero open holes, crisp raytraced AO & specular catchlight!
- **Corrugated Scalloped Fins:** Modulate fin half-thickness by `cos(pi * n_rays * s)^2` along the span to create real 3D bony actinotrichia fin rays, and scallop the trailing chord by `abs(sin(pi * n_rays * s))`.

## 3. Polar `EyePolarUV` Layer for Razor-Sharp Jewel Irises
- Build eyeballs along the `±X` optical axis (`alpha = 0` at outer cornea apex -> `alpha = pi` at inner pole) and map `r_uv = 0.20 * (alpha / pi)` centered at `(0.25, 0.50)` (Port) and `(0.75, 0.50)` (Starboard) onto a dedicated `EyePolarUV` layer before packing active `UVMap` onto the shared `2048x2048` atlas (with a `2.8x` island scale boost for `Eyes`).
- Note that the visible orbital aperture outside the skull spans `alpha in [0, ~0.62 rad]`, which corresponds to **`r_uv in [0.0, 0.040]`**! Place the pupil transition at `r_uv ~ 0.016..0.019` and outer iris limbal ring at `r_uv ~ 0.036..0.041` so the metallic iris gleams clearly inside the open socket. Delete `EyePolarUV` right after baking so game export sees a single clean `UVMap`.

## 4. Analytical Normalized Axial Spine Rig (`<= 3` Weights/Vert, `0` Heat-Fail Risk)
- Blender's automatic Bone Heat weighting frequently fails on multi-part meshes (`Body` + `Fins` + `Eyes`).
- For swimming fish/creatures, create an axial spine (`Root -> Head`, `Root -> Spine1 -> Spine2 -> Spine3 -> Peduncle -> TailFin`) and assign Gaussian axial weights $w_i(y) = \exp(-\frac{1}{2}((y - y_i)/\sigma)^2)$ normalized across the top 3 bones per vertex! Export a seamless 48-frame sinusoidal subcarangiform swim loop (`phase - lag_i`) to `rigged/<species>_swim_rigged.glb`.

## Reference Implementation
- See `examples/mahi_mahi/build_mahi_mahi.py` and `examples/mahi_mahi/bake_lod_variants.py`.
