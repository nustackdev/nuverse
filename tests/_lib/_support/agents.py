"""Shared pieces for the agent plane tests: the fake Agent's preset, and an engine run on a test store.

The fake Agent (``acp_agent.py``) runs as a real subprocess of this
interpreter; no real agent and no network.
"""

from __future__ import annotations

import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import nu
import nuspace
from _support.made import MADE
from nuspace.places import inside
from nuspace.specs import SpecCells
from nuverse import agents
from nuverse.agents import engine, terms


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping


__all__ = ["FAKE", "Engine", "entries", "fake_preset", "start", "until"]


#: The scripted Agent, run by this interpreter.
FAKE = [sys.executable, str(Path(__file__).with_name("acp_agent.py"))]


def fake_preset(
    env: Mapping[str, str] | None = None, command: list[str] | None = None
) -> dict[str, object]:
    """The fake Agent as a preset, the shape the real ones take: its argv, and env on top."""
    return {"command": list(command or FAKE), "env": dict(env or {})}


async def until(store, term: nu.Nu, pred: Callable[[Any], bool], timeout: float = 10.0) -> Any:
    """Read ``term`` until ``pred`` holds on it, or fail with the last value."""
    deadline = time.monotonic() + timeout
    while True:
        value = await store.read(term)
        if pred(value):
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting, last read: {value!r}")
        await asyncio.sleep(0.05)


async def entries(store, plane: str) -> list[dict[str, Any]]:
    """Every entry of agent plane ``plane``, in order, each with its ``key``."""
    held = agents.trace(plane).entries
    keys = await store.read(nu.list(held.keys()))
    return [{"key": k, **(await store.read(held[k].extract()))} for k in keys]


@dataclass
class Engine:
    """One engine run on a test store, as the kernel would run the engine cell."""

    store: Any
    plane: str
    run: str
    task: asyncio.Task

    async def status(self, *wanted: str) -> str:
        """Wait until the Session's status is one of ``wanted``; the engine's own error if it died."""

        def landed(status: object) -> bool:
            if self.task.done() and status not in wanted:
                self.task.result()
            return status in wanted

        return await until(self.store, agents.session(self.plane).status, landed)

    async def ask(self, text: str) -> str:
        """Ask ``text``; the id it got."""
        await self.store.run(agents.ask(self.plane, text, by="test"))
        return (await self.store.read(nu.list(agents.asks(self.plane).prompts.keys())))[-1]

    async def turn(self, prompt: str) -> dict[str, Any]:
        """Wait until the turn on prompt ``prompt`` ended; its record."""
        turn = agents.trace(self.plane).turns[f"turn:{prompt}"]
        await until(self.store, turn.ended_at.exists(), bool)
        return await self.store.read(turn.extract())

    async def stop(self) -> None:
        if not self.task.done():
            self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)


async def start(
    store,
    cwd: str,
    *,
    plane: str | None = None,
    idle: float = 30.0,
    owner: str | None = None,
) -> Engine:
    """An agent plane on the ``fake`` preset (made unless given), and its engine running as plane run of its own."""
    if plane is None:
        plane = await store.made(agents.add("fake", cwd, into=MADE))
    run = await store.made(nuspace.atomic(nuspace.plane_run.add(plane, into=MADE)))
    cell = await store.read(nuspace.at.plane(id=plane).state(SpecCells).ids["engine"])
    term = inside(engine.engine(plane, idle=idle), plane=plane, cell=cell, plane_run=run)
    task = asyncio.create_task(store.run(term))
    held = Engine(store, plane, run, task)
    if owner is None:
        await until(store, agents.session(plane).owner, lambda o: o == run or task.done())
    return held


def use_fake(monkeypatch, **kw: Any) -> None:
    """Register the fake Agent as preset ``fake``."""
    monkeypatch.setitem(terms.PRESETS, "fake", fake_preset(**kw))
