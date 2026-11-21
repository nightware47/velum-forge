"""Reference image staging, automatic palette & aspect-ratio extraction, and `asset_spec.json` management."""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def analyze_reference_image(img_path: str | Path) -> dict[str, Any]:
    """Extract dimensions, foreground bounding-box aspect ratio, and dominant hex color palette from a reference image."""
    p = Path(img_path)
    with Image.open(p) as im:
        rgba = im.convert("RGBA")
        w, h = rgba.size
        arr = np.asarray(rgba, dtype=np.uint8)

    # Detect foreground subject vs uniform background/alpha to estimate real subject aspect ratio!
    alpha = arr[..., 3]
    rgb = arr[..., :3].astype(np.float32)
    if np.min(alpha) < 240 and np.any(alpha > 32):
        fg_mask = alpha > 32
    else:
        # Compare against border corner color
        corners = np.vstack([rgb[0, :], rgb[-1, :], rgb[:, 0], rgb[:, -1]])
        bg_med = np.median(corners, axis=0)
        dist = np.linalg.norm(rgb - bg_med[None, None, :], axis=-1)
        fg_mask = dist > 24.0

    ys, xs = np.where(fg_mask)
    if len(xs) > 50 and len(ys) > 50:
        subj_w = int(xs.max() - xs.min() + 1)
        subj_h = int(ys.max() - ys.min() + 1)
        subj_aspect = round(subj_w / max(subj_h, 1), 3)
        fg_pixels = arr[fg_mask][:, :3]
    else:
        subj_w, subj_h = w, h
        subj_aspect = round(w / max(h, 1), 3)
        fg_pixels = arr.reshape(-1, 4)[:, :3]

    # Extract 5 dominant vivid/distinct hex colors via saturation-boosted quantized histogram
    # (prevents studio backdrop/floor grays from beating vivid subject colors!)
    small = Image.fromarray(fg_pixels.reshape(-1, 1, 3).astype(np.uint8)).quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    pal = small.getpalette() or []
    scored_clusters: list[tuple[float, str]] = []
    for cnt, idx in (small.getcolors() or []):
        base = idx * 3
        if base + 2 < len(pal):
            r_c, g_c, b_c = pal[base], pal[base + 1], pal[base + 2]
            c_max = max(r_c, g_c, b_c)
            c_min = min(r_c, g_c, b_c)
            sat = (c_max - c_min) / max(c_max, 1)
            # Strongly favor chromatic subject colors over low-saturation studio floor gradients
            weight = (0.08 if sat < 0.12 else (0.45 + sat * 2.4))
            scored_clusters.append((float(cnt) * weight, f"#{r_c:02X}{g_c:02X}{b_c:02X}"))
    scored_clusters.sort(key=lambda item: item[0], reverse=True)
    hex_colors: list[str] = []
    for _score, hx in scored_clusters:
        if hx not in hex_colors:
            hex_colors.append(hx)
        if len(hex_colors) >= 5:
            break

    if not hex_colors:
        hex_colors = ["#12687A", "#E8B914", "#EEF2EB", "#1E293B"]

    # Infer view slot from filename (`front`, `side`, `top`, `back`, or `hero`)
    stem_low = p.stem.lower()
    view = "side" if "side" in stem_low or "profile" in stem_low else (
        "front" if "front" in stem_low else (
            "top" if "top" in stem_low else "hero"
        )
    )

    return {
        "filename": p.name,
        "path": str(p.resolve()),
        "view": view,
        "width_px": w,
        "height_px": h,
        "subject_aspect_w_over_h": subj_aspect,
        "dominant_palette": hex_colors,
    }


def save_uploaded_reference(asset_dir: Path, filename: str, data_url_or_bytes: str | bytes, view: str = "auto") -> dict[str, Any]:
    """Save a base64 data-URL or raw bytes into `<asset_dir>/references/` and analyze it."""
    ref_dir = asset_dir / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", os.path.basename(filename)) or "reference.png"
    if view != "auto" and view not in safe_name.lower():
        stem, ext = os.path.splitext(safe_name)
        safe_name = f"ref_{view}_{stem}{ext or '.png'}"

    dst = ref_dir / safe_name
    if isinstance(data_url_or_bytes, str):
        raw_b64 = data_url_or_bytes.split(",", 1)[-1] if "," in data_url_or_bytes else data_url_or_bytes
        raw = base64.b64decode(raw_b64)
    else:
        raw = data_url_or_bytes

    dst.write_bytes(raw)
    # Normalize to clean PNG if WebP/BMP/etc. so Blender & Pillow always read it effortlessly
    with Image.open(dst) as im:
        if dst.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            png_dst = dst.with_suffix(".png")
            im.convert("RGBA").save(png_dst, format="PNG")
            dst.unlink(missing_ok=True)
            dst = png_dst

    info = analyze_reference_image(dst)
    if view != "auto":
        info["view"] = view
    return info


def stage_local_reference_files(asset_dir: Path, file_paths: list[str]) -> list[dict[str, Any]]:
    """Copy local reference image files into `<asset_dir>/references/` and analyze them."""
    ref_dir = asset_dir / "references"
    ref_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for fp in file_paths:
        src = Path(fp)
        if not src.is_file():
            continue
        dst = ref_dir / src.name
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        results.append(analyze_reference_image(dst))
    return results


def write_asset_spec(
    asset_dir: Path,
    *,
    slug: str,
    title: str,
    kind: str,
    prompt: str,
    length_m: float = 1.20,
    profile: str = "roblox",
    variants_count: int = 4,
    references: list[dict[str, Any]] | None = None,
) -> Path:
    """Write `<asset_dir>/asset_spec.json` — the single source of truth read by Velum Forge & AI agents."""
    refs = references or []
    merged_palette: list[str] = []
    for r in refs:
        for hx in r.get("dominant_palette", []):
            if hx not in merged_palette:
                merged_palette.append(hx)

    spec = {
        "schema": "velum-forge/asset-spec/v1",
        "slug": slug,
        "title": title,
        "kind": kind,
        "prompt": prompt,
        "target_length_m": float(length_m),
        "qa_profile": profile,
        "variants_count": int(variants_count),
        "extracted_palette": merged_palette[:6] or ["#0E7490", "#EAB308", "#F1F5F9", "#1E293B"],
        "references": refs,
        "workflow_commands": {
            "qa": f'vforge qa "{asset_dir / f"build_{slug}.py"}" --profile {profile} --forward-axis +Y',
            "bake": f'vforge bake "{asset_dir / "bake_lod_variants.py"}"',
        },
    }
    spec_path = asset_dir / "asset_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec_path
