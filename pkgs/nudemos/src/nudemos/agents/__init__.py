"""The ``agents`` Plane: Claude Code sessions run, watched, steered and orchestrated from a space.

Nu is the control plane, Claude Code does the work. One agent is one Claude
Code session: a page that streams its transcript, and a headless job under
the page whose one cell is a short Nu loop over a ``nustd.cc.Session``
(:mod:`.job`), taking each message from the agent's state and streaming the
turn back into it. The pages around it only read and steer that state.

Orchestration is plain Nu over agents, no framework: a flow is a headless job
whose cell asks agents, waits on them and reads their answers through a
:class:`~.flows.Team` (:mod:`.flows`). Three ship, each a plane under this one
showing its cell in full: Fan-out and judge, Chain, Task board.

- :mod:`.claude`, :mod:`.job`: the Claude Code endpoint, and the agent's loop over it.
- :mod:`.launch`: making an agent, saying something to it, stopping and resuming it.
- :mod:`.flows`: the :class:`~.flows.Team` terms and the three flows, as cell sources.
- :mod:`.board`, :mod:`.page`, :mod:`.orchestrate`: the planes, as cell sources.
- :mod:`.views`, :mod:`.state`: what the cells read and how they shape it.

Talking to Claude Code needs the ``claude-agent-sdk`` package (the ``cc`` extra
of nustd) and a logged-in ``claude`` CLI. No API key: it runs on the login.
"""

from __future__ import annotations

from nuspace import PlaneSpec

from . import board, orchestrate


__all__ = ["PLANE"]


PLANE = PlaneSpec(
    "agents",
    "Agents",
    icon="bot",
    description="Claude Code sessions, run, steered and orchestrated from a space.",
    meta={"editable": True, "full_width": True},
    cells=(("intro", board.INTRO), ("new", board.NEW), ("board", board.BOARD)),
    children=(orchestrate.FANOUT_PLANE, orchestrate.CHAIN_PLANE, orchestrate.TASKS_PLANE),
    group="Demos",
    backend="async",
)
