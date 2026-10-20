"""Every design cell's source: one short Nu program each.

Each is ``def out(plane)`` and lands :class:`~.kit.System` at the Design
plane through :func:`~.kit.on_system`, so it reads and writes the one spec
wherever its page sits. Drawings follow the spec with ``redraws``; only a
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
import nustd.ui
from nuspace import ops
from nuspace.system.utils import park, redraws, snap
from nudemos.design import checks, draw, kit, logo, spec as specs
from nudemos.design.kit import System
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


def _sliders(rows: tuple[tuple[str, str, float, float, float], ...], columns: int = 4) -> str:
    """A row of sliders over spec keys: each seeded from the spec, each move one edit.

    ``rows`` are ``(key, label, min, max, step)``. A ``knob.*`` key rewrites
    every token it governs (:func:`~.spec.apply_knob`).
    """
    slots = "\n".join(f"    s{i} = nustd.ui.SliderRef.slot()" for i in range(len(rows)))
    return _cell(f"""\
ROWS = {list(rows)!r}


class Knobs(nustd.ui.Grid):
{slots}


class View(nustd.ui.Column):
    knobs = Knobs.slot(columns={columns}, min_width=130, gap=5)


def slider(i):
    return getattr(View.knobs, f"s{{i}}")


@nu.host
def values(spec):
    return [specs.num(spec, key) for key, *_ in ROWS]


@nu.host
def changes(spec, key, value):
    if key.startswith("knob."):
        return specs.apply_knob(spec, key, float(value))
    return {{key: f"{{float(value):g}}"}}


def out(plane):
    def build(base):
        shape = nu.Sequential(*(
            slider(i).set(specs.num(specs.DEFAULTS, key), min=lo, max=hi, step=step, label=label, show_value=True)
            for i, (key, label, lo, hi, step) in enumerate(ROWS)
        ))
        draw = lambda v: nu.Sequential(*(slider(i).set_value(nu.List(v)[i]) for i in range(len(ROWS))))
        moves = [
            nu.ReactForever(slider(i).on_change(), kit.edit(changes(kit.spec(), key, nu.float(slider(i))), "you", label))
            for i, (key, label, *_) in enumerate(ROWS)
        ]
        return shape >> nu.ParallelAsync(redraws([System.rev.on_change()], values(kit.spec()), draw), *moves)

    return kit.on_system(plane, build)
""")


# --- Design ----------------------------------------------------------------------------------------


WELCOME = _cell('''\
import nustd.time
from nudemos.design import job, studio

TEXT = """\\
The nustack design system as one live spec: every color, size, radius, duration and the mark itself.
Every swatch, control, mock and check here is drawn from it, so change a token anywhere and every page follows.
"""

ORDER = ["Tokens", "Mark", "Components", "Mocks", "Checks", "Review", "Export", "Principles"]


@nu.host
def pages(ids, names):
    by = dict(zip(names, ids))
    return "  ·  ".join(f"[{n}](/{by[n]})" for n in ORDER if n in by)


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    pages = nustd.ui.MarkdownRef.slot()


def seed(base):
    # Once per Design plane, whichever tab gets here first: the flag is taken in the commit that reads it.
    studio_job = studio.job_of(base)
    made = ops.add_plane(studio_job, backend="async", name="studio", parent=base, ui=False, made_by="design_studio",
                         meta=nu.Dict.of(base=base)) >> ops.add_cell(studio_job, studio.STUDIO, cell_id=studio.job_cell(studio_job), name="studio")
    # The space opens holding things: the decisions the team made before, and the first release, cut from the language.
    past = System.decided.set(studio.history(nustd.time.time()))
    first_release = nu.let(snap(job.export_of(base)), lambda export: nu.IfDo(nu.Str(export) != "", job.cut(base, nu.Str(export), "v1.0.0", specs.DEFAULTS)))

    def first(mine):
        take = nu.IfDo(System.seeded.missing(), System.seeded.set(True) >> past >> mine.set(True))
        return ops.atomic_state(ops.plane_state(base, take)) >> nu.IfDo(nu.Bool(mine), made >> nuspace.supervise(studio_job) >> first_release)

    return nu.let(False, first)


def out(plane):
    def build(base):
        kids = ops.children(base)
        names = kids.iter().map(lambda p: ops.plane_title(nu.Str(p))).to_list()
        return View.about.set(TEXT) >> View.pages.set(snap(pages(kids, names))) >> seed(base) >> park()

    return kit.on_system(plane, build)
''').replace("import nu\n", "import nu\nimport nuspace\n", 1)


STATS = _cell("""\
class Tiles(nustd.ui.Grid):
    tokens = nustd.ui.StatRef.slot(label="Tokens")
    changed = nustd.ui.StatRef.slot(label="Changed")
    checks = nustd.ui.StatRef.slot(label="Checks passing")
    failing = nustd.ui.StatRef.slot(label="Failing")
    inbox = nustd.ui.StatRef.slot(label="Proposals")
    release = nustd.ui.StatRef.slot(label="Last release")


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=6, min_width=120, gap=3)


