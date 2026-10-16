"""Flows: agents orchestrated by a short Nu cell. No framework, a few terms.

A flow is a headless job with one cell. The cell is plain Nu over a
:class:`Team`, the agents it makes and talks to by role: ``ask`` a role to do
something (made the first time, with that as its brief), ``wait`` for roles to
finish, read their ``answer``, write the ``phase`` and the ``outcome``. Each
agent is a real agent page under the Agents plane, so everything a flow does
is watched, and steered, from there.

Three flows ship, each a cell source here, baked at launch (:func:`flow_source`):

- :data:`FANOUT`: N agents take the same brief, each in its own folder; a judge reads them all and picks one.
- :data:`CHAIN`: research, build, review; each agent's answer is the next one's brief.
- :data:`TASKS`: a board of tasks; idle workers pull the next open one.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import nu
import nustd.time
from nuspace import ops
from nuspace.system.utils import snap

from .launch import launch, say
from .state import Agent, Flow, at


__all__ = [
    "CHAIN",
    "FANOUT",
    "KINDS",
    "SCENARIO",
    "TASKS",
    "Team",
    "closed",
    "flow_source",
    "launch_flow",
    "taken",
    "tally_of",
]


#: The built-in scenario: a brief small enough to run three times for cents.
SCENARIO = (
    "Build a one-file static web page, index.html, with inline CSS and no JavaScript: "
    'a landing page for a tiny product called "Nu", a programming model where everything is an interaction. '
    "A headline, one line under it, three short feature cards and a footer. "
    "Make it look good. Keep it under 120 lines. Do not run a server or open a browser."
)

#: The task board's starting tasks.
BOARD = [
    "Write haiku.md: three haiku about event loops.",
    "Write primes.py: a function that returns the first n primes, and a main that prints 20.",
    "Write README.md describing the files in this folder, one line each.",
    "Write colors.css: a 6-color palette as CSS variables, named after weather.",
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"


def _made_dir(path: str) -> str:
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


made_dir = nu.host(_made_dir, name="MadeDir")


def _filled(template: str, parts: dict) -> str:
    return template.format(**parts)


filled = nu.host(_filled, name="Filled")


class Team:
    """The agents one flow makes and talks to, by role. Every method builds a term.

    Args:
        root: The Agents plane, where the agents' pages go.
        folder: The flow's folder. Each role works in its own folder under it,
            or in it, given ``folder="."``.
        name: The flow's name, put before each role in its agents' names.
        model: The model its agents run.
        mode: Their permission mode.
    """

    def __init__(
        self,
        root: str,
        folder: str,
        name: str,
        *,
        model: str = "claude-sonnet-5",
        mode: str = "acceptEdits",
    ) -> None:
        self.root, self.folder, self.name = root, folder, name
        self.model, self.mode = model, mode

    def begin(self, kind: str, spec: dict[str, Any]) -> nu.Nu:
        """Say what this flow is, once."""
        return ops.atomic_state(
            Flow.kind.set(kind)
            >> Flow.spec.set(spec)
            >> Flow.status.set("running")
            >> Flow.started.set(Flow.started.fallback(nustd.time.time()))
        )

    def phase(self, text: str) -> nu.Nu:
        """Where the flow is now, in a few words."""
        return ops.atomic_state(Flow.phase.set(text))

    def job(self, role: str) -> nu.Nu:
        """The job of ``role``'s agent, ``""`` before it is made. Bare."""
        return Flow.agents.get_item(role, "")

    def ask(self, role: str, brief: nu.StrArg, *, folder: str = "") -> nu.Nu:
        """``role`` made with ``brief`` as its first turn. Once: a role already made is left be.

        It works in a folder of its own under the flow's, or in the flow's
        own folder given ``folder="."``.
        """
        where = self.folder if folder == "." else str(Path(self.folder) / (folder or _slug(role)))
        spec = nu.Dict.of(
            name=f"{self.name} · {role}",
            cwd=made_dir(where),
            model=self.model,
            mode=self.mode,
            brief=snap(nu.Str(brief)),
        )

        def made(page: nu.Ref, job: nu.Ref) -> nu.Nu:
            kept = ops.atomic_state(
                Flow.agents.set_item(role, nu.Str(job))
                >> Flow.pages.set_item(role, nu.Str(page))
                >> Flow.roles.append(role)
            )
            return launch(self.root, spec, page=page, job=job, plane_id=self.plane_of(role)) >> kept

        fresh = nu.let("", lambda p: nu.let("", lambda j: made(p, j)))
        return nu.IfDo(snap(Flow.agents.contains(role)), nu.Noop(), fresh)

    def plane_of(self, role: str) -> str:
        """The page id of ``role``'s agent: fixed by the flow's folder and the role, so it is made once."""
        return f"p_{_slug(Path(self.folder).name)}_{_slug(role)}"

    def tell(self, role: str, text: nu.StrArg) -> nu.Nu:
        """``text`` for ``role``: its next turn, or its brief if it is not made yet."""
        return nu.IfDo(
            snap(Flow.agents.contains(role)), say(snap(self.job(role)), text), self.ask(role, text)
        )

    def answered(self, role: str) -> nu.Nu:
        """How many turns ``role`` has finished, 0 before it is made. Bare."""
        return nu.Int(
            nu.If(Flow.agents.contains(role), at(self.job(role), Agent.answered.fallback(0)), 0)
        )

    def busy(self, role: str) -> nu.Nu:
        """Whether ``role`` is in a turn or has one queued. Bare."""
        job = self.job(role)
        working = at(job, Agent.status.fallback("")) == "working"
        queued = at(job, Agent.inbox.fallback([]).len()) > 0
        return nu.Bool(nu.If(Flow.agents.contains(role), working.or_(queued), False))

    def finished(self, role: str) -> nu.Nu:
        """Whether ``role`` has finished a turn and has nothing under way. Bare."""
        return (self.answered(role) > 0).and_(self.busy(role).not_())

    def wait(self, *roles: str) -> nu.Nu:
        """Until every one of ``roles`` has finished its turn."""
        done = self.finished(roles[0])
        for role in roles[1:]:
            done = done.and_(self.finished(role))
        return nu.WaitReactive(snap(Flow.agents.on_change()), snap(done), every=1.5)

    def answer(self, role: str) -> nu.Nu:
        """``role``'s latest answer. Bare."""
        return at(self.job(role), Agent.answer.fallback(""))

    def brief(self, template: str, **parts: object) -> nu.Nu:
        """``template`` filled from ``parts``, Nu terms read when the flow gets there."""
        return filled(template, nu.Dict.of(**parts))

    def done(self, outcome: nu.StrArg) -> nu.Nu:
        """The flow is over, and this is what it came to (markdown)."""
        return ops.atomic_state(
            Flow.outcome.set(nu.Str(outcome)) >> Flow.phase.set("done") >> Flow.status.set("done")
        )

    # --- a task board ---

    def post(self, tasks: list[str]) -> nu.Nu:
        """The board's tasks, once: a restarted flow keeps the ones it has."""
        board = [{"task": t, "status": "open", "by": "", "mark": 0, "answer": ""} for t in tasks]
        return nu.IfDo(
            snap(Flow.tasks.exists()), nu.Noop(), ops.atomic_state(Flow.tasks.set(board))
        )

    def pull(self, worker: str) -> nu.Nu:
        """``worker``, when it is free, takes the next open task: it is told it, made with it if it is new."""

        def took(picked: nu.Ref) -> nu.Nu:
            def mark(r: nu.Nu) -> nu.Nu:
                d = nu.Dict(r)
                return nu.IfDo(d["task"] != "", Flow.tasks.set(d["tasks"]) >> picked.set(d["task"]))

            pick = ops.atomic_state(
                nu.let(_take(Flow.tasks.fallback([]), worker, self.answered(worker)), mark)
            )
            return pick >> nu.IfDo(nu.Str(picked) != "", self.tell(worker, nu.Str(picked)))

        free = snap(
            self.busy(worker).not_().and_(nu.Bool(_holding(Flow.tasks.fallback([]), worker)).not_())
        )
        return nu.IfDo(free, nu.let("", took))

    def close(self, worker: str) -> nu.Nu:
        """``worker``'s task done, with its answer, once it has finished the turn it was given it on."""

        def mark(r: nu.Nu) -> nu.Nu:
            d = nu.Dict(r)
            return nu.IfDo(d["changed"], Flow.tasks.set(d["tasks"]))

        over = self.finished(worker)
        shut = _close(
            Flow.tasks.fallback([]), worker, self.answered(worker), self.answer(worker), over
        )
        return ops.atomic_state(nu.let(shut, mark))

    def tally(self) -> nu.Nu:
        """The board's count, as its phase and outcome."""

        def write(t: nu.Nu) -> nu.Nu:
            d = nu.Dict(t)
            return Flow.phase.set(d["phase"]) >> Flow.outcome.set(d["outcome"])

        return ops.atomic_state(nu.let(_tally(Flow.tasks.fallback([])), write))


