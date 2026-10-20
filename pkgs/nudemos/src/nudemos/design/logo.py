"""The Nu mark as SVG, built from the spec. A port of ``brand/logo/build.mjs``.

The glyph is :mod:`.glyph`'s soft outline; the ground's three stops, the
glyph's two, the text-only mark's four, the glyph's size on the 1024 tile,
the tile's corner and the shadow all come from the spec (``mark.*``), so
every drawing of the mark follows it. Plain Python, no Nu.
"""

from __future__ import annotations

import colorsys
from urllib.parse import quote

from . import color
from .glyph import GH, GW, GX, GY, PATH
from .spec import num


__all__ = ["ASSETS", "asset", "data_url", "glyph_defs", "lockup", "variants"]


#: Every asset the brand ships, as the brand's README names them.
ASSETS = ("square", "circle", "full-bleed", "text-only")

#: At or below this size the tiled assets go flat: no shadow, a bigger glyph.
SMALL = 48


def glyph_defs() -> str:
    """The glyph once, for a document whose inline marks point at it (``asset(..., shared=True)``)."""
    return f'<svg width="0" height="0" style="position:absolute"><defs><path id="nu-glyph" d="{PATH}"/></defs></svg>'


def _mark(h: float, fill: str, shared: bool = False) -> str:
    """The glyph placed on a 1024 canvas by its height."""
    s = h / GH
    w = GW * s
    glyph = (
        f'<use href="#nu-glyph" fill="{fill}"/>' if shared else f'<path d="{PATH}" fill="{fill}"/>'
    )
    return (
        f'<g transform="translate({(1024 - w) / 2:.2f},{(1024 - h) / 2:.2f}) scale({s:.5f}) '
        f'translate({-GX},{-GY})"><g transform="translate(0,552) scale(.1,-.1)">{glyph}</g></g>'
    )


def _layer(blur: int, dy: int, tint: str, op: float, name: str) -> str:
    return (
        f'<feGaussianBlur in="SourceAlpha" stdDeviation="{blur}"/><feOffset dy="{dy}" result="{name}o"/>'
        f'<feFlood flood-color="{tint}" flood-opacity="{op}"/>'
        f'<feComposite in2="{name}o" operator="in" result="{name}"/>'
    )


def _shadow(uid: str) -> str:
    return (
        f'<filter id="sh{uid}" x="-30%" y="-30%" width="160%" height="180%">'
        + _layer(5, 6, "#1b0d4d", 0.35, "c")
        + _layer(42, 40, "#120638", 0.42, "w")
        + '<feMerge><feMergeNode in="w"/><feMergeNode in="c"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )


def _ground(spec: dict[str, str], uid: str) -> str:
    return (
        f'<linearGradient id="t{uid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{spec["mark.from"]}"/>'
        f'<stop offset=".5" stop-color="{spec["mark.mid"]}"/>'
        f'<stop offset="1" stop-color="{spec["mark.to"]}"/></linearGradient>'
        f'<radialGradient id="hl{uid}" cx=".2" cy=".05" r=".9"><stop offset="0" stop-color="#fff" stop-opacity=".35"/>'
        '<stop offset=".5" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="dk{uid}" cx=".8" cy="1.05" r=".8"><stop offset="0" stop-color="#05081a" stop-opacity=".45"/>'
        '<stop offset="1" stop-color="#05081a" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="rim{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".45"/>'
        '<stop offset=".35" stop-color="#fff" stop-opacity=".04"/><stop offset="1" stop-color="#fff" stop-opacity=".02"/>'
        "</linearGradient>"
        f'<linearGradient id="m{uid}" x1="0" y1="1" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{spec["mark.glyph-from"]}"/>'
        f'<stop offset="1" stop-color="{spec["mark.glyph-to"]}"/></linearGradient>'
    )


def asset(
    spec: dict[str, str], name: str, *, small: bool = False, shared: bool = False, uid: str = ""
) -> str:
    """One asset as an SVG document. ``small`` is the flat variant for 48px and below.

    ``shared`` points the glyph at :func:`glyph_defs` instead of carrying it,
    for marks drawn inline many times in one html document; ``uid`` keeps
    their gradient ids apart when they differ.
    """
    mark_h = num(spec, "mark.size")
    radius = num(spec, "mark.radius")
    shadow = spec.get("mark.shadow", "on") == "on" and not small
    if name == "text-only":
        stops = [spec[f"mark.text-{i}"] for i in (1, 2, 3, 4)]
        grad = "".join(
            f'<stop offset="{o}" stop-color="{c}"/>'
            for o, c in zip((0, 0.3, 0.62, 1), stops, strict=False)
        )
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="222 222 580 580">'
            f'<defs><linearGradient id="g{uid}" x1="0" y1="1" x2="1" y2="0">{grad}</linearGradient></defs>'
            f"{_mark(560, f'url(#g{uid})', shared)}</svg>"
        )
    if name == "square":
        h = mark_h * (600 / 560 if small else 1)
        draw = lambda a: f'<rect width="1024" height="1024" rx="{radius:g}" {a}/>'  # noqa: E731
        rim = (
            f'<rect x="2" y="2" width="1020" height="1020" rx="{max(radius - 2, 0):g}" '
            f'fill="none" stroke="url(#rim{uid})" stroke-width="4"/>'
        )
        clip, defs = "", ""
    else:
        # The round and full bleed marks sit smaller, as in the build: 400 of the square's 560.
        h = mark_h * (400 / 560) * (460 / 400 if small else 1)
        draw = lambda a: f'<rect width="1024" height="1024" {a}/>'  # noqa: E731
        if name == "circle":
            defs = f'<clipPath id="cc{uid}"><circle cx="512" cy="512" r="512"/></clipPath>'
            clip = f'clip-path="url(#cc{uid})"'
            rim = f'<circle cx="512" cy="512" r="510" fill="none" stroke="url(#rim{uid})" stroke-width="4"/>'
        else:
            defs, clip, rim = "", "", ""
    mark = _mark(h, f"url(#m{uid})", shared)
    body = "".join(draw(f'fill="url(#{g}{uid})"') for g in ("t", "hl", "dk"))
    body += f'<g filter="url(#sh{uid})">{mark}</g>' if shadow else mark
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">'
        f"<defs>{_ground(spec, uid)}{_shadow(uid) if shadow else ''}{defs}</defs>"
        f"<g {clip}>{body}</g>{rim}</svg>"
    )


