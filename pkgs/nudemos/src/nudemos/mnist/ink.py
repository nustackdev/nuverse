"""Ink: strokes drawn on a pad, made into a 28x28 digit the way MNIST made its digits.

MNIST's digits were scanned pen strokes, cropped to the ink, scaled to fit a
20x20 box with their aspect kept, antialiased, and placed in a 28x28 field
with their center of mass at its center. :func:`strokes_to_image` does the
same to strokes from a pad: it draws them with a round brush on a large
canvas, crops to the ink, scales it into 20x20 with a high quality filter,
and shifts it by its center of mass.

The brush is sized from the drawing, not from the pad: a digit drawn small
or large comes out at MNIST's stroke weight either way.

What comes out is pixels in 0..1, ink high, as MNIST stores them. The model
normalizes them by MNIST's mean and std (:data:`~.trainer.MEAN`,
:data:`~.trainer.STD`) at its input, for training and reading alike.

:data:`SAMPLES` are hand authored strokes for each digit, a few styles each,
and :func:`sample` draws one with a little jitter: the "draw a sample"
button, and the quality test of the whole path.
"""

from __future__ import annotations

import itertools
import math
import random


__all__ = ["BOX", "BRUSH", "SAMPLES", "SIZE", "blank", "sample", "strokes_of", "strokes_to_image"]


#: The field, and the box the ink is scaled to fit inside it.
SIZE, BOX = 28, 20

#: Brush width as a fraction of the drawing's longer side.
BRUSH = 0.15

#: Pixels on the longer side of the drawing, on the canvas it is drawn on.
_SPAN = 400

#: The least side a drawing is taken to have, in pad units: a dot does not blow up.
_LEAST = 0.04

Strokes = list[list[list[float]]]


def blank() -> list[list[float]]:
    """An empty field: what a blank pad reads as."""
    return [[0.0] * SIZE for _ in range(SIZE)]


def strokes_of(value: object) -> Strokes:
    """A pad's value as plain strokes: lists of ``[x, y]``.

    Takes the strokes as they are, or a board's elements, keeping the points of
    its ``path`` elements only and dropping a third (pressure) value per point.
    Anything else reads as no strokes.
    """
    out: Strokes = []
    for item in value if isinstance(value, list | tuple) else []:
        if isinstance(item, dict):
            if item.get("type") != "path":
                continue
            item = item.get("points") or []
        if isinstance(item, list | tuple):
            points = [
                [float(p[0]), float(p[1])]
                for p in item
                if isinstance(p, list | tuple) and len(p) >= 2
            ]
            if points:
                out.append(points)
    return out


def _points(strokes: Strokes) -> list[list[tuple[float, float]]]:
    out = []
    for stroke in strokes or []:
        pts = [(float(p[0]), float(p[1])) for p in stroke if len(p) >= 2]
        if pts:
            out.append(pts)
    return out


