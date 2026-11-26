"""How the desk's jobs ask Claude: Claude Code over ACP (``nustd.acp``), one question per session.

A prompt in, the reply out as ``{"text": ...}``. Here, in a module, and not
in a job's cell, so the terms that name the agent can travel to the job's
worker process. The knowledge demo asks through the same helpers.

ACP reports no cost, so a reply carries none and the desk counts it as zero.
"""

from __future__ import annotations

import importlib.util
import tempfile

import nu


__all__ = ["CWD", "READY", "Claude", "ask", "bind", "reply"]


#: Whether the ACP SDK is here to talk to Claude Code with (the ``acp`` extra of nustd).
READY = importlib.util.find_spec("acp") is not None

#: Where the agent runs: the temp dir, so no project around it is read. It gets no tools.
CWD = tempfile.gettempdir()


@nu.host
def reply(items: list) -> dict:
    """A prompt turn's Session Updates as the reply: the text of its message chunks."""
    text = "".join(
        (item.get("content") or {}).get("text", "")
        for item in items or []
        if isinstance(item, dict) and item.get("session_update") == "agent_message_chunk"
    )
    return {"text": text}


if READY:
    import nustd.acp

    #: The desk's Claude Code, by the name its fabric binds under.
    Claude = nustd.acp.AgentRef("nudemos.claude")

    def bind(agent: nustd.acp.AgentRef = Claude) -> nu.Nu:
        """Claude Code under ``agent``'s name for the span of a tree: answers only, every tool refused."""
        return nustd.acp.claude(agent, cwd=CWD, permissions="reject_always")

    def ask(
        prompt: nu.StrArg,
        model: nu.StrArg,
        system: nu.StrArg,
        agent: nustd.acp.AgentRef = Claude,
    ) -> nu.Nu:
        """``prompt`` asked once in a session of its own, ``model`` answering, ``system`` added to its prompt."""

        def turn(sid: nu.Nu) -> nu.Nu:
            session = agent[sid]
            picked = session.set_config_option("model", model)
            return nu.let(lambda _: reply(nu.Collect(session.prompt(prompt))), _=picked)

        return nu.let(turn, sid=nu.Dict(agent.new_session(system_prompt=system))["session_id"])
