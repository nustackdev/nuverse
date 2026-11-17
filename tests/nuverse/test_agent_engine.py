"""The agent engine against the fake ACP Agent: turns, the fold, permissions, cancel, sleep, restarts, errors."""

from __future__ import annotations

import asyncio

import pytest
from _support.agents import entries, start, until, use_fake

import nu
import nustd.acp
from nuverse import agents
from nuverse.agents import engine as engine_module


pytestmark = pytest.mark.timeout(60)


def _texts(held: list[dict]) -> list[tuple[str, str]]:
    return [(e["kind"], e.get("text", "")) for e in held if e["kind"] != "tool"]


async def test_a_turn_folds_into_entries_and_ends_idle(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    try:
        await e.status("idle")
        pid = await e.ask("hello")
        turn = await e.turn(pid)
        assert (turn["prompt"], turn["stop_reason"]) == (pid, "end_turn")
        assert turn["ended_at"] >= turn["started_at"] > 0
        await until(store, nu.Int(nu.Len(agents.trace(e.plane).entries.keys())), lambda n: n == 2)
        held = await entries(store, e.plane)
        assert _texts(held) == [("user", "hello"), ("agent", "hello")]
        assert {x["turn"] for x in held} == {f"turn:{pid}"}
        s = agents.session(e.plane)
        assert await store.read(s.session_id) == "s1"
        assert await store.read(agents.asks(e.plane).cursor) == pid
        assert await e.status("idle") == "idle"
        assert await store.read(s.owner) == e.run
    finally:
        await e.stop()


async def test_the_fold_keeps_thoughts_tools_plan_usage_and_title(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    try:
        pid = await e.ask("rich")
        await e.turn(pid)
        s = agents.session(e.plane)
        await until(store, s.title, lambda t: t == "Rich")
        held = await entries(store, e.plane)
        assert [x["kind"] for x in held] == ["user", "thought", "tool", "agent"]
        assert held[1]["text"] == "hmm"
        assert held[3]["text"] == "all good"
        tool = held[2]
        assert tool["key"] == "tool:r1"
        assert tool["tool"]["status"] == "completed"
        assert tool["tool"]["title"] == "Read a.py"
        assert tool["tool"]["locations"] == [{"path": "/w/a.py"}]
        assert tool["tool"]["content"][0]["content"]["text"] == "x = 1"
        plan = await store.read(s.plan.extract())
        assert [p["status"] for p in plan] == ["completed", "in_progress"]
        usage = await store.read(s.usage.extract())
        assert (usage["used"], usage["size"], usage["cost"]["amount"]) == (41000, 200000, 0.38)
    finally:
        await e.stop()


async def test_an_echoed_prompt_shows_once_and_message_ids_split(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    try:
        await e.turn(await e.ask("echo"))
        await e.turn(await e.ask("ids"))
        await until(store, nu.Int(nu.Len(agents.trace(e.plane).entries.keys())), lambda n: n == 5)
        held = await entries(store, e.plane)
        assert _texts(held) == [
            ("user", "echo"),
            ("agent", "ok"),
            ("user", "ids"),
            ("agent", "a"),
            ("agent", "b"),
        ]
    finally:
        await e.stop()


async def test_asks_queue_and_run_one_turn_at_a_time(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    try:
        first = await e.ask("slow")
        second = await e.ask("probe")
        one, two = await e.turn(first), await e.turn(second)
        assert two["started_at"] >= one["ended_at"]
        await until(store, nu.Int(nu.Len(agents.trace(e.plane).entries.keys())), lambda n: n == 3)
        # The probe saw one prompt running on the Session: its own.
        assert _texts(await entries(store, e.plane))[-1] == ("agent", "1")
    finally:
        await e.stop()


async def test_a_permission_waits_for_its_answer(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    try:
        pid = await e.ask("perm")
        await e.status("waiting")
        held = await entries(store, e.plane)
        perm = held[-1]
        assert perm["kind"] == "permission"
        assert perm["permission"]["tool_call_id"] == "t1"
        assert [o["option_id"] for o in perm["permission"]["options"]] == [
            "allow",
            "always",
            "reject",
        ]
        await store.run(agents.answer(e.plane, perm["key"], "allow"))
        assert (await e.turn(pid))["stop_reason"] == "end_turn"
        await until(store, nu.Int(nu.Len(agents.trace(e.plane).entries.keys())), lambda n: n == 4)
        held = await entries(store, e.plane)
        assert held[2]["permission"]["answer"] == "allow"
        assert held[2]["permission"]["outcome"] == "selected"
        assert _texts(held)[-1] == ("agent", "selected:allow")
        await e.status("idle")
    finally:
        await e.stop()


async def test_cancel_stops_the_running_turn_and_its_open_tools(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    try:
        # A cancel stamped before the turn starts leaves it alone.
        await store.run(agents.cancel(e.plane))
        await asyncio.sleep(0.01)
        pid = await e.ask("tool-wait")
        await until(store, agents.trace(e.plane).entries.contains("tool:w1"), bool)
        await store.run(agents.cancel(e.plane))
        assert (await e.turn(pid))["stop_reason"] == "cancelled"
        tool = await store.read(agents.trace(e.plane).entries["tool:w1"].tool.extract())
        assert tool["status"] == "cancelled"
        await e.status("idle")
    finally:
        await e.stop()


async def test_cancel_answers_a_waiting_permission_cancelled(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    try:
        pid = await e.ask("perm")
        await e.status("waiting")
        await store.run(agents.cancel(e.plane))
        assert (await e.turn(pid))["stop_reason"] == "cancelled"
        held = await entries(store, e.plane)
        assert held[2]["permission"]["outcome"] == "cancelled"
        assert _texts(held)[-1] == ("agent", "cancelled")
    finally:
        await e.stop()


async def test_idle_goes_to_sleep_and_the_run_ends(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path), idle=0.3)
    await e.turn(await e.ask("hello"))
    await asyncio.wait_for(e.task, 10)
    s = agents.session(e.plane)
    assert await store.read(nu.Dict.of(owner=s.owner, status=s.status)) == {
        "owner": "",
        "status": "asleep",
    }
    assert len(await entries(store, e.plane)) == 2


async def test_a_run_finding_a_live_owner_ends_at_once(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    first = await start(store, str(tmp_path))
    try:
        await first.status("idle")
        second = await start(store, str(tmp_path), plane=first.plane, owner="taken")
        await asyncio.wait_for(second.task, 5)
        assert await store.read(agents.session(first.plane).owner) == first.run
        assert await store.read(agents.session(first.plane).status) == "idle"
    finally:
        await first.stop()


async def test_a_stored_session_resumes(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    p = await _with_session(store, tmp_path, "old")
    e = await start(store, str(tmp_path), plane=p)
    try:
        await e.status("idle")
        assert await store.read(agents.session(p).session_id) == "old"
        assert await entries(store, p) == []
    finally:
        await e.stop()


async def test_a_stored_session_loads_and_drops_the_replay(store, tmp_path, monkeypatch):
    use_fake(monkeypatch, env={"FAKE_ACP_NO_RESUME": "1"})
    p = await _with_session(store, tmp_path, "old")
    e = await start(store, str(tmp_path), plane=p)
    try:
        await e.status("idle")
        assert await store.read(agents.session(p).session_id) == "old"
        await e.turn(await e.ask("hello"))
        await until(store, nu.Int(nu.Len(agents.trace(p).entries.keys())), lambda n: n == 2)
        assert _texts(await entries(store, p)) == [("user", "hello"), ("agent", "hello")]
    finally:
        await e.stop()


async def test_a_lost_session_starts_anew_with_a_notice(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    p = await _with_session(store, tmp_path, "gone")
    e = await start(store, str(tmp_path), plane=p)
    try:
        await e.status("idle")
        assert await store.read(agents.session(p).session_id) == "s1"
        await until(store, nu.Int(nu.Len(agents.trace(p).entries.keys())), lambda n: n == 1)
        assert _texts(await entries(store, p)) == [("notice", engine_module.LOST_CONTEXT)]
    finally:
        await e.stop()


async def test_a_restart_closes_what_a_dead_run_left_open(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    p = await _with_session(store, tmp_path, "old")
    trace = agents.trace(p)
    turn = "turn:q0"
    tool = {"tool_call_id": "x", "title": "Run", "kind": "execute", "status": "in_progress"}
    perm = {"request": 1, "tool_call_id": "x", "options": [], "answer": "", "outcome": ""}
    await store.do(
        trace.turns.set_item(turn, {"prompt": "q0", "started_at": 1})
        >> trace.entries.set_item("tool:x", {"kind": "tool", "turn": turn, "at": 1, "tool": tool})
        >> trace.entries.set_item(
            "perm:old-1", {"kind": "permission", "turn": turn, "at": 2, "permission": perm}
        )
    )
    e = await start(store, str(tmp_path), plane=p)
    try:
        await e.status("idle")
        ended = await until(store, trace.turns[turn].extract(), lambda t: "ended_at" in t)
        assert ended["error"] == "engine restarted"
        assert await store.read(trace.entries["tool:x"].tool["status"]) == "cancelled"
        assert await store.read(trace.entries["perm:old-1"].permission["outcome"]) == "expired"
    finally:
        await e.stop()


async def test_not_logged_in_lands_as_an_error_and_a_notice(store, tmp_path, monkeypatch):
    use_fake(monkeypatch, env={"FAKE_ACP_LOGGED_OUT": "1"})
    e = await start(store, str(tmp_path))
    with pytest.raises(nustd.acp.AcpError):
        await asyncio.wait_for(e.task, 10)
    s = agents.session(e.plane)
    assert await store.read(nu.Dict.of(status=s.status, owner=s.owner)) == {
        "status": "error",
        "owner": "",
    }
    (notice,) = await entries(store, e.plane)
    assert notice["kind"] == "notice"
    assert "not logged in" in notice["text"]


async def test_an_agent_that_cannot_start_lands_as_an_error(store, tmp_path, monkeypatch):
    use_fake(monkeypatch, command=[str(tmp_path / "no-npx")])
    e = await start(store, str(tmp_path))
    with pytest.raises(nustd.acp.AcpError):
        await asyncio.wait_for(e.task, 10)
    assert await store.read(agents.session(e.plane).status) == "error"
    (notice,) = await entries(store, e.plane)
    assert "could not start" in notice["text"]
    assert "npx" in notice["text"]


async def test_an_agent_dying_mid_turn_ends_the_turn_and_the_run(store, tmp_path, monkeypatch):
    use_fake(monkeypatch)
    e = await start(store, str(tmp_path))
    pid = await e.ask("die")
    with pytest.raises(nustd.acp.AcpError):
        await asyncio.wait_for(e.task, 10)
    turn = await store.read(agents.trace(e.plane).turns[f"turn:{pid}"].extract())
    assert "exited" in turn["error"] or "closed" in turn["error"]
    s = agents.session(e.plane)
    assert await store.read(nu.Dict.of(status=s.status, owner=s.owner)) == {
        "status": "error",
        "owner": "",
    }
    assert _texts(await entries(store, e.plane))[-1][0] == "notice"


async def _with_session(store, tmp_path, session_id: str) -> str:
    from _support.made import MADE

    p = await store.made(agents.add("fake", str(tmp_path), into=MADE))
    await store.do(agents.session(p).session_id.set(session_id))
    return p
