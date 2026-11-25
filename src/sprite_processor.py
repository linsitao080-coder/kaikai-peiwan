"""
Sprite Processor & Layer Compositor for Typing Desktop Pet.
- Exterior flood-fill background removal (preserves white clothes, eyes, and keycaps!)
- Halo-free edge decontamination for clean rendering on both dark and light wallpapers
- Automatic translation alignment across expression / hand-down frames
- Independent Left-Hand / Right-Hand / Both-Hands composite generation
"""

from __future__ import annotations

import os
from collections import deque
import numpy as np
from PIL import Image, ImageFilter


def remove_white_bg_floodfill(
    img: Image.Image,
    bg_thresh: int = 240,
    soft_thresh: int = 218,
) -> Image.Image:
    """Remove exterior white background via corner flood-fill while keeping interior whites opaque."""
    rgba = np.array(img.convert("RGBA"), dtype=np.float32)
    h, w, _ = rgba.shape
    rgb = rgba[:, :, :3]

    # Brightness / whiteness metric: min channel high & low saturation
    min_c = rgb.min(axis=2)
    max_c = rgb.max(axis=2)
    chroma = max_c - min_c
    passable = (min_c >= bg_thresh) & (chroma <= 22)

    visited = np.zeros((h, w), dtype=bool)
    q: deque[tuple[int, int]] = deque()

    # Seed from all four borders where passable
    for x in range(w):
        for y in (0, h - 1):
            if passable[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if passable[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))

    while q:
        cy, cx = q.popleft()
        for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and passable[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    # Build smooth alpha near exterior boundary to prevent jagged 1-bit edges
    bg_mask = Image.fromarray((visited.astype(np.uint8) * 255), mode="L")
    dilated = np.array(bg_mask.filter(ImageFilter.MaxFilter(5)), dtype=np.float32) / 255.0
    blurred_bg = np.array(bg_mask.filter(ImageFilter.GaussianBlur(radius=1.1)), dtype=np.float32) / 255.0

    alpha = np.ones((h, w), dtype=np.float32)
    alpha[visited] = 0.0

    # Soften 1-2px anti-aliased white border pixels adjacent to exterior background
    edge_zone = (dilated > 0.0) & (~visited)
    whiteness = np.clip((min_c - soft_thresh) / max(1.0, (255.0 - soft_thresh)), 0.0, 1.0)
    low_sat = (chroma <= 28).astype(np.float32)
    edge_fade = 1.0 - (whiteness * low_sat * blurred_bg * 0.92)
    alpha[edge_zone] = np.clip(edge_fade[edge_zone], 0.0, 1.0)

    # Decontaminate whitematte from semi-transparent edge pixels: C_fg = (C - (1-a)*255) / a
    semi = (alpha > 0.05) & (alpha < 0.98)
    for c in range(3):
        fg = (rgba[:, :, c] - (1.0 - alpha) * 255.0) / np.maximum(alpha, 0.05)
        rgba[:, :, c] = np.where(semi, np.clip(fg, 0.0, 255.0), rgba[:, :, c])

    rgba[:, :, 3] = np.clip(alpha * 255.0, 0.0, 255.0)
    return Image.fromarray(rgba.astype(np.uint8), mode="RGBA")


def align_to_base(
    base_img: Image.Image,
    target_img: Image.Image,
    anchor_box_rel: tuple[float, float, float, float] = (0.15, 0.03, 0.85, 0.30),
    max_shift: int = 18,
) -> Image.Image:
    """Align target_img to base_img using integer pixel search over static upper-head/hair anchor."""
    if target_img.size != base_img.size:
        target_img = target_img.resize(base_img.size, Image.LANCZOS)

    w, h = base_img.size
    x1, y1, x2, y2 = (
        int(w * anchor_box_rel[0]),
        int(h * anchor_box_rel[1]),
        int(w * anchor_box_rel[2]),
        int(h * anchor_box_rel[3]),
    )
    b_gray = np.array(base_img.convert("L"), dtype=np.float32)[y1:y2, x1:x2]
    t_full = np.array(target_img.convert("L"), dtype=np.float32)

    best_dx, best_dy = 0, 0
    best_err = float("inf")
    for dy in range(-max_shift, max_shift + 1, 2):
        for dx in range(-max_shift, max_shift + 1, 2):
            ty1, ty2 = y1 + dy, y2 + dy
            tx1, tx2 = x1 + dx, x2 + dx
            if ty1 < 0 or tx1 < 0 or ty2 > h or tx2 > w:
                continue
            err = float(np.mean(np.abs(b_gray - t_full[ty1:ty2, tx1:tx2])))
            if err < best_err:
                best_err = err
                best_dx, best_dy = dx, dy

    # Refine +/- 1px around best coarse shift
    coarse_dx, coarse_dy = best_dx, best_dy
    for dy in range(coarse_dy - 1, coarse_dy + 2):
        for dx in range(coarse_dx - 1, coarse_dx + 2):
            ty1, ty2 = y1 + dy, y2 + dy
            tx1, tx2 = x1 + dx, x2 + dx
            if ty1 < 0 or tx1 < 0 or ty2 > h or tx2 > w:
                continue
            err = float(np.mean(np.abs(b_gray - t_full[ty1:ty2, tx1:tx2])))
            if err < best_err:
                best_err = err
                best_dx, best_dy = dx, dy

    if best_dx == 0 and best_dy == 0:
        return target_img

    # Shift target_img by (-best_dx, -best_dy) to match base_img, filling border with white
    bg = Image.new(target_img.mode, (w, h), (255, 255, 255, 255) if target_img.mode == "RGBA" else (255, 255, 255))
    bg.paste(target_img, (-best_dx, -best_dy))
    return bg


def make_soft_box_mask(
    size: tuple[int, int],
    box_rel: tuple[float, float, float, float],
    blur_rel: float = 0.025,
) -> Image.Image:
    """Create a soft feathered rectangular alpha mask in relative [0..1] coordinates."""
    w, h = size
    mask = Image.new("L", (w, h), 0)
    arr = np.zeros((h, w), dtype=np.uint8)
    x1, y1, x2, y2 = (
        int(w * box_rel[0]),
        int(h * box_rel[1]),
        int(w * box_rel[2]),
        int(h * box_rel[3]),
    )
    arr[max(0, y1):min(h, y2), max(0, x1):min(w, x2)] = 255
    mask = Image.fromarray(arr, mode="L")
    radius = max(2.0, min(w, h) * blur_rel)
    return mask.filter(ImageFilter.GaussianBlur(radius=radius))


def auto_crop_common_bbox(frames: dict[str, Image.Image], pad: int = 16) -> dict[str, Image.Image]:
    """Crop all RGBA frames to their shared union bounding box so every sprite shares identical dimensions."""
    min_x, min_y = 10**9, 10**9
    max_x, max_y = 0, 0
    w, h = next(iter(frames.values())).size

    for im in frames.values():
        alpha = np.array(im)[:, :, 3]
        ys, xs = np.where(alpha > 8)
        if len(xs) > 0:
            min_x = min(min_x, int(xs.min()))
            min_y = min(min_y, int(ys.min()))
            max_x = max(max_x, int(xs.max()))
            max_y = max(max_y, int(ys.max()))

    crop_box = (
        max(0, min_x - pad),
        max(0, min_y - pad),
        min(w, max_x + pad + 1),
        min(h, max_y + pad + 1),
    )
    return {k: v.crop(crop_box) for k, v in frames.items()}
