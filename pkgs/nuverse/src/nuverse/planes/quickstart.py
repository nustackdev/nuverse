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
The helpers the cells share (:func:`where`, :func:`throwaway`, :func:`again`,
:func:`tips`, :func:`put_back`, :func:`welcome_back`, :func:`moved`) live
here, not in any cell, so the code a newcomer opens stays short.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import nu
import nuspace
import nustd.ui
from nuspace._telemetry.usage import track
from nuspace.ops.interactions import Fabrics
from nuspace.shapes import Space
from nuspace.specs import PlaneSpec, SpecCells, WebOptions


__all__ = [
    "AGENT",
    "DIAL",
    "METER",
    "NEXT",
    "PLANE",
    "SHIPPED_LIMIT",
    "START",
    "THROWAWAY",
    "WELCOME",
    "again",
    "counting",
    "moved",
    "put_back",
    "throwaway",
    "tips",
    "welcome_back",
    "where",
]


START = 62.0  # the slider's first value, the still's number
SHIPPED_LIMIT = 70  # what meter ships with; anything else counts as edited

#: The home folder, read once, so a path under it shows as ``~/...``.
HOME = str(Path.home())

#: Where the host makes a throwaway space, ``<temp dir>/nuspace-<hex>``. A
#: space whose path starts with it is gone once it stops.
THROWAWAY = str(Path(tempfile.gettempdir()) / "nuspace-")


WELCOME = """\
# For agents: this is the person's Quickstart page. Build new work on a page of its own, not here.
import nu
import nustd.ui
import nuspace
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
    return nu.IfDo(quickstart.throwaway(raw), gone, kept >> back)


def out():
    raw = nuspace.atomic(nuspace.Space.info.path.fallback(""))
    drawn = View.lead.init() >> View.where.init() >> View.again.init() >> View.then.init()
    return drawn >> nu.let(raw, show)
"""


DIAL = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuverse.planes import quickstart


class Page(nu.Shape):
    level = nustd.kv.FloatRef.slot()        # the number the meter below reads


PAGE = nuspace.at.plane.state(Page)         # this plane's state, shared by its cells


class Turn(nustd.ui.Card):
    actions = nustd.ui.ButtonRef.slot(label="Put the meter back", variant="ghost", size="sm", icon="undo-2")
    level = nustd.ui.SliderRef.slot(min=0, max=100, step=1)


class View(nu.Shape):
    turn = Turn.slot(title="Your first cell",
                     subtitle="Drag the slider and let go, the meter below follows. It stays where you leave it.")


slider = View.turn.level


def keep(v):
    return nuspace.atomic(PAGE.level.set(nu.Float(v)))


def out(plane):
    moved = nu.ReactEvery(slider.on_change(), nu.let(nu.float(slider), keep) >> quickstart.moved())
    follow = nu.Reconcile(
        nuspace.atomic(nu.OnAny(PAGE.level.on_change())),
        nu.let(nuspace.atomic(PAGE.level.fallback(quickstart.START)), slider.set_value),
    )
    return quickstart.counting(
        View.turn.actions.hide() >> View.turn.init()
        >> quickstart.welcome_back(View.turn, nuspace.atomic(PAGE.level.fallback(quickstart.START)))
        >> nu.ParallelAsync(moved, follow, quickstart.put_back(plane, View.turn.actions)))
"""


METER = """\
# Change me to 40, then press Cmd+Enter (Ctrl+Enter on Linux).
LIMIT = 70

import nu
import nustd.kv
import nustd.ui
import nuspace
from nuverse.planes import quickstart


class Page(nu.Shape):
    level = nustd.kv.FloatRef.slot()        # the number from the slider above


PAGE = nuspace.at.plane.state(Page)         # this plane's state, shared by its cells


class Reading(nustd.ui.Row):
    gauge = nustd.ui.GaugeRef.slot()
    note = nustd.ui.TextRef.slot(size="lg", weight="medium")


class View(nu.Shape):
    reading = Reading.slot(gap=4, align="center")


R = View.reading


def draw(level):
    over = nu.Float(level) > LIMIT
    said = nu.Str(nu.If(over, "Over", "Under")) + " the limit of " + str(LIMIT) + "."
    return R.gauge.set(nu.Float(level) / 100, variant=nu.If(over, "warn", "neutral")) >> R.note.set(said)


def out():
    follow = nu.Reconcile(
        nuspace.atomic(nu.OnAny(PAGE.level.on_change())),
        nu.let(nuspace.atomic(PAGE.level.fallback(quickstart.START)), draw),
    )
    return R.init() >> quickstart.tips(LIMIT) >> follow
"""


AGENT = """\
import nu
import nustd.ui
import nuspace
from nuverse.planes import quickstart


class Ask(nustd.ui.Card):
    asks = nustd.ui.Column.slot(gap=2)
    none = nustd.ui.TextRef.slot(tone="muted")
    footer = nustd.ui.LinkRef.slot(href="https://nustack.dev/#start-agent", target="_blank",
        label="Agent not set up yet? Add nustack to Claude Code or Codex, then come back and paste a prompt above.")


