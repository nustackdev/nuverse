"""Meridian, the made-up product every recipe is a page of: a network of small observatories.

Plain Python, no Refs: the seed data the pages draw, and :func:`sky`, a
night sky drawn as an SVG data URI so a page has pictures with nothing to
fetch. Everything here is fixed, so a page drawn twice is the same page.
"""

from __future__ import annotations

import datetime
import math
import random
from typing import TYPE_CHECKING
from urllib.parse import quote


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = [
    "INSTRUMENTS",
    "LINKS",
    "NIGHTS",
    "SITES",
    "TONIGHT",
    "instrument",
    "links",
    "night_labels",
    "night_series",
    "sky",
]


#: Where a page's links go, by the name of the page they open. In-page
#: anchors by default, so a page drawn alone (a story, a test) goes nowhere;
#: a host that serves the pages passes its own routes to ``page(links=...)``.
LINKS = {
    "dashboard": "#dashboard",
    "detail": "#detail",
    "catalog": "#catalog",
    "settings": "#settings",
    "landing": "#landing",
}


def links(overrides: Mapping[str, str] | None) -> dict[str, str]:
    """:data:`LINKS` with a host's routes over it."""
    return {**LINKS, **(overrides or {})}


#: The observing sites, west to east.
SITES = ("Atacama", "La Palma", "Namibia", "Siding Spring")

#: Nights the dashboard charts, oldest first, up to and with :data:`TONIGHT`.
NIGHTS = 30

#: The night every page is drawn on.
TONIGHT = datetime.date(2026, 10, 25)


#: The instruments a page lists, links to and draws. ``seed`` and ``hue``
#: pick the instrument's picture: the same seed draws the same sky.
INSTRUMENTS = (
    {
        "id": "kestrel",
        "name": "Kestrel 2",
        "kind": "Reflector",
        "aperture": "0.6 m",
        "site": "Atacama",
        "status": "open",
        "queue": 12,
        "seeing": "0.7 arcsec",
        "summary": "Wide field CMOS reflector for transients and variable stars.",
        "seed": 7,
        "hue": "violet",
    },
    {
        "id": "osprey",
        "name": "Osprey",
        "kind": "Refractor",
        "aperture": "0.2 m",
        "site": "La Palma",
        "status": "open",
        "queue": 5,
        "seeing": "0.9 arcsec",
        "summary": "Fast apochromat for nebulae and narrowband imaging.",
        "seed": 11,
        "hue": "blue",
    },
    {
        "id": "harrier",
        "name": "Harrier",
        "kind": "Spectrograph",
        "aperture": "1.0 m",
        "site": "Namibia",
        "status": "busy",
        "queue": 21,
        "seeing": "1.1 arcsec",
        "summary": "Echelle spectrograph on a meter class mount, for radial velocities.",
        "seed": 23,
        "hue": "teal",
    },
    {
        "id": "merlin",
        "name": "Merlin",
        "kind": "Reflector",
        "aperture": "0.4 m",
        "site": "Siding Spring",
        "status": "closed",
        "queue": 0,
        "seeing": "n/a",
        "summary": "Southern sky survey scope, down for a mirror recoat until Friday.",
        "seed": 31,
        "hue": "rose",
    },
    {
        "id": "kite",
        "name": "Kite",
        "kind": "Solar",
        "aperture": "0.15 m",
        "site": "La Palma",
        "status": "open",
        "queue": 3,
        "seeing": "1.4 arcsec",
        "summary": "Hydrogen alpha solar telescope, booked by the hour in daylight.",
        "seed": 43,
        "hue": "amber",
    },
    {
        "id": "falcon",
        "name": "Falcon",
        "kind": "Reflector",
        "aperture": "0.8 m",
        "site": "Atacama",
        "status": "open",
        "queue": 9,
        "seeing": "0.6 arcsec",
        "summary": "Photometry workhorse with a filter wheel of twelve.",
        "seed": 53,
        "hue": "blue",
    },
)


def instrument(instrument_id: str) -> dict[str, object]:
    """One instrument by id."""
    return next(i for i in INSTRUMENTS if i["id"] == instrument_id)


def night_labels(n: int = NIGHTS) -> list[str]:
    """The last ``n`` nights as axis labels, "Sep 26" to "Oct 25"."""
    days = [TONIGHT - datetime.timedelta(days=k) for k in range(n - 1, -1, -1)]
    return [f"{d:%b} {d.day}" for d in days]


def night_series(
    seed: int, base: float, swing: float, n: int = NIGHTS, places: int = 1
) -> list[float]:
    """``n`` nights of a value wandering around ``base`` by up to ``swing``, rounded to ``places``."""
    rng = random.Random(seed)  # noqa: S311 -- seeded on purpose: a chart, not a secret
    out = []
    for i in range(n):
        wave = math.sin(i / 4.2 + seed) * 0.5 + math.sin(i / 1.7 + seed * 0.3) * 0.25
        out.append(round(base + swing * (wave + rng.uniform(-0.35, 0.35)), places))
    return out


# The nebula colors per hue: a deep ground, then two glows. Fixed hex rather
# than kit tokens, since a data URI image never sees the page's CSS.
_HUES = {
    "violet": ("#0b0820", "#8946db", "#1e63b8"),
    "blue": ("#060b1d", "#1e63b8", "#2aa3a0"),
    "teal": ("#04110f", "#1f8f7a", "#1e63b8"),
    "rose": ("#13060f", "#c2417a", "#8946db"),
    "amber": ("#140b04", "#d1782a", "#c2417a"),
}


def sky(seed: int, hue: str = "violet", width: int = 800, height: int = 450) -> str:
    """A night sky as an SVG data URI: a ground, two soft glows and a field of stars.

    Args:
        seed: picks the stars and where the glows sit. The same seed is the
            same picture.
        hue: one of violet, blue, teal, rose, amber.
        width: the picture's width in px; with ``height``, its aspect too.
        height: the picture's height in px.
    """
    rng = random.Random(seed)  # noqa: S311 -- seeded on purpose: a picture, not a secret
    ground, glow, second = _HUES[hue]
    gx, gy = rng.uniform(0.25, 0.75) * width, rng.uniform(0.3, 0.7) * height
    sx, sy = rng.uniform(0.1, 0.9) * width, rng.uniform(0.2, 0.8) * height
    stars = []
    for _ in range(110):
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        r = rng.choice((0.5, 0.6, 0.7, 0.8, 1.0, 1.0, 1.3, 1.8))
        stars.append(
            f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" opacity="{rng.uniform(0.35, 1):.2f}"/>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        "<defs>"
        f'<radialGradient id="a" cx="{gx / width:.2f}" cy="{gy / height:.2f}" r="0.6">'
        f'<stop offset="0" stop-color="{glow}" stop-opacity="0.75"/>'
        f'<stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="b" cx="{sx / width:.2f}" cy="{sy / height:.2f}" r="0.45">'
        f'<stop offset="0" stop-color="{second}" stop-opacity="0.55"/>'
        f'<stop offset="1" stop-color="{second}" stop-opacity="0"/></radialGradient>'
        "</defs>"
        f'<rect width="{width}" height="{height}" fill="{ground}"/>'
        f'<rect width="{width}" height="{height}" fill="url(#a)"/>'
        f'<rect width="{width}" height="{height}" fill="url(#b)"/>'
        f'<g fill="#fff">{"".join(stars)}</g>'
        "</svg>"
    )
    # Only what a data URI cannot carry as is gets escaped, which keeps it small.
    return "data:image/svg+xml;charset=utf-8," + quote(svg, safe=" =:/'\".,-")