# --- the task board, as plain Python ---------------------------------------------------------


def taken(tasks: list, worker: str, mark: int) -> dict:
    """The first open task given to ``worker``: ``{tasks, task}``, ``task`` empty when none is open."""
    tasks = [dict(t) for t in tasks or []]
    for t in tasks:
        if t["status"] == "open":
            t.update(status="doing", by=worker, mark=int(mark))
            return {"tasks": tasks, "task": t["task"]}
    return {"tasks": tasks, "task": ""}


def holds(tasks: list, worker: str) -> bool:
    """Whether ``worker`` has a task under way."""
    return any(t["status"] == "doing" and t["by"] == worker for t in tasks or [])


def closed(tasks: list, worker: str, answered: int, answer: str, finished: bool) -> dict:
    """``worker``'s task marked done once it has answered past its mark: ``{tasks, changed}``."""
    tasks = [dict(t) for t in tasks or []]
    for t in tasks:
        if t["status"] == "doing" and t["by"] == worker and finished and answered > t["mark"]:
            t.update(status="done", answer=answer)
            return {"tasks": tasks, "changed": True}
    return {"tasks": tasks, "changed": False}


def tally_of(tasks: list) -> dict:
    """The board in a line and a table: ``{phase, outcome}``."""
    tasks = tasks or []
    done = sum(t["status"] == "done" for t in tasks)
    doing = sum(t["status"] == "doing" for t in tasks)
    phase = f"{done} of {len(tasks)} done, {doing} under way" if tasks else "no tasks yet"
    if tasks and done == len(tasks):
        phase = f"all {done} done, waiting for more"
    rows = ["| Task | Who | Status | Answer |", "| --- | --- | --- | --- |"]
    for t in tasks:
        said = " ".join((t.get("answer") or "").split())
        said = said if len(said) <= 90 else said[:89] + "…"
        who = (t["by"] or "-").replace("-", "\u2011")
        rows.append(f"| {t['task']} | {who} | {t['status']} | {said or '-'} |")
    return {"phase": phase, "outcome": "\n".join(rows)}


