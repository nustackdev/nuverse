"""The spec: every nustack design token, its defaults, and the knobs that move many at once.

One flat ``key -> str`` dict. Colors carry a value per theme, keyed
``dusk:<token>`` and ``dawn:<token>``; everything else has one value, keyed
``<group>.<name>`` (``type.base``, ``radius.md``, ``motion.fast``,
``mark.size``). The space stores only what someone changed; a key never
written reads :data:`DEFAULTS`, so dropping a key puts it back.

Values are the language's own (``go/projects/nustackdev/design/language``):
Dusk and Dawn grounds on hue 264, Afterglow Violet on 300, Starlight Blue on
256, the four state colors, the eight chart slots, the type ladder, the 4px
grid, four radii, four durations, and the mark's build settings.

Knobs (``knob.*``) are the spec's own levers: the sky's lean, how much tint
it carries, Afterglow's and Starlight's hues. Moving one rewrites every token
it governs (:func:`apply_knob`), keeping each token's lightness and chroma:
the palette turns as one.

Plain Python, no Nu.
"""

from __future__ import annotations

from . import color


__all__ = [
    "COLORS",
    "DEFAULTS",
    "GROUPS",
    "KNOBS",
    "SCALARS",
    "THEMES",
    "apply_knob",
    "changed",
    "describe",
    "merged",
    "num",
    "theme",
]


THEMES = ("dusk", "dawn")


#: Every color token: ``(group, token, dusk, dawn, use)``, in the order the spec shows them.
COLORS: tuple[tuple[str, str, str, str, str], ...] = (
    ("ground", "ground-deep", "#13161d", "#f7f8fa", "sidebars, wells, status bars"),
    ("ground", "ground", "#15181f", "#f9fafc", "the page canvas"),
    ("ground", "ground-raised", "#191c24", "#ffffff", "app main, the document"),
    ("ground", "ground-card", "#1e222a", "#ffffff", "cards, panels"),
    ("ground", "ground-overlay", "#292e37", "#ffffff", "menus, popovers, dialogs"),
    ("ground", "ground-hover", "#2e333d", "#f1f2f4", "an opaque hover step"),
    ("line", "line-subtle", "#232831", "#e5e6e8", "hairlines inside surfaces"),
    ("line", "line", "#2d323d", "#d9dadc", "default borders, dividers"),
    ("line", "line-strong", "#444a57", "#b3b4b6", "control edges, emphasis"),
    ("ink", "ink-1", "#eceef4", "#1a1d24", "primary text"),
    ("ink", "ink-2", "#bcc1cc", "#4e5158", "secondary text"),
    ("ink", "ink-3", "#9ba2ae", "#6a6d74", "labels, metadata"),
    ("ink", "ink-4", "#777d8a", "#8a8e94", "placeholders, disabled"),
    ("ink", "ink-twilight", "#abb2e3", "#5758af", "second tone of headlines"),
    ("afterglow", "afterglow", "#8946db", "#8946db", "primary fills"),
    ("afterglow", "afterglow-hover", "#7f3ccd", "#7f3ccd", "fill hover"),
    ("afterglow", "afterglow-pressed", "#7335bc", "#7335bc", "fill pressed"),
    ("afterglow", "afterglow-text", "#cbaeff", "#7638c0", "Afterglow as text"),
    ("afterglow", "afterglow-focus", "#a274ec", "#7638c0", "the focus ring"),
    ("afterglow", "afterglow-soft", "#3e2a5d", "#ede5fe", "chips, selected items"),
    ("starlight", "starlight", "#8cbcff", "#1e63b8", "data, information, live state"),
    ("starlight", "starlight-soft", "#1e3457", "#ddebfe", "info chips, data fills"),
    ("state", "aurora", "#65d391", "#00713f", "good"),
    ("state", "aurora-soft", "#153522", "#ddf6e4", "good, as a fill"),
    ("state", "sunset", "#f4b353", "#8d5401", "careful"),
    ("state", "sunset-soft", "#3f2b0d", "#ffeed4", "careful, as a fill"),
    ("state", "ember", "#ff8781", "#bb262c", "wrong"),
    ("state", "ember-soft", "#47201f", "#fee9e7", "wrong, as a fill"),
    ("state", "ember-solid", "#c72c34", "#bb262c", "destructive fills"),
    ("state", "moonlight", "#6fc7f2", "#03698e", "a note, worth knowing"),
    ("state", "moonlight-soft", "#0b3345", "#ddf2fe", "a note, as a fill"),
    ("chart", "chart-1", "#3392db", "#0268a7", "cobalt"),
    ("chart", "chart-2", "#efc558", "#a67e1b", "saffron"),
    ("chart", "chart-3", "#d36c9d", "#973069", "orchid"),
    ("chart", "chart-4", "#76e4f7", "#2692b3", "glacier"),
    ("chart", "chart-5", "#de6f53", "#ae391b", "terracotta"),
    ("chart", "chart-6", "#58dec1", "#1c9480", "lagoon"),
    ("chart", "chart-7", "#9887e8", "#5d43ac", "iris"),
    ("chart", "chart-8", "#faba80", "#cb6f1d", "apricot"),
)


