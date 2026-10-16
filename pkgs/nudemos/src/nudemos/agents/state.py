"""The state an agent keeps, the state a flow keeps, and where the cells that show them find it.

An agent is a headless job plane with one cell, ``<job>_main``, running one
Claude Code session. :class:`Agent` is that cell's state: what it was asked
to be, the conversation it is in, what it is doing, everything it said and
did, and what that cost. The job writes it bare (its own state); every other
cell reads it, and steers it, under the job's cell with :func:`at`.

A flow (fan-out and judge, a chain, a task board) is a headless job too,
one Nu cell over agents: :class:`Flow` is what it did so far.

The planes hang as the cells make them::

    Agents               the root, made from :data:`nudemos.agents.PLANE`
      Fan-out, Chain, Task board
        <flow>           a flow (headless, async), made_by ``agents_flow``
      <agent>            an agent page (ui), made_by ``agents_page``
        run              the agent (headless, mp), made_by ``agents_job``
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space


__all__ = [
    "FLOW",
    "JOB",
    "PAGE",
    "Agent",
    "Flow",
    "agents_of",
    "at",
    "flow_at",
    "flows_of",
    "job_cell",
    "job_of",
    "made_by",
    "status_of",
]


#: ``made_by`` of an agent page, of the agent's job under it, and of a flow.
PAGE, JOB, FLOW = "agents_page", "agents_job", "agents_flow"


class Agent(nuspace.CellState):
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


class Flow(nuspace.CellState):
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


def made_by(plane: nu.Nu) -> nu.Str:
    """What made ``plane``, ``""`` for nothing. Bare read."""
    return Space.planes[nu.Str(plane)].props.made_by.fallback("")


def job_of(page: nu.StrArg) -> nu.Str:
    """The agent job under an agent page, ``""`` while it has none. Bare read."""
    jobs = ops.children(page).iter().filter(lambda p: made_by(p) == JOB)
    return nu.str(nu.First(jobs)).fallback("")


def job_cell(job: nu.StrArg) -> nu.Str:
    """A job's one cell: its id with ``_main`` after it."""
    return nu.Str(job) + "_main"


def at(job: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`Agent`, landed on agent ``job``'s cell. Bare."""
    return ops.cell_state(job_cell(job), term)


def flow_at(job: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`Flow`, landed on flow ``job``'s cell. Bare."""
    return ops.cell_state(job_cell(job), term)


def agents_of(root: nu.StrArg) -> nu.List:
    """``[[page, job], ...]``, every agent under the Agents plane, oldest first. Bare read."""
    pages = ops.children(root).iter().filter(lambda p: made_by(p) == PAGE)
    return pages.map(lambda p: nu.List.of(nu.Str(p), job_of(nu.Str(p)))).to_list()


def flows_of(plane: nu.StrArg) -> nu.List:
    """The flow jobs under an orchestration plane, oldest first. Bare read."""
    return ops.children(plane).iter().filter(lambda p: made_by(p) == FLOW).to_list()


def status_of(job: nu.StrArg) -> nu.Str:
    """An agent's status, ``down`` for one that says it works but has no live job. Bare read."""
    said = at(job, Agent.status.fallback("starting"))
    live = Space.kernel.planes_running.contains(job)
    resting = (said == "idle").or_(said == "stopped").or_(said == "error").or_(said == "starting")
    return nu.Str(nu.If(resting.or_(live), said, "down"))