def strokes_to_image(strokes: Strokes) -> list[list[float]]:
    """Strokes in 0..1 (origin top-left) as a 28x28 MNIST-like digit, rows of pixels in 0..1.

    Empty strokes give a blank field.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    lines = _points(strokes)
    if not lines:
        return blank()
    xs = [x for s in lines for x, _ in s]
    ys = [y for s in lines for _, y in s]
    side = max(max(xs) - min(xs), max(ys) - min(ys), _LEAST)
    scale = _SPAN / side
    width = max(2, round(BRUSH * _SPAN))
    pad = width
    w = round((max(xs) - min(xs)) * scale) + 2 * pad
    h = round((max(ys) - min(ys)) * scale) + 2 * pad

    def at(x: float, y: float) -> tuple[float, float]:
        return (x - min(xs)) * scale + pad, (y - min(ys)) * scale + pad

    canvas = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(canvas)
    r = width / 2
    for stroke in lines:
        pts = [at(x, y) for x, y in stroke]
        if len(pts) > 1:
            draw.line(pts, fill=255, width=width, joint="curve")
        # Round caps, and a dot for a stroke of one point.
        for x, y in pts if len(pts) < 3 else (pts[0], pts[-1]):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=255)

    ink = canvas.getbbox()
    if ink is None:
        return blank()
    crop = canvas.crop(ink)
    cw, ch = crop.size
    fit = BOX / max(cw, ch)
    small = crop.resize((max(1, round(cw * fit)), max(1, round(ch * fit))), Image.LANCZOS)
    patch = np.asarray(small, dtype=np.float32) / 255.0
    patch = np.clip(patch, 0.0, 1.0)

    # Place it by its center of mass: that point lands at the field's center.
    total = float(patch.sum())
    ph, pw = patch.shape
    if total > 0:
        cy = float((patch.sum(1) * np.arange(ph)).sum()) / total
        cx = float((patch.sum(0) * np.arange(pw)).sum()) / total
    else:
        cy, cx = (ph - 1) / 2, (pw - 1) / 2
    top, left = round((SIZE - 1) / 2 - cy), round((SIZE - 1) / 2 - cx)
    field = np.zeros((SIZE, SIZE), dtype=np.float32)
    y0, x0 = max(top, 0), max(left, 0)
    y1, x1 = min(top + ph, SIZE), min(left + pw, SIZE)
    if y1 > y0 and x1 > x0:
        field[y0:y1, x0:x1] = patch[y0 - top : y1 - top, x0 - left : x1 - left]
    return [[round(float(v), 4) for v in row] for row in field]


# --- samples -----------------------------------------------------------------------------------


def _arc(cx: float, cy: float, rx: float, ry: float, a0: float, a1: float, n: int = 24) -> list:
    """Points on an ellipse from angle ``a0`` to ``a1``, in degrees, 0 at 3 o'clock, clockwise (y runs down)."""
    return [
        [
            cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
            cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)),
        ]
        for i in range(n + 1)
    ]


def _line(*pts: tuple[float, float], n: int = 8) -> list:
    """A polyline through ``pts``, each leg cut in ``n`` points, as a hand moves."""
    out = [list(pts[0])]
    for (ax, ay), (bx, by) in itertools.pairwise(pts):
        out += [[ax + (bx - ax) * i / n, ay + (by - ay) * i / n] for i in range(1, n + 1)]
    return out