def lockup(spec: dict[str, str], ink: str, *, shared: bool = False, uid: str = "lk") -> str:
    """The text-only mark beside the wordmark, as one SVG (Inter 600, as the site sets it)."""
    mark = asset(spec, "text-only", shared=shared, uid=uid).replace(
        "<svg ", '<svg x="0" y="0" width="64" height="64" ', 1
    )
    weight = int(num(spec, "type.title-weight"))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 64">'
        f"{mark}"
        f'<text x="78" y="44" font-family="{spec["type.sans"]}, sans-serif" font-size="38" font-weight="{weight}" '
        f'letter-spacing="-0.6" fill="{ink}">nustack</text></svg>'
    )


def data_url(svg: str) -> str:
    """An SVG as a data url, for an ``<img src>`` or an ``ImageRef``."""
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def _turn(c: str, dh: float, ds: float = 0.0, dl: float = 0.0) -> str:
    h, lightness, s = colorsys.rgb_to_hls(*color.rgb(c))
    r, g, b = colorsys.hls_to_rgb(
        (h + dh) % 1.0, min(1, max(0, lightness + dl)), min(1, max(0, s + ds))
    )
    return "#" + "".join(f"{round(x * 255):02x}" for x in (r, g, b))


#: The walks a variant takes from the current ground: hue turn, saturation, lightness, per stop.
_WALKS = (
    ("warmer", (0.04, 0, 0), (0.03, 0, 0), (0.02, 0, 0)),
    ("cooler", (-0.04, 0, 0), (-0.03, 0, 0), (-0.02, 0, 0)),
    ("deeper", (0, 0.05, -0.08), (0, 0.05, -0.08), (0, 0.05, -0.06)),
    ("lighter", (0, -0.04, 0.07), (0, -0.04, 0.06), (0, -0.03, 0.05)),
    ("wider", (-0.05, 0, 0), (0, 0, 0), (0.05, 0, 0)),
    ("narrower", (0.03, 0, 0), (0, 0, 0), (-0.03, 0, 0)),
)


def variants(spec: dict[str, str]) -> list[dict[str, str]]:
    """Six grounds one step away from the spec's: each ``{name, mark.from, mark.mid, mark.to}``."""
    keys = ("mark.from", "mark.mid", "mark.to")
    out = []
    for name, *steps in _WALKS:
        v = {"name": name}
        for key, step in zip(keys, steps, strict=False):
            v[key] = _turn(spec[key], *step)
        out.append(v)
    return out
