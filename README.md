<div align="center">
  <img src="plugins/velum-forge/assets/logo.svg" width="108" height="108" alt="Velum Forge Logo" />
  <h1>Velum Forge</h1>
  <p><strong>AI-Driven Precision B-Rep CAD, Blender 5.2+ Cycles GPU PBR Baking, 4-Tier LOD &amp; Game Asset Studio</strong></p>
  <p>
    <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-22c55e.svg" alt="MIT License" /></a>
    <img src="https://img.shields.io/badge/Blender-5.2%2B%20LTS-0ea5e9.svg" alt="Blender 5.2+" />
    <img src="https://img.shields.io/badge/CAD-build123d%20%2F%20OpenCascade-6366f1.svg" alt="build123d" />
    <img src="https://img.shields.io/badge/AI%20Agents-Antigravity%20%7C%20Claude%20%7C%20Codex%20%7C%20Cursor-fbbf24.svg" alt="AI Ready" />
  </p>
</div>

---

**Velum Forge** turns AI coding agents (**Google Antigravity**, **Claude Code CLI**, **Codex**, **Cursor**) into deterministic, studio-grade 3D asset engineers. Instead of fragile primitive kitbashing or un-exportable procedural shaders, Velum Forge enforces a **6-Gate Production Pipeline** combining OpenCascade B-Rep CAD (`build123d`), closed `S^2` `bmesh` surfacing, hard `BVHTree` shell-clipping gates, 10-view automated visual QA, `2048x2048` Cycles `OPTIX` GPU PBR texture baking, multi-variant generation, and seam-locked `LOD0`–`LOD3` chains.

## Showcase — Built 100% Programmatically with Velum Forge

### 1. Hard-Surface & Naval Architecture (`examples/sunrunner_24`)
*24-ft Offshore Center-Console Sportfisher — `build123d` CAD helm/cleats/prop + parametric Carolina-flare hull + `0` BVH shell breaches + `2048x2048` Cycles-baked Burmese teak, diamond non-skid & sonar UI + 4 showroom/patrol variants + `LOD0`–`LOD3` (`97.2k -> 13.0k` tris).*

| 4 Baked Showroom & Roleplay Variants | Macro Close-Up (`2048x2048` Baked Teak & Non-Skid) |
| :---: | :---: |
| ![Sunrunner 24 Variants](docs/images/sunrunner24_variants.png) | ![Sunrunner 24 Baked Closeup](docs/images/sunrunner24_baked_closeup.png) |

### 2. Organic Wildlife & Pelagic Anatomy (`examples/mahi_mahi`)
*Offshore Trophy Mahi-Mahi (`Coryphaena hippurus`, `1.20 m` LOA) — Closed `S^2` watertight manifolds + Bull/Cow cranial sexual dimorphism + `2048x2048` baked imbricated diamond scales, wet mucus roughness & gill operculum + 4 rarity tiers + 7-bone swim rig + `LOD0`–`LOD3` (`40.1k -> 4.5k` tris).*

| 4 Bull/Cow Rarity Variants | Macro Scales & Gill Operculum (`2048x2048` Bake) |
| :---: | :---: |
| ![Mahi-Mahi Variants](docs/images/mahimahi_variants.png) | ![Mahi-Mahi Baked Closeup](docs/images/mahimahi_baked_closeup.png) |

---

## Quick Start & 1-Click Installer

### Windows (Zero-Prerequisite PowerShell 1-Liner or Native Setup Wizard)
> **No Python, `uv`, or Git on `PATH`? No problem.** `install.ps1` and `Setup-VelumForge.cmd` automatically bootstrap standalone `uv` + portable CPython 3.12 (rejecting broken Windows Store stubs) and deep-scan all drives (`C:`–`Z:`), **Steam libraries (`libraryfolders.vdf`)**, **Blender Launcher**, **Windows Registry (`.blend` file associations, `Uninstall` keys, `MuiCache`)**, **Scoop/Chocolatey**, and **Microsoft Store** to find `blender.exe` automatically.

```powershell
# Clone (or HTTPS zip fallback) + auto-bootstrap Python 3.12 .venv + detect Blender + install AI skills:
irm https://raw.githubusercontent.com/velumix/velum-forge/main/install.ps1 | iex
```
Or after cloning/downloading locally:
- Double-click **`Setup-VelumForge.cmd`** to open the zero-dependency native Windows `.NET` Setup Wizard (includes a **Browse...** picker if Blender lives on an external drive).
- Double-click **`Launch-VelumForge-Studio.cmd`** (or run `vforge studio`) to launch the **Velum Forge Studio** desktop app.
- Need to point to a custom portable Blender manually? Click **`Locate blender.exe...`** in Studio's Environment Doctor tab or run:
  ```powershell
  vforge set-blender "D:\CustomTools\Blender 5.2\blender.exe"
  ```

