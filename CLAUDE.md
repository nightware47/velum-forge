# CLAUDE.md — Claude Code Instructions for Velum Forge

Follow all rules in [`AGENTS.md`](AGENTS.md) and [`docs/AI_AGENT_PLAYBOOK.md`](docs/AI_AGENT_PLAYBOOK.md).

## Quick Commands (`vforge`)

```bash
# 1. Generate a brand-new 3D asset from a prompt + reference image(s) (extracts palette, builds 3D + Ref-vs-Model QA!)
vforge generate red_snapper --kind fish --length 0.85 --ref ./snapper_side.png --prompt "Crimson Red Snapper"

# 2. Attach additional reference photos to an existing asset folder or print an AI Handoff Brief
vforge add-ref examples/mahi_mahi ./mahi_photo.jpg
vforge brief examples/mahi_mahi

# 3. Check Blender 5.2+, CAD Python venv & installed AI skills
vforge doctor

# 4. Install/sync skills into ~/.claude/skills and ~/.gemini/config/plugins/velum-forge
vforge install-ai

# 5. Run the 10-view QA gate + automatic side-by-side `renders/ref_comparison.png`
vforge qa examples/mahi_mahi/build_mahi_mahi.py --profile roblox --forward-axis +Y

# 6. Run headless Blender 5.2+ 2048x2048 Cycles GPU PBR bake + 4 variants + 4-tier LODs
vforge bake examples/mahi_mahi/bake_lod_variants.py
```
