"""End to end through a real model: one tiny task on mem, over llm and over cc.

Skipped unless ``NUAGENT_E2E=1``. They cost money (cc) or need the cluster
(llm), and a model may take a few turns. Each prints its transcript, so run
with ``-s`` to read it.

- llm: ``NUAGENT_LLM_URL`` (default ``http://red:11434``, the cluster's
  ollama) and ``NUAGENT_LLM_MODEL`` (default ``qwen2.5-coder:32b-instruct-q4_K_M``).
- cc: the local ``claude`` login, ``NUAGENT_CC_MODEL`` (default ``claude-haiku-4-5``).
"""

from __future__ import annotations

import asyncio
import os

import pytest
from _support.scripted import Mem

import nu
from nuagent.core import agent
from nuagent.presets.store.mem import MemSession
from nuagent.protocol import prompt


pytestmark = pytest.mark.skipif(os.environ.get("NUAGENT_E2E") != "1", reason="NUAGENT_E2E=1 to run")

#: A run that has not ended by then has gone wrong.
CEILING = 600.0

TASK = (
    "Your task: set `Notes.title` to 'hi', then end the run. `Notes` is a mem Shape "
    "with one slot, `title = nu.StrRef.slot()`; declare it in your module."
)


def _ran(mem: Mem, backend: object) -> object:
    ctx = nu.Context().bind(dict, mem.session, MemSession).bind(dict, mem.world)
    term = agent(MemSession, backend, prompt() + "\n\n" + TASK)
    print()
    try:
        return asyncio.run(asyncio.wait_for(nu.arun(term, ctx), CEILING))
    finally:
        for message in mem.session.get("messages", [])[1:]:
            print(f"--- {message['role']}\n{message['content']}")


def _done(mem: Mem) -> None:
    assert mem.world.get("title") == "hi"
    assert mem.world.get("done") is True


def test_llm_does_the_task():
    from nuagent.presets.backends.llm import LLM

    url = os.environ.get("NUAGENT_LLM_URL", "http://red:11434")
    model = os.environ.get("NUAGENT_LLM_MODEL", "qwen2.5-coder:32b-instruct-q4_K_M")
    mem = Mem()
    _ran(mem, LLM("bind", base_url=url, model=model, timeout=300.0, request={"temperature": 0}))
    _done(mem)


def test_cc_does_the_task(tmp_path, monkeypatch):
    from nuagent.presets.backends.cc import ClaudeCode
    from nustd.cc import fabric

    costs: list[float] = []
    collected = fabric.collected

    async def counted(messages):
        result = await collected(messages)
        costs.append(result.get("total_cost_usd") or 0.0)
        return result

    monkeypatch.setattr(fabric, "collected", counted)
    model = os.environ.get("NUAGENT_CC_MODEL", "claude-haiku-4-5")
    mem = Mem()
    try:
        _ran(mem, ClaudeCode(model=model, cwd=str(tmp_path)))
    finally:
        print(f"turns: {len(costs)}, cost: ${sum(costs):.4f} (per turn {costs})")
    _done(mem)


def test_cc_holds_the_conversation_across_turns(tmp_path, monkeypatch):
    from nuagent.presets.backends.cc import REPLAY, ClaudeCode
    from nustd.cc import fabric

    sent: list[str] = []
    aturn = fabric.CCFabric.aturn

    async def recorded(self, client, text):
        sent.append(text)
        return await aturn(self, client, text)

    monkeypatch.setattr(fabric.CCFabric, "aturn", recorded)
    task = (
        "Your task, in two turns. First turn: return `nu.Int(6) * 7` and do not end the run. "
        "Second turn, once you have read the outcome: set `Notes.title` to that number as a "
        "string and end the run. `Notes` is a mem Shape with one slot, "
        "`title = nu.StrRef.slot()`; declare it in your module."
    )
    model = os.environ.get("NUAGENT_CC_MODEL", "claude-haiku-4-5")
    mem = Mem()
    ctx = nu.Context().bind(dict, mem.session, MemSession).bind(dict, mem.world)
    term = agent(MemSession, ClaudeCode(model=model, cwd=str(tmp_path)), prompt() + "\n\n" + task)
    asyncio.run(asyncio.wait_for(nu.arun(term, ctx), CEILING))
    print(*(f"--- sent\n{text[:200]}" for text in sent), sep="\n")
    assert mem.world.get("title") == "42"
    assert len(sent) >= 2
    assert not any(text.startswith(REPLAY) for text in sent)
    assert sent[1:] == [m["content"] for m in mem.session["messages"][2:-1:2]]
