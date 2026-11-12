"""Every design cell's source: one short Nu program each.

Each is ``def out(plane)`` and finds the Design plane and its
:class:`~.kit.System` through :func:`~.kit.on_system` (``S`` in a cell), so
it reads and writes the one spec wherever its page sits. Drawings follow the spec with ``nu.Reconcile``; only a
slider, an edit, a click or an accepted proposal writes it.

- Design (:data:`ROOT`): welcome, numbers, the system at a glance, activity.
- Tokens (:data:`TOKENS`) and under it Color, Type, Shape, Motion.
- Mark (:data:`MARK`), Components (:data:`COMPONENTS`), Mocks (:data:`MOCKS`).
- Checks (:data:`CHECKS`), Review (:data:`REVIEW`), Export (:data:`EXPORT`)
  and a page per release (:data:`RELEASE`), Principles (:data:`PRINCIPLES`).
"""

from __future__ import annotations

from .principles import DOCS
from .spec import KNOBS as _KNOBS


__all__ = [
    "CHECKS",
    "COLOR",
    "COMPONENTS",
    "EXPORT",
    "MARK",
    "MOCKS",
    "MOTION",
    "PRINCIPLES",
    "RELEASE",
    "REVIEW",
    "ROOT",
    "SHAPE",
    "TOKENS",
    "TYPE",
]


HEAD = """\
import nu
import nuspace
import nuspace.web
import nustd.ui
from nudemos.design import checks, draw, kit, logo, spec as specs
"""


def _cell(body: str) -> str:
    return HEAD + "\n\n" + body


def _drawing(name: str, call: str) -> str:
    """A frame drawing ``call`` (an expression over ``s``, the spec, and ``mode``) from the spec, live."""
    return _cell(f"""\
view = nustd.ui.HtmlRef("{name}", props={{"title": "{name}", "bordered": False}})


@nu.host
def doc(v):
    s, mode = v["spec"], v["mode"]
    return {call}


def out(plane):
    return kit.drawn(plane, view, doc)
""")


_KNOBS_BODY = """\
class View(nu.Shape):
    knobs = nustd.ui.GridRef.slot(nustd.ui.SliderRef, max_columns=COLUMNS, min_cell_width=130, gap=5)


@nu.host
def values(spec):
    return [specs.num(spec, key) for key, *_ in ROWS]


@nu.host
def changes(spec, key, value):
    if key.startswith("knob."):
        return specs.apply_knob(spec, key, float(value))
    return {key: f"{float(value):g}"}


def out(plane):
    knobs = View.knobs

    def build(base, S):
        shape = nu.Sequential(*(
            knobs[i].set(specs.num(specs.DEFAULTS, key), min=lo, max=hi, step=step, label=label, show_value=True)
            for i, (key, label, lo, hi, step) in enumerate(ROWS)
        ))
        draw = lambda v: nu.Sequential(*(knobs[i].set_value(nu.List(v)[i]) for i in range(len(ROWS))))
        moves = [
            nu.ReactEvery(knobs[i].on_change(), kit.edit(S, changes(kit.spec(S), key, nu.float(knobs[i])), "you", label))
            for i, (key, label, *_) in enumerate(ROWS)
        ]
        return shape >> nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(values(kit.spec(S))), draw)), *moves)

    return kit.on_system(plane, build)
"""


def _sliders(rows: tuple[tuple[str, str, float, float, float], ...], columns: int = 4) -> str:
    """A grid of sliders over spec keys: each seeded from the spec, each move one edit.

    ``rows`` are ``(key, label, min, max, step)``, one slider each by
    position. A ``knob.*`` key rewrites every token it governs
    (:func:`~.spec.apply_knob`). The body is one; only the rows differ.
    """
    return _cell(f"ROWS = {list(rows)!r}\nCOLUMNS = {columns}\n\n\n" + _KNOBS_BODY)


# --- Design ----------------------------------------------------------------------------------------


WELCOME = _cell('''\
import nuspace.system.supervisor
import nustd.time
from nudemos import bases
from nudemos.design import job, studio

TEXT = """\\
The nustack design system as one live spec: every color, size, radius, duration and the mark itself.
Every swatch, control, mock and check here is drawn from it, so change a token anywhere and every page follows.
"""

ORDER = {
    "Tokens": "Four knobs that turn the palette, every token, the history.",
    "Mark": "The Nu mark built from the spec, its ladder and variants.",
    "Components": "The kit's controls drawn in the current tokens.",
    "Mocks": "The site hero, a nuspace screen, the social card.",
    "Checks": "Contrast for every pair that must read, both themes.",
    "Review": "The team's proposals, each checked before anyone accepts.",
    "Export": "Releases: tokens, SVGs, PNGs and a favicon.",
    "Principles": "The foundations, in the language's words.",
}


@nu.host
def ordered(ids, names):
    by = dict(zip(names, ids))
    return [{"page": by[n], "about": about} for n, about in ORDER.items() if n in by]


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    pages = nustd.ui.GridRef.slot(nustd.ui.PageLinkRef.slot(variant="tile"), max_columns=4, min_cell_width=180, gap=3)


def tile(r):
    page = nu.Str(nu.Dict(r)["page"])
    return nuspace.atomic(nuspace.web.link(View.pages[page], page, description=nu.Str(nu.Dict(r)["about"])))


def tiles(rows):
    # A tile per page, keyed by its plane id, in the order above.
    return nu.ForEachDo(nu.List(rows), tile)


def studio_job(base, S):
    # The studio: a headless job under the Design plane, its one cell drawing nothing. Its id kept, then supervised.
    def made(job):
        add = nuspace.plane.add(parent=base, name="studio", backend="async", spec="design_studio", into=job)
        one = nuspace.cell.add(nu.Str(job), studio.STUDIO, name="studio", fabrics=[])
        up = nuspace.system.supervisor.supervise(nu.Str(job), policy=nuspace.system.supervisor.ON_FAILURE, exists_ok=True)
        kept = S.studio.set(nu.Str(job)) >> bases.belongs(nu.Str(job), base) >> up
        return nuspace.atomic(add >> one) >> nuspace.atomic(kept)

    return nu.let("", made)


def seed(base, S):
    # Once per Design plane, whichever tab gets here first: the flag is taken in the commit that reads it.
    # The space opens holding things: the decisions the team made before, and the first release, cut from the language.
    past = S.decided.set(studio.history(nustd.time.time()))
    first_release = nu.let(nuspace.atomic(job.export_of(base)), lambda export: nu.IfDo(nu.Str(export) != "", job.cut(base, nu.Str(export), "v1.0.0", specs.DEFAULTS)))

    def first(mine):
        take = nu.IfDo(S.seeded.is_null(), S.seeded.set(True) >> past >> mine.set(True))
        return nuspace.atomic(take) >> nu.IfDo(nu.Bool(mine), studio_job(base, S) >> first_release)

    return nu.let(False, first)


def out(plane):
    def build(base, S):
        kids = nu.List(nuspace.Space.planes[base].children.keys(limit=len(ORDER) + 4))
        names = kids.iter().map(lambda p: nuspace.plane.title(nu.Str(p))).to_list()
        return View.about.set(TEXT) >> nu.let(nuspace.atomic(ordered(kids, names)), tiles) >> seed(base, S) >> nu.Park()

    return kit.on_system(plane, build)
''')


