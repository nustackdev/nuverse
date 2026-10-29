"""The ``quickstart`` Plane: the first page a newcomer sees, five cells stacked.

``nuspace run --with quickstart`` opens it, and every run after reopens
the same one. In a minute it shows what a space is, lets the person change
a live cell with their own hands, and hands them a next step.

- ``welcome``: what a cell is, where this space lives, how to come back.
- ``dial``: a slider kept in the plane's state, ``level``.
- ``meter``: a gauge that follows ``level``. Its ``LIMIT`` is the line the
  person edits: Cmd+Enter reruns it and it picks up where it was.
- ``agent``: two prompts to paste into an agent, the path filled in.
- ``next``: make a page, open a demo, docs, Discord.

Every source is inline, so opening a cell's code shows the real program.
The helpers the cells share (:func:`where`, :func:`again`, :func:`tips`, :func:`put_back`,
:func:`welcome_back`, :func:`moved`) live here, not in any cell, so the
code a newcomer opens stays short.
"""

from __future__ import annotations

from pathlib import Path

import nu
import nustd.ui
from nuspace import PlaneSpec, ops
from nuspace.shapes import Space
from nuspace.system.utils import redraws, snap


__all__ = [
    "AGENT",
    "DIAL",
    "METER",
    "NEXT",
    "PLANE",
    "SHIPPED_LIMIT",
    "START",
    "WELCOME",
    "again",
    "counting",
    "moved",
    "put_back",
    "tips",
    "welcome_back",
    "where",
]


START = 62.0  # the slider's first value, the still's number
SHIPPED_LIMIT = 70  # what meter ships with; anything else counts as edited

#: The home folder, read once, so a path under it shows as ``~/...``.
HOME = str(Path.home())


WELCOME = """\
# For agents: this is the person's Quickstart page. Build new work on a page of its own, not here.
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import park
from nuverse.planes import quickstart

LEAD = "Everything here is a cell: a tiny program that holds data, runs logic and draws itself. This page is cells too."


class Where(nustd.ui.Line):
    mark = nustd.ui.IconRef.slot(name="folder", size="sm", tone="muted")
    said = nustd.ui.TextRef.slot(tone="muted")
    path = nustd.ui.TextRef.slot(mono=True)
    tail = nustd.ui.TextRef.slot(tone="muted")


class View(nustd.ui.Column):
    lead = nustd.ui.TextRef.slot(value=LEAD, size="lg")
    where = Where.slot()
    again = nustd.ui.CodeRef.slot(language="bash", show_copy=True)
    then = nustd.ui.TextRef.slot(tone="muted")


W = View.where


def show(raw):
    back = View.again.set(quickstart.again(raw)) >> View.then.set(
        "It opens as you left it. Your agent can build here too, prompts are below.")
    kept = (W.said.set("This space lives in") >> W.path.set(quickstart.where(raw) + "/.nuspace.")
            >> W.tail.set("Come back any time:"))
    gone = (W.said.set("This space is throwaway, it goes when you stop it. To keep one, run:")
            >> W.path.hide() >> W.tail.hide() >> View.again.set(quickstart.again(raw))
            >> View.then.set("Your agent can build here too, prompts are below."))
    return nu.IfDo(nu.Str(raw) == "", gone, kept >> back)


def out():
    raw = ops.snapshot(nuspace.Space.state.info.path.fallback(""))
    drawn = View.lead.init() >> View.where.init() >> View.again.init() >> View.then.init()
    return drawn >> nu.let(raw, show) >> park()
"""


DIAL = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws, snap
from nuverse.planes import quickstart


class Page(nuspace.PlaneState):
    level = nustd.kv.FloatRef.slot()        # the number the meter below reads


class Turn(nustd.ui.PageSection):
    actions = nustd.ui.ButtonRef.slot(label="Put the meter back", variant="ghost", size="sm", icon="undo-2")
    level = nustd.ui.SliderRef.slot(min=0, max=100, step=1)


class View(nustd.ui.Column):
    turn = Turn.slot(title="Your first cell", bordered=True,
                     description="Drag the slider and let go, the meter below follows. It stays where you leave it.")


slider = View.turn.level