def draw(t):
    T = View.tiles
    return (
        T.tokens.set_value(t["tokens"]) >> T.changed.set_value(t["changed"]) >> T.checks.set_value(t["checks"])
        >> T.failing.set(t["failing"], trend=nu.If(nu.Str(t["failing"]) == "0", "flat", "down"))
        >> T.inbox.set_value(t["inbox"]) >> T.release.set_value(t["release"])
    )


def out(plane):
    read = lambda: kit.tally(System.spec.fallback({}), System.inbox.fallback([]), System.releases.fallback([]))
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change(), System.mail.on_change()], read(), draw))
""")


GLANCE = _drawing("glance", "draw.glance(s, mode=mode)")


THEME = _cell("""\
MODES = [{"value": "auto", "label": "Drawings follow the system theme"}, {"value": "dusk", "label": "Draw everything on Dusk"},
         {"value": "dawn", "label": "Draw everything on Dawn"}]


class Bar(nustd.ui.Row):
    mode = nustd.ui.SelectRef.slot(options=MODES)
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    bar = Bar.slot(gap=4, align="center", wrap=True)


def out(plane):
    def build(base):
        return (
            View.bar.note.set("Frames draw in their own theme. Pick one, or let them follow your system.")
            >> nu.ParallelAsync(
                redraws([System.preview.on_change()], System.preview.fallback("auto"), View.bar.mode.set),
                nu.ReactForever(View.bar.mode.on_change(), System.preview.set(nu.Str(View.bar.mode))),
            )
        )

    return kit.on_system(plane, build)
""")


ACTIVITY = _cell("""\
import time


@nu.host
def feed(log, inbox, releases, decided):
    now = time.time()
    rows = [(e["at"], f"**{e['who']}**  {e['what']}  ·  {kit.describe_change(e['changes'])}") for e in log or []]
    rows += [(p["at"], f"**{p['who']}** proposed *{p['title']}*") for p in inbox or []]
    rows += [(d["at"], f"**{d['who']}**'s *{d['title']}* was {d['verdict']}") for d in decided or [] if d.get("at")]
    rows += [(r["at"], f"Release **{r['version']}** cut, {r['files']} files") for r in releases or []]
    rows.sort(key=lambda r: -r[0])
    lines = [f"- {text}  ·  {kit.ago(at, now)}" for at, text in rows[:9]]
    return "#### Activity\\n\\n" + ("\\n".join(lines) if lines else "Quiet so far. Move a knob on Tokens, or wait for the team.")


def out(plane):
    text = nustd.ui.MarkdownRef("activity")
    read = lambda: feed(System.log.fallback([]), System.inbox.fallback([]), System.releases.fallback([]), System.decided.fallback([]))
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change(), System.mail.on_change()], read(), text.set, every=15.0))
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
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    bar = Bar.slot(gap=4, align="center", wrap=True)


@nu.host
def note(stored, log):
    n = len(specs.changed(stored))
    last = f" Last: {log[-1]['who']}, {log[-1]['what'].lower()}." if log else ""
    return ("As the language ships it." if n == 0 else f"{n} tokens changed from the language.") + last