STATS = _cell("""\
TILES = {"tokens": "Tokens", "changed": "Changed", "checks": "Checks passing", "failing": "Failing", "inbox": "Proposals", "release": "Last release"}


class View(nu.Shape):
    tiles = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=6, min_cell_width=120, gap=3)


def draw(t):
    trend = nu.If(nu.Str(t["failing"]) == "0", "flat", "down")
    return nu.Sequential(*(
        View.tiles[k][0].to(nustd.ui.StatRef).set(t[k], label=label, trend=trend) if k == "failing" else View.tiles[k][0].to(nustd.ui.StatRef).set(t[k], label=label)
        for k, label in TILES.items()
    ))


def out(plane):
    read = lambda S: kit.tally(S.spec.fallback({}), S.inbox.fallback([]), S.releases.fallback([]))
    moves = lambda S: nu.OnAny(S.rev.on_change(), S.mail.on_change(), S.releases.on_change())
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(moves(S)), nu.let(nuspace.atomic(read(S)), draw)))
""")


GLANCE = _drawing("glance", "draw.glance(s, mode=mode)")


THEME = _cell("""\
MODES = [{"value": "auto", "label": "Drawings follow the system theme"}, {"value": "dusk", "label": "Draw everything on Dusk"},
         {"value": "dawn", "label": "Draw everything on Dawn"}]


class Bar(nustd.ui.Row):
    mode = nustd.ui.SelectRef.slot(options=MODES)
    note = nustd.ui.TextRef.slot(tone="muted")


class View(nu.Shape):
    bar = Bar.slot(gap=4, align="center", wrap=True)


def out(plane):
    def build(base, S):
        return (
            View.bar.mode.set("auto") >> View.bar.note.set("Frames draw in their own theme. Pick one, or let them follow your system.")
            >> nu.ParallelAsync(
                nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.preview.on_change()])), nu.let(nuspace.atomic(S.preview.fallback("auto")), View.bar.mode.set)),
                nu.ReactEvery(View.bar.mode.on_change(), S.preview.set(nu.Str(View.bar.mode))),
            )
        )

    return kit.on_system(plane, build)
""")


ACTIVITY = _cell("""\
#: Lines the feed keeps, newest first.
KEEP = 30


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Activity", subtitle="Edits, proposals, decisions and releases, newest first")


lines = View.card[0].to(nustd.ui.ColumnRef.slot(nustd.ui.LineRef, gap=0, max_height=320, scroll="y"))
quiet = View.card[1].to(nustd.ui.TextRef.slot(tone="muted"))


@nu.host
def feed(log, inbox, releases, decided):
    rows = [(e["at"], e["who"], f"{e['what']}: {kit.describe_change(e['changes'])}") for e in log or []]
    rows += [(p["at"], p["who"], f"proposed {p['title']}") for p in inbox or []]
    rows += [(d["at"], d["who"], f"{d['title']}, {d['verdict']}") for d in decided or [] if d.get("at")]
    rows += [(r["at"], "Export", f"cut {r['version']}, {r['files']} files") for r in releases or []]
    rows.sort(key=lambda r: -r[0])
    return [{"i": i, "at": at * 1000, "who": who, "what": what} for i, (at, who, what) in enumerate(rows[:KEEP])]


def line(r):
    at_ = lines[nu.Int(nu.Dict(r)["i"])]
    return (
        at_[0].to(nustd.ui.TextRef.slot(weight="medium")).set(nu.Dict(r)["who"]) >> at_[1].to(nustd.ui.TextRef).set(nu.Dict(r)["what"])
        >> at_[2].to(nustd.ui.RelativeTimeRef).set(nu.Dict(r)["at"])
    )


def draw(rows):
    n = nu.List(rows).len()
    empty = lines.erase() >> quiet.set("Quiet so far. Move a knob on Tokens, or wait for the team.")
    return nu.IfDo(n == 0, empty, quiet.erase() >> nu.ForEachDo(nu.List(rows), line) >> lines.truncate(n))


def out(plane):
    read = lambda S: feed(S.log.fallback([]), S.inbox.fallback([]), S.releases.fallback([]), S.decided.fallback([]))
    moves = lambda S: nu.OnAny(S.rev.on_change(), S.mail.on_change(), S.decided.on_change(), S.releases.on_change())
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(moves(S)), nu.let(nuspace.atomic(read(S)), draw)))
""")


ROOT = (
    ("welcome", WELCOME),
    ("numbers", STATS),
    ("glance", GLANCE),
    ("activity", ACTIVITY),
    ("theme", THEME),
)


# --- Tokens ----------------------------------------------------------------------------------------


KNOBS = _sliders(tuple((k, v[1], v[2], v[3], v[4]) for k, v in _KNOBS.items()))