def keep(v):
    return ops.atomic_state(Page.level.set(nu.Float(v)))


def out(plane):
    moved = nu.ReactForever(slider.on_change(), nu.let(nu.float(slider), keep) >> quickstart.moved())
    follow = redraws([Page.level.on_change()], Page.level.fallback(quickstart.START), slider.set_value)
    return quickstart.counting(
        View.turn.actions.hide() >> View.turn.init()
        >> quickstart.welcome_back(View.turn, snap(Page.level.fallback(quickstart.START)))
        >> nu.ParallelAsync(moved, follow, quickstart.put_back(plane, View.turn.actions)))
"""


METER = """\
# Change me to 40, then press Cmd+Enter (Ctrl+Enter on Linux).
LIMIT = 70

import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace.system.utils import redraws
from nuverse.planes import quickstart


class Page(nuspace.PlaneState):
    level = nustd.kv.FloatRef.slot()        # the number from the slider above


class Reading(nustd.ui.Row):
    gauge = nustd.ui.GaugeRef.slot()
    note = nustd.ui.TextRef.slot(size="lg", weight="medium")


class View(nustd.ui.Column):
    reading = Reading.slot(gap=4, align="center")


R = View.reading


def draw(level):
    over = nu.Float(level) > LIMIT
    said = nu.Str(nu.If(over, "Over", "Under")) + " the limit of " + str(LIMIT) + "."
    return R.gauge.set(nu.Float(level) / 100, variant=nu.If(over, "warn", "neutral")) >> R.note.set(said)


def out():
    follow = redraws([Page.level.on_change()], Page.level.fallback(quickstart.START), draw)
    return R.init() >> quickstart.tips(LIMIT) >> follow
"""


AGENT = """\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import park
from nuverse.planes import quickstart


class Ask(nustd.ui.PageSection):
    asks = nustd.ui.Column.slot(gap=2)
    none = nustd.ui.TextRef.slot(tone="muted")
    setup = nustd.ui.LinkRef.slot(href="https://nustack.dev/#start-agent", target="_blank",
        label="Agent not set up yet? Add nustack to Claude Code or Codex, then come back and paste a prompt above.")


class View(nustd.ui.Column):
    ask = Ask.slot(title="Build with your agent", bordered=True,
        description="Your agent can build here too. What it makes shows up in the sidebar on the left, as it builds.")


A = View.ask
ASKS = (
    "build a live monitor of this machine: CPU, memory and disk, on a page of its own.",
    "make a reading list page: a form to add a book, and a table of what I have read.",
)
PROMPT = dict(nustd.ui.CodeRef.slot(wrap=True, show_copy=True).props)


def show(raw):
    lead = nu.Str("In my nuspace space at ") + quickstart.where(raw) + ", "
    asks = nu.Sequential(*(nustd.ui.CodeRef(f"ask{i}", parent_ref=A.asks, props=PROMPT).set(lead + a)
                           for i, a in enumerate(ASKS))) >> A.none.hide()
    gone = A.asks.hide() >> A.none.set("Your agent finds a space by its folder, and this one has none. "
                                       "Stop it and run nuspace run --with quickstart to get one.")
    return nu.IfDo(nu.Str(raw) == "", gone, asks)


def out():
    raw = ops.snapshot(nuspace.Space.state.info.path.fallback(""))
    return A.init() >> nu.let(raw, show) >> park()
"""


NEXT = """\
import importlib.util
import shutil
import nu
import nustd.ui
import nuspace
import nuspace.ui
from nuspace import ops
from nuspace.ext import EMPTY_PLANE
from nuspace.system.utils import snap
from nuverse.planes import quickstart

HAS_DEMOS = importlib.util.find_spec("nudemos") is not None
HAS_CC = shutil.which("claude") is not None


class Demo(nustd.ui.Row):
    icon = nustd.ui.IconRef.slot(framed=True)
    words = nustd.ui.HeadingRef.slot(level=4)
    room = nustd.ui.SpacerRef.slot()
    go = nustd.ui.ButtonRef.slot(label="Open", variant="outline", size="sm")


