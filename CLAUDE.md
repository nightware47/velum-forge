# CLAUDE.md — Claude Code Instructions for Velum Forge

Follow all rules in [`AGENTS.md`](AGENTS.md) and [`docs/AI_AGENT_PLAYBOOK.md`](docs/AI_AGENT_PLAYBOOK.md).

## Quick Commands (`vforge`)

```bash
# Check Blender 5.2+, CAD Python venv & installed AI skills
vforge doctor

# Install/sync skills into ~/.claude/skills and ~/.gemini/config/plugins/velum-forge
vforge install-ai

# Scaffold a new asset (boat | fish | prop | cad)
vforge new fish yellowfin_tuna

# Run the 10-view automated visual & geometric QA gate (must exit 0 with 0 errors, 0 warnings)
vforge qa examples/mahi_mahi/build_mahi_mahi.py --profile roblox --forward-axis +Y

# Run headless Blender 5.2+ 2048x2048 Cycles GPU PBR bake + 4 variants + 4-tier LODs
vforge bake examples/mahi_mahi/bake_lod_variants.py

# Inspect any GLB/STL/OBJ mesh with trimesh
vforge inspect path/to/model.glb
```
