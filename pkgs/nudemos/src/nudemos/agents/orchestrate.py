"""The orchestration planes: Fan-out, Chain, Task board. One flow each, run from a form.

Each plane shows its flow's cell, the whole of it, then a form that starts a
run of it and every run so far: its phase, its agents and what they are up
to, and what it came to. A run is a headless job under the plane
(:func:`~.flows.launch_flow`); its agents are pages under the Agents plane.
"""

from __future__ import annotations

from typing import Any

import nu
import nuspace
from nuspace.specs import PlaneSpec, WebOptions

from .flows import BOARD, SCENARIO
from .state import agent, flow_of, flows_of, status_of
from .views import TONES


__all__ = [
    "ASKS",
    "CHAIN_PLANE",
    "FANOUT_PLANE",
    "RUN",
    "TASKS_PLANE",
    "about",
    "add_task",
    "flow_view",
    "flows_view",
    "shown",
    "with_task",
]


#: What each flow's form starts out saying: the brief (a task per line for the board) and how many agents.
ASKS: dict[str, dict[str, Any]] = {
    "fanout": {"brief": SCENARIO, "n": 3},
    "chain": {"brief": SCENARIO, "n": 1},
    "tasks": {"brief": "\n".join(BOARD), "n": 2},
}

_ABOUTS = {
    "fanout": (
        "### Fan-out and judge\n\n"
        "Every builder gets the same brief, each in a folder of its own, all at once. "
        "When all are done, a judge reads every folder and picks the best one, with its reasons. "
        "This is the whole flow, a Nu cell over a `Team` of agents:"
    ),
    "chain": (
        "### Chain\n\n"
        "A researcher plans, a builder builds from the plan, a reviewer reviews what was built. "
        "Each agent's answer is the next one's brief, all in one folder. The whole flow:"
    ),
    "tasks": (
        "### Task board\n\n"
        "A list of tasks in the flow's state. Every round, a worker that finished closes its task "
        "and a free one pulls the next open task. The whole flow:"
    ),
}


def about(kind: str) -> str:
    """The ``about`` cell of flow ``kind``'s plane: what it does, and its cell's source."""
    return f"""\
import nu
import nustd.ui
from nudemos.agents.flows import KINDS

TEXT = {_ABOUTS[kind]!r}


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    code = nustd.ui.CodeRef.slot(language="python", line_numbers=True, max_height=640)


def out(plane):
    return View.text.set(TEXT) >> View.code.set(KINDS[{kind!r}][0]) >> nu.ForeverDo(nu.Delay(3600.0))
"""


def flow_view(job: nu.StrArg) -> nu.Nu:
    """A flow run, in one dict: name, phase, status, outcome, and ``[role, page, status, doing]`` per agent. Bare."""

    def member(role: nu.Nu) -> nu.Nu:
        r = nu.Str(role)
        aj = nu.Str(flow_of(job).agents.get_item(r, ""))
        page = flow_of(job).pages.get_item(r, "")
        return nu.List.of(r, page, status_of(aj), agent(aj).doing.fallback(""))

    roles = nu.list(flow_of(job).roles.fallback([]))
    return nu.Dict.of(
        job=job,
        name=nuspace.plane.title(job),
        phase=flow_of(job).phase.fallback("starting"),
        status=flow_of(job).status.fallback("starting"),
        outcome=flow_of(job).outcome.fallback(""),
        agents=roles.iter().map(member).to_list(),
    )


def flows_view(plane: nu.StrArg) -> nu.Nu:
    """Every flow run under ``plane``, oldest first, as :func:`flow_view` dicts. Bare."""
    return flows_of(plane).iter().map(lambda j: flow_view(nu.Str(j))).to_list()


def shown_of(runs: list) -> list:
    """Per run, what its card shows: ``{key, title, phase, tone, agents, outcome}``.

    ``agents`` is a line per agent, ``{i, role, page, tone, said}``: its status
    dot, its role linking to its page (an empty page draws the role alone),
    and its status with what it is doing while it works.
    """
    out = []
    for v in runs:
        agents = []
        for role, page, status, doing in v["agents"]:
            live = status in ("working", "starting", "resuming")
            said = f"{status}, {doing}" if live and doing else status
            agents.append(
                {
                    "i": len(agents),
                    "role": role,
                    "page": page,
                    "tone": TONES.get(status, "neutral"),
                    "said": said,
                }
            )
        done = v["status"] == "done"
        out.append(
            {
                "key": v["job"],
                "title": v["name"],
                "phase": v["phase"],
                "tone": "ok" if done else "info",
                "agents": agents,
                "outcome": v["outcome"] or "",
            }
        )
    return out


def lines_of(text: str) -> list[str]:
    """A task per non-blank line."""
    return [line.strip(" -*\t") for line in text.splitlines() if line.strip(" -*\t")]


def with_task(tasks: list, text: str) -> list:
    """``tasks`` with one more open task at the end."""
    return [*(tasks or []), {"task": text, "status": "open", "by": "", "mark": 0, "answer": ""}]


shown = nu.host(shown_of, name="Shown")
lines = nu.host(lines_of, name="Lines")
_with_task = nu.host(with_task, name="WithTask")


