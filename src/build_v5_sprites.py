"""
Build pixel-locked modular RGBA sprite packs (v5 Furina-style layout) for Chibi Typing Companion Pet.
- Flood-fill exterior white background removal + halo-free edge decontamination
- Automatic sub-pixel-accurate alignment using static anatomical anchors
- Spatially disjoint polygon masks (Face, Left Arm + Mousepad, Right Arm + Keyboard)
- Zero-ghost premultiplied masked blending for QA verification & runtime modular layers
- Generates dark + light background QA contact sheets for visual inspection
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from sprite_processor import (
    align_to_base,
    auto_crop_common_bbox,
    remove_white_bg_floodfill,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "assets" / "raw_v5" / "verified"
OUT_DIR = PROJECT_ROOT / "assets" / "sprites_v5"

# Target crisp sprite max dimension before runtime scaling
TARGET_MAX_DIM = 640

# Polygon masks in relative [0..1] coordinates of the 1024x1024 raw canvas (verified on bear_grid.png)
# Strictly disjoint regions:
#   - Face: y in [0.315 .. 0.595], x in [0.31 .. 0.69]
#   - Left Arm + Mousepad: stays strictly right of bottom-left corner charm & left of keyboard seam
#   - Right Arm + Keyboard: stays strictly right of keyboard seam & below chin
FACE_ELLIPSE_REL = (0.305, 0.285, 0.735, 0.595)

LEFT_MOUSE_POLY_REL = [
    (0.220, 0.610),
    (0.478, 0.610),
    (0.505, 0.755),
    (0.506, 0.798),
    (0.484, 0.835),
    (0.418, 0.912),
    (0.205, 0.905),
    (0.202, 0.815),
    (0.180, 0.775),
    (0.195, 0.690),
]

RIGHT_KB_POLY_REL = [
    (0.555, 0.615),
    (0.605, 0.585),
    (0.845, 0.585),
    (0.865, 0.955),
    (0.430, 0.928),
    (0.495, 0.838),
    (0.514, 0.798),
    (0.516, 0.745),
    (0.545, 0.720),
]

# Keycap polygons/boxes in relative [0..1] raw 1024x1024 coordinates (verified on bear_grid.png)
# Each entry: (cx, cy, rw, rh, angle_deg)
RAW_KEYCAPS_REL: Dict[str, Tuple[float, float, float, float, float]] = {
    "Space":    (0.756, 0.812, 0.094, 0.042, -5.5),
    "Shift":    (0.725, 0.855, 0.092, 0.042, -5.5),
    "Tab":      (0.692, 0.896, 0.090, 0.042, -5.5),
    "1":        (0.614, 0.891, 0.049, 0.040, -5.5),
    "2":        (0.560, 0.886, 0.049, 0.040, -5.5),
    "3":        (0.506, 0.881, 0.049, 0.040, -5.5),
    "4":        (0.453, 0.876, 0.049, 0.040, -5.5),
    "A":        (0.646, 0.848, 0.049, 0.040, -5.5),
    "D":        (0.594, 0.842, 0.049, 0.040, -5.5),
    "S":        (0.540, 0.836, 0.049, 0.040, -5.5),
    "F":        (0.488, 0.830, 0.049, 0.040, -5.5),
    "TopLong":  (0.590, 0.798, 0.086, 0.036, -5.5),
    "TopRound": (0.517, 0.790, 0.047, 0.036, -5.5),
}

# Mousepad center in relative raw coords (for cute mouse-click pulse effect)
RAW_MOUSE_POINTS_REL: Dict[str, Tuple[float, float]] = {
    "center": (0.314, 0.822),
    "ul":     (0.275, 0.785),
    "ur":     (0.365, 0.792),
    "dr":     (0.352, 0.848),
}

OUTFIT_THEMES = {
    "bear": {
        "name": "毛绒小熊发箍款",
        "key_glow_rgba": [255, 198, 72, 138],
        "key_glow_frantic_rgba": [255, 102, 92, 152],
        "mouse_click_rgba": [255, 198, 72, 165],
        "pill_bg_rgba": [255, 248, 236, 238],
        "pill_border_rgba": [146, 98, 66, 238],
        "pill_text_rgba": [92, 54, 34, 255],
        "pill_accent_rgba": [244, 176, 78, 255],
    },
    "daily": {
        "name": "日常浅蓝外套款",
        "key_glow_rgba": [104, 194, 255, 138],
        "key_glow_frantic_rgba": [255, 106, 138, 152],
        "mouse_click_rgba": [104, 194, 255, 165],
        "pill_bg_rgba": [242, 250, 255, 238],
        "pill_border_rgba": [88, 146, 198, 238],
        "pill_text_rgba": [44, 78, 118, 255],
        "pill_accent_rgba": [116, 188, 246, 255],
    },
    "summer": {
        "name": "夏日草帽香芋紫款",
        "key_glow_rgba": [188, 140, 255, 142],
        "key_glow_frantic_rgba": [255, 108, 152, 156],
        "mouse_click_rgba": [188, 140, 255, 168],
        "pill_bg_rgba": [250, 244, 255, 238],
        "pill_border_rgba": [146, 112, 186, 238],
        "pill_text_rgba": [86, 54, 118, 255],
        "pill_accent_rgba": [196, 152, 246, 255],
    },
    "hoodie": {
        "name": "灰色卫衣斜挎包款",
        "key_glow_rgba": [255, 146, 184, 144],
        "key_glow_frantic_rgba": [255, 96, 128, 158],
        "mouse_click_rgba": [255, 146, 184, 168],
        "pill_bg_rgba": [255, 246, 250, 238],
        "pill_border_rgba": [154, 124, 142, 238],
        "pill_text_rgba": [82, 56, 72, 255],
        "pill_accent_rgba": [248, 162, 194, 255],
    },
    "puffer": {
        "name": "奶白羽绒服冬日款",
        "key_glow_rgba": [126, 206, 255, 142],
        "key_glow_frantic_rgba": [255, 114, 138, 156],
        "mouse_click_rgba": [126, 206, 255, 168],
        "pill_bg_rgba": [246, 251, 255, 238],
        "pill_border_rgba": [112, 152, 192, 238],
        "pill_text_rgba": [48, 76, 108, 255],
        "pill_accent_rgba": [142, 204, 248, 255],
    },
}


def remove_hair_loop_holes(rgba_img: Image.Image) -> Image.Image:
    """Clear tiny enclosed white background holes trapped strictly inside outer wavy hair curls."""
    arr = np.array(rgba_img, dtype=np.float32)
    h, w, _ = arr.shape
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0

    min_c = rgb.min(axis=2)
    max_c = rgb.max(axis=2)
    chroma = max_c - min_c

    # Outer left/right wavy hair curl zones (strictly clear of eyes, white sweater, desk tray)
    ys, xs = np.mgrid[0:h, 0:w]
    in_hair_zone = (
        ((xs < int(w * 0.305)) | (xs > int(w * 0.695)))
        & (ys >= int(h * 0.42))
        & (ys <= int(h * 0.745))
    )
    hole = in_hair_zone & (alpha > 0.5) & (min_c >= 236) & (chroma <= 18)
    if not np.any(hole):
        return rgba_img

    hole_mask = Image.fromarray((hole.astype(np.uint8) * 255), mode="L")
    dilated = np.array(hole_mask.filter(ImageFilter.MaxFilter(5)), dtype=np.float32) / 255.0
    blurred = np.array(hole_mask.filter(ImageFilter.GaussianBlur(radius=1.0)), dtype=np.float32) / 255.0

    alpha[hole] = 0.0
    edge = (dilated > 0.0) & (~hole) & (alpha > 0.05)
    whiteness = np.clip((min_c - 210.0) / 45.0, 0.0, 1.0)
    low_sat = (chroma <= 26).astype(np.float32)
    alpha[edge] = np.clip(alpha[edge] * (1.0 - whiteness[edge] * low_sat[edge] * blurred[edge] * 0.9), 0.0, 1.0)

    semi = (alpha > 0.05) & (alpha < 0.98) & edge
    for c in range(3):
        fg = (arr[:, :, c] - (1.0 - alpha) * 255.0) / np.maximum(alpha, 0.05)
        arr[:, :, c] = np.where(semi, np.clip(fg, 0.0, 255.0), arr[:, :, c])

    arr[:, :, 3] = np.clip(alpha * 255.0, 0.0, 255.0)
    return Image.fromarray(arr.astype(np.uint8), mode="RGBA")


def make_ellipse_mask(size: Tuple[int, int], box_rel: Tuple[float, float, float, float], blur_px: float = 10.0) -> Image.Image:
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    x1, y1, x2, y2 = int(w * box_rel[0]), int(h * box_rel[1]), int(w * box_rel[2]), int(h * box_rel[3])
    d.rounded_rectangle((x1, y1, x2, y2), radius=int(min(x2 - x1, y2 - y1) * 0.24), fill=255)
    return m.filter(ImageFilter.GaussianBlur(radius=blur_px))


def make_poly_mask(size: Tuple[int, int], poly_rel: List[Tuple[float, float]], blur_px: float = 8.0) -> Image.Image:
    w, h = size
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    pts = [(int(round(px * w)), int(round(py * h))) for px, py in poly_rel]
    d.polygon(pts, fill=255)
    return m.filter(ImageFilter.GaussianBlur(radius=blur_px))


def premul_masked_replace(base_rgba: Image.Image, var_rgba: Image.Image, mask_l: Image.Image) -> Image.Image:
    """Ghost-free RGBA masked replacement in premultiplied color space."""
    b = np.array(base_rgba, dtype=np.float32)
    v = np.array(var_rgba, dtype=np.float32)
    m = (np.array(mask_l, dtype=np.float32) / 255.0)[:, :, None]

    ba = b[:, :, 3:4] / 255.0
    va = v[:, :, 3:4] / 255.0

    b_pre = b[:, :, :3] * ba
    v_pre = v[:, :, :3] * va

    out_pre = b_pre * (1.0 - m) + v_pre * m
    out_a = ba * (1.0 - m) + va * m

    out_rgb = np.where(out_a > 1e-4, out_pre / np.maximum(out_a, 1e-4), 0.0)
    out = np.empty_like(b)
    out[:, :, :3] = np.clip(out_rgb, 0.0, 255.0)
    out[:, :, 3:4] = np.clip(out_a * 255.0, 0.0, 255.0)
    return Image.fromarray(out.astype(np.uint8), mode="RGBA")


def crop_patch_by_mask(var_rgba: Image.Image, mask_l: Image.Image, pad: int = 4) -> Tuple[Image.Image, Image.Image, Tuple[int, int]]:
    """Crop RGBA variant + L mask tightly around mask > 2 so runtime patches are tiny & fast."""
    m_arr = np.array(mask_l)
    ys, xs = np.where(m_arr > 2)
    w, h = mask_l.size
    x1 = max(0, int(xs.min()) - pad)
    y1 = max(0, int(ys.min()) - pad)
    x2 = min(w, int(xs.max()) + pad + 1)
    y2 = min(h, int(ys.max()) + pad + 1)
    box = (x1, y1, x2, y2)
    return var_rgba.crop(box), mask_l.crop(box), (x1, y1)


def process_outfit(outfit_id: str) -> None:
    master_path = RAW_DIR / f"{outfit_id}_master_v5.png"
    if not master_path.exists():
        print(f"[SKIP] {outfit_id}: missing {master_path}")
        return

    print(f"\n=== Building v5 sprite pack: {outfit_id} ===")
    master_raw = Image.open(master_path).convert("RGB")
    raw_w, raw_h = master_raw.size

    # Map variant keys -> (filename, category, align_anchor)
    variant_specs = {
        "kb_up":        (f"{outfit_id}_kb_up.png",        "kb",    (0.22, 0.16, 0.78, 0.56)),
        "kb_high":      (f"{outfit_id}_kb_high.png",      "kb",    (0.22, 0.16, 0.78, 0.56)),
        "kb_low":       (f"{outfit_id}_kb_low.png",       "kb",    (0.22, 0.16, 0.78, 0.56)),
        "mouse_ul":     (f"{outfit_id}_mouse_ul.png",     "mouse", (0.22, 0.16, 0.78, 0.56)),
        "mouse_ur":     (f"{outfit_id}_mouse_ur.png",     "mouse", (0.22, 0.16, 0.78, 0.56)),
        "mouse_dr":     (f"{outfit_id}_mouse_dr.png",     "mouse", (0.22, 0.16, 0.78, 0.56)),
        "expr_blink":   (f"{outfit_id}_expr_blink.png",   "face",  (0.14, 0.75, 0.86, 0.94)),
        "expr_happy":   (f"{outfit_id}_expr_happy.png",   "face",  (0.14, 0.75, 0.86, 0.94)),
        "expr_focused": (f"{outfit_id}_expr_focused.png", "face",  (0.14, 0.75, 0.86, 0.94)),
        "expr_frantic": (f"{outfit_id}_expr_frantic.png", "face",  (0.14, 0.75, 0.86, 0.94)),
    }

    # Build full-size masks on raw canvas
    mask_face_raw = make_ellipse_mask((raw_w, raw_h), FACE_ELLIPSE_REL, blur_px=10.0)
    mask_mouse_raw = make_poly_mask((raw_w, raw_h), LEFT_MOUSE_POLY_REL, blur_px=5.5)
    mask_kb_raw = make_poly_mask((raw_w, raw_h), RIGHT_KB_POLY_REL, blur_px=6.5)

    cat_masks = {
        "face": mask_face_raw,
        "mouse": mask_mouse_raw,
        "kb": mask_kb_raw,
    }

    # Step 1: Flood-fill remove background + enclosed outer hair-loop holes on master + every aligned variant
    rgba_frames: Dict[str, Image.Image] = {
        "base": remove_hair_loop_holes(remove_white_bg_floodfill(master_raw)),
    }

    present_keys: Dict[str, str] = {}  # key -> category
    for key, (fname, cat, anchor) in variant_specs.items():
        p = RAW_DIR / fname
        if not p.exists():
            print(f"  [WARN] missing optional variant: {fname}")
            continue
        raw_v = Image.open(p).convert("RGB")
        aligned = align_to_base(master_raw, raw_v, anchor_box_rel=anchor, max_shift=22)
        rgba_v = remove_hair_loop_holes(remove_white_bg_floodfill(aligned))
        # Bake clean localized composite on full canvas so union bbox & edges are 100% consistent
        rgba_frames[key] = premul_masked_replace(rgba_frames["base"], rgba_v, cat_masks[cat])
        present_keys[key] = cat
        print(f"  [OK] aligned & keyed: {key}")

    # Step 2: Compute common union bounding box across base + all variants
    min_x, min_y = 10**9, 10**9
    max_x, max_y = 0, 0
    for im in rgba_frames.values():
        alpha = np.array(im)[:, :, 3]
        ys, xs = np.where(alpha > 8)
        if len(xs) > 0:
            min_x = min(min_x, int(xs.min()))
            min_y = min(min_y, int(ys.min()))
            max_x = max(max_x, int(xs.max()))
            max_y = max(max_y, int(ys.max()))

    pad = 14
    cx1 = max(0, min_x - pad)
    cy1 = max(0, min_y - pad)
    cx2 = min(raw_w, max_x + pad + 1)
    cy2 = min(raw_h, max_y + pad + 1)
    crop_box = (cx1, cy1, cx2, cy2)
    cw, ch = cx2 - cx1, cy2 - cy1

    scale = min(1.0, TARGET_MAX_DIM / float(max(cw, ch)))
    out_w = max(64, int(round(cw * scale)))
    out_h = max(64, int(round(ch * scale)))

    def transform_img(im: Image.Image) -> Image.Image:
        cropped = im.crop(crop_box)
        if cropped.size != (out_w, out_h):
            return cropped.resize((out_w, out_h), Image.LANCZOS)
        return cropped

    # Save modular assets
    outfit_out = OUT_DIR / outfit_id
    outfit_out.mkdir(parents=True, exist_ok=True)

    base_final = transform_img(rgba_frames["base"])
    base_final.save(outfit_out / "base.png", optimize=True)

    masks_final = {
        cat: transform_img(m) for cat, m in cat_masks.items()
    }

    patches_meta: Dict[str, dict] = {}
    for cat in ("face", "mouse", "kb"):
        # Save shared mask crop per category + each variant patch crop
        m_img = masks_final[cat]
        _, m_crop, (ox, oy) = crop_patch_by_mask(base_final, m_img, pad=2)
        m_crop.save(outfit_out / f"mask_{cat}.png", optimize=True)
        patches_meta[f"mask_{cat}"] = {"x": ox, "y": oy, "w": m_crop.width, "h": m_crop.height}

        for key, kcat in present_keys.items():
            if kcat != cat:
                continue
            v_final = transform_img(rgba_frames[key])
            v_crop = v_final.crop((ox, oy, ox + m_crop.width, oy + m_crop.height))
            v_crop.save(outfit_out / f"{key}.png", optimize=True)
            patches_meta[key] = {"cat": cat, "x": ox, "y": oy, "w": v_crop.width, "h": v_crop.height}

    # Map keycap & mouse coordinates from raw [0..1] into cropped/scaled sprite [0..1]
    def raw_pt_to_sprite_rel(rx: float, ry: float) -> Tuple[float, float]:
        px = (rx * raw_w - cx1) * scale
        py = (ry * raw_h - cy1) * scale
        return round(px / out_w, 5), round(py / out_h, 5)

    keycaps_sprite = {}
    for kname, (rx, ry, rw, rh, ang) in RAW_KEYCAPS_REL.items():
        sx, sy = raw_pt_to_sprite_rel(rx, ry)
        sw = round((rw * raw_w * scale) / out_w, 5)
        sh = round((rh * raw_h * scale) / out_h, 5)
        keycaps_sprite[kname] = {
            "cx": sx, "cy": sy, "w": sw, "h": sh, "angle": ang,
        }

    mouse_pts_sprite = {}
    for mname, (rx, ry) in RAW_MOUSE_POINTS_REL.items():
        mx, my = raw_pt_to_sprite_rel(rx, ry)
        mouse_pts_sprite[mname] = {"x": mx, "y": my}

    layout = {
        "outfit_id": outfit_id,
        "sprite_size": [out_w, out_h],
        "crop_box_raw": [cx1, cy1, cx2, cy2],
        "theme": OUTFIT_THEMES.get(outfit_id, OUTFIT_THEMES["bear"]),
        "patches": patches_meta,
        "keycaps": keycaps_sprite,
        "mouse_points": mouse_pts_sprite,
    }
    (outfit_out / "layout.json").write_text(
        json.dumps(layout, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Step 3: Build dark + light QA contact sheet showing base, all poses, and combined states!
    def compose_test(expr: str, mouse: str, kb: str) -> Image.Image:
        cur = base_final.copy()
        for key, cat in ((f"expr_{expr}", "face"), (f"mouse_{mouse}", "mouse"), (f"kb_{kb}", "kb")):
            if key in present_keys:
                v_final = transform_img(rgba_frames[key])
                cur = premul_masked_replace(cur, v_final, masks_final[cat])
        return cur

    qa_combos = [
        ("Idle (Base)",         "idle",    "center", "mid"),
        ("KB Up (Hover)",       "idle",    "center", "up"),
        ("KB High (S/D/F)",     "happy",   "center", "high"),
        ("KB Low (Tab/1/Shf)",  "focused", "center", "low"),
        ("Mouse UL + Blink",    "blink",   "ul",     "up"),
        ("Mouse UR + Happy",    "happy",   "ur",     "mid"),
        ("Mouse DR + Focused",  "focused", "dr",     "high"),
        ("Frantic + UL + Low",  "frantic", "ul",     "low"),
    ]

    tile = 280
    cols = 4
    rows = 2
    sheet = Image.new("RGBA", (cols * tile, rows * tile), (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    for idx, (label, expr, mouse, kb) in enumerate(qa_combos):
        r, c = divmod(idx, cols)
        x0, y0 = c * tile, r * tile
        # Alternating dark navy and warm light cream backgrounds to catch ANY white halo or edge artifact!
        bg_col = (26, 30, 42, 255) if (r + c) % 2 == 0 else (244, 242, 238, 255)
        txt_col = (255, 248, 232, 255) if (r + c) % 2 == 0 else (40, 32, 30, 255)
        draw.rectangle((x0, y0, x0 + tile, y0 + tile), fill=bg_col)
        comp = compose_test(expr, mouse, kb)
        comp.thumbnail((tile - 16, tile - 32), Image.LANCZOS)
        px = x0 + (tile - comp.width) // 2
        py = y0 + (tile - 24 - comp.height) // 2 + 20
        sheet.alpha_composite(comp, (px, py))
        draw.text((x0 + 8, y0 + 5), label, fill=txt_col)

    qa_path = OUT_DIR / f"{outfit_id}_qa.png"
    sheet.save(qa_path, optimize=True)
    print(f"  [DONE] Saved sprite pack -> {outfit_out} ({out_w}x{out_h})")
    print(f"  [QA]   Saved contact sheet -> {qa_path}")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["bear", "daily", "summer", "hoodie", "puffer"]
    for oid in targets:
        process_outfit(oid)