#: Every token with one value for both themes: ``(group, key, value, use)``.
SCALARS: tuple[tuple[str, str, str, str], ...] = (
    ("type", "type.sans", "Inter", "every word"),
    ("type", "type.mono", "JetBrains Mono", "code, ids, figures that align"),
    ("type", "type.xs", "11", "micro labels, badges"),
    ("type", "type.sm", "12", "secondary text, dense cells"),
    ("type", "type.base", "13", "default app text"),
    ("type", "type.lg", "14", "controls"),
    ("type", "type.xl", "16", "reading"),
    ("type", "type.2xl", "20", "small titles, site copy"),
    ("type", "type.3xl", "24", "titles"),
    ("type", "type.display", "32", "headings, heroes"),
    ("type", "type.hero", "56", "the site's hero line"),
    ("type", "type.title-weight", "600", "titles"),
    ("type", "type.tracking", "-0.02", "display tracking, em"),
    ("space", "space.unit", "4", "the grid: everything snaps to it"),
    ("space", "space.control", "32", "control height, app"),
    ("radius", "radius.sm", "4", "badges, small chips"),
    ("radius", "radius.md", "6", "controls"),
    ("radius", "radius.lg", "8", "cards, panels"),
    ("radius", "radius.xl", "12", "large surfaces, frames"),
    ("motion", "motion.fast", "120", "hover, focus, small toggles"),
    ("motion", "motion.base", "180", "menus, popovers, tooltips"),
    ("motion", "motion.slow", "280", "dialogs, sheets"),
    ("motion", "motion.ease-out", "0.2, 0, 0, 1", "enter"),
    ("motion", "motion.ease-in", "0.4, 0, 1, 1", "leave"),
    ("motion", "motion.ease-in-out", "0.4, 0, 0.2, 1", "move"),
    ("mark", "mark.from", "#9a5cec", "tile ground, top left"),
    ("mark", "mark.mid", "#6a49d6", "tile ground, middle"),
    ("mark", "mark.to", "#1e63b8", "tile ground, bottom right"),
    ("mark", "mark.glyph-from", "#ffffff", "glyph, bottom left"),
    ("mark", "mark.glyph-to", "#dfe4f5", "glyph, top right"),
    ("mark", "mark.text-1", "#c7a6ff", "text-only mark, stop 1"),
    ("mark", "mark.text-2", "#9257e3", "text-only mark, stop 2"),
    ("mark", "mark.text-3", "#4f7fe0", "text-only mark, stop 3"),
    ("mark", "mark.text-4", "#1b4f98", "text-only mark, stop 4"),
    ("mark", "mark.size", "560", "glyph height on the 1024 tile"),
    ("mark", "mark.radius", "230", "tile corner radius on 1024"),
    ("mark", "mark.shadow", "on", "ambient shadow under the glyph"),
)


#: The levers: ``key -> (default, label, min, max, step)``.
KNOBS: dict[str, tuple[str, str, float, float, float]] = {
    "knob.sky": ("264", "Sky lean (hue)", 200, 330, 1),
    "knob.tint": ("1", "Sky tint", 0, 3, 0.1),
    "knob.afterglow": ("300", "Afterglow hue", 250, 345, 1),
    "knob.starlight": ("256", "Starlight hue", 200, 290, 1),
}

#: Which tokens each knob governs.
_SKY = ("ground", "line", "ink")
_GOVERNS: dict[str, tuple[str, ...]] = {
    "knob.sky": tuple(t for g, t, *_ in COLORS if g in _SKY),
    "knob.tint": tuple(t for g, t, *_ in COLORS if g in _SKY),
    "knob.afterglow": tuple(t for g, t, *_ in COLORS if g == "afterglow"),
    "knob.starlight": tuple(t for g, t, *_ in COLORS if g == "starlight"),
}
_MARK = {
    "knob.afterglow": ("mark.from", "mark.mid", "mark.text-1", "mark.text-2"),
    "knob.starlight": ("mark.to", "mark.text-3", "mark.text-4"),
}


