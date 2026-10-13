"""The job: one agent, a Nu loop over one Claude Code session.

Nu owns the loop, Claude Code owns the turn. :data:`RUN` binds the agent's
options, opens one ``nustd.cc.Session`` on the conversation id kept in its
state, and loops: take the next message from the inbox, stream the turn,
write every event into the state as it lands. Between turns it waits for
the next message, so saying something to a working agent queues the next
turn, and saying something to an idle one starts it.

A stop races every turn: the moment the state says stop, the turn is cut,
the process goes, and the loop ends. An agent left idle for :data:`IDLE`
seconds ends too, its process with it; the next message brings it back up.
Restarted either way (a resume, a message, the space reopened), it opens
the same conversation again, and a turn that was cut is carried on.

:func:`job_source` is the cell the launch writes for an agent, its spec
baked in as ``SPEC``.
"""

from __future__ import annotations

from typing import Any

import nu


__all__ = ["CARRY", "IDLE", "RUN", "SKETCH", "job_source", "launch_source"]


#: Seconds an agent waits for a message before it lets its process go.
IDLE = 120.0

#: What a cut turn is carried on with.
CARRY = "You were stopped partway through. Carry on where you left off."

#: What every agent is told about its page, on top of Claude Code's own system prompt.
SKETCH = (
    "You run inside a nuspace page that shows everything you do. "
    "The page has a sketch board: to draw on it, write sketch.json in your working directory, "
    "a JSON list of elements with coordinates from 0 to 1, origin top-left: "
    '{"type": "rect" | "ellipse", "x", "y", "w", "h", "stroke", "fill"} or '
    '{"type": "line" | "arrow", "points": [[x1, y1], [x2, y2]], "stroke"}. '
    "Colors: ink, gray, red, amber, green, blue, violet, or <color>-soft for fills. "
    "Only draw when asked to sketch."
)