def out(plane):
    def build(base):
        read = note(System.spec.fallback({}), System.log.fallback([]))
        labels = View.bar.undo.set("Undo", icon="undo-2", variant="secondary") >> View.bar.reset.set("Back to the language", icon="rotate-ccw", variant="ghost")
        return labels >> nu.ParallelAsync(
            redraws([System.rev.on_change()], read, View.bar.note.set),
            nu.ReactForever(View.bar.undo.on_click(), kit.undo()),
            nu.ReactForever(View.bar.reset.on_click(), kit.reset()),
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
    {"key": "use", "label": "Use", "editable": False},
    {"key": "changed", "label": "Changed", "kind": "bool", "editable": False, "width": 90},
]


class Bar(nustd.ui.Row):
    group = nustd.ui.SelectRef.slot(options=GROUPS)
    hint = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    bar = Bar.slot(gap=3, align="center")
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="token", editable=True, dense=True, label="Colors")


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
    def build(base):
        read = rows(System.spec.fallback({}), nu.Str(View.bar.group))
        return (
            View.bar.group.set("all") >> View.bar.hint.set("Edit a hex in place: every page drawing it follows.")
            >> nu.ParallelAsync(
                redraws([System.rev.on_change(), View.bar.group.on_change()], read, View.table.set_rows),
                nu.ReactForever(View.table.on_edit(), lambda ev: kit.edit(change(ev), "you", "Edited a color")),
            )
        )

    return kit.on_system(plane, build)
""")


SCALES_TABLE = _cell("""\
COLUMNS = [
    {"key": "key", "label": "Token", "editable": False, "width": 190},
    {"key": "group", "label": "Group", "editable": False, "width": 90},
    {"key": "value", "label": "Value", "width": 150},
    {"key": "use", "label": "Use", "editable": False},
    {"key": "changed", "label": "Changed", "kind": "bool", "editable": False, "width": 90},
]


@nu.host
def rows(stored):
    sp, ch = specs.merged(stored), specs.changed(stored)
    return [{"key": k, "group": g, "value": sp[k], "use": use, "changed": k in ch} for g, k, _, use in specs.SCALARS]


@nu.host
def change(ev):
    return {ev["key"]: str(ev["value"]).strip()}


def out(plane):
    table = nustd.ui.TableRef("scales", props={"columns": COLUMNS, "row_key": "key", "editable": True, "dense": True, "label": "Type, space, radius, motion, mark"})
    return kit.on_system(plane, lambda base: nu.ParallelAsync(
        redraws([System.rev.on_change()], rows(System.spec.fallback({})), table.set_rows),
        nu.ReactForever(table.on_edit(), lambda ev: kit.edit(change(ev), "you", "Edited a token")),
    ))
""")


HISTORY = _cell("""\
import time

COLUMNS = [{"key": "when", "label": "When", "width": 110}, {"key": "who", "label": "Who", "width": 140},
           {"key": "what", "label": "What"}, {"key": "change", "label": "Change"}]


@nu.host
def rows(log):
    now = time.time()
    return [{"i": str(i), "when": kit.ago(e["at"], now), "who": e["who"], "what": e["what"],
             "change": kit.describe_change(e["changes"]).replace("`", "")} for i, e in reversed(list(enumerate(log or [])))]


def out(plane):
    table = nustd.ui.TableRef("history", props={"columns": COLUMNS, "row_key": "i", "dense": True, "label": "History, newest first", "max_rows": 12})
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change()], rows(System.log.fallback([])), table.set_rows, every=20.0))
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


class View(nustd.ui.Column):
    bar = Bar.slot(gap=6, align="start", wrap=True, min_width=320)


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
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change()], ladders(kit.spec()), draw))
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
class View(nustd.ui.Column):
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
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change()], sample(kit.spec()), View.curves.set))
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