#: A few hand written styles per digit, each a list of strokes in a unit box.
SAMPLES: dict[int, list[Strokes]] = {
    0: [
        [_arc(0.5, 0.5, 0.28, 0.4, -90, 275, 40)],
        [_arc(0.5, 0.5, 0.22, 0.38, -100, 265, 40)],
        [_arc(0.5, 0.52, 0.3, 0.36, 250, -95, 40)],
    ],
    1: [
        [_line((0.52, 0.12), (0.5, 0.88))],
        [_line((0.36, 0.28), (0.54, 0.12), (0.54, 0.88))],
        [_line((0.56, 0.12), (0.46, 0.88))],
    ],
    2: [
        [
            _arc(0.5, 0.33, 0.24, 0.21, 190, 360, 18)
            + _line((0.74, 0.33), (0.26, 0.86), (0.78, 0.86))
        ],
        [
            _arc(0.48, 0.32, 0.22, 0.2, 200, 380, 18)
            + _line((0.68, 0.4), (0.28, 0.84), (0.74, 0.82))
        ],
        [
            _arc(0.5, 0.35, 0.25, 0.23, 180, 340, 18)
            + _line((0.73, 0.27), (0.6, 0.55), (0.3, 0.85), (0.8, 0.85))
        ],
    ],
    3: [
        [_arc(0.47, 0.3, 0.23, 0.18, 200, 450, 20) + _arc(0.47, 0.68, 0.26, 0.2, -90, 160, 20)],
        [
            _line((0.28, 0.14), (0.7, 0.14), (0.45, 0.45))
            + _arc(0.47, 0.66, 0.25, 0.21, -90, 160, 20)
        ],
        [_arc(0.5, 0.31, 0.22, 0.18, 210, 440, 20) + _arc(0.5, 0.67, 0.25, 0.21, -80, 150, 20)],
    ],
    4: [
        [_line((0.58, 0.12), (0.24, 0.62), (0.8, 0.62)), _line((0.64, 0.38), (0.64, 0.9))],
        [_line((0.3, 0.12), (0.26, 0.55), (0.76, 0.55)), _line((0.7, 0.12), (0.7, 0.9))],
        [_line((0.62, 0.1), (0.2, 0.6), (0.82, 0.6)), _line((0.62, 0.1), (0.6, 0.9))],
    ],
    5: [
        [
            _line((0.72, 0.13), (0.34, 0.13), (0.3, 0.46))
            + _arc(0.49, 0.65, 0.25, 0.22, -120, 150, 22)
        ],
        [
            _line((0.3, 0.14), (0.3, 0.45)) + _arc(0.5, 0.64, 0.24, 0.22, -125, 145, 22),
            _line((0.3, 0.14), (0.72, 0.12)),
        ],
        [
            _line((0.74, 0.12), (0.36, 0.14), (0.32, 0.44))
            + _arc(0.5, 0.66, 0.26, 0.22, -110, 160, 22)
        ],
    ],
    6: [
        [_arc(0.62, 0.5, 0.3, 0.4, 250, 160, 18) + _arc(0.5, 0.68, 0.2, 0.2, 180, 540, 26)],
        [_line((0.66, 0.12), (0.36, 0.48), (0.3, 0.68)) + _arc(0.5, 0.7, 0.2, 0.18, 180, 520, 26)],
        [_arc(0.66, 0.52, 0.34, 0.4, 245, 170, 18) + _arc(0.52, 0.7, 0.2, 0.18, 170, 530, 26)],
    ],
    7: [
        [_line((0.24, 0.15), (0.76, 0.15), (0.42, 0.88))],
        [_line((0.26, 0.2), (0.3, 0.14), (0.78, 0.14), (0.5, 0.88))],
        [_line((0.24, 0.15), (0.76, 0.15), (0.44, 0.88)), _line((0.4, 0.5), (0.72, 0.5))],
    ],
    8: [
        [_arc(0.5, 0.3, 0.2, 0.17, 90, -270, 26) + _arc(0.5, 0.68, 0.24, 0.2, -90, 270, 26)],
        [_arc(0.5, 0.31, 0.18, 0.18, 0, 360, 26), _arc(0.5, 0.69, 0.23, 0.19, -90, 270, 26)],
        [_arc(0.52, 0.3, 0.19, 0.17, 120, -240, 26) + _arc(0.48, 0.68, 0.24, 0.2, -80, 280, 26)],
    ],
    9: [
        [_arc(0.48, 0.33, 0.22, 0.2, 0, -360, 28) + _line((0.7, 0.33), (0.66, 0.9))],
        [_arc(0.5, 0.3, 0.2, 0.18, 10, -350, 28) + _line((0.7, 0.27), (0.56, 0.9))],
        [_arc(0.47, 0.32, 0.23, 0.2, 0, -360, 28) + _line((0.7, 0.32), (0.7, 0.9))],
    ],
}


def sample(digit: int | None = None, seed: int | None = None) -> list:
    """``[digit, strokes]``: one of :data:`SAMPLES`, scaled, slanted, moved and wobbled a little.

    Random ``digit`` when left out. The strokes stay inside the unit box.
    """
    rng = random.Random(seed)  # noqa: S311 - a doodle, not a secret
    digit = rng.randrange(10) if digit is None else int(digit)
    strokes = rng.choice(SAMPLES[digit])
    size = rng.uniform(0.55, 0.9)
    sx = size * rng.uniform(0.85, 1.1)
    turn = math.radians(rng.uniform(-10, 10))
    slant = rng.uniform(-0.25, 0.1)
    dx, dy = rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08)
    cos, sin = math.cos(turn), math.sin(turn)

    def move(x: float, y: float) -> list[float]:
        x, y = x - 0.5, y - 0.5
        x += slant * y
        x, y = x * cos - y * sin, x * sin + y * cos
        x = x * sx + 0.5 + dx + rng.gauss(0, 0.004)
        y = y * size + 0.5 + dy + rng.gauss(0, 0.004)
        return [round(min(max(x, 0.0), 1.0), 4), round(min(max(y, 0.0), 1.0), 4)]

    return [digit, [[move(x, y) for x, y in s] for s in strokes]]