RUN = """\
import nu
import nustd.cc
import nustd.time
from nuspace import ops
from nuspace.system.utils import snap
from nuverse_demos.agents import views
from nuverse_demos.agents.claude import Claude
from nuverse_demos.agents.job import CARRY, SKETCH
from nuverse_demos.agents.state import Agent

#: This agent, as it was made: name, folder, model, permission mode, brief.
SPEC = {}

#: Seconds it waits idle for a message before it lets its process go.
IDLE = 120.0

OPTIONS = {
    "model": SPEC["model"],
    "cwd": SPEC["cwd"],
    "permission_mode": SPEC["mode"],
    "system_prompt": {"type": "preset", "preset": "claude_code", "append": SKETCH},
}


def logged(ev):
    # One commit per event: into the log, what it is doing now, and the idle clock.
    count = Agent.n.fallback(0)
    return ops.atomic_state(
        Agent.log.append(views.dumped(ev)) >> Agent.n.set(count + 1)
        >> Agent.doing.set(views.doing_of(ev)) >> Agent.beat.set(nustd.time.time())
    )


def accounted(ev):
    # A result: what the turn cost, and what it came to.
    def add(t):
        return ops.atomic_state(
            Agent.turns.set(Agent.turns.fallback(0) + t["turns"])
            >> Agent.tokens_in.set(Agent.tokens_in.fallback(0) + t["in"])
            >> Agent.tokens_out.set(Agent.tokens_out.fallback(0) + t["out"])
            >> Agent.cost.set(Agent.cost.fallback(0.0) + t["cost"])
            >> Agent.seconds.set(Agent.seconds.fallback(0.0) + t["seconds"])
            >> Agent.answer.set(ev["text"]) >> Agent.answered.set(Agent.answered.fallback(0) + 1)
        )

    return nu.let(views.tally(ev), add)


def drawn():
    # Whatever it put in sketch.json, onto its page's board.
    seen = snap(Agent.sketch.fallback([]))
    return nu.let(views.sketch_in(SPEC["cwd"], seen), lambda s: ops.atomic_state(Agent.sketch.set(s)))


def heard(ev):
    kind = nu.Str(ev["type"])
    return (
        logged(ev)
        >> nu.IfDo(kind == "result", accounted(ev))
        >> nu.IfDo(kind == "tool_use", ops.atomic_state(Agent.calls.set(Agent.calls.fallback(0) + 1)))
        >> nu.IfDo(kind == "tool_result", drawn())
    )


def turn():
    # The next message, its turn streamed into the log, raced against a stop.
    def told(msg):
        took = ops.atomic_state(
            Agent.inbox.del_at(0) >> Agent.status.set("working") >> Agent.error.set("")
            >> Agent.prompts.set(Agent.prompts.fallback(0) + 1)
        )
        streamed = nu.ForEachDo(Claude.say(msg), heard)
        stopped = nu.WaitReactive(snap(Agent.stop.on_change()), snap(Agent.stop.fallback(False)), every=2.0)
        cut = ops.atomic_state(Agent.cut.set(True) >> Agent.status.set("stopped") >> Agent.doing.set(""))
        failed = lambda err: (
            logged(nu.Dict.of(type="error", text=nu.Str(err)))
            >> ops.atomic_state(
                Agent.error.set(nu.Str(err)) >> Agent.answer.set(nu.Str("Failed: ") + nu.Str(err))
                >> Agent.answered.set(Agent.answered.fallback(0) + 1)
            )
        )
        user = nu.Dict.of(type="user", text=msg)
        return took >> logged(user) >> nu.TryCatch(nu.Race(streamed, stopped >> cut), catch=failed)

    return nu.let(snap(Agent.inbox.first_elem()), told)


def waiting():
    # Idle until told something, stopped, or idle too long.
    rest = ops.atomic_state(Agent.status.set("idle") >> Agent.doing.set(""))
    stale = nustd.time.time() - Agent.beat.fallback(0.0) > IDLE
    woken = snap((Agent.inbox.fallback([]).len() > 0).or_(Agent.stop.fallback(False)).or_(stale))
    return rest >> nu.WaitReactive(snap(Agent.inbox.on_change()), woken, every=2.0)


def loop():
    told = (Agent.inbox.fallback([]).len() > 0)
    fresh = nustd.time.time() - Agent.beat.fallback(0.0) <= IDLE
    going = snap(Agent.stop.fallback(False).not_().and_(told.or_(fresh)))
    return nu.WhileDo(going, nu.IfDo(snap(told), turn(), waiting()))


def begun():
    # The first start mints the conversation and queues the brief. Later ones carry on a cut turn.
    def first(sid):
        brief = nu.IfDo(nu.Str(SPEC["brief"]) != "", Agent.inbox.append(SPEC["brief"]))
        return ops.atomic_state(Agent.sid.set(sid) >> Agent.spec.set(SPEC) >> brief)

    fresh = snap(Agent.sid.fallback("") == "")
    cut = snap(Agent.cut.fallback(False).or_(Agent.status.fallback("") == "working"))
    carry = ops.atomic_state(Agent.inbox.insert(0, CARRY) >> Agent.cut.set(False))
    clock = ops.atomic_state(Agent.beat.set(nustd.time.time()) >> Agent.status.set("starting"))
    return nu.IfDo(fresh, nu.let(nustd.cc.NewSession(), first), nu.IfDo(cut, carry)) >> clock


def ended():
    stopped = snap(Agent.stop.fallback(False))
    return ops.atomic_state(Agent.status.set(nu.If(stopped, "stopped", "idle")) >> Agent.doing.set(""))


def out(cell):
    session = nustd.cc.Session(loop(), sid=snap(Agent.sid))
    run = begun() >> nu.With(nustd.cc.bind(Claude, **OPTIONS), body=session) >> ended()
    return nu.IfDo(snap(Agent.stop.fallback(False)), ended(), run)
"""


def job_source(spec: dict[str, Any], **pace: float) -> str:
    """:data:`RUN` with ``spec`` baked in as ``SPEC``, and ``idle=`` over :data:`IDLE`."""
    lines = "".join(f"    {k!r}: {v!r},\n" for k, v in spec.items())
    source = RUN.replace("SPEC = {}", "SPEC = {\n" + lines + "}")
    if "idle" in pace:
        source = source.replace("IDLE = 120.0", f"IDLE = {float(pace['idle'])!r}")
    return source


#: ``job_source`` as a term, for a cell that launches agents from what a form or a flow says.
launch_source = nu.host(job_source, name="AgentSource")
