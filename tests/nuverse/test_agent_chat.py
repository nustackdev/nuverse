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

    def under(self, *names: str) -> list[Frame]:
        """The frames whose ref holds ``names`` in order, the last one at its end."""

        def holds(ref: tuple[str, ...]) -> bool:
            at = 0
            for part in ref:
                if at < len(names) and part == names[at]:
                    at += 1
            return at == len(names) and ref[-1] == names[-1]

        return [f for f in self.frames if holds(f.ref)]

    def ops(self, *names: str) -> list[tuple[str, object]]:
        return [(f.op, f.payload) for f in self.under(*names)]

    def notify(self, name: str, payload: object) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=self.path(name), payload=payload))


async def _wait(check, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.02)


def _installs(monkeypatch, *names: str, sdk: bool = True) -> None:
    on_path = {"npx", *names}
    monkeypatch.setattr(shutil, "which", lambda n: f"/bin/{n}" if n in on_path else None)
    monkeypatch.setattr(terms.importlib.util, "find_spec", lambda name: object() if sdk else None)


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
        await _wait(lambda: ("init", None) in browser.ops("empty"))
        assert not browser.has("start")
        assert ("init", None) not in browser.ops("no_sdk")
    finally:
        task.cancel()


async def test_no_acp_sdk_says_so_whatever_is_on_path(store, monkeypatch):
    _installs(monkeypatch, "claude", sdk=False)
    browser = _Browser()
    task = await _running(store, browser)
    try:
        await _wait(lambda: ("init", None) in browser.ops("no_sdk"))
        assert not browser.has("start")
        assert ("init", None) not in browser.ops("empty")
    finally:
        task.cancel()


async def _chatting(store, browser: _Browser, monkeypatch) -> tuple[asyncio.Task, str]:
    """A cell past setup, its chat drawn; the task and the agent plane."""
    _installs(monkeypatch, "claude")
    task = await _running(store, browser)
    await _wait(lambda: browser.has("start"))
    await asyncio.sleep(0.1)
    browser.notify("start", {"event": "click"})
    held = nuspace.at.cell(id="c").state(chat.Chat).plane
    plane = await until(store, held.fallback(""), bool)
    await _wait(lambda: browser.has("composer") and browser.has("status"))
    return task, plane


def _tool(**fields: object) -> dict:
    return {"kind": "tool", "turn": "t", "at": 2, "tool": {"tool_call_id": "x", **fields}}


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
        await _wait(lambda: browser.under("perm:n-1", "allow") and browser.under("tool:x", "title"))
        assert ("write", "hi") in browser.ops("user:q1", "bubble", "text")
        assert ("write", {"value": "Edit a.py"}) in browser.ops("tool:x", "header", "title")
        await _wait(
            lambda: ("write", {"value": "Allow Edit a.py?"}) in browser.ops("perm:n-1", "title")
        )
        assert ("display", None) in browser.ops("perm:n-1", "options")

        # A click on an option answers through the agent terms.
        await asyncio.sleep(0.1)
        browser.notify("allow", {"event": "click"})
        answer = trace.entries["perm:n-1"].permission["answer"]
        assert await until(store, answer.fallback(""), bool) == "allow"
        # Answered, the options go and the state says which.
        await _wait(lambda: browser.ops("perm:n-1", "options")[-1] == ("hide", None))
        assert browser.ops("perm:n-1", "state")[-1] == (
            "write",
            {"label": "Allow", "variant": "ok"},
        )

        # The composer asks: a blank submit does nothing, a typed one asks.
        prompts = agents.asks(plane).prompts
        browser.notify("composer", {"event": "submit", "values": {"text": "  "}, "button": "send"})
        browser.notify(
            "composer", {"event": "submit", "values": {"text": "fix it"}, "button": "send"}
        )
        keys = await until(store, nu.list(prompts.keys()), bool)
        assert len(keys) == 1
        assert (await store.read(prompts[keys[0]]))["text"] == "fix it"
    finally:
        task.cancel()


async def test_tool_content_is_keyed_by_kind_and_place_and_shrinks(store, monkeypatch):
    browser = _Browser()
    task, plane = await _chatting(store, browser, monkeypatch)
    try:
        entries = agents.trace(plane).entries
        text = {"type": "content", "content": {"type": "text", "text": "x = 1"}}
        diff = {"type": "diff", "path": "/w/a.py", "old_text": "a\n", "new_text": "b\n"}
        await store.do(entries.set_item("tool:x", _tool(title="Edit", content=[text, text])))
        await _wait(lambda: ("write", "x = 1") in browser.ops("content", "text:1"))

        # The piece at place 0 turns into a diff, place 1 goes away.
        await store.do(entries["tool:x"].tool.set_item("content", [diff]))
        await _wait(lambda: browser.under("content", "diff:0", "code"))
        assert ("write", {"value": "b\n", "original": "a\n"}) in browser.ops("diff:0", "code")
        assert ("write", {"language": "python"}) in browser.ops("diff:0", "code")
        assert ("write", {"value": "/w/a.py"}) in browser.ops("diff:0", "path")
        await _wait(lambda: ("keep_items", {"keys": ["diff:0"]}) in browser.ops("content"))
    finally:
        task.cancel()


async def test_plan_rows_and_stop_while_a_turn_runs(store, monkeypatch):
    browser = _Browser()
    task, plane = await _chatting(store, browser, monkeypatch)
    try:
        session = agents.session(plane)
        plan = [
            {"content": "find it", "priority": "high", "status": "completed"},
            {"content": "fix it", "priority": "high", "status": "in_progress"},
        ]
        await store.do(session.plan.set(plan))
        await _wait(lambda: ("write", {"value": "fix it"}) in browser.ops("s1", "text"))
        assert ("write", {"tone": "info", "label": "in progress", "pulse": True}) in browser.ops(
            "s1", "dot"
        )
        assert browser.ops("plan")[-1] == ("display", None)
        await store.do(session.plan.set([]))
        await _wait(lambda: browser.ops("plan")[-1] == ("hide", None))

        # Stop shows while a turn runs, and a click on it cancels.
        assert browser.ops("stop")[-1] == ("hide", None)
        await store.do(session.status.set(agents.PROMPTING))
        await _wait(lambda: browser.ops("stop")[-1] == ("display", None))
        browser.notify("stop", {"event": "click"})
        cancel_at = agents.asks(plane).cancel_at
        assert await until(store, cancel_at.fallback(0), bool) > 0
        await store.do(session.status.set(agents.IDLE))
        await _wait(lambda: browser.ops("stop")[-1] == ("hide", None))
    finally:
        task.cancel()