class Missing(nustd.ui.Column):
    said = nustd.ui.TextRef.slot(tone="muted", value=(
        "Demos come in their own package. Install it, then stop the space with Ctrl+C and run it again:"))
    pip = nustd.ui.CodeRef.slot(language="bash", value="pip install nudemos")
    again = nustd.ui.CodeRef.slot(language="bash")


class Bye(nustd.ui.Line):
    said = nustd.ui.TextRef.slot(tone="muted", value=(
        "This page is yours. Change it, add to it, or delete it. Click below the last cell to write, or press"))
    slash = nustd.ui.KbdRef.slot(label="/", size="sm")
    rest = nustd.ui.TextRef.slot(tone="muted", value="for a new cell. Deleted it? The same line brings a fresh one back.")


class Where(nustd.ui.PageSection):
    actions = nustd.ui.ButtonRef.slot(label="Make a page", icon="file-plus")
    movies = Demo.slot(align="center", gap=3)
    agents = Demo.slot(align="center", gap=3)
    recipes = Demo.slot(align="center", gap=3)
    install = Missing.slot(gap=2)       # the install lines, only when nudemos is missing
    docs = nustd.ui.PageLinkRef.slot(variant="row", href="https://nustack.dev/docs/nuspace", target="_blank",
                                     icon="book-open", title="Docs", description="How spaces, cells and nu fit together.")
    discord = nustd.ui.PageLinkRef.slot(variant="row", href="https://discord.gg/tCa8YE7XVr", target="_blank",
                                        icon="messages-square", title="Discord", description="Ask, show what you built.")
    bye = Bye.slot()


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    where = Where.slot(title="Where next", bordered=True)


W = View.where
made = nuspace.Space.state.made
DEMOS = (
    (W.movies, "film", "Your personal movie tracker.",
     "A film base you run yourself. Films, people and timelines, all linked."),
    (W.agents, "bot", "A team of agents, run from one space.",
     "Brief, watch and steer Claude Code sessions."),
    (W.recipes, "layout-dashboard", "Pages to poke at",
     "A dashboard, a catalog, a settings page. Whole pages built from the kit, each one live."),
)


def fill_rows(raw):
    rows = [row.icon.set(icon) >> row.words.set(title) >> row.words.set_subtitle(line)
            for row, icon, title, line in DEMOS]
    if HAS_DEMOS:
        rows.append(W.install.hide())
        if not HAS_CC:
            rows.append(W.agents.words.set_eyebrow("Needs Claude Code"))
    else:
        rows += [row.go.hide() for row, *_ in DEMOS]
        rows.append(W.agents.words.set_subtitle(
            'Brief, watch and steer Claude Code sessions. Also needs pip install "nudemos[agents]".'))
        rows.append(W.install.again.set(quickstart.again(raw)))
    return nu.Sequential(*rows)


def open_made(name, spec):
    \"\"\"Make it once, kept under the name with_plane uses, then go there.\"\"\"
    def go(pid):
        make = ops.create_plane(spec, into=pid) >> ops.atomic(made.set_item(name, nu.Str(pid)))
        return (pid.set(snap(made.get_item(name, "")))
                >> nu.IfDo(snap(ops.plane_exists(nu.Str(pid))), nu.Noop(), make)
                >> ops.track("quickstart_demo_opened") >> View.history.push(nuspace.ui.href(nu.Str(pid))))
    return nu.let("", go)


def make_page(plane):
    def go(pid):
        return (ops.create_plane(EMPTY_PLANE, parent=plane, name="My first page", into=pid)
                >> ops.track("quickstart_page_made") >> View.history.push(nuspace.ui.href(nu.Str(pid))))
    return nu.let("", go)


def out(plane):
    arms = [nu.ReactForever(W.actions.on_click(), make_page(plane))]
    if HAS_DEMOS:
        from nudemos import agents, movies, recipes
        arms += [
            nu.ReactForever(W.movies.go.on_click(), open_made("nudemos.movies", movies.PLANE)),
            nu.ReactForever(W.agents.go.on_click(), open_made("nudemos.agents", agents.PLANE)),
            nu.ReactForever(W.recipes.go.on_click(), open_made("nudemos.recipes", recipes.PLANE)),
        ]
    raw = ops.snapshot(nuspace.Space.state.info.path.fallback(""))
    return W.init() >> nu.let(raw, fill_rows) >> nu.ParallelAsync(*arms)