class View(nu.Shape):
    ask = Ask.slot(title="Build with your agent",
        subtitle="Your agent can build here too. What it makes shows up in the sidebar on the left, as it builds.")


A = View.ask
ASKS = (
    "build a live monitor of this machine: CPU, memory and disk, on a page of its own.",
    "make a reading list page: a form to add a book, and a table of what I have read.",
)
PROMPT = nustd.ui.CodeRef.slot(wrap=True, show_copy=True)


def show(raw):
    lead = nu.Str("In my nuspace space at ") + quickstart.where(raw) + ", "
    asks = nu.Sequential(*(A.asks[i].to(PROMPT).set(lead + a) for i, a in enumerate(ASKS))) >> A.none.hide()
    gone = A.asks.hide() >> A.none.set("Your agent finds a space by its folder, and this one has none. "
                                       "Stop it and run nuspace run --with quickstart to get one.")
    return nu.IfDo(quickstart.throwaway(raw), gone, asks)


def out():
    raw = nuspace.atomic(nuspace.Space.info.path.fallback(""))
    return A.init() >> nu.let(raw, show)
"""


NEXT = """\
import importlib
import importlib.util
import shutil
import nu
import nustd.ui
import nuspace
import nuspace.web as web
from nuspace._telemetry.usage import track
from nuspace.specs import EMPTY_PLANE
from nuverse.planes import quickstart

HAS_DEMOS = importlib.util.find_spec("nudemos") is not None
HAS_CC = shutil.which("claude") is not None


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


class Where(nustd.ui.Card):
    actions = nustd.ui.ButtonRef.slot(label="Make a page", icon="file-plus", size="sm")
    demos = nustd.ui.GridRef.slot(max_columns=3, min_cell_width=150, gap=3)
    install = Missing.slot(gap=2)       # the install lines, only when nudemos is missing
    links = nustd.ui.GridRef.slot(max_columns=2, min_cell_width=240, gap=3)
    bye = Bye.slot()


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    where = Where.slot(title="Where next", gap=4)


W = View.where
# Each demo: its nudemos module, icon, title, what it is.
DEMOS = (
    ("movies", "film", "Your personal movie tracker.",
     "A film base you run yourself. Films, people and timelines, all linked."),
    ("agents", "bot", "A team of agents, run from one space.",
     "Brief, watch and steer Claude Code sessions."),
    ("recipes", "layout-dashboard", "Pages to poke at",
     "A dashboard, a catalog, a settings page. Whole pages built from the kit, each one live."),
)
DEMO = nustd.ui.CardRef.slot(size="sm", variant="outline")
OPEN = nustd.ui.ButtonRef.slot(label="Open", variant="outline", size="sm")
LINKS = (
    nustd.ui.PageLinkRef.slot(variant="tile", href="https://nustack.dev/docs/nuspace", target="_blank",
                              icon="book-open", title="Docs", description="How spaces, cells and nu fit together."),
    nustd.ui.PageLinkRef.slot(variant="tile", href="https://discord.gg/tCa8YE7XVr", target="_blank",
                              icon="messages-square", title="Discord", description="Ask, show what you built."),
)


def demo(i):
    return W.demos[i].to(DEMO)


def fill(raw):
    drawn = []
    for i, (name, icon, title, line) in enumerate(DEMOS):
        card = demo(i)
        if name == "agents" and not HAS_DEMOS:
            line += ' Also needs pip install "nudemos[agents]".'
        drawn.append(card.set_title(title) >> card.set_subtitle(line)
                     >> card.media[0].to(nustd.ui.IconRef.slot(framed=True)).set(icon))
        if HAS_DEMOS:
            drawn.append(card.footer[0].to(OPEN).init())
        if name == "agents" and HAS_DEMOS and not HAS_CC:
            drawn.append(card.set_caption("Needs Claude Code"))
    drawn.append(W.install.hide() if HAS_DEMOS else W.install.again.set(quickstart.again(raw)))
    drawn += [W.links[i].to(link).init() for i, link in enumerate(LINKS)]
    return nu.Sequential(*drawn)


def open_made(spec):
    \"\"\"Open the newest plane made from the spec, as with_plane does: made first when there is none.\"\"\"
    newest = nuspace.Space.indexes.spec_planes[nuspace.specs.registered_name(spec)].ids.last(default="")

    def go(pid):
        gone = nuspace.plane.exists(nu.Str(pid)).not_()
        return (pid.set(nuspace.atomic(newest))
                >> nu.IfDo(nuspace.atomic(gone), nuspace.specs.add_plane(spec, into=pid))
                >> track("quickstart_demo_opened") >> View.history.push(web.href(nu.Str(pid))))
    return nu.let("", go)


