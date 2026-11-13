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
import nuspace
import nuspace.web as web
import nustd.ui

TEXT = """\\
Claude Code sessions, run, watched, steered and orchestrated from a space, with Nu as the control plane.

One agent is one Claude Code session: a page that streams everything it says and does, and a headless job \\
under it that runs a short Nu loop over the session. Say something and it is the agent's next turn. \\
Stop it mid-turn, resume it later: it picks up the same conversation, even after the space restarts.

Orchestration is a few lines of Nu over agents, each flow a plane with its cell in full:
"""


#: The three flow planes, made with this one as its first three children: what each tile says.
FLOWS = [
    ("Fan-out and judge", "N agents on one brief, a judge picks the best"),
    ("Chain", "Research, build, review: each answer is the next brief"),
    ("Task board", "A board of tasks that idle agents pull from"),
]


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    flows = nustd.ui.GridRef.slot(nustd.ui.PageLinkRef.slot(variant="tile"), max_columns=3, min_cell_width=200, gap=3)


def tiles(kids):
    return nu.Sequential(*(
        web.link(View.flows[i], nu.List(kids)[i], label=label, description=what) for i, (label, what) in enumerate(FLOWS)
    ))


def out(plane):
    kids = nuspace.Space.planes[plane].children.keys(limit=3)
    return View.text.set(TEXT) >> nu.let(nuspace.atomic(kids), lambda k: nuspace.atomic(tiles(k))) >> nu.ForeverDo(nu.Delay(3600.0))
'''


NEW = """\
import nu
import nuspace
import nuspace.web as web
import nustd.ui
from nudemos.agents import views
from nudemos.agents.claude import READY
from nudemos.agents.flows import SCENARIO, launch_flow
from nudemos.agents.launch import launch
from nudemos.agents.state import agents_of, flows_of, spec_of


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    notice = nustd.ui.MarkdownRef.slot()
    card = nustd.ui.CardRef.slot(title="New agent", subtitle="One Claude Code session: a page that streams it, and a job that runs it")


form = View.card[0].to(nustd.ui.GridRef.slot(max_columns=4, min_cell_width=180, gap=3))
name = form["name"].to(nustd.ui.InputRef.slot(label="Name", placeholder="Name it, or leave it to us"))
cwd = form["cwd"].to(nustd.ui.InputRef.slot(label="Working folder", placeholder="A fresh temp folder"))
model = form["model"].to(nustd.ui.FieldRef.slot(label="Model")).control.to(nustd.ui.SelectRef.slot(options=views.MODELS, value=views.MODELS[0]))
mode = form["mode"].to(nustd.ui.FieldRef.slot(label="Permission mode")).control.to(nustd.ui.SelectRef.slot(options=views.MODES, value=views.MODES[0]))
brief = View.card[1].to(nustd.ui.TextAreaRef.slot(rows=3, auto_resize=True, placeholder="The brief: what should it do?"))
go = View.card[2].to(nustd.ui.RowRef.slot(gap=2, justify="end", wrap=True))
start = go[0].to(nustd.ui.ButtonRef.slot(label="Start agent", icon="play"))
demo_run = go[1].to(nustd.ui.ButtonRef.slot(label="Run the demo: 3 builders and a judge", variant="secondary", icon="git-fork"))


def started(root):
    # One agent from what the form says, its page opened.
    def made(spec):
        def opened(page):
            return launch(root, spec, page=page) >> View.history.push(web.href(page))

        return nu.let("", opened) >> name.reset() >> brief.reset()

    count = nuspace.atomic(agents_of(root).len())
    spec = views.spec_of(nu.Str(name), nu.Str(cwd), nu.Str(model), nu.Str(mode), nu.Str(brief), count)
    return nu.let(spec, made)


def demo(root):
    # The built-in scenario: the Fan-out flow, three builders and a judge, on one brief.
    # The flow planes are the first three children, made with this one.
    kids = nu.List(nuspace.Space.planes[root].children.keys(limit=3))
    fanout = kids.iter().filter(lambda p: spec_of(p) == "agents_fanout").first(default="")

    def run(plane):
        title = nu.Str("Fan-out ") + nu.str(nu.Int(nuspace.atomic(flows_of(plane).len())) + 1)
        spec = nu.Dict.of(brief=SCENARIO, n=3, tasks=[])
        return launch_flow(nu.Str(plane), root, "fanout", spec, title)

    return nu.let(nuspace.atomic(nu.str(fanout)), run)


def defaults():
    # Every part as its slot declares it.
    return nu.Sequential(*(part.init() for part in (name, cwd, model, mode, brief, start, demo_run)))


def out(plane):
    if not READY:
        return View.notice.set(views.MISSING) >> View.card.erase() >> nu.ForeverDo(nu.Delay(3600.0))
    root = nu.Str(plane)
    return defaults() >> nu.ParallelAsync(
        nu.ReactEvery(start.on_click(), started(root)),
        nu.ReactEvery(demo_run.on_click(), demo(root)),
    )
"""


BOARD = """\
import nu
import nuspace
import nuspace.web as web
import nustd.ui
from nudemos.agents import views
from nudemos.agents.state import agents_at


class AgentCard(nustd.ui.Card):
    # The pill sits in the card's actions place; the whole card opens the agent's page.
    actions = nustd.ui.StatusPillRef.slot()
    doing = nustd.ui.TextRef.slot()
    stats = nustd.ui.TextRef.slot(tone="muted", size="sm")


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    empty = nustd.ui.EmptyStateRef.slot(label="No agents yet", description="Start one above, or run the demo.")
    cards = nustd.ui.GridRef.slot(AgentCard, max_columns=3, min_cell_width=280, gap=3)


def card(c):
    k = View.cards[c["key"]]
    return (
        k.set_title(c["name"]) >> k.set_subtitle(c["where"]) >> k.set_href(web.href(c["page"]))
        >> k.actions.set(c["status"], tone=c["tone"]) >> k.doing.set(c["doing"]) >> k.stats.set(c["stats"])
    )


def draw(cards):
    # Every agent's card in place, then the ones gone dropped.
    rows = nu.List(cards)
    keys = rows.iter().map(lambda c: nu.Dict(c)["key"]).to_list()
    empty = nu.IfDo(rows.len() > 0, View.empty.erase(), View.empty.set("No agents yet"))
    return empty >> nu.ForEachDo(rows, card) >> View.cards.keep(keys)


def out(plane):
    kids = agents_at(plane).jobs.on_change()
    return View.head.set("All agents") >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[kids])), nu.let(nuspace.atomic(views.cards(views.board(plane))), draw), every=1.0)
"""
