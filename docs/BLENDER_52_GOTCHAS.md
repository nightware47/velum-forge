# Blender 5.2+ Headless & Cycles Baking Gotchas

Every item in this field guide was discovered and verified in production on Blender 5.2 LTS. Keep this checklist in mind whenever writing headless `bpy` automation.

---

## 1. `ShaderNodeMix(data_type="RGBA")` Socket Name Collision
In Blender 5.x, `ShaderNodeMix` exposes multiple input/output sockets with **identical `.name` strings** (`"A"`, `"B"`, `"Result"`) for `Float`, `Vector`, and `RGBA`:
- `mx.outputs["Result"]` or searching `.name == "Result"` returns **`outputs[0]` (`Float`)**, silently stripping RGB color channels!
- **Correct indices for `data_type = "RGBA"`:**
  - `mx.inputs[0]` -> Factor (`Float`)
  - `mx.inputs[6]` -> Color A (`RGBA`)
  - `mx.inputs[7]` -> Color B (`RGBA`)
  - `mx.outputs[2]` -> Color Result (`RGBA`)
- Helper: `vflib.bake.mix_rgba(nt, fac, col_a, col_b)`.

---

## 2. `Image.pixels.foreach_set` Writes Raw Bytes on `float_buffer=False`
When saving a baked float array (`bc_lin * ao_fac`, which is in **scene-linear** color space) into an 8-bit `bpy.data.images.new(..., float_buffer=False)` image tagged `colorspace_settings.name = "sRGB"`:
- `img.pixels.foreach_set(...)` does **not** apply linear-to-sRGB gamma conversion — it quantizes `[0..1]` linearly into `[0..255]`, making midtones ~2.2x too dark!
- **Fix:** Apply exact IEC 61966-2-1 sRGB transfer (`vflib.bake.lin_arr_to_srgb(arr)`) before `foreach_set`.
- Conversely, for data maps (`Normal`, `Roughness`, `Metalness`, `AO`, `ORM`), tag `colorspace_settings.name = "Non-Color"` and write linear `[0..1]` values directly without gamma encoding.

---

## 3. `ShaderNodeTexVoronoi`: `.distance` Replaced `.metric`
In Blender 5.x, `vor.metric = "MANHATTAN"` raises `AttributeError`. Use:
```python
vor = nt.nodes.new("ShaderNodeTexVoronoi")
vor.feature = "DISTANCE_TO_EDGE"  # or "F1", "SMOOTH_F1"
vor.distance = "MANHATTAN"        # "EUCLIDEAN", "MANHATTAN", "CHEBYCHEV", "MINKOWSKI"
```

---

## 4. Headless (`-b`) `bpy.ops.object.mode_set(mode="EDIT")` Poll Failure
Wrapping `bpy.ops.object.mode_set(mode="EDIT")` + `bpy.ops.mesh.select_all(action="SELECT")` solely inside `with bpy.context.temp_override(...)` in background mode (`blender -b`, where no `VIEW_3D` area exists) can fail with `Operator bpy.ops.mesh.select_all.poll() failed`.
- **Fix:** Set selection and active object directly on `bpy.context.view_layer` before calling `mode_set`:
```python
core.ensure_object_mode()
for o in bpy.context.view_layer.objects:
    o.select_set(False)
ob.select_set(True)
bpy.context.view_layer.objects.active = ob
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
# ... UV / mesh ops ...
bpy.ops.object.mode_set(mode="OBJECT")
ob.select_set(False)
```

---

## 5. Cloud-Synced Folders (`OneDrive` / `Dropbox`) Locking `OpenImageIO` Writes
When Cycles writes several high-res PNGs rapidly into a OneDrive-synced folder, OneDrive's background indexer briefly locks newly created files, causing Blender's `OpenImageIO` saver to throw `Could not open file`.
- **Fix:** Always render/save into `tempfile.gettempdir()` first and `shutil.copy2` to the destination inside a 6-attempt `PermissionError` retry loop (`vflib.bake.render_still_safe` & `vflib.bake.save_png_8bit`).

---

## 6. Freed StructRNA References When Clearing Studio Collections
`vflib.core.clear_collection(studio_col)` automatically removes zero-user datablocks (`Light`, `Camera`, `Mesh`). Calling `bpy.data.lights.remove(light_data)` afterward raises `ReferenceError: StructRNA of type AreaLight has been removed`. Let `clear_collection` clean up datablocks on its own.

---

## 7. Hybrid GPU + All-Core CPU Power Spikes (`d.use = True`) & CPU OIDN Denoising Spikes
On high-core-count workstations (e.g. 16-core/32-thread Ryzen 9 + RTX GPU), two silent Cycles defaults cause simultaneous GPU + all-core CPU transient spikes during `vforge bake`:
1. **Never loop `for d in prefs.devices: d.use = True`:** That activates **both** the GPU (`OPTIX`/`CUDA`) and all CPU cores simultaneously! Always filter strictly to GPU-only:
   ```python
   for d in prefs.devices:
       d.use = (d.type == dev_type)
   ```
2. **Never leave default CPU `OPENIMAGEDENOISE` with `AUTO` threads:** Blender 5.2/5.3 defaults `sc.cycles.denoiser = "OPENIMAGEDENOISE"` with `denoising_use_gpu = False` and `threads_mode = "AUTO"`, firing an all-core AVX2 CPU spike right on top of a hot GPU pass!
- **Fix (Built Automatically into `vflib.bake.enable_cycles_gpu` & `vforge bake`):**
  - Strictly GPU-only device selection (`d.use = (d.type == dev_type)`).
  - GPU denoising (`sc.cycles.denoiser = "OPTIX"` on OptiX GPUs, or `denoising_use_gpu = True` on CUDA/HIP/ONEAPI/Metal).
  - Fixed CPU thread cap (`sc.render.threads_mode = "FIXED"`, `-t 8` / `VELUM_BLENDER_THREADS=8`, `OMP_NUM_THREADS=8`).
  - Safe tile size (`sc.cycles.use_auto_tile = True`, `tile_size = 512`) + `1.0 s` thermal cooldown (`VELUM_BAKE_COOLDOWN=1.0`) between heavy Cycles passes.
  - Cross-process sequential GPU lock (`~/.velum-forge/gpu_bake.lock`) so concurrent bakes never overlap, plus `--factory-startup` by default in headless batch jobs (opt in with `--user-addons`).