ACTIONS = _cell("""\
class Bar(nustd.ui.Row):
    undo = nustd.ui.ButtonRef.slot(label="Undo", icon="undo-2", variant="secondary")
    reset = nustd.ui.ButtonRef.slot(label="Back to the language", icon="rotate-ccw", variant="ghost")
    note = nustd.ui.TextRef.slot(tone="muted")


class View(nu.Shape):
    bar = Bar.slot(gap=4, align="center", wrap=True)


@nu.host
def note(stored, log):
    n = len(specs.changed(stored))
    last = f" Last: {log[-1]['who']}, {log[-1]['what'].lower()}." if log else ""
    return ("As the language ships it." if n == 0 else f"{n} tokens changed from the language.") + last


def out(plane):
    def build(base, S):
        read = note(S.spec.fallback({}), S.log.fallback([]))
        labels = View.bar.undo.set("Undo", icon="undo-2", variant="secondary") >> View.bar.reset.set("Back to the language", icon="rotate-ccw", variant="ghost")
        return labels >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(read), View.bar.note.set)),
            nu.ReactEvery(View.bar.undo.on_click(), kit.undo(S)),
            nu.ReactEvery(View.bar.reset.on_click(), kit.reset(S)),
        )

    return kit.on_system(plane, build)
""")


COLORS_TABLE = _cell("""\
GROUPS = ["all", "ground", "line", "ink", "afterglow", "starlight", "state", "chart"]

COLUMNS = [
    {"key": "token", "label": "Token", "editable": False, "width": 170},
    {"key": "group", "label": "Group", "editable": False, "width": 100},
    {"key": "dusk", "label": "Dusk", "width": 110},
    {"key": "dawn", "label": "Dawn", "width": 110},
    {"key": "use", "label": "Use", "editable": False, "hide_below": 640},
    {"key": "changed", "label": "Changed", "kind": "bool", "editable": False, "width": 90},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Colors", subtitle="Edit a hex in place: every page drawing it follows.")


group = View.card.actions[0].to(nustd.ui.SelectRef.slot(options=GROUPS))
table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="token", editable=True, density="compact", label="Colors"))


@nu.host
def rows(stored, group):
    sp, ch = specs.merged(stored), specs.changed(stored)
    return [
        {"token": tok, "group": g, "dusk": sp[f"dusk:{tok}"], "dawn": sp[f"dawn:{tok}"], "use": use,
         "changed": f"dusk:{tok}" in ch or f"dawn:{tok}" in ch}
        for g, tok, _, _, use in specs.COLORS if group in ("", "all", g)
    ]


@nu.host
def change(ev):
    return {f"{ev['column']}:{ev['key']}": str(ev["value"]).strip()}


def out(plane):
    def build(base, S):
        read = rows(S.spec.fallback({}), nu.Str(group))
        return group.set("all") >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change(), group.on_change()])), nu.let(nuspace.atomic(read), table.set_rows)),
            nu.ReactEvery(table.on_edit(), lambda ev: kit.edit(S, change(ev), "you", "Edited a color")),
        )

    return kit.on_system(plane, build)
""")


SCALES_TABLE = _cell("""\
COLUMNS = [
    {"key": "key", "label": "Token", "editable": False, "width": 190},
    {"key": "group", "label": "Group", "editable": False, "width": 90},
    {"key": "value", "label": "Value", "width": 150},
    {"key": "use", "label": "Use", "editable": False, "hide_below": 640},
    {"key": "changed", "label": "Changed", "kind": "bool", "editable": False, "width": 90},
]


@nu.host
def rows(stored):
    sp, ch = specs.merged(stored), specs.changed(stored)
    return [{"key": k, "group": g, "value": sp[k], "use": use, "changed": k in ch} for g, k, _, use in specs.SCALARS]


@nu.host
def change(ev):
    return {ev["key"]: str(ev["value"]).strip()}


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Scales", subtitle="Type, space, radius, motion and the mark. Edit a value in place.")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", editable=True, density="compact", label="Scales"))


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.ParallelAsync(
        nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(rows(S.spec.fallback({}))), table.set_rows)),
        nu.ReactEvery(table.on_edit(), lambda ev: kit.edit(S, change(ev), "you", "Edited a token")),
    ))
""")


HISTORY = _cell("""\
COLUMNS = [{"key": "when", "label": "When", "width": 110, "cell": nustd.ui.RelativeTimeRef}, {"key": "who", "label": "Who", "width": 140},
           {"key": "what", "label": "What"}, {"key": "change", "label": "Change", "wrap": "truncate"}]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="History", subtitle="Every edit, newest first")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="i", density="compact", label="History", max_rows=12))


@nu.host
def rows(log):
    return [{"i": str(i), "when": e["at"] * 1000, "who": e["who"], "what": e["what"], "change": kit.describe_change(e["changes"])}
            for i, e in reversed(list(enumerate(log or [])))]


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(rows(S.log.fallback([]))), table.set_rows)))
""")


TOKENS = (
    ("knobs", KNOBS),
    ("actions", ACTIONS),
    ("colors", COLORS_TABLE),
    ("scales", SCALES_TABLE),
    ("history", HISTORY),
)


PALETTE = _drawing("palette", "draw.palette(s, set(v['changed']))")


LADDER = _cell("""\
from nudemos.design import color

STEPS = ["ground-deep", "ground", "ground-raised", "ground-card", "ground-overlay", "ground-hover", "line-subtle", "line", "line-strong", "ink-4", "ink-3", "ink-2", "ink-1"]


class Bar(nustd.ui.Row):
    lightness = nustd.ui.LineChart.slot(("dusk", "dawn"), title="Lightness up the ladder, OKLCH", x_type="category", symbols=True, y_min=0, y_max=100, height=280)
    hue = nustd.ui.LineChart.slot(("dusk", "dawn"), title="Chroma: the sky's tint, step by step", x_type="category", symbols=True, height=280)


class View(nu.Shape):
    bar = Bar.slot(gap=6, align="start", wrap=True, grow={"lightness": 1, "hue": 1}, basis={"lightness": 320, "hue": 320})


@nu.host
def ladders(spec):
    out = {}
    for name, key in (("l", 0), ("c", 1)):
        for t in specs.THEMES:
            th = specs.theme(spec, t)
            out.setdefault(name, {})[t] = [[s, round(color.oklch(th[s])[key] * (100 if key == 0 else 1000), 1)] for s in STEPS]
    return out


def draw(v):
    return View.bar.lightness.set(v["l"]) >> View.bar.hue.set(v["c"])


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(ladders(kit.spec(S))), draw)))
""")