def add_task(job: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """One more open task on the board flow ``job`` runs."""
    tasks = flow_of(job).tasks.fallback([])
    return nuspace.atomic(nu.let(_with_task(tasks, text), lambda t: flow_of(job).tasks.set(t)))


RUN = """\
import nu
import nuspace
import nuspace.web as web
import nustd.ui
from nudemos.agents import orchestrate, views
from nudemos.agents.claude import READY
from nudemos.agents.flows import KINDS, launch_flow
from nudemos.agents.state import flows_of, runs_at

KIND = "fanout"
ASK = orchestrate.ASKS[KIND]


class Ask(nustd.ui.Row):
    n = nustd.ui.NumberInputRef.slot(label="Agents", min=1, max=5, step=1)
    run = nustd.ui.ButtonRef.slot(label="Run it", icon="play")


class Run(nustd.ui.Card):
    # The phase pill sits in the card's actions place.
    actions = nustd.ui.StatusPillRef.slot()
    agents = nustd.ui.ColumnRef.slot(nustd.ui.LineRef, gap=2)
    outcome = nustd.ui.MarkdownRef.slot()


class MoreLine(nustd.ui.InputGroup):
    task = nustd.ui.InputRef.slot(placeholder="Another task for the newest board", required=True)
    add = nustd.ui.ButtonRef.slot(label="Add task", variant="secondary", icon="plus", submit=True)


class More(nustd.ui.Form):
    line = MoreLine.slot()


class View(nustd.ui.Column):
    notice = nustd.ui.MarkdownRef.slot()
    brief = nustd.ui.TextAreaRef.slot(rows=4, auto_resize=True)
    ask = Ask.slot(gap=3, align="end")
    more = More.slot(clear_on_submit=True)
    head = nustd.ui.HeadingRef.slot(level=4)
    runs = nustd.ui.ColumnRef.slot(Run, gap=3)


def started(plane):
    # A run of this plane's flow: its job under this plane, its agents under the Agents plane.
    def go(root, count):
        name = nu.Str(KINDS[KIND][1] + " ") + nu.str(nu.Int(count) + 1)
        text = nu.Str(View.brief).strip()
        n = nu.int(View.ask.n) if KIND != "chain" else 1
        spec = nu.Dict.of(brief=text, n=n, tasks=orchestrate.lines(text))
        return launch_flow(plane, root, KIND, spec, name)

    return nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), lambda root: nu.let(nuspace.atomic(flows_of(plane).len()), lambda c: go(root, c)))


def added(plane):
    # Enter or Add task: a task onto the newest board, the box cleared. A free
    # worker pulls it on the board's next round.
    newest = nuspace.atomic(nu.str(flows_of(plane).iter().last(default="")))
    def add(sub):
        t = nu.Str(sub["values"]["line"]["task"]).strip()
        return nu.let(newest, lambda j: nu.IfDo(nu.Str(j) != "", orchestrate.add_task(j, t)))
    return add


def member(r, a):
    # One agent of a run, by its position: status dot, role linked to its page, what it says.
    line = r.agents[nu.Int(a["i"])]
    role = line[1].to(nustd.ui.LinkRef)
    page = nu.Str(a["page"])
    linked = nu.IfDo(page != "", role.set(href=web.href(page), label=a["role"]), role.set(label=a["role"]))
    return line[0].to(nustd.ui.StatusDotRef).set(a["tone"], label=a["said"]) >> linked >> line[2].to(nustd.ui.TextRef.slot(tone="muted")).set(a["said"])


def card(c):
    r = View.runs[c["key"]]
    agents = nu.List(c["agents"])
    each = nu.ForEachDo(agents, lambda a: member(r, nu.Dict(a)))
    return (
        r.set_title(c["title"]) >> r.actions.set(c["phase"], tone=c["tone"])
        >> each >> r.agents.truncate(agents.len()) >> r.outcome.set(c["outcome"])
    )


def draw(runs):
    # Every run's card in place and in order, the ones gone dropped.
    rows = nu.List(runs)
    keys = rows.iter().map(lambda c: nu.Dict(c)["key"]).to_list()
    return nu.ForEachDo(rows, card) >> View.runs.keep(keys) >> View.runs.set_order(keys)


def out(plane):
    if not READY:
        return View.notice.set(views.MISSING) >> nu.ForeverDo(nu.Delay(3600.0))
    # A chain is one agent a step, so it takes no count; only a board takes more tasks.
    count = View.ask.n.set(float(ASK["n"])) if KIND != "chain" else nu.Noop()
    more = View.more.init() if KIND == "tasks" else nu.Noop()
    placed = View.brief.set(ASK["brief"]) >> count >> View.ask.run.init() >> more >> View.head.set("Runs")
    kids = runs_at(plane).flows.on_change()
    runs = orchestrate.shown(orchestrate.flows_view(plane))
    return placed >> nu.ParallelAsync(
        nu.ReactEvery(View.ask.run.on_click(), started(plane)),
        nu.ReactEvery(View.more.on_submit(), added(plane)),
        nu.Reconcile(nuspace.atomic(nu.OnAny(*[kids])), nu.let(nuspace.atomic(runs), draw), every=1.5),
    )
"""


def _plane(kind: str, label: str, icon: str, description: str) -> PlaneSpec:
    return PlaneSpec(
        f"agents_{kind}",
        label,
        icon=icon,
        description=description,
        web=WebOptions(editable=True, width="board"),
        cells=(("flow", about(kind)), ("run", RUN.replace('KIND = "fanout"', f"KIND = {kind!r}"))),
        backend="async",
    )


FANOUT_PLANE = _plane(
    "fanout", "Fan-out", "git-fork", "N agents on one brief, a judge picks the best."
)
CHAIN_PLANE = _plane(
    "chain", "Chain", "link", "Research, build, review: each answer is the next brief."
)
TASKS_PLANE = _plane(
    "tasks", "Task board", "list-checks", "A board of tasks that idle agents pull from."
)