_take = nu.host(taken, name="Take")
_holding = nu.host(holds, name="Holding")
_close = nu.host(closed, name="Close")
_tally = nu.host(tally_of, name="BoardTally")


# --- the flows, as cells ---------------------------------------------------------------------


_HEAD = """\
import nu
from nudemos.agents.flows import Team

#: Baked in at launch: the Agents plane, this flow's folder and name, and what it was asked.
ROOT, DIR, NAME = "", "", ""
SPEC = {}
"""


FANOUT = (
    _HEAD
    + '''
JUDGE = """{n} agents each took this brief, each in its own folder here: {folders}.

{brief}

Look at what each one made. Pick the best one and say why, in a few lines.
Start your reply with: Winner: <folder>"""


def out(cell):
    team = Team(ROOT, DIR, NAME)
    builders = [f"builder-{i + 1}" for i in range(SPEC["n"])]
    judge = JUDGE.format(n=SPEC["n"], folders=", ".join(builders), brief=SPEC["brief"])
    return (
        team.begin("fanout", SPEC)
        >> team.phase("building")
        >> nu.Sequential(*(team.ask(b, SPEC["brief"]) for b in builders))
        >> team.wait(*builders)
        >> team.phase("judging")
        >> team.ask("judge", judge, folder=".")
        >> team.wait("judge")
        >> team.done(team.answer("judge"))
    )
'''
)