COLOR = (
    ("knobs", _sliders(tuple((k, v[1], v[2], v[3], v[4]) for k, v in _KNOBS.items()))),
    ("palette", PALETTE),
    ("ladder", LADDER),
)


TYPE = (
    (
        "scale",
        _sliders(
            (
                ("type.base", "Base, app text", 11, 16, 1),
                ("type.display", "Display", 24, 48, 2),
                ("type.hero", "Hero", 40, 80, 2),
                ("type.title-weight", "Title weight", 400, 700, 100),
            )
        ),
    ),
    ("specimen", _drawing("specimen", "draw.specimen(s, mode=mode)")),
)


SHAPE = (
    (
        "scale",
        _sliders(
            (
                ("space.unit", "Grid unit", 2, 8, 1),
                ("radius.sm", "Radius sm", 0, 12, 1),
                ("radius.md", "Radius md", 0, 16, 1),
                ("radius.lg", "Radius lg", 0, 20, 1),
                ("radius.xl", "Radius xl", 0, 28, 1),
            ),
            columns=5,
        ),
    ),
    ("space", _drawing("space", "draw.space(s, mode=mode)")),
    ("elevation", _drawing("elevation", "draw.elevation(s)")),
)


CURVES = _cell("""\
class View(nu.Shape):
    curves = nustd.ui.LineChart.slot(("ease-out, enter", "ease-in, leave", "ease-in-out, move"), title="The three easings: progress over time",
                                     y_min=0, y_max=1, height=300, x_format="{value}%")


@nu.host
def sample(spec):
    def bezier(p, n=40):
        x1, y1, x2, y2 = (float(x) for x in p.split(","))
        pts = []
        for i in range(n + 1):
            t = i / n
            x = 3 * (1 - t) ** 2 * t * x1 + 3 * (1 - t) * t ** 2 * x2 + t ** 3
            y = 3 * (1 - t) ** 2 * t * y1 + 3 * (1 - t) * t ** 2 * y2 + t ** 3
            pts.append([round(x * 100, 1), round(y, 3)])
        return pts
    return {f"{name}, {use}": bezier(spec[f"motion.{name}"]) for name, use in (("ease-out", "enter"), ("ease-in", "leave"), ("ease-in-out", "move"))}


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(sample(kit.spec(S))), View.curves.set)))
""")


MOTION = (
    (
        "durations",
        _sliders(
            (
                ("motion.fast", "fast, ms", 60, 400, 10),
                ("motion.base", "base, ms", 80, 500, 10),
                ("motion.slow", "slow, ms", 120, 700, 10),
            ),
            columns=3,
        ),
    ),
    ("live", _drawing("motion", "draw.motion(s, mode=mode)")),
    ("curves", CURVES),
)


# --- Mark --------------------------------------------------------------------------------------------


MARK_FORM = _cell("""\
class Bar(nustd.ui.Row):
    size = nustd.ui.SliderRef.slot()
    radius = nustd.ui.SliderRef.slot()
    shadow = nustd.ui.SwitchRef.slot(label="Ambient shadow")


class View(nu.Shape):
    bar = Bar.slot(gap=4, align="center", wrap=True)


@nu.host
def seen(spec):
    return {"size": specs.num(spec, "mark.size"), "radius": specs.num(spec, "mark.radius"), "shadow": spec.get("mark.shadow") == "on"}


@nu.host
def whole(x):
    return str(round(float(x)))


@nu.host
def flag(x):
    return "on" if x else "off"


def out(plane):
    def build(base, S):
        shape = View.bar.size.set(560, min=360, max=760, step=10, label="Glyph on the 1024 tile", show_value=True) >> View.bar.radius.set(
            230, min=0, max=512, step=2, label="Tile corner", show_value=True)
        draw = lambda v: View.bar.size.set_value(v["size"]) >> View.bar.radius.set_value(v["radius"]) >> View.bar.shadow.set(v["shadow"])
        return shape >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(seen(kit.spec(S))), draw)),
            nu.ReactEvery(View.bar.size.on_change(), kit.edit(S, nu.Dict.of(**{"mark.size": whole(nu.float(View.bar.size))}), "you", "Resized the glyph")),
            nu.ReactEvery(View.bar.radius.on_change(), kit.edit(S, nu.Dict.of(**{"mark.radius": whole(nu.float(View.bar.radius))}), "you", "Rounded the tile")),
            nu.ReactEvery(View.bar.shadow.on_change(), kit.edit(S, nu.Dict.of(**{"mark.shadow": flag(nu.Bool(View.bar.shadow))}), "you", "Set the shadow")),
        )

    return kit.on_system(plane, build)
""")


BOARD = _drawing("board", "draw.board(s)")


VARIANTS = _cell("""\
N = 6


class Pick(nustd.ui.Column):
    face = nustd.ui.HtmlRef.slot(bordered=False, title="A variant")
    use = nustd.ui.ButtonRef.slot(variant="secondary")


class View(nustd.ui.Column):
    about = nustd.ui.TextRef.slot(tone="muted")
    walks = nustd.ui.GridRef.slot(Pick, max_columns=N, min_cell_width=124, gap=3)


@nu.host
def faces(v):
    s = v["spec"]
    return [{"doc": draw.tile(s, w, mode=v["mode"]), "label": "Use " + w["name"]} for w in logo.variants(s)]


@nu.host
def ground(spec, i):
    w = logo.variants(spec)[int(i)]
    return {k: w[k] for k in ("mark.from", "mark.mid", "mark.to")}


@nu.host
def named(spec, i):
    return "Took the " + logo.variants(spec)[int(i)]["name"] + " ground"


def paint(rows):
    def one(i):
        r = nu.Dict(nu.List(rows)[i])
        return View.walks[i].face.set_html(r["doc"]) >> View.walks[i].use.set_label(r["label"])

    return nu.Sequential(*(one(i) for i in range(N)))


def out(plane):
    def build(base, S):
        uses = [nu.ReactEvery(View.walks[i].use.on_click(), kit.edit(S, ground(kit.spec(S), i), "you", named(kit.spec(S), i))) for i in range(N)]
        return View.about.set("Six grounds one step from the current one. Use one, and the next six walk on from there.") >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.follows(S))), nu.let(nuspace.atomic(faces(kit.seen(S))), paint)), *uses)

    return kit.on_system(plane, build)
""")


