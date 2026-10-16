"""The orchestration planes: Fan-out, Chain, Task board. One flow each, run from a form.

Each plane shows its flow's cell, the whole of it, then a form that starts a
run of it and every run so far: its phase, its agents and what they are up
to, and what it came to. A run is a headless job under the plane
(:func:`~.flows.launch_flow`); its agents are pages under the Agents plane.
"""

from __future__ import annotations

from typing import Any

import nu
from nuspace import Plane, ops

from .flows import BOARD, SCENARIO
from .state import Agent, Flow, at, flow_at, flows_of, status_of


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

    def agent(role: nu.Nu) -> nu.Nu:
        r = nu.Str(role)
        aj = nu.Str(flow_at(job, Flow.agents.get_item(r, "")))
        page = flow_at(job, Flow.pages.get_item(r, ""))
        return nu.List.of(r, page, status_of(aj), at(aj, Agent.doing.fallback("")))

    roles = nu.list(flow_at(job, Flow.roles.fallback([])))
    return nu.Dict.of(
        job=job,
        name=ops.plane_title(job),
        phase=flow_at(job, Flow.phase.fallback("starting")),
        status=flow_at(job, Flow.status.fallback("starting")),
        outcome=flow_at(job, Flow.outcome.fallback("")),
        agents=roles.iter().map(agent).to_list(),
    )


def flows_view(plane: nu.StrArg) -> nu.Nu:
    """Every flow run under ``plane``, oldest first, as :func:`flow_view` dicts. Bare."""
    return flows_of(plane).iter().map(lambda j: flow_view(nu.Str(j))).to_list()


def shown_of(runs: list) -> list:
    """Per run, what its card shows: ``{key, title, phase, tone, agents, outcome}``."""
    out = []
    for v in runs:
        lines = []
        for role, page, status, doing in v["agents"]:
            live = status in ("working", "starting", "resuming")
            tail = f" · {doing}" if live and doing else ""
            link = f"[{role}](/{page})" if page else role
            lines.append(f"- {link} · **{status}**{tail}")
        done = v["status"] == "done"
        out.append(
            {
                "key": v["job"],
                "title": v["name"],
                "phase": v["phase"],
                "tone": "ok" if done else "info",
                "agents": "\n".join(lines) or "_no agents yet_",
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
    tasks = flow_at(job, Flow.tasks.fallback([]))
    return ops.atomic_state(
        nu.let(_with_task(tasks, text), lambda t: flow_at(job, Flow.tasks.set(t)))
    )


RUN = """\
import nu
import nustd.ui
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import redraws, snap
from nudemos.agents import orchestrate, views
from nudemos.agents.claude import READY
from nudemos.agents.flows import KINDS, launch_flow
from nudemos.agents.state import flows_of

KIND = "fanout"
ASK = orchestrate.ASKS[KIND]


class Ask(nustd.ui.Row):
    n = nustd.ui.NumberInputRef.slot(label="Agents", min=1, max=5, step=1)
    run = nustd.ui.ButtonRef.slot(label="Run it", icon="play")


class Run(nustd.ui.Card):
    pill = nustd.ui.StatusPillRef.slot()
    agents = nustd.ui.MarkdownRef.slot()
    outcome = nustd.ui.MarkdownRef.slot()


class More(nustd.ui.Row):
    task = nustd.ui.InputRef.slot(placeholder="Another task for the newest board")
    add = nustd.ui.ButtonRef.slot(label="Add task", variant="secondary", icon="plus")


class View(nustd.ui.Column):
    notice = nustd.ui.MarkdownRef.slot()
    brief = nustd.ui.TextAreaRef.slot(rows=4, auto_resize=True)
    ask = Ask.slot(gap=3, align="end")
    more = More.slot(gap=2, align="end")
    head = nustd.ui.HeadingRef.slot(level=4)
    runs = nustd.ui.GridRef.slot(Run, columns=1, gap=3)


def started(plane):
    # A run of this plane's flow: its job under this plane, its agents under the Agents plane.
    def go(root, count):
        name = nu.Str(KINDS[KIND][1] + " ") + nu.str(nu.Int(count) + 1)
        text = nu.Str(View.brief).strip()
        n = nu.int(View.ask.n) if KIND != "chain" else 1
        spec = nu.Dict.of(brief=text, n=n, tasks=orchestrate.lines(text))
        return launch_flow(plane, root, KIND, spec, name)

    return nu.let(snap(ops.parent(plane)), lambda root: nu.let(snap(flows_of(plane).len()), lambda c: go(root, c)))


def added(plane):
    # A task onto the newest board: a free worker pulls it on the board's next round.
    text = snap(nu.Str(View.more.task).strip())
    newest = snap(nu.str(nu.Last(flows_of(plane).iter())).fallback(""))
    def add(t, job):
        return nu.IfDo((nu.Str(t) != "").and_(nu.Str(job) != ""), orchestrate.add_task(job, t) >> View.more.task.set(""))
    return nu.let(text, lambda t: nu.let(newest, lambda j: add(t, j)))


def card(c):
    r = View.runs[c["key"]]
    return (
        r.set_title(c["title"]) >> r.pill.set(c["phase"], tone=c["tone"])
        >> r.agents.set(c["agents"]) >> r.outcome.set(c["outcome"])
    )


def out(plane):
    if not READY:
        return View.notice.set(views.MISSING) >> nu.ForeverDo(nu.Delay(3600.0))
    # A chain is one agent a step, so it takes no count; only a board takes more tasks.
    count = View.ask.n.set_value(float(ASK["n"])) if KIND != "chain" else nu.Noop()
    more = View.more.task.set("") >> View.more.add.set("Add task") if KIND == "tasks" else nu.Noop()
    placed = View.brief.set(ASK["brief"]) >> count >> View.ask.run.set("Run it", icon="play") >> more >> View.head.set("Runs")
    kids = Space.planes[plane].children.on_change()
    runs = orchestrate.shown(orchestrate.flows_view(plane))
    return placed >> nu.ParallelAsync(
        nu.ReactForever(View.ask.run.on_click(), started(plane)),
        nu.ReactForever(View.more.add.on_click(), added(plane)),
        redraws([kids], runs, lambda rs: nu.ForEachDo(nu.List(rs), card), every=1.5),
    )
"""


def _plane(kind: str, label: str, icon: str, description: str) -> Plane:
    return Plane(
        f"agents_{kind}",
        label,
        icon=icon,
        description=description,
        meta={"editable": True, "full_width": True},
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
