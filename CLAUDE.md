# CLAUDE.md — Claude Code Instructions for Velum Forge (v1.2)

Follow all rules in [`AGENTS.md`](AGENTS.md) and [`docs/AI_AGENT_PLAYBOOK.md`](docs/AI_AGENT_PLAYBOOK.md).

## Quick Commands (`vforge`)

```bash
# 1. Generate a 3D asset from perspective photos or blueprints (opt-in --iterate or --rate-to-10 enables Honest Rating Reviews!)
vforge generate ocean_dr_800 --kind building --length 18.0 --ref ./gsv_front.jpg --ref ./gsv_corner.jpg --iterate --target-score 9.0

# 2. Attach perspective photos (or ortho blueprints) to an existing asset & print AI Handoff / Next-Iter Fix Brief
vforge add-ref examples/mahi_mahi ./mahi_photo.jpg --view hero --lens 50
vforge brief examples/mahi_mahi --rate-to-10
vforge brief examples/mahi_mahi --next-iteration

# 3. Optional Iterative Critic & Honest Rating Loop (`vforge review`)
vforge review config examples/mahi_mahi --enable --target 9.0 --max-iter 3
vforge review config examples/mahi_mahi --rate-to-10
vforge review snapshot examples/mahi_mahi
vforge review log examples/mahi_mahi --score 7.8 --summary "Strong progress, not 10/10 yet." --strength "Crisp silhouette" --defect "Detail|major|Missing trim|Add beveled molding"
vforge review status examples/mahi_mahi
vforge review prompt examples/mahi_mahi

# 4. Run 10-view QA + matched perspective multi-ref comparison (use --profile game for buildings, --ortho-grid ONLY for ortho blueprints!)
vforge qa examples/news_cafe_south_beach/build_news_cafe_south_beach.py --profile game --forward-axis +Y --max-tris 300000
vforge qa examples/mahi_mahi/build_mahi_mahi.py --profile roblox --forward-axis +Y --snapshot-iteration

# 5. Check Blender 5.2+/5.3, sync 5/5 AI skills, and bake dedicated 2K PBR sets + variants + LODs (hardware-safe defaults automatic!)
vforge doctor
vforge install-ai
vforge bake examples/mahi_mahi/bake_lod_variants.py [--threads 8] [--device auto|gpu|optix|cuda|cpu] [--cooldown 1.0] [--tile-size 512] [--no-lock] [--user-addons]
```