SOURCE = _cell("""\
import re


@nu.host
def source(spec):
    svg = logo.asset(spec, "square")
    svg = re.sub(r'd="[^"]{200,}"', lambda m: f'd="... {len(m.group(0)) // 1000}k of soft glyph ..."', svg)
    return svg.replace("><", ">\\n<")


def out(plane):
    code = nustd.ui.CodeRef("svg", props={"language": "xml", "max_height": 360, "wrap": True})
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(source(kit.spec(S))), code.set)))
""")


MARK = (("form", MARK_FORM), ("board", BOARD), ("variants", VARIANTS), ("source", SOURCE))


# --- Components, mocks --------------------------------------------------------------------------------


TRY = _sliders(
    (
        ("knob.afterglow", "Afterglow hue", 250, 345, 1),
        ("radius.md", "Control radius", 0, 16, 1),
        ("space.control", "Control height", 24, 44, 2),
        ("type.lg", "Control text", 12, 17, 1),
    )
)


COMPONENTS = (
    ("try", TRY),
    ("theme", THEME),
    ("gallery", _drawing("gallery", "draw.gallery(s, mode=mode)")),
)


MOCKS = (
    ("theme", THEME),
    ("hero", _drawing("hero", "draw.hero(s, mode=mode)")),
    ("app", _drawing("app", "draw.app(s, mode=mode)")),
    ("social", _drawing("social", "draw.social(s)")),
    ("readme", _drawing("readme", "draw.readme(s)")),
)


# --- Checks ------------------------------------------------------------------------------------------


VERDICT = _cell("""\
class Bar(nustd.ui.Row):
    pill = nustd.ui.StatusPillRef.slot()
    passing = nustd.ui.StatRef.slot(label="Passing")
    under = nustd.ui.StatRef.slot(label="Under target")
    failing = nustd.ui.StatRef.slot(label="Failing")
    worst = nustd.ui.StatRef.slot(label="Lowest pair")


class View(nu.Shape):
    bar = Bar.slot(gap=4, align="center", wrap=True)


@nu.host
def summary(spec):
    s = checks.summary(spec)
    pairs = checks.run(spec)["pairs"]
    low = min(((float(r[t]) / float(r["min"]), r, t) for r in pairs for t in specs.THEMES), key=lambda x: x[0])
    _, r, t = low
    tone = "danger" if s["fail"] else ("warn" if s["under"] else "ok")
    word = f"{s['fail']} failing" if s["fail"] else ("passing, some under target" if s["under"] else "every check passes")
    return {"pass": str(s["pass"]), "under": str(s["under"]), "fail": str(s["fail"]), "tone": tone, "word": word,
            "worst": f"{r[t]}", "worst_label": f"Lowest: {r['pair']}, {t}"}


def draw(v):
    return (
        View.bar.pill.set(v["word"], tone=v["tone"]) >> View.bar.passing.set_value(v["pass"]) >> View.bar.under.set_value(v["under"])
        >> View.bar.failing.set(v["fail"], trend=nu.If(nu.Str(v["fail"]) == "0", "flat", "down")) >> View.bar.worst.set(v["worst"], label=v["worst_label"])
    )


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(summary(kit.spec(S))), draw)))
""")


PAIRS = _cell("""\
COLUMNS = [
    {"key": "verdict", "label": "Verdict", "width": 140, "cell": nustd.ui.StatusPillRef},
    {"key": "pair", "label": "Pair"},
    {"key": "what", "label": "What it is", "hide_below": 640},
    {"key": "dusk", "label": "Dusk", "kind": "number", "width": 80, "align": "end"},
    {"key": "dawn", "label": "Dawn", "kind": "number", "width": 80, "align": "end"},
    {"key": "min", "label": "Needs", "kind": "number", "width": 80, "align": "end"},
]

ORDER = {"fail": 0, "under target": 1, "pass": 2}


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Contrast", subtitle="Every pair that must read, both themes, WCAG 2")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Contrast"))


@nu.host
def rows(spec):
    pairs = sorted(checks.run(spec)["pairs"], key=lambda r: ORDER[r["verdict"]])
    return [{**{k: r[k] for k in ("key", "pair", "what", "dusk", "dawn", "min")}, "verdict": kit.pill(r["verdict"])} for r in pairs]


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(rows(kit.spec(S))), table.set_rows)))
""")


RULES = _cell("""\
COLUMNS = [{"key": "verdict", "label": "Verdict", "width": 140, "cell": nustd.ui.StatusPillRef}, {"key": "rule", "label": "Rule"}, {"key": "seen", "label": "Seen"}]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Rules", subtitle="The language's own rules, checked on the spec")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Rules"))


@nu.host
def rows(spec):
    return [{"key": r["key"], "verdict": kit.pill(r["verdict"]), "rule": r["rule"], "seen": r["seen"]} for r in checks.run(spec)["rules"]]


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.rev.on_change()])), nu.let(nuspace.atomic(rows(kit.spec(S))), table.set_rows)))
""")


CHECKS = (
    ("verdict", VERDICT),
    ("sheet", _drawing("sheet", "draw.contrast_sheet(s)")),
    ("pairs", PAIRS),
    ("rules", RULES),
)


# --- Review ------------------------------------------------------------------------------------------