def make_page(plane):
    def go(pid):
        return (nuspace.specs.add_plane(EMPTY_PLANE, parent=plane, name="My first page", into=pid)
                >> track("quickstart_page_made") >> View.history.push(web.href(nu.Str(pid))))
    return nu.let("", go)


def out(plane):
    arms = [nu.ReactEvery(W.actions.on_click(), make_page(plane))]
    if HAS_DEMOS:
        arms += [nu.ReactEvery(demo(i).footer[0].to(OPEN).on_click(),
                               open_made(importlib.import_module("nudemos." + name).PLANE))
                 for i, (name, *_) in enumerate(DEMOS)]
    raw = nuspace.atomic(nuspace.Space.info.path.fallback(""))
    return W.init() >> nu.let(raw, fill) >> nu.ParallelAsync(*arms)
"""


PLANE = PlaneSpec(
    "quickstart",  # nuverse.quickstart, what --with quickstart resolves to
    "Quickstart",
    icon="emoji:👋",
    description="Your first page: what a space is, one live cell to change, where to go next.",
    cells=(
        ("welcome", WELCOME),
        ("dial", DIAL),
        ("meter", METER),
        ("agent", AGENT),
        ("next", NEXT),
    ),
    group="Quickstart",
    web=WebOptions(editable=True),
    backend="async",
)


# --- what the cells share --------------------------------------------------------------------


def where(raw: nu.StrArg) -> nu.Str:
    """The space's path the way the terminal header shows it: absolute, home as ``~``."""
    path = nu.Str(raw)
    return nu.Str(nu.If(path.startswith(HOME), path.replace(HOME, "~", 1), path))


def throwaway(raw: nu.StrArg) -> nu.Bool:
    """Whether the space at path ``raw`` is a throwaway one, gone when it stops: no path, or under :data:`THROWAWAY`."""
    path = nu.Str(raw)
    return nu.Bool((path == "").or_(path.startswith(THROWAWAY)))


def again(raw: nu.StrArg) -> nu.Str:
    """The line that reopens this space: no path for home or a throwaway, else the path."""
    path = nu.Str(raw)
    bare = nu.Str("nuspace run --with quickstart")
    named = nu.Str("nuspace run ") + where(raw) + " --with quickstart"
    return nu.Str(nu.If(throwaway(raw).or_(path == HOME), bare, named))


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
    done = _Tips.done.init() >> track("quickstart_edited") if edited else _Tips.done.hide()
    return _Tips.tip.init() >> done


def put_back(plane: nu.StrArg, button: nustd.ui.Ref) -> nu.Nu:
    """``button`` up while meter's source is not as shipped; a click puts it back.

    Meter is found by the name the spec gave it, in the plane's state
    (:class:`~nuspace.specs.SpecCells`). Never returns while meter is in the
    space; a plane with no meter keeps the button down and returns.
    """

    def found(cid: nu.ObjectRef) -> nu.Nu:
        meter = nu.Str(cid)
        source = nu.Str(Space.cells[meter].prog.fallback(""))
        shown = nu.Reconcile(
            nuspace.atomic(nu.OnAny(Space.cells[meter].prog.on_change())),
            nu.let(
                nuspace.atomic(source != METER),
                lambda off: nu.IfDo(nu.Bool(off), button.display(), button.hide()),
            ),
        )
        # The fabrics worked out before the commit, so no build runs inside it.
        fixed = nu.let(
            Fabrics(METER, plane, meter),
            lambda used: nuspace.atomic(nuspace.cell.set_prog(meter, METER, fabrics=used)),
        )
        back = fixed >> track("quickstart_put_back")
        there = nuspace.atomic(nuspace.cell.exists(meter))
        return nu.IfDo(
            there, nu.ParallelAsync(shown, nu.ReactEvery(button.on_click(), back)), button.hide()
        )

    named = nuspace.at.plane(id=plane).state(SpecCells).ids["meter"]
    return nu.let(nuspace.atomic(named.fallback("")), found)


def welcome_back(card: nustd.ui.CardRef, level: nu.Nu) -> nu.Nu:
    """Say where the slider was left, when it was moved off :data:`START` on an earlier run."""
    said = (
        nu.Str("Still at ")
        + nu.str(nu.int(nu.Round(nu.Float(level))))
        + ", where you left it. Drag it again, the meter below follows."
    )
    return nu.IfDo(nu.Float(level) != START, card.set_subtitle(said))


class _Told(nu.Shape):
    """Whether this run has tracked ``quickstart_moved`` yet."""

    moved = nu.ObjectRef.slot()


def counting(body: nu.Nu) -> nu.Nu:
    """``body`` with a run-local flag for :func:`moved`, so a run tracks its first move only."""
    return nu.Frame(_Told, body, moved=False)


def moved() -> nu.Nu:
    """Track ``quickstart_moved`` the first time in a run, inside :func:`counting`. No store write."""
    first = track("quickstart_moved") >> _Told.moved.set(True)
    return nu.IfDo(nu.Bool(_Told.moved).not_(), first)
