"""What an agent plane keeps: its Spec, the Session, the Asks, and the Trace of Turns and Entries.

Everything sits in the agent plane's own state, ``State.planes[plane]``,
one slot per name across these Shapes. Names follow ACP where the value is
ACP's. Only the engine writes :class:`Session` and :class:`Trace`; views
and agents write :class:`Asks` and a permission entry's ``answer``, through
:mod:`nuverse.agents.terms`.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv


__all__ = [
    "ASLEEP",
    "ERROR",
    "IDLE",
    "KINDS",
    "PROMPTING",
    "STARTING",
    "STATUSES",
    "WAITING",
    "Asks",
    "Entry",
    "Session",
    "Spec",
    "Trace",
    "Turn",
    "asks_of",
    "session_of",
    "spec_of",
    "trace_of",
]


#: No engine runs; the next ask wakes one.
ASLEEP = "asleep"
#: An engine claimed the plane and is opening the Session.
STARTING = "starting"
#: The Session is open and no Prompt Turn runs.
IDLE = "idle"
#: A Prompt Turn runs.
PROMPTING = "prompting"
#: A Prompt Turn waits on a permission answer.
WAITING = "waiting"
#: The last thing the engine tried failed; a notice entry says why.
ERROR = "error"

#: Every ``Session.status``, in the order a wake goes through them.
STATUSES = (ASLEEP, STARTING, IDLE, PROMPTING, WAITING, ERROR)

#: Every ``Entry.kind``.
KINDS = ("user", "agent", "thought", "tool", "permission", "notice")


class Spec(nu.Shape):
    """Set once, at add: which agent runs, where, and what it is told first."""

    agent = nustd.kv.StrRef.slot()  # "claude" | "codex", the preset to bind
    cwd = nustd.kv.StrRef.slot()  # absolute, fixed for the Session (ACP: cwd is immutable)
    system_prompt = nustd.kv.StrRef.slot()  # appended, "" for none


class Session(nu.Shape):
    """What the engine learned from the Agent; the engine is the only writer."""

    session_id = nustd.kv.StrRef.slot()  # minted by the Agent at session/new; "" before
    title = nustd.kv.StrRef.slot()  # session_info_update
    usage = nustd.kv.DictRef.slot(object)  # usage_update: {used, size, cost}
    plan = nustd.kv.ListRef.slot(dict)  # plan: the complete plan, replaced whole
    commands = nustd.kv.ListRef.slot(dict)  # available_commands_update
    config_options = nustd.kv.ListRef.slot(dict)  # from new/resume, config_option_update
    status = nustd.kv.StrRef.slot()  # one of STATUSES
    owner = nustd.kv.StrRef.slot()  # plane run id that owns the engine, "" while asleep
    error = nustd.kv.StrRef.slot()


class Asks(nu.Shape):
    """What views and agents write; the engine reads."""

    prompts = nustd.kv.LogDictRef.slot(dict)  # id -> {text, at, by}; append only
    cursor = nustd.kv.StrRef.slot()  # the last prompt id taken (engine writes)
    cancel_at = nustd.kv.IntRef.slot()  # ms; newer than the running turn's start cancels it


class Turn(nu.Shape):
    """One Prompt Turn."""

    prompt = nustd.kv.StrRef.slot()  # the Asks.prompts id it answers
    started_at = nustd.kv.IntRef.slot()
    ended_at = nustd.kv.IntRef.slot()
    # end_turn | max_tokens | max_turn_requests | refusal | cancelled
    stop_reason = nustd.kv.StrRef.slot()
    error = nustd.kv.StrRef.slot()  # a JSON-RPC error instead of a stop reason


class Entry(nu.Shape):
    """One thing a person sees in the conversation, folded from the Session Updates."""

    kind = nustd.kv.StrRef.slot()  # one of KINDS
    turn = nustd.kv.StrRef.slot()  # Trace.turns id, "" between turns
    at = nustd.kv.IntRef.slot()  # ms
    text = nustd.kv.StrRef.slot()  # user, agent, thought, notice: markdown, grows as chunks land
    tool = nustd.kv.DictRef.slot(object)  # {tool_call_id, title, kind, status, content, locations}
    permission = nustd.kv.DictRef.slot(object)  # {request, tool_call_id, options, answer, outcome}


class Trace(nu.Shape):
    """The conversation as the engine folded it: its Turns and its Entries, in arrival order."""

    turns = nustd.kv.LogDictRef.slot(Turn)
    entries = nustd.kv.LogDictRef.slot(Entry)


def spec_of(plane: nu.StrArg) -> Spec:
    """Agent plane ``plane``'s :class:`Spec`. A ref, nothing read."""
    return nuspace.at.plane(id=plane).state(Spec)


def session_of(plane: nu.StrArg) -> Session:
    """Agent plane ``plane``'s :class:`Session`. A ref, nothing read."""
    return nuspace.at.plane(id=plane).state(Session)


def asks_of(plane: nu.StrArg) -> Asks:
    """Agent plane ``plane``'s :class:`Asks`. A ref, nothing read."""
    return nuspace.at.plane(id=plane).state(Asks)


def trace_of(plane: nu.StrArg) -> Trace:
    """Agent plane ``plane``'s :class:`Trace`. A ref, nothing read."""
    return nuspace.at.plane(id=plane).state(Trace)