INBOX = _cell("""\
from nudemos.design import studio

COLUMNS = [{"key": "who", "label": "From", "width": 150}, {"key": "title", "label": "Proposal"},
           {"key": "checks", "label": "Checks", "width": 150, "cell": nustd.ui.StatusPillRef},
           {"key": "when", "label": "Arrived", "width": 110, "cell": nustd.ui.RelativeTimeRef, "hide_below": 560}]


class Studio(nustd.ui.Row):
    live = nustd.ui.SwitchRef.slot(label="Team proposals arrive on their own")
    pace = nustd.ui.SliderRef.slot()


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Inbox", subtitle="Waiting for a decision. Pick one to open it below.")


# A row click picks the proposal Review opens: it selects, it does not leave the page.
table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="id", clickable_rows=True, density="compact", label="Inbox"))
studio_bar = View.card.footer[0].to(Studio.slot(gap=6, align="center", wrap=True))


@nu.host
def rows(inbox, stored, pick):
    sp = specs.merged(stored)
    return [{"id": p["id"], "who": p["who"], "title": ("> " if p["id"] == pick else "") + p["title"],
             "checks": kit.pill(studio.verdict(sp, p["changes"])), "when": p["at"] * 1000} for p in inbox or []]


def out(plane):
    def build(base, S):
        read = rows(S.inbox.fallback([]), S.spec.fallback({}), S.pick.fallback(""))
        pace = studio_bar.pace
        first = table.set_rows([]) >> pace.set(24, min=6, max=90, step=2, label="Seconds between arrivals", show_value=True)
        return first >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.mail.on_change(), S.rev.on_change(), S.pick.on_change()])), nu.let(nuspace.atomic(read), table.set_rows)),
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.paused.on_change()])), nu.let(nuspace.atomic(S.paused.fallback(False).not_()), studio_bar.live.set)),
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.pace.on_change()])), nu.let(nuspace.atomic(S.pace.fallback(studio.PACE)), pace.set_value)),
            nu.ReactEvery(table.on_row_click(), lambda ev: S.pick.set(nu.Str(ev["key"]))),
            nu.ReactEvery(studio_bar.live.on_change(), S.paused.set(nu.Bool(studio_bar.live).not_())),
            nu.ReactEvery(pace.on_change(), S.pace.set(nu.float(pace))),
        )

    return kit.on_system(plane, build)
""")


OPEN = _cell("""\
import time


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Waiting for the team")


accept = View.card.actions[0].to(nustd.ui.ButtonRef.slot(label="Accept", icon="check"))
decline = View.card.actions[1].to(nustd.ui.ButtonRef.slot(label="Decline", icon="x", variant="secondary"))
by_line = View.card[0].to(nustd.ui.LineRef)
why = View.card[1].to(nustd.ui.MarkdownRef)
diff = View.card[2].to(nustd.ui.HtmlRef.slot(title="The proposal", bordered=False))
note = View.card.footer[0].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))


@nu.host
def opened(inbox, pick):
    inbox = list(inbox or [])
    return next((p for p in inbox if p["id"] == pick), inbox[0] if inbox else {})


@nu.host
def shown(v, prop, waiting):
    if not prop:
        return {"title": "Nothing waiting", "who": "", "role": "", "at": 0, "why": "The team's proposals land here as they come in.",
                "doc": draw.proposal(v["spec"], {}, mode=v["mode"]), "note": ""}
    return {"title": prop["title"], "who": prop["who"], "role": prop["role"], "at": prop["at"] * 1000, "why": prop["why"],
            "doc": draw.proposal(v["spec"], prop, mode=v["mode"]), "note": f"{waiting} waiting"}


@nu.host
def without(inbox, pid):
    return [p for p in inbox or [] if p["id"] != pid]


@nu.host
def decided(done, prop, verdict):
    return [*list(done or []), {**prop, "verdict": verdict, "at": time.time()}][-40:]


@nu.host
def count(inbox):
    return len(inbox or [])


@nu.host
def has(prop):
    return bool(prop and prop.get("id"))


@nu.host
def by(prop):
    return prop.get("who", "")


def decide(S, prop, accepted):
    pid = nu.Str(nu.Dict(prop)["id"])
    move = (
        S.decided.set(decided(S.decided.fallback([]), prop, "accepted" if accepted else "declined"))
        >> S.inbox.set(without(S.inbox.fallback([]), pid))
        >> S.mail.set(S.mail.fallback(0) + 1)
    )
    write = kit.edit(S, nu.Dict(prop)["changes"], by(prop), nu.Dict(prop)["title"]) if accepted else nu.Noop()
    return nu.IfDo(has(prop), write >> move)


def draw_open(v):
    # Who sent it and when on one line, their reasons under it, then the proposal drawn.
    sent = (
        by_line[0].to(nustd.ui.TextRef.slot(weight="medium")).set(v["who"]) >> by_line[1].to(nustd.ui.TextRef.slot(tone="muted")).set(v["role"])
        >> by_line[2].to(nustd.ui.RelativeTimeRef).set(v["at"])
    )
    return (
        View.card.set_title(v["title"]) >> nu.IfDo(nu.Str(v["who"]) != "", sent, by_line.erase())
        >> why.set(v["why"]) >> diff.set_html(v["doc"]) >> note.set(v["note"])
    )


def out(plane):
    def build(base, S):
        prop = opened(S.inbox.fallback([]), S.pick.fallback(""))
        read = shown(kit.seen(S), prop, count(S.inbox.fallback([])))
        moves = [S.mail.on_change(), S.pick.on_change(), S.rev.on_change(), S.preview.on_change()]
        labels = accept.set("Accept", icon="check") >> decline.set("Decline", icon="x", variant="secondary")
        return labels >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*moves)), nu.let(nuspace.atomic(read), draw_open)),
            nu.ReactEvery(accept.on_click(), nu.let(nuspace.atomic(prop), lambda p: decide(S, p, True))),
            nu.ReactEvery(decline.on_click(), nu.let(nuspace.atomic(prop), lambda p: decide(S, p, False))),
        )

    return kit.on_system(plane, build)
""")


