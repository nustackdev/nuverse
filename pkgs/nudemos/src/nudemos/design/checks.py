"""The checks a spec must pass: contrast for every pair that has to read, and the language's rules.

Contrast is WCAG 2, computed, never eyeballed (``language/a11y.md``): each
pair is a foreground on the ground under it, with the bar it must clear and
the target it should reach, in both themes. Rules are the rest of the
language said as tests: the 4px grid, a ladder that only climbs, motion in
four steps, gentle radii.

Plain Python, no Nu. :func:`run` is what the Checks page and every badge read.
"""

from __future__ import annotations

import itertools

from . import color
from .spec import THEMES, num, theme


__all__ = ["PAIRS", "RULES", "grid", "run", "summary"]


#: ``(fg, bg, min, target, what)``: the pairs that must read, per theme.
PAIRS: tuple[tuple[str, str, float, float, str], ...] = (
    ("ink-1", "ground", 4.5, 7.0, "body text"),
    ("ink-1", "ground-card", 4.5, 7.0, "body text on a card"),
    ("ink-2", "ground", 4.5, 5.0, "secondary text"),
    ("ink-2", "ground-card", 4.5, 5.0, "secondary text on a card"),
    ("ink-3", "ground", 4.5, 4.5, "labels, metadata"),
    ("ink-3", "ground-deep", 4.5, 4.5, "labels in a sidebar"),
    ("ink-twilight", "ground", 3.0, 4.5, "headline second tone"),
    ("on-afterglow", "afterglow", 4.5, 5.0, "label on a primary button"),
    ("on-afterglow", "afterglow-hover", 4.5, 5.0, "label on a hovered primary"),
    ("afterglow-text", "ground", 4.5, 5.0, "Afterglow as text"),
    ("afterglow-text", "afterglow-soft", 4.5, 4.5, "text on an Afterglow chip"),
    ("afterglow-focus", "ground-card", 3.0, 3.0, "the focus ring"),
    ("starlight", "ground", 4.5, 5.0, "Starlight as text"),
    ("starlight", "starlight-soft", 4.5, 4.5, "text on an info chip"),
    ("aurora", "ground", 4.5, 5.0, "good"),
    ("sunset", "ground", 4.5, 5.0, "careful"),
    ("ember", "ground", 4.5, 5.0, "wrong"),
    ("moonlight", "ground", 4.5, 5.0, "a note"),
    ("aurora", "aurora-soft", 4.5, 4.5, "good, on its fill"),
    ("ember", "ember-soft", 4.5, 4.5, "wrong, on its fill"),
    ("on-afterglow", "ember-solid", 4.5, 5.0, "label on a delete button"),
    ("line-strong", "ground-card", 1.3, 1.7, "control edges"),
    ("chart-1", "ground-card", 3.0, 3.0, "chart slot 1"),
    ("chart-2", "ground-card", 3.0, 3.0, "chart slot 2"),
    ("chart-3", "ground-card", 3.0, 3.0, "chart slot 3"),
    ("chart-4", "ground-card", 3.0, 3.0, "chart slot 4"),
)


def grid(spec: dict[str, str]) -> list[int]:
    """The spacing scale: the language's twelve steps, in units of ``space.unit``."""
    u = num(spec, "space.unit")
    return [round(u * k) for k in (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24)]


def _rules(spec: dict[str, str]) -> list[tuple[str, bool, str]]:
    """``(rule, ok, what is seen)`` for the language's rules."""
    out = []
    unit = num(spec, "space.unit")
    out.append(("grid is 4px", unit == 4, f"space.unit is {unit:g}"))
    ladder = [
        num(spec, f"type.{s}")
        for s in ("xs", "sm", "base", "lg", "xl", "2xl", "3xl", "display", "hero")
    ]
    climbs = all(b > a for a, b in itertools.pairwise(ladder))
    out.append(("type ladder climbs", climbs, " < ".join(f"{v:g}" for v in ladder)))
    out.append(("nothing under 11px ships", ladder[0] >= 11, f"type.xs is {ladder[0]:g}"))
    radii = [num(spec, f"radius.{s}") for s in ("sm", "md", "lg", "xl")]
    out.append(
        (
            "radii climb, gently",
            all(b >= a for a, b in itertools.pairwise(radii)) and radii[-1] <= 16,
            " / ".join(f"{r:g}" for r in radii),
        )
    )
    on_grid = all(r % 2 == 0 for r in radii)
    out.append(("radii on the half grid", on_grid, " / ".join(f"{r:g}" for r in radii)))
    steps = [num(spec, f"motion.{s}") for s in ("fast", "base", "slow")]
    out.append(
        (
            "motion is calm, under 400ms",
            max(steps) <= 400 and steps == sorted(steps),
            " / ".join(f"{s:g}ms" for s in steps),
        )
    )
    weight = num(spec, "type.title-weight")
    out.append(
        ("titles at 600, 700 rare", weight in (500, 590, 600), f"type.title-weight is {weight:g}")
    )
    for t in THEMES:
        th = theme(spec, t)
        glow = color.oklch(th["afterglow"])[1]
        out.append((f"Afterglow stays decisive, {t}", glow >= 0.12, f"chroma {glow:.3f}"))
    return out


#: The rules by name, for the Checks page's legend.
RULES = tuple(r for r, _, _ in _rules({}))


def run(spec: dict[str, str]) -> dict[str, list[dict[str, object]]]:
    """Every check: ``pairs`` (one row per pair, both themes) and ``rules``."""
    themes = {t: theme(spec, t) for t in THEMES}
    pairs = []
    for fg, bg, low, target, what in PAIRS:
        row: dict[str, object] = {
            "key": f"{fg} on {bg}",
            "pair": f"{fg} on {bg}".replace("on-afterglow", "white"),
            "what": what,
            "min": low,
            "target": target,
        }
        worst = "pass"
        for t in THEMES:
            r = color.contrast(themes[t][fg], themes[t][bg])
            row[t] = round(r, 2)
            row[f"{t}_fg"], row[f"{t}_bg"] = themes[t][fg], themes[t][bg]
            if r < low:
                worst = "fail"
            elif r < target and worst == "pass":
                worst = "under target"
        row["verdict"] = worst
        pairs.append(row)
    rules = [
        {"key": r, "rule": r, "ok": ok, "seen": seen, "verdict": "pass" if ok else "fail"}
        for r, ok, seen in _rules(spec)
    ]
    return {"pairs": pairs, "rules": rules}


def summary(spec: dict[str, str]) -> dict[str, int]:
    """Counts: ``pass``, ``under`` (under target), ``fail``, over pairs and rules together."""
    res = run(spec)
    rows = res["pairs"] + res["rules"]
    return {
        "pass": sum(1 for r in rows if r["verdict"] == "pass"),
        "under": sum(1 for r in rows if r["verdict"] == "under target"),
        "fail": sum(1 for r in rows if r["verdict"] == "fail"),
        "total": len(rows),
    }
