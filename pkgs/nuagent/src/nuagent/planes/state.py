"""What a conversation keeps: all of it in its engine plane's own state.

One engine per conversation, and everything the conversation is lives in the
engine plane's ``PlaneState``, ``States.planes[engine].state``. Three Shapes
land there, side by side, addressed by slot name:

- :class:`Chat`: the page's half (the inbox the person writes) and the
  engine's (where it is, what each turn did), and the loop's session.
- :class:`Run`: the one slot the model ends a run through. Its own class,
  so the prompt shows the model that slot and nothing else.

The page writes ``inbox`` and nothing else. The engine writes the rest, and
the model's program writes ``done``. A model ``PlaneState`` of its own lands
in the same state too: a program running on the engine is a cell of it.
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace import PlaneState


__all__ = [
    "ERROR",
    "IDLE",
    "RUNNING",
    "STATUSES",
    "STOPPED",
    "THINKING",
    "Chat",
    "Outcome",
    "Run",
]


#: Nothing to do: every message is handled.
IDLE = "idle"

#: A message is being handled: the model is asked, or its program runs.
THINKING = "thinking"

#: Shown, never kept: thinking, while the program of the latest reply runs.
RUNNING = "running"

#: The person stopped the run under way.
STOPPED = "stopped"

#: The last message failed outside the model's program (the backend, the store).
ERROR = "error"

#: Every status the engine keeps.
STATUSES = (IDLE, THINKING, STOPPED, ERROR)


class Outcome(nu.Shape):
    """How the last program went. ``kind`` is one of :data:`nuagent.protocol.KINDS`."""

    kind = nustd.kv.StrRef.slot()
    value = nustd.kv.StrRef.slot()  #: repr of the yield, for ``ok``
    message = nustd.kv.StrRef.slot()  #: what went wrong, for ``construct`` and ``runtime``
    line = nustd.kv.IntRef.slot()  #: source line of a ``construct`` failure, when it has one


class Chat(PlaneState):
    """One conversation: what the person said, where the engine is, and what each turn did.

    The last four slots are the loop's session (:class:`nuagent.core.Store`).
    """

    inbox = nustd.kv.ListRef.slot(str)  #: what the person sent, in order, appended by the page
    cursor = nustd.kv.IntRef.slot()  #: how many of ``inbox`` the engine has handled
    status = nustd.kv.StrRef.slot()  #: one of :data:`STATUSES`
    error = nustd.kv.StrRef.slot()  #: what failed, while ``status`` is :data:`ERROR`
    turns = nustd.kv.ListRef.slot(dict)  #: per turn ``{at, reply, program, kind, observation}``
    sid = nustd.kv.StrRef.slot()  #: the Claude Code conversation, on the cc backend
    messages = nustd.kv.ListRef.slot(dict)  #: ``{role, content}``, appended to, never rebuilt
    reply = nustd.kv.StrRef.slot()
    program = nustd.kv.ProgramRef.slot()
    outcome = nustd.kv.ShapeRef.slot(Outcome)


class Run(PlaneState):
    """The run itself: the model sets ``done`` and the engine moves on after that turn."""

    done = nustd.kv.BoolRef.slot()
