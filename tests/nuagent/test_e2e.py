"""End to end through a real model, over llm and over cc, with the full opening prompt.

Two tasks: a one-line write, and a composition over a bound world (the sum of
the even numbers in a list, into a slot). The opening is
:func:`nuagent.prompt.opening`: protocol, the nu pieces, the catalogue, and
for the second task the surface.

Skipped unless ``NUAGENT_E2E=1``. They cost money (cc) or need the cluster
(llm), and a model may take a few turns. Each prints its transcript, so run
with ``-s`` to read it.

- llm: ``NUAGENT_LLM_URL`` (default ``http://red:11434``, the cluster's
  ollama) and ``NUAGENT_LLM_MODEL`` (default ``qwen2.5-coder:32b-instruct-q4_K_M``).
- cc: the local ``claude`` login, ``NUAGENT_CC_MODEL`` (default ``claude-haiku-4-5``).

Every task runs on mem; cc runs both on kv too, session and world on one
sqlite file, with the world's Shapes declared on ``nustd.kv``.
"""

from __future__ import annotations

import asyncio
import os
import time

import pytest
from _support.scripted import KV, Mem

import nu
import nustd.kv
from nuagent.core import agent
from nuagent.presets.store.kv import KVRun
from nuagent.prompt import MODULES, opening, sections


pytestmark = pytest.mark.skipif(os.environ.get("NUAGENT_E2E") != "1", reason="NUAGENT_E2E=1 to run")

#: A run that has not ended by then has gone wrong.
CEILING = 600.0

TASK = (
    "Your task: set `Notes.title` to 'hi', then end the run. `Notes` is a mem Shape "
    "with one slot, `title = nu.StrRef.slot()`; declare it in your module."
)


class Data(nu.Shape):
    """The numbers the task is about, and where its answer goes."""

    nums = nu.ListRef.slot(int)
    even_sum = nu.IntRef.slot()


NUMS = [3, 8, 5, 14, 7, 21, 10, 2, 9]

SUM_TASK = (
    "Your task: write the sum of the even numbers in `Data.nums` to `Data.even_sum`, "
    "then end the run. Compute it in the program, from the list as it is when the "
    "program runs; do not read the numbers and write a constant."
)


class KVNotes(nu.Shape):
    """The title task's world, on kv."""

    title = nustd.kv.StrRef.slot()


class KVData(nu.Shape):
    """The sum task's world, on kv."""

    nums = nustd.kv.ListRef.slot(int)
    even_sum = nustd.kv.IntRef.slot()


KV_TASK = "Your task: set `KVNotes.title` to 'hi', then end the run."


def _kv_sections(*app: type) -> tuple:
    return sections(modules=(*MODULES, "nustd.kv"), app=app, run=KVRun)


def _ran(h: Mem | KV, backend: object, opened: str) -> None:
    term = agent(h.store, backend, opened)
    print(f"\nprompt: {len(opened)} chars, ~{len(opened) // 4} tokens")
    start = time.monotonic()
    try:
        if isinstance(h, Mem):
            asyncio.run(asyncio.wait_for(nu.arun(term, h.context()), CEILING))
        else:
            asyncio.run(asyncio.wait_for(nu.arun(h.store.bound(term)), CEILING))
            h.run(nu.Int(0))
    finally:
        messages = h.session.get("messages", [])
        for message in messages[1:]:
            print(f"--- {message['role']}\n{message['content']}")
        took = time.monotonic() - start
        print(f"turns: {(len(messages) - 1) // 2}, time: {took:.1f}s")


def _done(mem: Mem | KV) -> None:
    assert mem.world.get("title") == "hi"
    assert mem.world.get("done") is True


def _summed(mem: Mem | KV) -> None:
    assert mem.world.get("even_sum") == sum(n for n in NUMS if n % 2 == 0)
    assert mem.world.get("done") is True


def _llm() -> object:
    from nuagent.presets.backends.llm import LLM

    url = os.environ.get("NUAGENT_LLM_URL", "http://red:11434")
    model = os.environ.get("NUAGENT_LLM_MODEL", "qwen2.5-coder:32b-instruct-q4_K_M")
    return LLM("bind", base_url=url, model=model, timeout=300.0, request={"temperature": 0})


@pytest.fixture
def cc(tmp_path, monkeypatch):
    """A Claude Code backend that prints what the run cost."""
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
    yield ClaudeCode(model=model, cwd=str(tmp_path))
    print(f"cost: ${sum(costs):.4f} (per turn {costs})")


def test_llm_does_the_task():
    mem = Mem()
    _ran(mem, _llm(), opening(TASK))
    _done(mem)


def test_cc_does_the_task(cc):
    mem = Mem()
    _ran(mem, cc, opening(TASK))
    _done(mem)


def test_llm_sums_the_evens():
    mem = Mem(world={"nums": list(NUMS)})
    _ran(mem, _llm(), opening(SUM_TASK, sections(app=[Data])))
    _summed(mem)


def test_cc_sums_the_evens(cc):
    mem = Mem(world={"nums": list(NUMS)})
    _ran(mem, cc, opening(SUM_TASK, sections(app=[Data])))
    _summed(mem)


def test_cc_does_the_task_on_kv(cc, tmp_path):
    h = KV(str(tmp_path / "run.db"))
    _ran(h, cc, opening(KV_TASK, _kv_sections(KVNotes)))
    _done(h)


def test_cc_sums_the_evens_on_kv(cc, tmp_path):
    h = KV(str(tmp_path / "run.db"), world={"nums": list(NUMS)})
    _ran(h, cc, opening(SUM_TASK.replace("Data.", "KVData."), _kv_sections(KVData)))
    _summed(h)


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
    term = agent(mem.store, ClaudeCode(model=model, cwd=str(tmp_path)), opening(task))
    asyncio.run(asyncio.wait_for(nu.arun(term, mem.context()), CEILING))
    print(*(f"--- sent\n{text[:200]}" for text in sent), sep="\n")
    assert mem.world.get("title") == "42"
    assert len(sent) >= 2
    assert not any(text.startswith(REPLAY) for text in sent)
    assert sent[1:] == [m["content"] for m in mem.session["messages"][2:-1:2]]