CHAIN = (
    _HEAD
    + """
STEPS = [
    ("researcher", "Here is a brief:\\n\\n{brief}\\n\\nDo not build anything. "
     "Reply with a short, concrete plan for it, at most 8 bullets."),
    ("builder", "Build this, in this folder:\\n\\n{brief}\\n\\nFollow this plan:\\n\\n{prev}\\n\\n"
     "Reply with what you built, in a few lines."),
    ("reviewer", "Review what was built in this folder for this brief:\\n\\n{brief}\\n\\n"
     "The builder said:\\n\\n{prev}\\n\\nDo not change anything. "
     "Reply with a verdict in one line, then the three fixes that matter most."),
]


def out(cell):
    team = Team(ROOT, DIR, NAME)
    flow, prev = team.begin("chain", SPEC), ""
    for role, step in STEPS:
        brief = team.brief(step, brief=SPEC["brief"], prev=team.answer(prev) if prev else "")
        flow = flow >> team.phase(role) >> team.ask(role, brief, folder=".") >> team.wait(role)
        prev = role
    return flow >> team.done(team.answer(prev))
"""
)


TASKS = (
    _HEAD
    + """

def out(cell):
    team = Team(ROOT, DIR, NAME)
    workers = [f"worker-{i + 1}" for i in range(SPEC["n"])]
    # Each round, a worker that finished closes its task, a free one takes the next.
    rounds = nu.Sequential(*(team.close(w) >> team.pull(w) for w in workers))
    return (
        team.begin("tasks", SPEC)
        >> team.post(SPEC["tasks"])
        >> nu.ForeverDo(rounds >> team.tally() >> nu.Delay(1.5))
    )
"""
)


#: The flows by kind: their cell source and their name.
KINDS: dict[str, tuple[str, str]] = {
    "fanout": (FANOUT, "Fan-out"),
    "chain": (CHAIN, "Chain"),
    "tasks": (TASKS, "Board"),
}


def flow_source(kind: str, root: str, folder: str, name: str, spec: dict[str, Any]) -> str:
    """The flow ``kind``'s cell with where it runs and what it was asked baked in."""
    source = KINDS[kind][0]
    lines = "".join(f"    {k!r}: {v!r},\n" for k, v in spec.items())
    return source.replace(
        'ROOT, DIR, NAME = "", "", ""', f"ROOT, DIR, NAME = {root!r}, {folder!r}, {name!r}"
    ).replace("SPEC = {}", "SPEC = {\n" + lines + "}")


def _flow_dir(kind: str) -> str:
    import tempfile

    return tempfile.mkdtemp(prefix=f"nu-flow-{kind}-")


baked = nu.host(flow_source, name="FlowSource")
flow_dir = nu.host(_flow_dir, name="FlowDir")


def launch_flow(
    plane: nu.StrArg,
    root: nu.StrArg,
    kind: str,
    spec: nu.Nu,
    name: nu.StrArg,
    *,
    job: nu.Ref | None = None,
) -> nu.Nu:
    """Flow ``kind`` started under ``plane``: a headless job running its cell, supervised.

    Args:
        plane: The orchestration plane it hangs under.
        root: The Agents plane its agents go under.
        kind: ``fanout``, ``chain`` or ``tasks``.
        spec: What it is asked, a dict term: ``brief``, ``n``, ``tasks``.
        name: Its name, put before its agents' names.
        job: Set to the new job's id.
    """
    import nuspace

    from .state import FLOW, job_cell

    def made(called: nu.Ref, asked: nu.Ref, j: nu.Ref, folder: nu.Ref) -> nu.Nu:
        source = baked(kind, nu.Str(root), nu.Str(folder), nu.Str(called), asked)
        kept = [] if job is None else [job.set(nu.Str(j))]
        return nu.Sequential(
            ops.add_plane(
                backend="async", name=nu.Str(called), parent=plane, ui=False, made_by=FLOW, into=j
            ),
            ops.add_cell(nu.Str(j), source, cell_id=job_cell(nu.Str(j)), name="flow"),
            nuspace.supervise(nu.Str(j)),
            *kept,
        )

    # The name and the spec are read once, before anything is made: they may count
    # the flows there are, or read a form.
    return nu.let(
        nu.Str(name),
        lambda n: nu.let(
            spec, lambda s: nu.let("", lambda j: nu.let(flow_dir(kind), lambda f: made(n, s, j, f)))
        ),
    )
