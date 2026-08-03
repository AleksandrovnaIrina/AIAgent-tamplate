# © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
"""Generate Instagram carousel slides (1080×1080) with Iryna's brand palette."""
import io
import os
import random
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Brand palette (RGB tuples)
C_DARK      = (7, 7, 7)          # #070707
C_GRAPHITE  = (33, 32, 29)       # #21201D
C_BEIGE     = (218, 214, 207)    # #DAD6CF
C_TAUPE     = (189, 184, 176)    # #BDB8B0
C_MUTED     = (158, 149, 140)    # #9E958C

SIZE   = (1080, 1080)
MARGIN = 96


# ── fonts ────────────────────────────────────────────────────────────────────

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    regular = [
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans_Condensed-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    bolds = [
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans_Condensed-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in (bolds if bold else regular):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ── background generators ─────────────────────────────────────────────────────

def _grain(img: Image.Image, strength: float = 0.03) -> Image.Image:
    try:
        import numpy as np
        arr = np.array(img).astype("float32")
        arr += np.random.normal(0, strength * 255, arr.shape)
        return Image.fromarray(arr.clip(0, 255).astype("uint8"))
    except ImportError:
        return img


def _bg_solid(seed: int) -> Image.Image:
    rng = random.Random(seed)
    c = rng.choice([C_DARK, C_GRAPHITE, (12, 11, 10), (20, 19, 17)])
    return Image.new("RGB", SIZE, c)


def _bg_grain(seed: int) -> Image.Image:
    return _grain(_bg_solid(seed), 0.028)


def _bg_shadow(seed: int) -> Image.Image:
    rng = random.Random(seed)
    base = Image.new("RGB", SIZE, C_DARK)
    glow = Image.new("RGB", SIZE, C_GRAPHITE)
    mask = Image.new("L", SIZE, 0)
    d = ImageDraw.Draw(mask)
    cx, cy = SIZE[0] // 2 + rng.randint(-120, 120), SIZE[1] // 2 + rng.randint(-80, 80)
    d.ellipse([cx - 380, cy - 380, cx + 380, cy + 380], fill=100)
    mask = mask.filter(ImageFilter.GaussianBlur(200))
    base.paste(glow, mask=mask)
    return base


def _bg_lines(seed: int) -> Image.Image:
    rng = random.Random(seed)
    bg = rng.choice([C_DARK, C_GRAPHITE])
    img = Image.new("RGB", SIZE, bg)
    d = ImageDraw.Draw(img)
    style = rng.choice(["corner", "bottom_line", "bracket"])
    acc = (*C_MUTED,)
    m = MARGIN
    if style == "corner":
        ll = rng.randint(100, 180)
        d.line([(m, m), (m + ll, m)], fill=acc, width=1)
        d.line([(m, m), (m, m + ll // 2)], fill=acc, width=1)
        d.line([(SIZE[0]-m-ll, SIZE[1]-m), (SIZE[0]-m, SIZE[1]-m)], fill=acc, width=1)
    elif style == "bottom_line":
        y = SIZE[1] - m - 30
        d.line([(m, y), (SIZE[0]-m, y)], fill=(*C_MUTED, 70), width=1)
    else:
        d.line([(m, m+30), (m, m+110)], fill=acc, width=2)
        d.line([(m, m+30), (m+55, m+30)], fill=acc, width=2)
    return img


def _bg_taupe(seed: int) -> Image.Image:
    rng = random.Random(seed)
    c = rng.choice([C_BEIGE, C_TAUPE, (205, 200, 192)])
    return _grain(Image.new("RGB", SIZE, c), 0.018)


_BG_FUNCS = {
    "solid":  _bg_solid,
    "grain":  _bg_grain,
    "shadow": _bg_shadow,
    "lines":  _bg_lines,
    "taupe":  _bg_taupe,
}

def _pick_style(idx: int, total: int, rng: random.Random) -> str:
    if idx == 0:
        return rng.choice(["lines", "grain", "shadow"])
    if idx == total - 1:
        return rng.choice(["solid", "taupe", "lines"])
    return rng.choice(["solid", "grain", "shadow", "lines", "taupe"])


def _text_color(img: Image.Image) -> tuple:
    px = img.getpixel((SIZE[0] // 2, SIZE[1] // 2))
    bright = (px[0] * 299 + px[1] * 587 + px[2] * 114) / 1000
    return C_GRAPHITE if bright > 130 else C_BEIGE


# ── text layout ───────────────────────────────────────────────────────────────

def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        bb = font.getbbox(test)
        if bb[2] - bb[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_block(draw: ImageDraw.Draw, text: str, cy: int,
                font: ImageFont.FreeTypeFont, color: tuple,
                max_w: int, spacing: float = 1.4) -> int:
    lines = _wrap(text, font, max_w)
    bb = font.getbbox("Мg")
    lh = int((bb[3] - bb[1]) * spacing)
    total = lh * len(lines)
    y = cy - total // 2
    for line in lines:
        bb = font.getbbox(line)
        x = (SIZE[0] - (bb[2] - bb[0])) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += lh
    return total


def _draw_counter(draw: ImageDraw.Draw, idx: int, total: int, tc: tuple) -> None:
    font = _font(28)
    t = f"{idx+1} / {total}"
    bb = font.getbbox(t)
    w, h = bb[2]-bb[0], bb[3]-bb[1]
    fade = tuple(max(0, c-50) if sum(tc) > 300 else min(255, c+50) for c in tc)
    draw.text((SIZE[0]-MARGIN-w, SIZE[1]-MARGIN//2-h), t, font=font, fill=(*fade, 120))


# ── slide renderer ────────────────────────────────────────────────────────────

def _render_slide(
    text: str,
    idx: int,
    total: int,
    seed: int,
    cover_photo: Optional[bytes] = None,
) -> bytes:
    rng = random.Random(seed + idx * 13)
    style = _pick_style(idx, total, rng)
    bg = _BG_FUNCS[style](seed + idx)

    # Cover photo: gradient overlay + text in lower third to avoid faces
    has_cover = False
    if idx == 0 and cover_photo:
        try:
            ph = Image.open(io.BytesIO(cover_photo)).convert("RGB")
            pw, ph_h = ph.size
            # Crop to square
            if pw > ph_h:
                off = (pw - ph_h) // 2
                ph = ph.crop((off, 0, off + ph_h, ph_h))
            else:
                ph = ph.crop((0, 0, pw, pw))
            ph = ph.resize(SIZE, Image.LANCZOS)
            # Gradient overlay: transparent at top, dark at bottom (keeps face clear)
            grad = Image.new("RGBA", SIZE, (0, 0, 0, 0))
            for y in range(SIZE[1]):
                # alpha 0 for top 40%, ramps to 220 at bottom
                t = max(0.0, (y / SIZE[1] - 0.40) / 0.60)
                a = int(t * 220)
                for x in range(SIZE[0]):
                    grad.putpixel((x, y), (7, 7, 7, a))
            ph_rgba = ph.convert("RGBA")
            ph_rgba.alpha_composite(grad)
            bg = ph_rgba.convert("RGB")
            has_cover = True
        except Exception:
            pass  # fall back to generated bg

    draw = ImageDraw.Draw(bg)
    tc = _text_color(bg)
    mw = SIZE[0] - MARGIN * 2

    if idx == 0:
        # Cover: large bold title — lower third when photo present (avoids face), center otherwise
        f = _font(74, bold=True)
        cy = int(SIZE[1] * 0.80) if has_cover else SIZE[1] // 2
        _draw_block(draw, text, cy, f, tc, mw, 1.25)
    else:
        # Body slides: optional split title + body
        dot_idx = text.find(". ")
        if dot_idx > 0 and dot_idx < 70 and len(text) > dot_idx + 15:
            title = text[:dot_idx + 1]
            body  = text[dot_idx + 2:]
            _draw_block(draw, title, int(SIZE[1] * 0.37), _font(58, bold=True), tc, mw, 1.2)
            _draw_block(draw, body,  int(SIZE[1] * 0.63), _font(44),             tc, mw, 1.5)
        else:
            _draw_block(draw, text, SIZE[1] // 2, _font(52), tc, mw, 1.4)

    _draw_counter(draw, idx, total, tc)

    buf = io.BytesIO()
    bg.save(buf, format="JPEG", quality=92, optimize=True)
    return buf.getvalue()


# ── public API ────────────────────────────────────────────────────────────────

def generate_carousel(
    slides: list[str],
    cover_photo: Optional[bytes] = None,
    seed: Optional[int] = None,
) -> list[bytes]:
    """Return list of JPEG bytes, one per slide."""
    if seed is None:
        seed = random.randint(1000, 99999)
    return [
        _render_slide(s, i, len(slides), seed, cover_photo if i == 0 else None)
        for i, s in enumerate(slides)
    ]