class View(nustd.ui.Column):
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
    def build(base):
        shape = View.bar.size.set(560, min=360, max=760, step=10, label="Glyph on the 1024 tile", show_value=True) >> View.bar.radius.set(
            230, min=0, max=512, step=2, label="Tile corner", show_value=True)
        draw = lambda v: View.bar.size.set_value(v["size"]) >> View.bar.radius.set_value(v["radius"]) >> View.bar.shadow.set(v["shadow"])
        return shape >> nu.ParallelAsync(
            redraws([System.rev.on_change()], seen(kit.spec()), draw),
            nu.ReactForever(View.bar.size.on_change(), kit.edit(nu.Dict.of(**{"mark.size": whole(nu.float(View.bar.size))}), "you", "Resized the glyph")),
            nu.ReactForever(View.bar.radius.on_change(), kit.edit(nu.Dict.of(**{"mark.radius": whole(nu.float(View.bar.radius))}), "you", "Rounded the tile")),
            nu.ReactForever(View.bar.shadow.on_change(), kit.edit(nu.Dict.of(**{"mark.shadow": flag(nu.Bool(View.bar.shadow))}), "you", "Set the shadow")),
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
    about = nustd.ui.TextRef.slot()
    walks = nustd.ui.GridRef.slot(Pick, min_width=124, gap=3)


@nu.host
def faces(v):
    s = v["spec"]
    return [{"i": str(i), "doc": draw.tile(s, w, mode=v["mode"]), "label": "Use " + w["name"]} for i, w in enumerate(logo.variants(s))]


@nu.host
def ground(spec, i):
    w = logo.variants(spec)[int(i)]
    return {k: w[k] for k in ("mark.from", "mark.mid", "mark.to")}


@nu.host
def named(spec, i):
    return "Took the " + logo.variants(spec)[int(i)]["name"] + " ground"


def paint(rows):
    return nu.ForEachDo(rows, lambda r: View.walks[nu.Str(r["i"])].face.set_html(r["doc"]) >> View.walks[nu.Str(r["i"])].use.set_label(r["label"]))


def out(plane):
    def build(base):
        uses = [nu.ReactForever(View.walks[str(i)].use.on_click(), kit.edit(ground(kit.spec(), i), "you", named(kit.spec(), i))) for i in range(N)]
        return View.about.set("Six grounds one step from the current one. Use one, and the next six walk on from there.") >> nu.ParallelAsync(
            redraws(kit.follows(), faces(kit.seen()), paint), *uses)

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
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change()], source(kit.spec()), code.set))
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


class View(nustd.ui.Column):
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
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change()], summary(kit.spec()), draw))
""")


PAIRS = _cell("""\
COLUMNS = [
    {"key": "verdict", "label": "Verdict", "width": 120},
    {"key": "pair", "label": "Pair"},
    {"key": "what", "label": "What it is"},
    {"key": "dusk", "label": "Dusk", "kind": "number", "width": 80},
    {"key": "dawn", "label": "Dawn", "kind": "number", "width": 80},
    {"key": "min", "label": "Needs", "kind": "number", "width": 80},
]

ORDER = {"fail": 0, "under target": 1, "pass": 2}


@nu.host
def rows(spec):
    pairs = checks.run(spec)["pairs"]
    return sorted(({k: r[k] for k in ("key", "verdict", "pair", "what", "dusk", "dawn", "min")} for r in pairs), key=lambda r: ORDER[r["verdict"]])


def out(plane):
    table = nustd.ui.TableRef("pairs", props={"columns": COLUMNS, "row_key": "key", "dense": True, "label": "Contrast, every pair, WCAG 2"})
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change()], rows(kit.spec()), table.set_rows))
""")


RULES = _cell("""\
COLUMNS = [{"key": "verdict", "label": "Verdict", "width": 120}, {"key": "rule", "label": "Rule"}, {"key": "seen", "label": "Seen"}]


@nu.host
def rows(spec):
    return [{k: r[k] for k in ("key", "verdict", "rule", "seen")} for r in checks.run(spec)["rules"]]


def out(plane):
    table = nustd.ui.TableRef("rules", props={"columns": COLUMNS, "row_key": "key", "dense": True, "label": "The language's rules"})
    return kit.on_system(plane, lambda base: redraws([System.rev.on_change()], rows(kit.spec()), table.set_rows))
""")


CHECKS = (
    ("verdict", VERDICT),
    ("sheet", _drawing("sheet", "draw.contrast_sheet(s)")),
    ("pairs", PAIRS),
    ("rules", RULES),
)


# --- Review ------------------------------------------------------------------------------------------


INBOX = _cell("""\
import time
from nudemos.design import studio