### macOS / Linux
```bash
git clone https://github.com/velumix/velum-forge.git
cd velum-forge && chmod +x install.sh && ./install.sh
vforge studio
```

---

## Generating Your First 3D Model (With Reference Photos!)

### In the Desktop Studio App (`vforge studio`)
1. Open **Velum Forge Studio** (`Launch-VelumForge-Studio.cmd` or `vforge studio`) — it opens directly to **`+ Generate 3D Asset`**.
2. **Step 1:** Enter a name (e.g. `Red Snapper`), pick an archetype (`Fish / Creature`, `Boat / Vehicle`, `Mechanical CAD`, or `Prop`), set real-world length in meters, and describe your model.
3. **Step 2:** **Drag & drop** reference photos/blueprints (or press **`Ctrl+V`** to paste straight from your clipboard!). Velum Forge automatically extracts the subject's aspect ratio & dominant hex color palette and places `1:1 m` orthographic reference planes inside Blender (`VF_References_ref`).
4. **Step 3 — Pick how to build:**
   - **Generate 3D Asset Now (Instant + Ref QA):** Immediately builds a reference-calibrated multi-part `.blend` + `.glb`, renders the 10-view QA sheets + **Side-by-Side Reference vs. Model (`ref_comparison.png`)**, and generates 4 variants + `LOD0`–`LOD3`!
   - **Generate Bespoke via Local AI CLI (`Claude` / `Codex` / `Gemini`):** Drives your installed multimodal AI CLI directly against `references/*` and `asset_spec.json`.
   - **Stage & Copy Prompt for Antigravity / Cursor:** Stages `references/` + `asset_spec.json` and copies a ready-to-paste prompt to your clipboard so your IDE AI agent builds custom geometry with zero guesswork!

### From the Command Line (`vforge`)
```powershell
# Generate a new 3D asset from reference photo(s) + prompt (auto-renders Ref-vs-Model QA + 4 variants + LOD0-LOD3!):
vforge generate red_snapper --kind fish --length 0.85 --ref C:\photos\snapper_side.png --prompt "Northern Red Snapper"

# Attach reference photos to any existing asset & re-run QA with side-by-side Ref-vs-Model comparison:
vforge add-ref examples\mahi_mahi C:\photos\dorado_ref.jpg
vforge qa examples\mahi_mahi\build_mahi_mahi.py --forward-axis +Y

# Print a complete AI Handoff Prompt for Antigravity, Cursor, or Claude Code:
vforge brief examples\mahi_mahi

# Other core commands:
vforge doctor                                                     # Verify Blender 5.2+, CAD venv & AI skills
vforge install-ai --workspace C:\path\to\your\game                # Sync Antigravity, Claude & Cursor skills/rules
vforge bake examples\mahi_mahi\bake_lod_variants.py               # Bake 2K Cycles PBR + variants + LOD0-LOD3
vforge studio                                                     # Launch Velum Forge Studio desktop app
```

---

## AI Agent Skills & Documentation (Antigravity, Claude Code, Codex, Cursor)

Running `install.ps1` or `vforge install-ai` automatically installs:
1. **Google Antigravity Plugin** (`~/.gemini/config/plugins/velum-forge`) with always-on `rules/AGENTS.md` and 4 progressive-disclosure skills:
   - [`velum-3d-workflow`](plugins/velum-forge/skills/velum-3d-workflow/SKILL.md) — Master 6-Gate 3D production runbook.
   - [`velum-cad-brep`](plugins/velum-forge/skills/velum-cad-brep/SKILL.md) — Precision `build123d` OpenCascade mechanical hardware (`STEP` + `1:1 m` `GLB`).
   - [`velum-pbr-bake-lods`](plugins/velum-forge/skills/velum-pbr-bake-lods/SKILL.md) — Cycles `OPTIX` `2048x2048` PBR baking, zero-staircase UV stripe splitting & seam-locked `LOD0`–`LOD3`.
   - [`velum-organic-species`](plugins/velum-forge/skills/velum-organic-species/SKILL.md) — Closed `S^2` organic/creature manifolds, signed-volume outward normals, polar jewel eyes & analytical swim rigs.
2. **Claude Code CLI Skills** (`~/.claude/skills/velum-*`) + root [`CLAUDE.md`](CLAUDE.md).
3. **Universal Agent Docs** — [`AGENTS.md`](AGENTS.md), [`docs/AI_AGENT_PLAYBOOK.md`](docs/AI_AGENT_PLAYBOOK.md), [`docs/BLENDER_52_GOTCHAS.md`](docs/BLENDER_52_GOTCHAS.md), and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## License
MIT &copy; [Velumix](https://github.com/velumix)
