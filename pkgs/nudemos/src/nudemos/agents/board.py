"""The Agents plane's own cells: what it is, a form that starts agents, and a card per agent.

- ``intro``: what the plane is, and where the flows are.
- ``new``: name, folder, model, permission mode and a brief, and two buttons:
  Start agent makes one agent page with its job (:func:`~.launch.launch`) and
  opens it; Run the demo starts the Fan-out flow on the built-in scenario,
  three builders and a judge.
- ``board``: every agent as a card, live: its status, what it is doing, what it cost.
"""

from __future__ import annotations


__all__ = ["BOARD", "INTRO", "NEW"]


INTRO = '''\
import nu
import nuspace.ui
import nustd.ui
from nuspace import ops
from nuspace.system.utils import snap

TEXT = """\\
Claude Code sessions, run, watched, steered and orchestrated from a space, with Nu as the control plane.

One agent is one Claude Code session: a page that streams everything it says and does, and a headless job \\
under it that runs a short Nu loop over the session. Say something and it is the agent's next turn. \\
Stop it mid-turn, resume it later: it picks up the same conversation, even after the space restarts.

Orchestration is a few lines of Nu over agents, each flow a plane with its cell in full: \\
**Fan-out** (N agents on one brief, a judge picks the best), **Chain** (research, build, review) \\
and **Task board** (idle agents pull the next task).
"""


class Links(nustd.ui.Row):
    fanout = nustd.ui.LinkRef.slot()
    chain = nustd.ui.LinkRef.slot()
    tasks = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    links = Links.slot(gap=4)


def links(kids):
    def to(i):
        return nuspace.ui.href(nu.List(kids)[i])

    L = View.links
    return (
        L.fanout.set(href=to(0), label="Fan-out and judge") >> L.chain.set(href=to(1), label="Chain")
        >> L.tasks.set(href=to(2), label="Task board")
    )


def out(plane):
    return View.text.set(TEXT) >> nu.let(snap(ops.children(plane)), links) >> nu.ForeverDo(nu.Delay(3600.0))
'''


NEW = """\
import nu
import nuspace.ui
import nustd.ui
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.agents import views
from nudemos.agents.claude import READY
from nudemos.agents.flows import SCENARIO, launch_flow
from nudemos.agents.launch import launch
from nudemos.agents.state import agents_of, flows_of, made_by


def pick(options):
    return type("Pick", (nustd.ui.Field,), {"choice": nustd.ui.SelectRef.slot(options=options)})


class Who(nustd.ui.Grid):
    name = nustd.ui.InputRef.slot(label="Name", placeholder="Name it, or leave it to us")
    cwd = nustd.ui.InputRef.slot(label="Working folder", placeholder="A fresh temp folder")
    model = pick(views.MODELS).slot(label="Model")
    mode = pick(views.MODES).slot(label="Permission mode")


class Go(nustd.ui.Row):
    start = nustd.ui.ButtonRef.slot(label="Start agent", icon="play")
    demo = nustd.ui.ButtonRef.slot(label="Run the demo: 3 builders and a judge", variant="secondary", icon="git-fork")


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    notice = nustd.ui.MarkdownRef.slot()
    head = nustd.ui.HeadingRef.slot(level=4)
    who = Who.slot(columns=4, min_width=180, gap=3)
    brief = nustd.ui.TextAreaRef.slot(rows=3, auto_resize=True, placeholder="The brief: what should it do?")
    go = Go.slot(gap=2, align="end")


W = View.who


def started(root):
    # One agent from what the form says, its page opened.
    def made(spec):
        def opened(page):
            return launch(root, spec, page=page) >> View.history.push(nuspace.ui.href(page))

        return nu.let("", opened) >> W.name.set("") >> View.brief.set("")

    count = snap(agents_of(root).len())
    spec = views.spec_of(
        nu.Str(W.name), nu.Str(W.cwd), nu.Str(W.model.choice), nu.Str(W.mode.choice), nu.Str(View.brief), count
    )
    return nu.let(spec, made)


def demo(root):
    # The built-in scenario: the Fan-out flow, three builders and a judge, on one brief.
    fanout = nu.First(ops.children(root).iter().filter(lambda p: made_by(p) == "agents_fanout"))

    def run(plane):
        name = nu.Str("Fan-out ") + nu.str(nu.Int(snap(flows_of(plane).len())) + 1)
        spec = nu.Dict.of(brief=SCENARIO, n=3, tasks=[])
        return launch_flow(nu.Str(plane), root, "fanout", spec, name)

    return nu.let(snap(nu.str(fanout).fallback("")), run)


def defaults():
    return (
        View.head.set("New agent") >> W.name.set("") >> W.cwd.set("")
        >> W.model.choice.set(views.MODELS[0]) >> W.mode.choice.set(views.MODES[0])
        >> View.brief.set("") >> View.go.start.set("Start agent", icon="play")
        >> View.go.demo.set("Run the demo: 3 builders and a judge", variant="secondary", icon="git-fork")
    )


def out(plane):
    if not READY:
        return View.notice.set(views.MISSING) >> nu.ForeverDo(nu.Delay(3600.0))
    root = nu.Str(plane)
    return defaults() >> nu.ParallelAsync(
        nu.ReactForever(View.go.start.on_click(), started(root)),
        nu.ReactForever(View.go.demo.on_click(), demo(root)),
    )
"""


BOARD = """\
import nu
import nustd.ui
from nuspace.shapes import Space
from nuspace.system.utils import redraws
from nudemos.agents import views


class AgentCard(nustd.ui.Card):
    pill = nustd.ui.StatusPillRef.slot()
    doing = nustd.ui.TextRef.slot()
    stats = nustd.ui.TextRef.slot()
    open = nustd.ui.LinkRef.slot(label="Open")


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    empty = nustd.ui.EmptyStateRef.slot(label="No agents yet", description="Start one above, or run the demo.")
    cards = nustd.ui.GridRef.slot(AgentCard, columns=3, min_width=280, gap=3)


def card(c):
    k = View.cards[c["key"]]
    return (
        k.set_title(c["name"]) >> k.set_subtitle(c["where"]) >> k.pill.set(c["status"], tone=c["tone"])
        >> k.doing.set(c["doing"]) >> k.stats.set(c["stats"]) >> k.open.set(href=c["href"], label="Open")
    )


def draw(cards):
    each = nu.ForEachDo(nu.List(cards), card)
    return nu.IfDo(nu.List(cards).len() > 0, View.empty.erase() >> each)


def out(plane):
    kids = Space.planes[plane].children.on_change()
    return View.head.set("All agents") >> View.empty.set("No agents yet") >> redraws(
        [kids], views.cards(views.board(plane)), draw, every=1.0
    )
"""