COLUMNS = [{"key": "who", "label": "From", "width": 150}, {"key": "title", "label": "Proposal"},
           {"key": "checks", "label": "Checks", "width": 140}, {"key": "when", "label": "Arrived", "width": 110}]


class Studio(nustd.ui.Row):
    live = nustd.ui.SwitchRef.slot(label="Team proposals arrive on their own")
    pace = nustd.ui.SliderRef.slot()


class View(nustd.ui.Column):
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="id", clickable_rows=True, dense=True, label="Waiting for a decision")
    studio = Studio.slot(gap=6, align="center")


@nu.host
def rows(inbox, stored, pick):
    sp, now = specs.merged(stored), time.time()
    return [{"id": p["id"], "who": p["who"], "title": ("> " if p["id"] == pick else "") + p["title"],
             "checks": studio.verdict(sp, p["changes"]), "when": kit.ago(p["at"], now)} for p in inbox or []]


def out(plane):
    def build(base):
        read = rows(System.inbox.fallback([]), System.spec.fallback({}), System.pick.fallback(""))
        pace = View.studio.pace
        first = View.table.set_rows([]) >> pace.set(24, min=6, max=90, step=2, label="Seconds between arrivals", show_value=True)
        return first >> nu.ParallelAsync(
            redraws([System.mail.on_change(), System.rev.on_change(), System.pick.on_change()], read, View.table.set_rows, every=15.0),
            redraws([System.paused.on_change()], System.paused.fallback(False).not_(), View.studio.live.set),
            redraws([System.pace.on_change()], System.pace.fallback(studio.PACE), pace.set_value),
            nu.ReactForever(View.table.on_row_click(), lambda ev: System.pick.set(nu.Str(ev["key"]))),
            nu.ReactForever(View.studio.live.on_change(), System.paused.set(nu.Bool(View.studio.live).not_())),
            nu.ReactForever(pace.on_change(), System.pace.set(nu.float(pace))),
        )

    return kit.on_system(plane, build)
""")


OPEN = _cell("""\
import time


class Act(nustd.ui.Row):
    accept = nustd.ui.ButtonRef.slot(label="Accept", icon="check")
    decline = nustd.ui.ButtonRef.slot(label="Decline", icon="x", variant="secondary")
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    head = nustd.ui.MarkdownRef.slot()
    act = Act.slot(gap=2, align="center")
    diff = nustd.ui.HtmlRef.slot(title="The proposal", bordered=False)


@nu.host
def opened(inbox, pick):
    inbox = list(inbox or [])
    return next((p for p in inbox if p["id"] == pick), inbox[0] if inbox else {})


@nu.host
def shown(v, prop, waiting):
    if not prop:
        return {"head": "#### Nothing waiting\\n\\nThe team's proposals land here as they come in.", "doc": draw.proposal(v["spec"], {}, mode=v["mode"]), "note": ""}
    head = f"#### {prop['title']}\\n\\n**{prop['who']}**, {prop['role']}  ·  {kit.ago(prop['at'])}\\n\\n> {prop['why']}"
    return {"head": head, "doc": draw.proposal(v["spec"], prop, mode=v["mode"]), "note": f"{waiting} waiting"}


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


def decide(prop, accepted):
    pid = nu.Str(nu.Dict(prop)["id"])
    move = (
        System.decided.set(decided(System.decided.fallback([]), prop, "accepted" if accepted else "declined"))
        >> System.inbox.set(without(System.inbox.fallback([]), pid))
        >> System.mail.set(System.mail.fallback(0) + 1)
    )
    write = kit.edit(nu.Dict(prop)["changes"], by(prop), nu.Dict(prop)["title"]) if accepted else nu.Noop()
    return nu.IfDo(has(prop), write >> move)


def out(plane):
    def build(base):
        prop = opened(System.inbox.fallback([]), System.pick.fallback(""))
        read = shown(kit.seen(), prop, count(System.inbox.fallback([])))
        draw = lambda v: View.head.set(v["head"]) >> View.diff.set_html(v["doc"]) >> View.act.note.set(v["note"])
        moves = [System.mail.on_change(), System.pick.on_change(), System.rev.on_change(), System.preview.on_change()]
        labels = View.head.set("#### Waiting for the team") >> View.act.accept.set("Accept", icon="check") >> View.act.decline.set("Decline", icon="x", variant="secondary")
        return labels >> nu.ParallelAsync(
            redraws(moves, read, draw),
            nu.ReactForever(View.act.accept.on_click(), nu.let(snap(prop), lambda p: decide(p, True))),
            nu.ReactForever(View.act.decline.on_click(), nu.let(snap(prop), lambda p: decide(p, False))),
        )

    return kit.on_system(plane, build)