DECIDED = _cell("""\
COLUMNS = [{"key": "verdict", "label": "Decision", "width": 120, "cell": nustd.ui.StatusPillRef}, {"key": "who", "label": "From", "width": 150},
           {"key": "title", "label": "Proposal"}, {"key": "when", "label": "When", "width": 110, "cell": nustd.ui.RelativeTimeRef, "hide_below": 560}]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Decided", subtitle="Newest first")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Decided", max_rows=8))


@nu.host
def rows(done):
    return [{"key": f"{d['id']}-{i}", "verdict": kit.pill(d["verdict"]), "who": d["who"], "title": d["title"], "when": d["at"] * 1000}
            for i, d in reversed(list(enumerate(done or [])))]


def out(plane):
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(nu.OnAny(*[S.mail.on_change()])), nu.let(nuspace.atomic(rows(S.decided.fallback([]))), table.set_rows)))
""")


REVIEW = (("inbox", INBOX), ("open", OPEN), ("decided", DECIDED))


# --- Export ------------------------------------------------------------------------------------------


CUT = _cell("""\
import re
from nudemos.design import job


class Go(nustd.ui.Row):
    version = nustd.ui.InputRef.slot(label="Version")
    cut = nustd.ui.ButtonRef.slot(label="Cut release", icon="package")


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    card = nustd.ui.CardRef.slot(title="Cut a release", subtitle="A page and a job in its own process that writes every file")


drift_text = View.card[0].to(nustd.ui.MarkdownRef)
go = View.card[1].to(Go.slot(gap=3, align="end"))


@nu.host
def drift(stored, releases):
    sp = specs.merged(stored)
    if not releases:
        return "#### Nothing released yet\\n\\nThe first release writes the system as it stands."
    last = releases[-1]
    was = specs.merged(last.get("spec") or {})
    diff = [k for k in specs.DEFAULTS if sp[k] != was[k] and not k.startswith("knob.")]
    if not diff:
        return f"#### In step with {last['version']}\\n\\nNothing has moved since the last release."
    keys = ", ".join(f"`{k}`" for k in diff[:10]) + (f" and {len(diff) - 10} more" if len(diff) > 10 else "")
    return f"#### {len(diff)} tokens moved since {last['version']}\\n\\n{keys}"


@nu.host
def following(releases):
    if not releases:
        return "v1.0.0"
    m = re.match(r"v?(\\d+)\\.(\\d+)\\.(\\d+)", releases[-1]["version"])
    return f"v{m.group(1)}.{int(m.group(2)) + 1}.0" if m else releases[-1]["version"] + "-next"


def cut(base, S, export):
    def made(version):
        v = nu.Str(version)
        return job.cut(base, export, v, nuspace.atomic(kit.spec(S))) >> View.history.push(nuspace.web.href(nuspace.atomic(job.release_page(base, v))))

    typed = nu.Str(go.version).strip()
    return nu.IfDo(typed != "", nu.let(typed, made))


def out(plane):
    def build(base, S):
        read = nu.Dict.of(drift=drift(S.spec.fallback({}), S.releases.fallback([])), next=following(S.releases.fallback([])))
        draw = lambda v: drift_text.set(v["drift"]) >> go.version.set(v["next"])
        moves = [S.rev.on_change(), S.mail.on_change(), S.releases.on_change()]
        return drift_text.set("") >> go.version.set("") >> go.cut.set("Cut release", icon="package") >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*moves)), nu.let(nuspace.atomic(read), draw)),
            nu.ReactEvery(go.cut.on_click(), cut(base, S, plane)),
        )

    return kit.on_system(plane, build)
""")


RELEASES = _cell("""\
from nudemos import pages

COLUMNS = [{"key": "version", "label": "Release", "width": 110, "cell": nustd.ui.PageLinkRef.slot(variant="inline")}, {"key": "files", "label": "Files", "kind": "number", "width": 80, "align": "end"},
           {"key": "size", "label": "Size", "width": 100, "align": "end"}, {"key": "moved", "label": "From the language", "hide_below": 560},
           {"key": "when", "label": "Cut", "width": 110, "cell": nustd.ui.RelativeTimeRef}]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Releases", subtitle="Newest first. Each opens its page.")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Releases"))


@nu.host
def rows(releases):
    out = []
    for r in reversed(releases or []):
        moved = len([k for k in specs.changed(r.get("spec") or {}) if not k.startswith("knob.")])
        out.append({"key": r["page"], "version": {"page": r["page"], "label": r["version"]}, "files": r["files"], "size": f"{r['bytes'] / 1024:.0f} KB",
                    "moved": f"{moved} tokens" if moved else "as the language ships it", "when": r["at"] * 1000})
    return out


def out(plane):
    read = lambda S: pages.linked(rows(S.releases.fallback([])), "version")
    moves = lambda S: nu.OnAny(S.mail.on_change(), S.releases.on_change())
    return kit.on_system(plane, lambda base, S: nu.Reconcile(nuspace.atomic(moves(S)), nu.let(nuspace.atomic(read(S)), table.set_rows)))
""")


EXPORT = (("cut", CUT), ("releases", RELEASES))


_RELEASE_HEAD = """\
from nudemos.design import job


def on_build(plane, body):
    # body(job), once the page holds its job's id: the cut writes it right after the page.
    made = nuspace.at.plane(id=plane).state(job.Made).job.on_change()
    ready = nu.WaitUntil(nuspace.atomic(made), nuspace.atomic(job.job_of(plane) != ""), every=2.0)
    return ready >> nu.let(nuspace.atomic(job.job_of(plane)), lambda jb: body(nu.Str(jb)))
"""


