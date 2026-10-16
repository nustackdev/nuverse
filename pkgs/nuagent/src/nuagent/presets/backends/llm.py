"""A model behind an OpenAI-compatible chat endpoint: stateless, the transcript rides every call.

Ollama, vLLM, OpenRouter, OpenAI and the rest speak one wire, so which of
them a run talks to is a ``nustd.llm`` preset and its kwargs, nothing more.
The far end remembers nothing between calls, so :meth:`LLM.ask` sends the
whole conversation every turn, and :meth:`LLM.wrap` only holds the http
client open for the run.

**The opening stays a ``user`` message.** The core seeds the conversation
with one ``user`` message (protocol, Nu prose, task), and this backend sends
it as it is rather than lifting it into ``system``:

- it carries the task, which is what the user asks for, and a chat whose
  only message is ``system`` is refused or ignored by some chat templates
  (Gemma, older Mistral) that want a ``user`` turn to answer;
- the conversation the model sees is then the one the session holds, the
  same on every backend, so a transcript reads and replays the same way.

A caller with a real system prompt (a persona, a locked-down mode) passes
``system=``, and it goes ahead of the conversation on every call.

Importing this needs ``httpx`` (``nuagent[llm]``); :data:`READY` says whether
it is here, and without it the module still imports and :class:`LLM` raises
when built.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import nu


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu


__all__ = ["LLM", "PRESETS", "READY", "Model"]


#: Whether ``nustd.llm`` can load: it talks http through ``httpx``.
READY = importlib.util.find_spec("httpx") is not None

#: The ``nustd.llm`` presets a run can name. ``bind`` takes ``base_url`` itself.
PRESETS = ("bind", "ollama", "vllm", "openrouter", "openai", "groq", "cerebras", "xai")


if READY:
    import nustd.llm

    class Model(nu.Service):
        """The chat endpoint a run asks. Module level, so a term naming it pickles."""

        chat = nustd.llm.ChatRef.method()


class LLM:
    """A stateless chat endpoint as a :class:`nuagent.core.Backend`.

    Args:
        preset: a ``nustd.llm`` preset by name (:data:`PRESETS`), or any
            callable ``(service_cls, **endpoint) -> Provide``.
        system: a system prompt sent ahead of the conversation on every call.
            Omitted, none is sent and the opening ``user`` message frames the
            run (see the module docstring).
        request: request-body keys for every call (``temperature``,
            ``max_tokens``, ...).
        **endpoint: the preset's kwargs, passed through as they are
            (``host``, ``model``, ``base_url``, ``api_key``, ``timeout``...).

    Example:
        backend = LLM("ollama", host="red", model="qwen2.5:7b-instruct")
        nu.arun(mem.bound(agent(MemSession, backend, task)))
    """

    def __init__(
        self,
        preset: str | Callable[..., Nu] = "bind",
        *,
        system: str | None = None,
        request: dict[str, object] | None = None,
        **endpoint: object,
    ) -> None:
        if not READY:
            msg = "the llm backend needs httpx: install nuagent[llm]"
            raise ImportError(msg)
        if isinstance(preset, str) and preset not in PRESETS:
            msg = f"unknown nustd.llm preset {preset!r}, expected one of {PRESETS}"
            raise ValueError(msg)
        self.preset = getattr(nustd.llm, preset) if isinstance(preset, str) else preset
        self.system = system
        self.request = dict(request or {})
        self.endpoint = endpoint

    def ask(self, messages: Nu) -> Nu:
        """The reply to the whole conversation, ``system`` first when there is one.

        Args:
            messages: the session's ``messages`` ref. Read with ``extract``,
                so a kv store's views go out as the plain dicts the wire wants.

        Returns:
            A ``Str`` term, the reply's text.
        """
        sent = nu.List(messages.extract())
        if self.system is not None:
            sent = nu.List.of(nu.Dict.of(role="system", content=self.system)) + sent
        return nu.Str(nu.dict(Model.chat(messages=sent, **self.request))["text"])

    def wrap(self, body: Nu) -> Nu:
        """The run with the endpoint bound: the client opens on entry and closes on exit."""
        return nu.With(self.preset(Model, **self.endpoint), body=body)
