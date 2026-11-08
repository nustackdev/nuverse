"""The state an agent keeps, the state a flow keeps, and where the cells that show them find it.

An agent is a headless job plane with one cell, named :data:`RUN_CELL`,
running one Claude Code session. :class:`Agent` is that cell's state: what it was asked
to be, the conversation it is in, what it is doing, everything it said and
did, and what that cost. The job reads and writes it as its own
(:data:`AGENT`); every other cell reads it, and steers it, at the job's
cell, found by its name in the job's plane state (:func:`agent`).

A flow (fan-out and judge, a chain, a task board) is a headless job too,
one Nu cell over agents, named :data:`FLOW_CELL`: :class:`Flow` is what it
did so far, its own (:data:`FLOW`), read by others with :func:`flow_of`.

Who finds whom is kept in plane state, written as things are made: an
agent page keeps its job (:class:`Page`), the Agents plane its agents
(:class:`Agents`), an orchestration plane its flows (:class:`Runs`). Every
id is minted, none is made from another.

The planes hang as the cells make them::

    Agents               the root, made from :data:`nudemos.agents.PLANE`
      Fan-out, Chain, Task board
        <flow>           a flow (headless, async), spec ``agents_flow``
      <agent>            an agent page (web), spec ``agents_page``
        run              the agent (headless, mp), spec ``agents_job``
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import Space

from .. import headless


__all__ = [
    "AGENT",
    "FLOW",
    "FLOW_CELL",
    "FLOW_JOB",
    "JOB",
    "PAGE",
    "RUN_CELL",
    "Agent",
    "Agents",
    "Flow",
    "Page",
    "Runs",
    "agent",
    "agents_at",
    "agents_of",
    "flow_made",
    "flow_of",
    "flows_of",
    "job_of",
    "page_at",
    "runs_at",
    "spec_of",
    "status_of",
]


#: ``spec`` of an agent page, of the agent's job under it, and of a flow.
PAGE, JOB, FLOW_JOB = "agents_page", "agents_job", "agents_flow"

#: The name of an agent job's one cell, and of a flow job's.
RUN_CELL, FLOW_CELL = "run", "flow"


class Agent(nu.Shape):
    """One agent's state, on its job's one cell."""

    # What it was made as: {name, cwd, model, mode, brief}, and the conversation it is.
    spec = nustd.kv.ObjectRef.slot()
    sid = nustd.kv.StrRef.slot()
    # starting, working, idle, stopping, stopped, error.
    status = nustd.kv.StrRef.slot()
    stop = nustd.kv.BoolRef.slot()
    # A turn the stop (or a restart) cut short: the next start carries on from it.
    cut = nustd.kv.BoolRef.slot()
    # What it is asked next, oldest first. Say appends; the loop takes the first each turn.
    inbox = nustd.kv.ListRef.slot(str)
    # Everything said and done, one event each as JSON (``nustd.cc`` events, and ``user`` for what it was told).
    log = nustd.kv.ListRef.slot(str)
    # The log's length, a scalar to follow: a list appended to in place does not say.
    n = nustd.kv.IntRef.slot()
    # What it is doing now, in a few words.
    doing = nustd.kv.StrRef.slot()
    # Prompts sent, model turns taken, tokens in and out, dollars, seconds of work.
    prompts = nustd.kv.IntRef.slot()
    turns = nustd.kv.IntRef.slot()
    # Tool calls made, counted as each one is made: the number that moves while a turn runs.
    calls = nustd.kv.IntRef.slot()
    tokens_in = nustd.kv.IntRef.slot()
    tokens_out = nustd.kv.IntRef.slot()
    cost = nustd.kv.FloatRef.slot()
    seconds = nustd.kv.FloatRef.slot()
    # Its latest answer, the final text of its latest turn. ``answered`` counts them.
    answer = nustd.kv.StrRef.slot()
    answered = nustd.kv.IntRef.slot()
    error = nustd.kv.StrRef.slot()
    # When it last did anything, for the idle clock.
    beat = nustd.kv.FloatRef.slot()
    # What it drew on its page's board, as SketchRef elements.
    sketch = nustd.kv.ObjectRef.slot()


class Flow(nu.Shape):
    """One flow's state, on its job's one cell."""

    # What it is (fanout, chain, tasks) and how it was asked: {brief, n, ...}.
    kind = nustd.kv.StrRef.slot()
    spec = nustd.kv.ObjectRef.slot()
    # Where it is, in a few words, and whether it is over.
    phase = nustd.kv.StrRef.slot()
    status = nustd.kv.StrRef.slot()
    # Its agents by role: role -> agent job id. ``pages`` the same, role -> page. ``roles`` in the order made.
    agents = nustd.kv.DictRef.slot(str)
    pages = nustd.kv.DictRef.slot(str)
    roles = nustd.kv.ListRef.slot(str)
    # A task board's tasks, oldest first, rewritten whole: [{task, by, status, mark, answer}, ...].
    tasks = nustd.kv.ObjectRef.slot()
    # Its end: the judge's verdict, the chain's review, the board's tally. Markdown.
    outcome = nustd.kv.StrRef.slot()
    started = nustd.kv.FloatRef.slot()


class Page(nu.Shape):
    """An agent page's plane state: the job under it, written at launch."""

    job = nustd.kv.StrRef.slot()


