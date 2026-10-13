"""The Service an agent's job speaks to Claude Code through.

One streamed endpoint over ``nustd.cc``: a call is one turn, its events
handed over as they happen. Here, in a module, and not in the job's cell,
so the term that names it can travel to the job's worker process.

Importing this needs the ``claude-agent-sdk`` package; the planes check for
it before they start any agent (:data:`READY`).
"""

from __future__ import annotations

import importlib.util

import nu


__all__ = ["READY", "Claude"]


#: Whether the Claude Agent SDK is here to talk to Claude Code with.
READY = importlib.util.find_spec("claude_agent_sdk") is not None


if READY:
    import nustd.cc

    class Claude(nu.Service):
        """An agent's one Claude Code endpoint: a turn, streamed."""

        say = nustd.cc.StreamRef.method()