"""


PLANE = PlaneSpec(
    "quickstart",  # nuverse.quickstart, what --with quickstart resolves to
    "Quickstart",
    icon="emoji:👋",
    description="Your first page: what a space is, one live cell to change, where to go next.",
    meta={"editable": True, "full_width": False},
    cells=(
        ("welcome", WELCOME),
        ("dial", DIAL),
        ("meter", METER),
        ("agent", AGENT),
        ("next", NEXT),
    ),
    group="Quickstart",
    backend="async",
)


# --- what the cells share --------------------------------------------------------------------


def where(raw: nu.StrArg) -> nu.Str:
    """The space's path the way the terminal header shows it: absolute, home as ``~``."""
    path = nu.Str(raw)
    return nu.Str(nu.If(path.startswith(HOME), path.replace(HOME, "~", 1), path))


def again(raw: nu.StrArg) -> nu.Str:
    """The line that reopens this space: no path for home or a throwaway, else the path."""
    path = nu.Str(raw)
    bare = nu.Str("nuspace run --with quickstart")
    named = nu.Str("nuspace run ") + where(raw) + " --with quickstart"
    return nu.Str(nu.If(path == "", bare, nu.If(path == HOME, bare, named)))


class _Tip(nustd.ui.Line):
    icon = nustd.ui.IconRef.slot(name="code", size="sm", tone="muted")
    said = nustd.ui.TextRef.slot(
        tone="muted",
        value=(
            "Point at this cell and a </> button shows on its right. "
            "Click it, change LIMIT to 40, then press"
        ),
    )
    press = nustd.ui.ShortcutRef.slot(keys=["mod", "enter"], size="sm")


class _Tips(nustd.ui.Column):
    tip = _Tip.slot()
    done = nustd.ui.TextRef.slot(
        tone="ok",
        value=(
            "You rewrote a running cell, and it picked up right where it was. "
            "That's nu: a cell is a few lines, not a thousand."
        ),
    )


def tips(limit: int) -> nu.Nu:
    """Draw the tip, and the done line once ``limit`` differs from what shipped. Draws and ends."""
    edited = limit != SHIPPED_LIMIT
    done = _Tips.done.init() >> ops.track("quickstart_edited") if edited else _Tips.done.hide()
    return _Tips.tip.init() >> done


def put_back(plane: nu.StrArg, button: nustd.ui.Ref) -> nu.Nu:
    """``button`` up while meter's source is not as shipped; a click puts it back. Never returns."""

    def found(cid: nu.ObjectRef) -> nu.Nu:
        meter = nu.Str(cid)
        shown = redraws(
            [Space.cells[meter].prog.on_change()],
            ops.prog(meter) != METER,
            lambda off: nu.IfDo(nu.Bool(off), button.display(), button.hide()),
        )
        back = ops.set_prog(meter, METER) >> ops.track("quickstart_put_back")
        return nu.ParallelAsync(shown, nu.ReactForever(button.on_click(), back))

    return nu.let(snap(ops.cell_named(plane, "meter")), found)


def welcome_back(section: nustd.ui.Ref, level: nu.Nu) -> nu.Nu:
    """Say where the slider was left, when it was moved off :data:`START` on an earlier run."""
    said = (
        nu.Str("Still at ")
        + nu.str(nu.int(nu.Round(nu.Float(level))))
        + ", where you left it. Drag it again, the meter below follows."
    )
    return nu.IfDo(nu.Float(level) != START, section.set_description(said))


class _Told(nu.Shape):
    """Whether this run has tracked ``quickstart_moved`` yet."""

    moved = nu.ObjectRef.slot()


def counting(body: nu.Nu) -> nu.Nu:
    """``body`` with a run-local flag for :func:`moved`, so a run tracks its first move only."""
    return nu.Frame(_Told, body, moved=False)


def moved() -> nu.Nu:
    """Track ``quickstart_moved`` the first time in a run, inside :func:`counting`. No store write."""
    first = ops.track("quickstart_moved") >> _Told.moved.set(True)
    return nu.IfDo(nu.Bool(_Told.moved).not_(), first)
