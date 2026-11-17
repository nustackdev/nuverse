"""The chat cell: setup, the entries it draws from the trace, answering, asking."""

from __future__ import annotations

import asyncio
import shutil

import pytest
from _support.agents import until

import nu
import nuspace
from nuspace.places import inside
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session
from nuverse import agents
from nuverse.agents import terms
from nuverse.cells.agents import chat


pytestmark = pytest.mark.timeout(30)


class _Browser(WsSession):
    """A session with no socket: keeps frames, answers the agent select, sends events."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        assert path[-1] == "agent"
        return self.last("agent")

    def path(self, name: str) -> tuple[str, ...]:
        return next(f.ref for f in self.frames if f.ref[-1] == name)

    def last(self, name: str) -> object:
        return next(f.payload for f in reversed(self.frames) if f.ref[-1] == name)

    def has(self, name: str) -> bool:
        return any(f.ref[-1] == name for f in self.frames)

    def notify(self, name: str, payload: object) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=self.path(name), payload=payload))


async def _wait(check, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.02)


def _installs(monkeypatch, *names: str) -> None:
    on_path = {"npx", *names}
    monkeypatch.setattr(shutil, "which", lambda n: f"/bin/{n}" if n in on_path else None)
    monkeypatch.setattr(terms.importlib.util, "find_spec", lambda name: object())


async def _running(store, browser: _Browser) -> asyncio.Task:
    await store.do(nuspace.plane.add(id="p", backend="async"))
    await store.do(nuspace.specs.add_cell("p", chat.CELL, id="c"))
    await store.do(nuspace.Space.info.path.set("/srv/space"))
    term = inside(chat.out(), plane="p", cell="c")
    return asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))


async def test_no_agent_installed_shows_an_empty_state(store, monkeypatch):
    _installs(monkeypatch)
    browser = _Browser()
    task = await _running(store, browser)
    try:
        await _wait(lambda: browser.has("empty"))
        assert not browser.has("start")
    finally:
        task.cancel()


async def test_setup_starts_a_chat_and_the_chat_draws_the_trace(store, monkeypatch):
    _installs(monkeypatch, "claude")
    browser = _Browser()
    task = await _running(store, browser)
    try:
        await _wait(lambda: browser.has("start"))
        assert browser.last("agent") == "claude"
        await asyncio.sleep(0.1)
        browser.notify("start", {"event": "click"})
        held = nuspace.at.cell(id="c").state(chat.Chat).plane
        plane = await until(store, held.fallback(""), bool)
        spec = agents.spec(plane)
        assert await store.read(nu.Dict.of(agent=spec.agent, cwd=spec.cwd)) == {
            "agent": "claude",
            "cwd": "/srv/space",
        }
        assert await store.read(nuspace.Space.planes[plane].parent) == "p"
        await _wait(lambda: browser.has("composer"))
        await _wait(lambda: browser.has("status"))
        assert browser.last("title") == {"label": "New chat"}
        assert browser.last("status") == {"tone": "neutral", "label": "asleep"}

        # The engine's writes, as it would make them: a user message, a tool, a permission.
        trace = agents.trace(plane)
        options = [{"option_id": "allow", "name": "Allow", "kind": "allow_once"}]
        await store.do(
            trace.entries.set_item("user:q1", {"kind": "user", "turn": "t", "at": 1, "text": "hi"})
            >> trace.entries.set_item(
                "tool:x",
                {
                    "kind": "tool",
                    "turn": "t",
                    "at": 2,
                    "tool": {
                        "tool_call_id": "x",
                        "title": "Edit a.py",
                        "kind": "edit",
                        "status": "pending",
                    },
                },
            )
            >> trace.entries.set_item(
                "perm:n-1",
                {
                    "kind": "permission",
                    "turn": "t",
                    "at": 3,
                    "permission": {"request": 1, "tool_call_id": "x", "options": options},
                },
            )
        )
        await _wait(lambda: browser.has("perm:n-1") and browser.has("tool:x"))
        assert any(f.ref[-1] == "user:q1" and "hi" in str(f.payload) for f in browser.frames)
        assert any(
            f.ref[-1] == "perm:n-1" and "Allow Edit a.py?" in str(f.payload) for f in browser.frames
        )

        # A click answers through the agent terms.
        await asyncio.sleep(0.1)
        browser.notify("perm:n-1", {"event": "select", "option_id": "allow"})
        answer = trace.entries["perm:n-1"].permission["answer"]
        assert await until(store, answer.fallback(""), bool) == "allow"

        # The composer asks.
        browser.notify("composer", {"event": "submit", "value": "fix it"})
        prompts = agents.asks(plane).prompts
        keys = await until(store, nu.list(prompts.keys()), bool)
        assert (await store.read(prompts[keys[0]]))["text"] == "fix it"
    finally:
        task.cancel()
