"""The mark as pixels: PNGs and a favicon drawn from the spec with Pillow and numpy.

The export job's real work. The soft glyph is plain line segments, so it
fills as polygons; the tile's three stop ground, its highlight and shade,
the glyph's gradient and the two layer shadow follow ``build.mjs``. Drawn at
four times the size and brought down, so small sizes stay crisp.

Plain Python, no Nu: the job calls :func:`png` per size in its own process.
"""

from __future__ import annotations

import functools
import io
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import color
from .glyph import GH, GW, GX, GY, PATH
from .spec import num


__all__ = ["favicon", "png"]


@functools.cache
def _outlines() -> tuple[np.ndarray, ...]:
    """The glyph's closed outlines, in the 546x552 viewBox."""
    out = []
    for sub in re.findall(r"M[^M]+", PATH):
        pts = np.array([float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", sub)]).reshape(-1, 2)
        pts[:, 0] = pts[:, 0] * 0.1
        pts[:, 1] = 552 - pts[:, 1] * 0.1
        out.append(pts)
    return tuple(out)


def _glyph_mask(n: int, h: float) -> tuple[Image.Image, tuple[float, float, float, float]]:
    """The glyph ``h`` tall on a 1024 canvas, drawn into an ``n`` px mask. Returns it and its bbox in px."""
    s = h / GH
    k = n / 1024
    x0, y0 = (1024 - GW * s) / 2, (1024 - h) / 2
    mask = Image.new("L", (n, n), 0)
    for pts in _outlines():
        one = Image.new("L", (n, n), 0)
        xy = [((x0 + s * (x - GX)) * k, (y0 + s * (y - GY)) * k) for x, y in pts]
        ImageDraw.Draw(one).polygon(xy, fill=255)
        mask = Image.fromarray(np.bitwise_xor(np.asarray(mask), np.asarray(one)))
    return mask, (x0 * k, y0 * k, GW * s * k, h * k)


def _stops(t: np.ndarray, stops: list[tuple[float, str]]) -> np.ndarray:
    """A gradient of ``stops`` sampled at ``t`` (0..1), as float RGB."""
    offs = [o for o, _ in stops]
    cols = np.array([color.rgb(c) for _, c in stops])
    return np.stack([np.interp(t, offs, cols[:, i]) for i in range(3)], axis=-1)


def _radial(n: int, cx: float, cy: float, r: float) -> np.ndarray:
    y, x = np.mgrid[0:n, 0:n] / n
    return np.clip(np.hypot(x - cx, y - cy) / r, 0, 1)


def _over(base: np.ndarray, top: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    a = alpha[..., None]
    return base * (1 - a) + top * a


def _tile(spec: dict[str, str], n: int, name: str, small: bool) -> Image.Image:
    y, x = np.mgrid[0:n, 0:n] / n
    rgb = _stops(
        (x + y) / 2, [(0, spec["mark.from"]), (0.5, spec["mark.mid"]), (1, spec["mark.to"])]
    )
    hl = 0.35 * np.clip(1 - _radial(n, 0.2, 0.05, 0.9) / 0.5, 0, 1)
    rgb = _over(rgb, np.ones_like(rgb), hl)
    dk = 0.45 * (1 - _radial(n, 0.8, 1.05, 0.8))
    rgb = _over(rgb, np.array(color.rgb("#05081a")) * np.ones_like(rgb), dk)

    mark_h = num(spec, "mark.size")
    if name == "square":
        h = mark_h * (600 / 560 if small else 1)
    else:
        h = mark_h * (400 / 560) * (460 / 400 if small else 1)
    gmask, (gx, gy, gw, gh) = _glyph_mask(n, h)
    galpha = np.asarray(gmask) / 255

    if spec.get("mark.shadow", "on") == "on" and not small:
        k = n / 1024
        for blur, dy, tint, op in ((42, 40, "#120638", 0.42), (5, 6, "#1b0d4d", 0.35)):
            sh = gmask.filter(ImageFilter.GaussianBlur(blur * k))
            sh = np.roll(np.asarray(sh) / 255, round(dy * k), axis=0) * op
            rgb = _over(rgb, np.array(color.rgb(tint)) * np.ones_like(rgb), sh)

    t = np.clip(((x * n - gx) / gw + (1 - (y * n - gy) / gh)) / 2, 0, 1)
    glyph = _stops(t, [(0, spec["mark.glyph-from"]), (1, spec["mark.glyph-to"])])
    rgb = _over(rgb, glyph, galpha)

    shape = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(shape)
    if name == "square":
        d.rounded_rectangle(
            (0, 0, n - 1, n - 1), radius=num(spec, "mark.radius") * n / 1024, fill=255
        )
    elif name == "circle":
        d.ellipse((0, 0, n - 1, n - 1), fill=255)
    else:
        d.rectangle((0, 0, n, n), fill=255)
    out = np.dstack([np.clip(rgb * 255, 0, 255), np.asarray(shape)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def _text_only(spec: dict[str, str], n: int) -> Image.Image:
    # The viewBox 222..802 of the 1024 canvas, with the glyph 560 tall in it.
    big = round(n * 1024 / 580)
    gmask, (gx, gy, gw, gh) = _glyph_mask(big, 560)
    y, x = np.mgrid[0:big, 0:big]
    t = np.clip(((x - gx) / gw + (1 - (y - gy) / gh)) / 2, 0, 1)
    rgb = _stops(
        t,
        [
            (o, spec[f"mark.text-{i}"])
            for i, o in zip((1, 2, 3, 4), (0, 0.3, 0.62, 1), strict=False)
        ],
    )
    img = Image.fromarray(np.dstack([rgb * 255, np.asarray(gmask)]).astype(np.uint8), "RGBA")
    o = round(222 * big / 1024)
    return img.crop((o, o, o + round(580 * big / 1024), o + round(580 * big / 1024))).resize(
        (n, n), Image.LANCZOS
    )


def image(spec: dict[str, str], name: str, size: int) -> Image.Image:
    """One asset at ``size`` px, drawn at four times that (two above 512) and brought down."""
    ss = 4 if size <= 512 else 2
    n = size * ss
    small = size <= 48 and name != "text-only"
    img = _text_only(spec, n) if name == "text-only" else _tile(spec, n, name, small)
    return img.resize((size, size), Image.LANCZOS)


def png(spec: dict[str, str], name: str, size: int) -> bytes:
    """One asset at ``size`` px as PNG bytes."""
    buf = io.BytesIO()
    image(spec, name, size).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def favicon(spec: dict[str, str]) -> bytes:
    """``favicon.ico``: the flat square at 16, 32 and 48."""
    buf = io.BytesIO()
    big = image(spec, "square", 48)
    big.save(
        buf,
        "ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=[image(spec, "square", s) for s in (16, 32)],
    )
    return buf.getvalue()