""")


DECIDED = _cell("""\
import time

COLUMNS = [{"key": "verdict", "label": "Decision", "width": 110}, {"key": "who", "label": "From", "width": 150},
           {"key": "title", "label": "Proposal"}, {"key": "when", "label": "When", "width": 110}]


@nu.host
def rows(done):
    now = time.time()
    return [{"key": f"{d['id']}-{i}", "verdict": d["verdict"], "who": d["who"], "title": d["title"], "when": kit.ago(d["at"], now)}
            for i, d in reversed(list(enumerate(done or [])))]


def out(plane):
    table = nustd.ui.TableRef("decided", props={"columns": COLUMNS, "row_key": "key", "dense": True, "label": "Decided", "max_rows": 8})
    return kit.on_system(plane, lambda base: redraws([System.mail.on_change()], rows(System.decided.fallback([])), table.set_rows, every=30.0))
""")


REVIEW = (("inbox", INBOX), ("open", OPEN), ("decided", DECIDED))


# --- Export ------------------------------------------------------------------------------------------


CUT = _cell("""\
import re
from nudemos.design import job


class Go(nustd.ui.Row):
    version = nustd.ui.InputRef.slot(label="Version")
    cut = nustd.ui.ButtonRef.slot(label="Cut release", icon="package")


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    drift = nustd.ui.MarkdownRef.slot()
    go = Go.slot(gap=3, align="end")


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


def cut(base, export):
    def made(version):
        v = nu.Str(version)
        return job.cut(base, export, v, snap(kit.spec())) >> kit.go(View.nav, nu.Str("/") + job.release_page(base, v))

    typed = nu.Str(View.go.version).strip()
    return nu.IfDo(typed != "", nu.let(typed, made))


def out(plane):
    def build(base):
        read = nu.Dict.of(drift=drift(System.spec.fallback({}), System.releases.fallback([])), next=following(System.releases.fallback([])))
        draw = lambda v: View.drift.set(v["drift"]) >> View.go.version.set(v["next"])
        return View.drift.set("") >> View.go.version.set("") >> View.go.cut.set("Cut release", icon="package") >> nu.ParallelAsync(
            redraws([System.rev.on_change(), System.mail.on_change()], read, draw),
            nu.ReactForever(View.go.cut.on_click(), cut(base, plane)),
        )

    return kit.on_system(plane, build)
""")


RELEASES = _cell("""\
import time

COLUMNS = [{"key": "version", "label": "Release", "width": 110}, {"key": "files", "label": "Files", "kind": "number", "width": 80},
           {"key": "size", "label": "Size", "width": 100}, {"key": "moved", "label": "From the language"}, {"key": "when", "label": "Cut", "width": 110}]


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="page", clickable_rows=True, dense=True, label="Releases, newest first")


@nu.host
def rows(releases):
    now = time.time()
    out = []
    for r in reversed(releases or []):
        moved = len([k for k in specs.changed(r.get("spec") or {}) if not k.startswith("knob.")])
        out.append({"page": r["page"], "version": r["version"], "files": r["files"], "size": f"{r['bytes'] / 1024:.0f} KB",
                    "moved": f"{moved} tokens" if moved else "as the language ships it", "when": kit.ago(r["at"], now)})
    return out


def out(plane):
    def build(base):
        return nu.ParallelAsync(
            redraws([System.mail.on_change()], rows(System.releases.fallback([])), View.table.set_rows, every=30.0),
            nu.ReactForever(View.table.on_row_click(), lambda ev: kit.go(View.nav, nu.Str("/") + nu.Str(ev["key"]))),
        )

    return kit.on_system(plane, build)
""")


EXPORT = (("cut", CUT), ("releases", RELEASES))


_RELEASE_HEAD = """\
from nudemos.design import job
from nudemos.design.job import Build


