---
name: velum-cad-brep
description: Precision OpenCascade B-Rep mechanical CAD modeling with build123d and cad_bridge.py. Use whenever building machined, cast, or ergonomic hard-surface components (wheels, cleats, throttles, propellers, brackets, enclosures, fasteners) exported as STEP + watertight 1:1 meter GLB for Blender assembly.
---

# Velum Forge — Precision B-Rep CAD (`build123d` -> Blender Bridge)

Polygon box-modeling struggles on exact circular bosses, countersunk bolt circles, tangent fillets, NACA hydrofoil blades, and ergonomic bezels. Use **`build123d`** (OpenCascade B-Rep kernel) via `engine/cad/cad_bridge.py` to generate exact watertight mechanical sub-parts and import them into Blender at `1:1` meter scale.

## Rules of Engagement
1. **Units = Meters (`1.0 = 1 m`), `+Z = Up`:**
   - A `380 mm` steering wheel has `radius = 0.190`. A `6 mm` bolt hole has `radius = 0.003`.
   - Always trim or align the resting base to `Z = 0.0` when building standalone props.
2. **Export via `cad_bridge.export_cad_part` or `export_cad_assembly`:**
   - Never use raw uncleaned STL exports. `cad_bridge.py` runs `BRepTools.Clean_s`, tessellates with controlled linear (`0.001 m`) & angular (`0.35 rad`) deflection, deletes degenerate slivers, enforces outward positive signed volume, applies `R_ZUP_TO_GLTF` **exactly once** so Blender's glTF importer lands it at `1:1 m` `Z-up` with zero axis flip, and returns a full `trimesh` watertightness + Roblox `< 20k` triangle inspection JSON!
3. **Safe Filleting Order:**
   - Apply primary structural booleans (`+` / `Mode.SUBTRACT`) first, filter target edges explicitly (`part.edges().filter_by(...)`), and keep fillet radii strictly smaller than half the adjacent face width so OpenCascade never fails with `StdFail_NotDone`.

## Minimal Template (`build123d` -> `.step` + `.glb`)

```python
import os, sys
sys.path.insert(0, r"<velum-forge>/engine/cad")

from build123d import Align, BuildPart, BuildSketch, Cylinder, Locations, Mode, Plane, RectangleRounded, extrude, fillet
from cad_bridge import export_cad_part

def build_flange() -> object:
    with BuildPart() as p:
        with BuildSketch(Plane.XY):
            RectangleRounded(0.140, 0.080, radius=0.014)
        extrude(amount=0.012)
        fillet(p.edges().filter_by(lambda e: abs(e.center().Z - 0.012) < 1e-4), radius=0.0025)
        with Locations([(-0.050, 0.0, 0.012), (0.050, 0.0, 0.012)]):
            Cylinder(radius=0.004, height=0.020, align=(Align.CENTER, Align.CENTER, Align.MAX), mode=Mode.SUBTRACT)
    return p.part

res = export_cad_part(build_flange(), out_dir="./cad", name="mounting_flange", metallic=0.9, roughness=0.22)
assert res["inspection"]["pass"], res["inspection"]["errors"]
```

## CLI Mesh Utilities (`cad_bridge.py`)
```powershell
# Inspect any GLB/STL/OBJ for watertightness, Euler number, m/studs size & 20k tri budget:
vforge inspect path\to\part.glb

# Convert external CAD STEP assembly directly to 1:1m watertight GLB:
.\.venv\Scripts\python.exe engine\cad\cad_bridge.py step-to-glb input.step output.glb

# Quadric-edge-collapse decimate or repair a dense mesh via PyMeshLab:
.\.venv\Scripts\python.exe engine\cad\cad_bridge.py decimate high.glb low.glb --target-tris 8000
.\.venv\Scripts\python.exe engine\cad\cad_bridge.py repair broken.glb clean.glb
```