BUILD_STATUS = _cell(
    _RELEASE_HEAD
    + """\

TILES = {"files": "Files", "size": "Size", "took": "Took", "now": "Writing"}


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Build", subtitle="The release job, in its own process")


pill = View.card.actions[0].to(nustd.ui.StatusPillRef)
progress = View.card[0].to(nustd.ui.ProgressRef)
tiles = View.card[1].to(nustd.ui.GridRef.slot(nustd.ui.StatRef, max_columns=4, min_cell_width=140, gap=3))


@nu.host
def summary(status, done, total, index, started, finished, current):
    import time
    n = len(index or [])
    size = sum(f["bytes"] for f in index or [])
    end = finished or time.time()
    took = f"{end - started:.1f}s" if started else "-"
    tone = {"done": "ok", "building": "info"}.get(status, "neutral")
    word = {"done": "released", "building": "building"}.get(status, "starting")
    return {"tone": tone, "word": word, "value": (done / total * 100) if total else 0.0, "caption": f"{done} of {total} files",
            "files": str(n), "size": f"{size / 1024:.0f} KB", "took": took, "now": current or ("all written" if status == "done" else "-")}


def draw(v):
    return (
        pill.set(v["word"], tone=v["tone"]) >> progress.set(v["value"], caption=v["caption"])
        >> nu.Sequential(*(tiles[k].set(v[k], label=label) for k, label in TILES.items()))
    )


def out(plane):
    def follow(jb):
        b = job.build_at(jb)
        read = summary(
            b.status.fallback(""), b.done.fallback(0), b.total.fallback(0), b.index.fallback([]),
            b.started.fallback(0.0), b.finished.fallback(0.0), b.current.fallback(""),
        )
        return nu.Reconcile(nuspace.atomic(nu.OnAny(b.done.on_change(), b.status.on_change())), nu.let(nuspace.atomic(read), draw), every=2.0)

    return on_build(plane, follow)
"""
)


BUILD_FILES = _cell(
    _RELEASE_HEAD
    + """\

COLUMNS = [{"key": "name", "label": "File"}, {"key": "kind", "label": "Kind", "width": 80, "cell": nustd.ui.BadgeRef.slot(variant="neutral", size="sm")},
           {"key": "size", "label": "Size", "width": 100, "align": "end"}, {"key": "ms", "label": "Drawn in", "width": 100, "align": "end"}]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Files written", subtitle="As the job writes them")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Files"))


@nu.host
def rows(index):
    return [{"key": f["key"], "name": f["name"], "kind": f["kind"], "size": f"{f['bytes'] / 1024:.1f} KB" if f["bytes"] >= 1024 else f"{f['bytes']} B",
             "ms": f"{f['ms']} ms"} for f in index or []]


def out(plane):
    def follow(jb):
        b = job.build_at(jb)
        return nu.Reconcile(nuspace.atomic(b.done.on_change()), nu.let(nuspace.atomic(rows(b.index.fallback([]))), table.set_rows), every=3.0)

    return on_build(plane, follow)
"""
)


BUILD_SHEET = _cell(
    _RELEASE_HEAD
    + """\
import base64

SHOW = ["nu-square-512.png", "nu-circle-256.png", "nu-full-bleed-256.png", "nu-text-only-256.png", "nu-square-64.png", "nu-square-32.png", "nu-square-16.png"]


@nu.host
def sheet(index, blobs, stored):
    by = {f["key"]: f for f in index or []}
    tiles = []
    shown = {f["name"]: f for f in by.values()}
    for name in SHOW:
        f = shown.get(name)
        blob = (blobs or {}).get(f["key"]) if f else None
        if not blob:
            continue
        size = min(160, max(16, int(f["size"]))) if f.get("size") else 96
        src = "data:image/png;base64," + base64.b64encode(blob).decode()
        tiles.append(f'<figure><div class="cv"><img src="{src}" width="{size}" height="{size}"></div><figcaption>{f["name"]}</figcaption></figure>')
    if not tiles:
        return draw.page(specs.merged(stored), '<div class="quiet">The PNGs show here as the job draws them.</div>', pad=18)
    css = (".row{display:flex;flex-wrap:wrap;gap:18px;align-items:flex-end}figure{margin:0;display:flex;flex-direction:column;gap:6px;align-items:center}"
           ".cv{padding:12px;border-radius:8px;background:repeating-conic-gradient(var(--ground-card) 0 25%,var(--ground-hover) 0 50%) 0 0/16px 16px}"
           "figcaption{font:11px var(--font-mono);color:var(--ink-3)}")
    head = '<div class="k" style="margin-bottom:12px">Drawn by the job, read back from its state</div>'
    return draw.page(specs.merged(stored), head + '<div class="row">' + "".join(tiles) + "</div>", css=css, pad=18)


def out(plane):
    view = nustd.ui.HtmlRef("pngs", props={"title": "PNGs", "bordered": False})

    def follow(jb):
        b = job.build_at(jb)
        read = sheet(b.index.fallback([]), b.blobs.extract(), {})
        return nu.Reconcile(nuspace.atomic(b.done.on_change()), nu.let(nuspace.atomic(read), view.set_html), every=3.0)

    return on_build(plane, follow)
"""
)


BUILD_CSS = _cell(
    _RELEASE_HEAD
    + """\

@nu.host
def text(index, blobs):
    key = next((f["key"] for f in index or [] if f["name"] == "tokens.css"), "")
    blob = (blobs or {}).get(key)
    return blob.decode() if blob else "/* tokens.css lands here first */"


def out(plane):
    code = nustd.ui.CodeRef("css", props={"language": "css", "max_height": 320})

    def follow(jb):
        b = job.build_at(jb)
        read = text(b.index.fallback([]), b.blobs.extract())
        return nu.Reconcile(nuspace.atomic(b.done.on_change()), nu.let(nuspace.atomic(read), code.set), every=5.0)

    return on_build(plane, follow)
"""
)


RELEASE = (
    ("status", BUILD_STATUS),
    ("pngs", BUILD_SHEET),
    ("files", BUILD_FILES),
    ("tokens", BUILD_CSS),
)


# --- Principles ----------------------------------------------------------------------------------------


def _doc(text: str) -> str:
    return f"""\
import nu
import nustd.ui

TEXT = {text!r}

out = nustd.ui.MarkdownRef("doc").set(TEXT) >> nu.Park()
"""


PRINCIPLES = tuple((name, _doc(text)) for name, text in DOCS)