def at(term_of):
    # A term over the build's state, landed on this release's job cell.
    return lambda jb: ops.cell_state(job.job_cell(jb), term_of())


def on_build(plane, body):
    return nu.let(snap(job.job_of(plane)), lambda jb: body(nu.Str(jb)))
"""


BUILD_STATUS = _cell(
    _RELEASE_HEAD
    + """\

class Tiles(nustd.ui.Grid):
    files = nustd.ui.StatRef.slot(label="Files")
    size = nustd.ui.StatRef.slot(label="Size")
    took = nustd.ui.StatRef.slot(label="Took")
    now = nustd.ui.StatRef.slot(label="Writing")


class View(nustd.ui.Column):
    pill = nustd.ui.StatusPillRef.slot()
    progress = nustd.ui.ProgressRef.slot()
    tiles = Tiles.slot(columns=4, min_width=140, gap=3)


@nu.host
def summary(status, done, total, index, started, finished, current):
    import time
    n = len(index or [])
    size = sum(f["bytes"] for f in index or [])
    end = finished or time.time()
    took = f"{end - started:.1f}s" if started else "-"
    tone = {"done": "ok", "building": "info"}.get(status, "neutral")
    word = {"done": "released", "building": "building in its own process"}.get(status, "starting")
    return {"tone": tone, "word": word, "value": (done / total * 100) if total else 0.0, "caption": f"{done} of {total} files",
            "files": str(n), "size": f"{size / 1024:.0f} KB", "took": took, "now": current or ("all written" if status == "done" else "-")}


def draw(v):
    t = View.tiles
    return (
        View.pill.set(v["word"], tone=v["tone"]) >> View.progress.set(v["value"], caption=v["caption"])
        >> t.files.set_value(v["files"]) >> t.size.set_value(v["size"]) >> t.took.set_value(v["took"]) >> t.now.set_value(v["now"])
    )


def out(plane):
    def follow(jb):
        cid = job.job_cell(jb)
        read = ops.cell_state(cid, summary(
            Build.status.fallback(""), Build.done.fallback(0), Build.total.fallback(0), Build.index.fallback([]),
            Build.started.fallback(0.0), Build.finished.fallback(0.0), Build.current.fallback(""),
        ))
        return redraws([ops.cell_state(cid, Build.done.on_change()), ops.cell_state(cid, Build.status.on_change())], read, draw, every=2.0)

    return on_build(plane, follow)
"""
)


BUILD_FILES = _cell(
    _RELEASE_HEAD
    + """\

COLUMNS = [{"key": "name", "label": "File"}, {"key": "kind", "label": "Kind", "width": 80},
           {"key": "size", "label": "Size", "width": 100}, {"key": "ms", "label": "Drawn in", "width": 100}]


@nu.host
def rows(index):
    return [{"key": f["key"], "name": f["name"], "kind": f["kind"], "size": f"{f['bytes'] / 1024:.1f} KB" if f["bytes"] >= 1024 else f"{f['bytes']} B",
             "ms": f"{f['ms']} ms"} for f in index or []]


def out(plane):
    table = nustd.ui.TableRef("files", props={"columns": COLUMNS, "row_key": "key", "dense": True, "label": "Files written"})

    def follow(jb):
        cid = job.job_cell(jb)
        return redraws([ops.cell_state(cid, Build.done.on_change())], ops.cell_state(cid, rows(Build.index.fallback([]))), table.set_rows, every=3.0)

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
        cid = job.job_cell(jb)

        read = ops.cell_state(cid, sheet(Build.index.fallback([]), Build.blobs.extract(), {}))
        return redraws([ops.cell_state(cid, Build.done.on_change())], read, view.set_html, every=3.0)

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
        cid = job.job_cell(jb)
        read = ops.cell_state(cid, text(Build.index.fallback([]), Build.blobs.extract()))
        return redraws([ops.cell_state(cid, Build.done.on_change())], read, code.set, every=5.0)

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
from nuspace.system.utils import park

TEXT = {text!r}

out = nustd.ui.MarkdownRef("doc").set(TEXT) >> park()
"""


PRINCIPLES = tuple((name, _doc(text)) for name, text in DOCS)