DEFAULTS: dict[str, str] = {
    **{
        f"{t}:{tok}": v
        for _, tok, dusk, dawn, _ in COLORS
        for t, v in (("dusk", dusk), ("dawn", dawn))
    },
    **{k: v for _, k, v, _ in SCALARS},
    **{k: v[0] for k, v in KNOBS.items()},
}

#: The spec's groups, in order, for tables and filters.
GROUPS: tuple[str, ...] = (
    "ground",
    "line",
    "ink",
    "afterglow",
    "starlight",
    "state",
    "chart",
    "type",
    "space",
    "radius",
    "motion",
    "mark",
)


def merged(stored: dict[str, str] | None) -> dict[str, str]:
    """The spec in effect: :data:`DEFAULTS` with what was stored over it."""
    return {**DEFAULTS, **{k: str(v) for k, v in dict(stored or {}).items() if k in DEFAULTS}}


def changed(stored: dict[str, str] | None) -> dict[str, str]:
    """What differs from the defaults."""
    return {k: v for k, v in merged(stored).items() if v != DEFAULTS[k]}


def num(spec: dict[str, str], key: str) -> float:
    """A scalar token as a number, its default when it does not read as one."""
    try:
        return float(spec[key])
    except (KeyError, ValueError):
        return float(DEFAULTS[key])


def theme(spec: dict[str, str], name: str) -> dict[str, str]:
    """One theme's colors by token, plus the washes the language derives from ``ink-1``."""
    out = {tok: spec.get(f"{name}:{tok}", DEFAULTS[f"{name}:{tok}"]) for _, tok, *_ in COLORS}
    for tok, v in out.items():
        if not color.is_hex(v):
            out[tok] = DEFAULTS[f"{name}:{tok}"]
    hover, press = (0.07, 0.11) if name == "dusk" else (0.05, 0.09)
    out["hover"] = color.mix(out["ink-1"], out["ground-card"], hover)
    out["press"] = color.mix(out["ink-1"], out["ground-card"], press)
    out["afterglow-line"] = color.mix(out["afterglow"], out["ground-card"], 0.44)
    out["selection"] = color.mix(
        out["starlight"], out["ground-card"], 0.24 if name == "dusk" else 0.18
    )
    out["on-afterglow"] = "#ffffff"
    return out


def describe(key: str) -> tuple[str, str]:
    """``(group, use)`` of a key."""
    tok = key.split(":", 1)[-1]
    for g, t, _, _, use in COLORS:
        if t == tok:
            return g, use
    for g, k, _, use in SCALARS:
        if k == key:
            return g, use
    if key in KNOBS:
        return "knob", KNOBS[key][1]
    return "", ""


def apply_knob(spec: dict[str, str], key: str, value: float) -> dict[str, str]:
    """The writes a knob at ``value`` makes: the knob itself and every token it governs.

    Each governed token keeps its default's lightness and chroma and takes the
    hue it had, turned by how far the knob moved; ``knob.tint`` scales the
    sky's chroma instead (0 is neutral gray, 1 the language, 3 a blue sky).
    """
    spec = merged(spec)
    sky = num(spec, "knob.sky") if key != "knob.sky" else value
    tint = num(spec, "knob.tint") if key != "knob.tint" else value
    out = {key: f"{value:g}"}
    if key in ("knob.sky", "knob.tint"):
        turned = sky - float(KNOBS["knob.sky"][0])
        for t in THEMES:
            for tok in _GOVERNS[key]:
                lab_l, c, h = color.oklch(DEFAULTS[f"{t}:{tok}"])
                out[f"{t}:{tok}"] = (
                    color.hexof(lab_l, c * tint, h + turned)
                    if c > 0.002
                    else DEFAULTS[f"{t}:{tok}"]
                )
        return out
    turned = value - float(KNOBS[key][0])
    for t in THEMES:
        for tok in _GOVERNS[key]:
            lab_l, c, h = color.oklch(DEFAULTS[f"{t}:{tok}"])
            out[f"{t}:{tok}"] = color.hexof(lab_l, c, h + turned)
    for k in _MARK[key]:
        lab_l, c, h = color.oklch(DEFAULTS[k])
        out[k] = color.hexof(lab_l, c, h + turned)
    return out
