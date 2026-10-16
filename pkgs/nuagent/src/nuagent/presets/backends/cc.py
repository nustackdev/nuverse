"""Claude Code as the model: one conversation for the whole run, the newest message per turn.

``nustd.cc.Session`` is a brace: every prompt inside it is a turn of one
conversation (on one ``claude`` process under ``nu.arun``). :meth:`ClaudeCode.wrap`
opens it around the whole run, so the far end holds the transcript and
:meth:`ClaudeCode.ask` sends only what is new, the newest message.

**The conversation outlives the process.** Its id is minted before the first
prompt (``NewSession``), and a caller that wants a restart to pick the same
conversation back up hands in a ref to keep it in (``sid=``). Keeping that
ref durable is the caller's or the store's business, not this module's.

**A fresh conversation with history gets the history once.** When the CLI
holds no transcript for the id (a new id, a lost transcript, a space moved
to another directory) but the session already holds more than the opening,
the newest message alone would make no sense. That turn sends the whole
conversation flattened instead (:data:`REPLAY`, then ``[role]`` and the
content of each message, oldest first). From then on the CLI holds it, and
every later turn is the newest message again.

**Agents bring their own tools.** The defaults are Claude Code's own system
prompt and its own tools: nothing is narrowed here. A locked-down agent is a
layer for later.

Importing this needs nothing extra; :data:`READY` says whether the Claude
Agent SDK (``nuagent[cc]``) is here, and without it :class:`ClaudeCode` raises
when built.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import nu
from nu.lang import ScalarQuery


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu, StrArg


__all__ = ["READY", "REPLAY", "SYSTEM_PROMPT", "Agent", "ClaudeCode", "Held", "Thread", "flattened"]


#: Whether the Claude Agent SDK is here to talk to Claude Code with.
READY = importlib.util.find_spec("claude_agent_sdk") is not None

#: Claude Code's own system prompt. The run's own framing is the opening message.
SYSTEM_PROMPT = {"type": "preset", "preset": "claude_code"}

#: Heads a conversation replayed into a fresh session.
REPLAY = (
    "This session started without the conversation so far. "
    "Here it is, oldest first. Reply to the last message.\n\n"
)


if READY:
    import nustd.cc

    class Agent(nu.Service):
        """The Claude Code endpoint a run asks. Module level, so a term naming it pickles."""

        ask = nustd.cc.PromptRef.method()


class Thread(nu.Shape):
    """The conversation the run is in, bound by :meth:`ClaudeCode.wrap` for the run."""

    sid = nu.StrRef.slot()


class Held(ScalarQuery):
    """Whether the CLI holds a transcript for a conversation id, in a working directory.

    The same lookup ``nustd.cc`` makes to pick ``--resume`` over
    ``--session-id``, so the two always agree on whether a conversation is
    fresh.

    Args:
        sid: the conversation id, a str or any Str-yielding term.
        cwd: the working directory the CLI runs in. None is this process's.

    Yields:
        A bool.
    """

    def __init__(self, sid: StrArg, *, cwd: str | None = None) -> None:
        super().__init__(sid)
        self._payload["cwd"] = cwd

    def _held(self, sid: object) -> bool:
        directory = self._payload["cwd"] or str(Path.cwd())
        return nustd.cc.fabric.get_session_info(str(sid), directory=directory) is not None

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (sid,) = children
        return lambda rt: self._held(sid(rt))

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (sid,) = children

        async def athunk(rt: object) -> bool:
            return self._held(await sid(rt))

        return athunk


def flattened(messages: Nu) -> Nu:
    """The conversation as one prompt: :data:`REPLAY`, then ``[role]`` and content per message.

    Args:
        messages: a list of ``{role, content}`` dicts, plain data.

    Returns:
        A ``Str`` term.
    """

    def told(message: Nu) -> Nu:
        """One message: its role in brackets, then what it says."""
        said = nu.Dict(message)
        return "[" + nu.Str(said["role"]) + "]\n" + nu.Str(said["content"])

    told_all = nu.List(messages).iter().map(told).to_list()
    return REPLAY + nu.Str("\n\n").join(told_all)


class ClaudeCode:
    """Claude Code in one conversation per run, as a :class:`nuagent.core.Backend`.

    Args:
        model: the model to ask. Omitted, the CLI's own default.
        sid: the conversation to be in. Omitted, one is minted per run. A str
            is used as it is. A ref (a ``StrRef`` slot) is minted into once,
            when it holds none, and read from then on, so a run started again
            over the same ref resumes the conversation.
        **options: more ``ClaudeAgentOptions`` fields (``cwd``,
            ``permission_mode``, ``max_turns``, ...), over the defaults.

    Notes:
        - A ref ``sid`` is read and written where :meth:`wrap` runs, outside
          the loop: a kv ref there needs its own bracket.
        - Prefer ``nu.arun``: there the run is one ``claude`` process. Under
          ``nu.run`` every turn starts one, on the same conversation.

    Example:
        store, backend = MemStore(), ClaudeCode(model="claude-haiku-4-5", cwd="/tmp/work")
        await nu.arun(store.bound(agent(store, backend, task)))
    """

    def __init__(
        self, *, model: str | None = None, sid: Nu | str | None = None, **options: object
    ) -> None:
        if not READY:
            msg = "the cc backend needs the Claude Agent SDK: install nuagent[cc]"
            raise ImportError(msg)
        self.sid = sid
        self.options: dict[str, object] = {"system_prompt": SYSTEM_PROMPT, **options}
        if model is not None:
            self.options["model"] = model

    def ask(self, messages: Nu) -> Nu:
        """The reply to the newest message, or to the whole conversation on a fresh one.

        Args:
            messages: the conversation as plain data, ``{role, content}`` dicts.

        Returns:
            A ``Str`` term, the reply's text.
        """
        cwd = self.options.get("cwd")
        fresh = nu.Bool(Held(Thread.sid, cwd=None if cwd is None else str(cwd))).not_()
        said = nu.List(messages)
        newest = nu.Str(nu.Dict(said[-1])["content"])
        prompt = nu.If(fresh.and_(said.len() > 1), flattened(said), newest)
        return nu.Str(nu.dict(Agent.ask(nu.Str(prompt)))["text"])

    def wrap(self, body: Nu) -> Nu:
        """The run inside the agent's bind and one Session, on an id held for the run."""
        session = nustd.cc.Session(body, sid=Thread.sid)
        if self.sid is None:
            held = nu.Frame(Thread, session, sid=nustd.cc.NewSession())
        elif isinstance(self.sid, str):
            held = nu.Frame(Thread, session, sid=self.sid)
        else:
            minted = nu.IfDo(self.sid.is_empty(), self.sid.set(nustd.cc.NewSession()))
            held = minted >> nu.Frame(Thread, session, sid=self.sid)
        return nu.With(nustd.cc.bind(Agent, **self.options), body=held)
