"""Compose labeled material, diagnostic, and optional reference contact sheets from QA renders."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


BG_DARK = (20, 24, 32)
PANEL_HEADER = (27, 33, 45)
BORDER = (48, 58, 76)
TEXT_PRIMARY = (238, 242, 247)
TEXT_MUTED = (165, 177, 194)
GREEN = (34, 197, 94)
RED = (239, 68, 68)
AMBER = (245, 158, 11)
DARK_INK = (11, 18, 32)


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        ["arialbd.ttf", "consolab.ttf", "segoeuib.ttf"]
        if bold
        else ["arial.ttf", "consola.ttf", "segoeui.ttf"]
    )
    fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    for name in candidates:
        p = fonts_dir / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _truncate(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int) -> str:
    if _text_size(draw, text, font)[0] <= max_w:
        return text
    suffix = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_size(draw, text[:mid] + suffix, font)[0] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + suffix


def _open_tile(path: str | None, fallback_size: tuple[int, int], placeholder_label: str) -> Image.Image:
    if path and os.path.exists(path):
        with Image.open(path) as im:
            return im.convert("RGB")
    im = Image.new("RGB", fallback_size, (34, 40, 52))
    d = ImageDraw.Draw(im)
    f = _load_font(18, bold=True)
    msg = f"Missing tile: {placeholder_label}"
    tw, th = _text_size(d, msg, f)
    d.text(((fallback_size[0] - tw) // 2, (fallback_size[1] - th) // 2), msg, fill=AMBER, font=f)
    return im


def _resize_cover_pad(im: Image.Image, target_w: int, target_h: int, bg=(30, 35, 45)) -> Image.Image:
    if im.size == (target_w, target_h):
        return im
    src_w, src_h = im.size
    scale = min(target_w / max(src_w, 1), target_h / max(src_h, 1))
    nw = max(1, int(round(src_w * scale)))
    nh = max(1, int(round(src_h * scale)))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg)
    canvas.paste(resized, ((target_w - nw) // 2, (target_h - nh) // 2))
    return canvas


def _draw_header(
    canvas: Image.Image,
    qa: dict[str, Any],
    subtitle: str,
    header_h: int = 76,
) -> None:
    draw = ImageDraw.Draw(canvas)
    w = canvas.width
    draw.rectangle([0, 0, w, header_h], fill=BG_DARK)
    draw.line([(0, header_h - 1), (w, header_h - 1)], fill=BORDER, width=2)

    passed = bool(qa.get("pass", False))
    pill_text = "PASS" if passed else "FAIL"
    pill_bg = GREEN if passed else RED
    pill_fg = DARK_INK if passed else (255, 255, 255)

    font_pill = _load_font(20, bold=True)
    font_title = _load_font(22, bold=True)
    font_meta = _load_font(15, bold=False)

    pad_x = 18
    pill_w, pill_h = 84, 38
    pill_y = (header_h - pill_h) // 2
    draw.rounded_rectangle([pad_x, pill_y, pad_x + pill_w, pill_y + pill_h], radius=8, fill=pill_bg)
    ptw, pth = _text_size(draw, pill_text, font_pill)
    draw.text(
        (pad_x + (pill_w - ptw) // 2, pill_y + (pill_h - pth) // 2 - 2),
        pill_text,
        fill=pill_fg,
        font=font_pill,
    )

    asset_name = str(qa.get("asset_name") or "Asset")
    profile = str(qa.get("profile") or "roblox")
    renderer = str(qa.get("renderer") or "")
    title_x = pad_x + pill_w + 16
    title_str = f"{asset_name}  |  {subtitle}"
    if renderer:
        title_str += f"  ({renderer}, profile={profile})"
    else:
        title_str += f"  (profile={profile})"
    draw.text(
        (title_x, 12),
        _truncate(draw, title_str, font_title, w - title_x - 16),
        fill=TEXT_PRIMARY,
        font=font_title,
    )

    total_tris = qa.get("total_tris", 0)
    obj_count = qa.get("object_count", len(qa.get("objects", {})))
    size_m = qa.get("size_m") or [0, 0, 0]
    size_studs = qa.get("size_studs_sclib") or [round(v * 3.0, 2) for v in size_m]
    err_n = len(qa.get("errors", []))
    warn_n = len(qa.get("warnings", []))
    ground_z = qa.get("ground_z")

    meta_parts = [
        f"Tris: {total_tris:,}",
        f"Parts/Meshes: {obj_count}",
        f"Size(m): {size_m[0]:.3g} x {size_m[1]:.3g} x {size_m[2]:.3g}",
        f"Studs(3/m): {size_studs[0]:.2g} x {size_studs[1]:.2g} x {size_studs[2]:.2g}",
        f"Ground Z: {ground_z if ground_z is not None else 'n/a'}",
        f"Errors: {err_n}  Warnings: {warn_n}",
    ]
    meta_str = "   |   ".join(meta_parts)
    draw.text(
        (title_x, 44),
        _truncate(draw, meta_str, font_meta, w - title_x - 16),
        fill=TEXT_MUTED,
        font=font_meta,
    )


def _compose_grid(
    tile_specs: list[tuple[str, str | None]],
    cols: int,
    rows: int,
    qa: dict[str, Any],
    subtitle: str,
    out_path: str,
    footer_lines: list[tuple[str, tuple[int, int, int]]] | None = None,
) -> str:
    # Determine natural tile size from first existing image
    base_size = (640, 480)
    for _, path in tile_specs:
        if path and os.path.exists(path):
            with Image.open(path) as im:
                base_size = im.size
            break

    tile_w, tile_h = base_size
    header_h = 76
    label_h = 34
    gap = 12
    pad = 14
    footer_h = (20 + len(footer_lines) * 24) if footer_lines else 0

    cell_w = tile_w
    cell_h = label_h + tile_h
    canvas_w = pad * 2 + cols * cell_w + (cols - 1) * gap
    canvas_h = header_h + pad * 2 + rows * cell_h + (rows - 1) * gap + footer_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG_DARK)
    _draw_header(canvas, qa, subtitle, header_h=header_h)
    draw = ImageDraw.Draw(canvas)
    font_label = _load_font(15, bold=True)

    for idx, (label, path) in enumerate(tile_specs):
        r = idx // cols
        c = idx % cols
        x0 = pad + c * (cell_w + gap)
        y0 = header_h + pad + r * (cell_h + gap)

        draw.rectangle([x0 - 2, y0 - 2, x0 + cell_w + 1, y0 + cell_h + 1], outline=BORDER, width=2)
        draw.rectangle([x0, y0, x0 + cell_w - 1, y0 + label_h - 1], fill=PANEL_HEADER)
        draw.text((x0 + 10, y0 + 7), label, fill=TEXT_PRIMARY, font=font_label)

        tile_im = _open_tile(path, (tile_w, tile_h), label)
        if tile_im.size != (tile_w, tile_h):
            tile_im = _resize_cover_pad(tile_im, tile_w, tile_h)
        canvas.paste(tile_im, (x0, y0 + label_h))

    if footer_lines:
        fy0 = canvas_h - footer_h
        draw.line([(0, fy0), (canvas_w, fy0)], fill=BORDER, width=2)
        font_foot = _load_font(14, bold=False)
        for i, (line, color) in enumerate(footer_lines):
            txt = _truncate(draw, line, font_foot, canvas_w - 32)
            draw.text((16, fy0 + 10 + i * 24), txt, fill=color, font=font_foot)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    canvas.save(out_path, format="PNG")
    return out_path


def _build_footer_lines(qa: dict[str, Any]) -> list[tuple[str, tuple[int, int, int]]]:
    lines: list[tuple[str, tuple[int, int, int]]] = []
    for err in qa.get("errors", [])[:3]:
        lines.append((f"[ERROR] {err}", RED))
    remaining = 4 - len(lines)
    if remaining > 0:
        for warn in qa.get("warnings", [])[:remaining]:
            lines.append((f"[WARN]  {warn}", AMBER))
    if not lines:
        lines.append(("[OK]    No automated QA errors or warnings detected.", GREEN))
    else:
        total_e = len(qa.get("errors", []))
        total_w = len(qa.get("warnings", []))
        if total_e + total_w > len(lines):
            lines.append(
                (f"... +{total_e + total_w - len(lines)} more item(s) in qa_report.json", TEXT_MUTED)
            )
    return lines


def _compose_ref_comparison(
    ref_path: str,
    model_path: str,
    model_label: str,
    qa: dict[str, Any],
    out_path: str,
) -> str:
    with Image.open(ref_path) as r_im:
        ref_im = r_im.convert("RGB")
    with Image.open(model_path) as m_im:
        mod_im = m_im.convert("RGB")

    target_h = max(min(max(ref_im.height, mod_im.height), 720), 480)
    ref_w = max(320, int(round(ref_im.width * (target_h / max(ref_im.height, 1)))))
    mod_w = max(320, int(round(mod_im.width * (target_h / max(mod_im.height, 1)))))
    ref_scaled = _resize_cover_pad(ref_im, ref_w, target_h, bg=(24, 28, 36))
    mod_scaled = _resize_cover_pad(mod_im, mod_w, target_h, bg=(24, 28, 36))

    header_h = 76
    label_h = 34
    pad = 14
    gap = 14
    canvas_w = pad * 2 + ref_w + gap + mod_w
    canvas_h = header_h + pad * 2 + label_h + target_h

    canvas = Image.new("RGB", (canvas_w, canvas_h), BG_DARK)
    _draw_header(canvas, qa, "REFERENCE COMPARISON", header_h=header_h)
    draw = ImageDraw.Draw(canvas)
    font_label = _load_font(15, bold=True)

    y0 = header_h + pad
    # Left: Reference
    draw.rectangle([pad - 2, y0 - 2, pad + ref_w + 1, y0 + label_h + target_h + 1], outline=BORDER, width=2)
    draw.rectangle([pad, y0, pad + ref_w - 1, y0 + label_h - 1], fill=PANEL_HEADER)
    draw.text((pad + 10, y0 + 7), f"REFERENCE ({os.path.basename(ref_path)})", fill=TEXT_PRIMARY, font=font_label)
    canvas.paste(ref_scaled, (pad, y0 + label_h))

    # Right: Model
    mx0 = pad + ref_w + gap
    draw.rectangle([mx0 - 2, y0 - 2, mx0 + mod_w + 1, y0 + label_h + target_h + 1], outline=BORDER, width=2)
    draw.rectangle([mx0, y0, mx0 + mod_w - 1, y0 + label_h - 1], fill=PANEL_HEADER)
    draw.text((mx0 + 10, y0 + 7), model_label, fill=TEXT_PRIMARY, font=font_label)
    canvas.paste(mod_scaled, (mx0, y0 + label_h))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    canvas.save(out_path, format="PNG")
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose labeled QA contact sheets.")
    parser.add_argument("--manifest", help="Path to render_manifest.json from qa_pipeline.py")
    parser.add_argument("--tiles", help="Optional JSON mapping tile keys to file paths")
    parser.add_argument("--qa-json", required=True, help="Path to qa_report.json")
    parser.add_argument("--out-material", required=True, help="Output path for material 6-view contact sheet")
    parser.add_argument("--out-diagnostic", required=True, help="Output path for diagnostic 4-view contact sheet")
    parser.add_argument("--ref", default="", help="Optional reference image path")
    parser.add_argument("--out-ref", default="", help="Output path for reference comparison sheet")
    args = parser.parse_args(argv)

    with open(args.qa_json, encoding="utf-8") as fh:
        qa = json.load(fh)

    tiles: dict[str, dict[str, str]] = {}
    if args.manifest and os.path.exists(args.manifest):
        with open(args.manifest, encoding="utf-8") as fh:
            manifest = json.load(fh)
        tiles.update(manifest.get("tiles", {}))

    if args.tiles:
        raw = json.loads(args.tiles)
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, str):
                    tiles[k] = {"path": v, "label": k.upper()}
                elif isinstance(v, dict):
                    tiles[k] = v

    def tile_entry(key: str, default_label: str) -> tuple[str, str | None]:
        item = tiles.get(key) or {}
        return item.get("label", default_label), item.get("path")

    material_specs = [
        tile_entry("hero", "HERO 3/4"),
        tile_entry("front", "FRONT (ORTHO)"),
        tile_entry("side", "SIDE (ORTHO)"),
        tile_entry("back", "BACK (ORTHO)"),
        tile_entry("top", "TOP (ORTHO)"),
        tile_entry("rear_34", "REAR 3/4"),
    ]
    _compose_grid(
        material_specs,
        cols=3,
        rows=2,
        qa=qa,
        subtitle="6-VIEW MATERIAL SHEET",
        out_path=args.out_material,
    )

    diagnostic_specs = [
        tile_entry("diag_wire", "WIREFRAME (HERO 3/4)"),
        tile_entry("diag_parts", "PART COLORS (HERO 3/4)"),
        tile_entry("diag_normals", "FACE ORIENTATION (BLUE=OUT / RED=FLIPPED)"),
        tile_entry("diag_bottom", "UNDERBODY / BOTTOM"),
    ]
    _compose_grid(
        diagnostic_specs,
        cols=2,
        rows=2,
        qa=qa,
        subtitle="4-VIEW DIAGNOSTIC SHEET",
        out_path=args.out_diagnostic,
        footer_lines=_build_footer_lines(qa),
    )

    if args.ref and os.path.exists(args.ref) and args.out_ref:
        ref_lower = os.path.basename(args.ref).lower()
        use_key = "side" if "side" in ref_lower else "front" if "front" in ref_lower else "hero"
        mod_label, mod_path = tile_entry(use_key, "MODEL")
        if mod_path and os.path.exists(mod_path):
            _compose_ref_comparison(args.ref, mod_path, f"MODEL - {mod_label}", qa, args.out_ref)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