class Agents(nu.Shape):
    """The Agents plane's state: its agents, agent plane to its job, oldest first, written at launch."""

    jobs = nustd.kv.OrderedDictRef.slot(str)


class Runs(nu.Shape):
    """An orchestration plane's state: its flows' jobs, oldest first, written at launch."""

    flows = nustd.kv.OrderedDictRef.slot(bool)


#: The running agent's own state: the job cell's.
AGENT = nuspace.here(Agent)

#: The running flow's own state: the flow cell's.
FLOW = nuspace.here(Flow)


def agent(job: nu.StrArg) -> Agent:
    """Agent ``job``'s state, on its one cell."""
    return nuspace.at.cell(id=headless.cell_of(job, RUN_CELL)).state(Agent)


def flow_of(job: nu.StrArg) -> Flow:
    """Flow ``job``'s state, on its one cell."""
    return nuspace.at.cell(id=headless.cell_of(job, FLOW_CELL)).state(Flow)


def page_at(page: nu.StrArg) -> Page:
    """Agent page ``page``'s state."""
    return nuspace.at.plane(id=page).state(Page)


def agents_at(root: nu.StrArg) -> Agents:
    """The Agents plane ``root``'s state."""
    return nuspace.at.plane(id=root).state(Agents)


def runs_at(plane: nu.StrArg) -> Runs:
    """Orchestration plane ``plane``'s state."""
    return nuspace.at.plane(id=plane).state(Runs)


def flow_made(flow: Flow | None = None) -> nu.Nu:
    """A flow's agent containers, made where missing: every read of its agents finds them. Unbracketed.

    Over ``flow``, a flow's state (:func:`flow_of`), the running flow's own (:data:`FLOW`) when absent.
    """
    f = FLOW if flow is None else flow
    return (
        f.agents.init(nu.Dict.create())
        >> f.pages.init(nu.Dict.create())
        >> f.roles.init(nu.List.create())
    )


def spec_of(plane: nu.Nu) -> nu.Str:
    """The spec ``plane`` was made from, ``""`` for none. Bare read."""
    return Space.planes[nu.Str(plane)].spec.fallback("")


def job_of(page: nu.StrArg) -> nu.Str:
    """The agent job under an agent page, ``""`` while it has none. Bare read."""
    return nu.Str(page_at(page).job.fallback(""))


def agents_of(root: nu.StrArg) -> nu.List:
    """``[[page, job], ...]``, every agent under the Agents plane, oldest first. Bare read."""
    jobs = agents_at(root).jobs
    return nu.List(nu.If(jobs.exists(), jobs.items(), []))


def flows_of(plane: nu.StrArg) -> nu.List:
    """The flow jobs under an orchestration plane, oldest first. Bare read."""
    flows = runs_at(plane).flows
    return nu.List(nu.If(flows.exists(), flows.keys(), []))


def status_of(job: nu.StrArg) -> nu.Str:
    """An agent's status, ``down`` for one that says it works but has no live job. Bare read."""
    said = agent(job).status.fallback("starting")
    live = headless.live(job)
    resting = (said == "idle").or_(said == "stopped").or_(said == "error").or_(said == "starting")
    return nu.Str(nu.If(resting.or_(live), said, "down"))
