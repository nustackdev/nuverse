"""The Service the desk's jobs ask Claude through.

One endpoint over ``nustd.cc``: a prompt in, the reply and what it cost out.
Here, in a module, and not in a job's cell, so the term that names it can
travel to the job's worker process.
"""

from __future__ import annotations

import importlib.util

import nu


__all__ = ["READY", "Claude", "options"]


#: Whether the Claude Agent SDK is here to talk to Claude Code with.
READY = importlib.util.find_spec("claude_agent_sdk") is not None


def options(model: str, system: str) -> dict:
    """One turn, no tools, nothing from the folder it runs in: a question and its answer."""
    return {
        "model": model,
        "tools": [],
        "max_turns": 1,
        "setting_sources": [],
        "system_prompt": system,
        "cwd": "/tmp",  # noqa: S108 - nothing is read or written there: no tools
    }


if READY:
    import nustd.cc

    class Claude(nu.Service):
        """A question, asked once."""

        ask = nustd.cc.PromptRef.method()
