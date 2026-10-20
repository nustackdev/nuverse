"""Color math the spec needs: hex, OKLCH, WCAG contrast, mixing. Plain Python.

The nustack palette is written in OKLCH (lightness, chroma, hue): the grounds
share one hue (the sky's lean), and each light keeps its lightness and chroma
while its hue turns. :func:`oklch` and :func:`hexof` go both ways; a color
out of the sRGB gamut keeps its lightness and hue and gives up chroma.
"""

from __future__ import annotations

import math


__all__ = ["contrast", "hexof", "is_hex", "luminance", "mix", "oklch", "rgb", "turn"]


def is_hex(value: str) -> bool:
    """``#rrggbb`` or ``#rgb``."""
    v = value.strip().lstrip("#")
    return (
        value.strip().startswith("#")
        and len(v) in (3, 6)
        and all(c in "0123456789abcdefABCDEF" for c in v)
    )


def rgb(color: str) -> tuple[float, float, float]:
    """``#rrggbb`` as 0..1 channels."""
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return (int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255)


def _hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in (r, g, b))


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gam(c: float) -> float:
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    r, g, b = _lin(r), _lin(g), _lin(b)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def _srgb(lab_l: float, a: float, b: float) -> tuple[float, float, float]:
    l_ = (lab_l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lab_l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lab_l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )
    return tuple(_gam(c) if c >= 0 else -_gam(-c) for c in lin)  # type: ignore[return-value]


def oklch(color: str) -> tuple[float, float, float]:
    """A hex color as ``(L 0..1, C, H degrees)``."""
    lab_l, a, b = _oklab(*rgb(color))
    return lab_l, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def hexof(lightness: float, chroma: float, hue: float) -> str:
    """OKLCH as hex. Out of gamut, chroma gives way until it fits."""
    h = math.radians(hue)
    for _ in range(40):
        r, g, b = _srgb(lightness, chroma * math.cos(h), chroma * math.sin(h))
        if all(-0.001 <= c <= 1.001 for c in (r, g, b)):
            return _hex(r, g, b)
        chroma *= 0.93
    return _hex(*_srgb(lightness, 0.0, 0.0))


def turn(color: str, hue: float | None = None, *, dl: float = 0.0, dc: float = 0.0) -> str:
    """``color`` with its hue set to ``hue`` (kept when None), lightness and chroma nudged."""
    lab_l, c, h = oklch(color)
    return hexof(min(1.0, max(0.0, lab_l + dl)), max(0.0, c + dc), h if hue is None else hue)


def luminance(color: str) -> float:
    """WCAG relative luminance."""
    r, g, b = (_lin(c) for c in rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    """WCAG 2 contrast ratio, 1 to 21."""
    a, b = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def mix(fg: str, bg: str, amount: float) -> str:
    """``fg`` laid over ``bg`` at ``amount`` (0..1) opacity, as one opaque hex."""
    f, b = rgb(fg), rgb(bg)
    return _hex(*(b[i] + (f[i] - b[i]) * amount for i in range(3)))
