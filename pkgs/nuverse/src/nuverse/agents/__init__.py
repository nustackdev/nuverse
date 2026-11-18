"""Agent chat: a coding agent (Claude Code, Codex) run on a headless plane, over ACP.

One agent plane per conversation does the work and holds the trace; cells
are views on it. The plane runs one engine cell
(:mod:`nuverse.agents.engine`) that binds ``nustd.acp`` under
``permissions="ask"``, owns the Agent process and the Session, takes asks
one Prompt Turn at a time, and folds what the Agent says into the trace
(:mod:`nuverse.agents.fold`). It sleeps after an idle timeout; the next ask
wakes it.

- :mod:`.shapes`: what the plane keeps, Spec, Session, Asks, Turn, Entry
  and Trace.
- :mod:`.terms`: what callers use, ``add``, ``ask``, ``cancel``,
  ``answer``, ``installed``, and the readers.

Nothing here imports the ACP SDK: it rides the ``nuverse[agents]`` extra,
and only the engine needs it, on the worker that runs it.
"""

from __future__ import annotations

from .shapes import (
    ASLEEP,
    ERROR,
    IDLE,
    PROMPTING,
    STARTING,
    WAITING,
    Asks,
    Entry,
    Session,
    Spec,
    Trace,
    Turn,
)
from .terms import (
    PRESETS,
    add,
    answer,
    ask,
    asks,
    cancel,
    installed,
    session,
    spec,
    trace,
)


__all__ = [
    "ASLEEP",
    "ERROR",
    "IDLE",
    "PRESETS",
    "PROMPTING",
    "STARTING",
    "WAITING",
    "Asks",
    "Entry",
    "Session",
    "Spec",
    "Trace",
    "Turn",
    "add",
    "answer",
    "ask",
    "asks",
    "cancel",
    "installed",
    "session",
    "spec",
    "trace",
]
