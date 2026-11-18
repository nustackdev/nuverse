"""The fold on its own: chunk batching, entry boundaries, tool patches, a turn's end, leftovers."""

from __future__ import annotations

import time

from nuverse.agents.fold import FLUSH_SECONDS, Fold


def _chunk(text: str, kind: str = "agent_message_chunk", **kw) -> dict:
    return {"session_update": kind, "content": {"type": "text", "text": text}, **kw}


def _ops(fold: Fold) -> list[tuple]:
    return [(op, key) for op, key, _ in fold.take()]


def test_chunks_grow_one_entry_and_wait_to_be_written():
    fold = Fold(nonce="n")
    fold.begin("q1", {"text": "hi"})
    fold.take()
    fold.step(_chunk("a"))
    assert fold.due() == 0.0  # a new entry is written at once
    fold.take()
    for piece in "bcd":
        fold.step(_chunk(piece))
    # Growing text waits out the flush interval, as one write.
    assert 0 < fold.due() <= FLUSH_SECONDS
    assert fold.due(time.monotonic() + FLUSH_SECONDS) == 0.0
    assert fold.take() == [("text", "agent:n-1", "abcd")]


def test_a_new_entry_starts_on_kind_message_id_or_another_entry():
    fold = Fold(nonce="n")
    fold.step(_chunk("a"))
    fold.step(_chunk("t", "agent_thought_chunk"))
    fold.step(_chunk("b", message_id="m2"))
    fold.step({"session_update": "tool_call", "tool_call_id": "x", "title": "Run"})
    fold.step(_chunk("c", message_id="m2"))
    fold.step({"session_update": "user_message_chunk", "content": {"type": "text", "text": "u"}})
    fold.step(
        {
            "session_update": "agent_message_chunk",
            "content": {"type": "image", "data": ""},
            "message_id": "m2",
        }
    )
    ops = fold.take()
    kinds = [v["kind"] for op, _, v in ops if op == "entry"]
    assert kinds == ["agent", "thought", "agent", "tool", "agent"]
    # Only text is drawn; anything else is a one-line placeholder.
    assert ops[-1] == ("text", "agent:n-4", "c\n[image]\n")


def test_tool_updates_patch_only_what_they_send():
    fold = Fold(nonce="n")
    fold.step({"session_update": "tool_call", "tool_call_id": "x", "title": "Edit", "kind": "edit"})
    fold.step({"session_update": "tool_call_update", "tool_call_id": "x", "status": "in_progress"})
    fold.step({"session_update": "tool_call_update", "tool_call_id": "x", "content": [{"a": 1}]})
    fold.step({"session_update": "tool_call_update", "tool_call_id": "y", "status": "completed"})
    ops = fold.take()
    tool = next(v for op, k, v in ops if op == "tool" and k == "tool:x")
    assert tool == {
        "tool_call_id": "x",
        "title": "Edit",
        "kind": "edit",
        "status": "in_progress",
        "content": [{"a": 1}],
    }
    # An unknown id is a create.
    assert ("entry", "tool:y") in [(op, k) for op, k, _ in ops]


def test_a_stop_closes_text_tools_and_permissions():
    fold = Fold(nonce="n")
    fold.begin("q1", {"text": "go"})
    fold.step({"session_update": "tool_call", "tool_call_id": "x", "title": "Run"})
    fold.step({"request_permission": 7, "tool_call": {"tool_call_id": "x"}, "options": []})
    assert fold.busy and fold.open_permissions() == [["perm:n-7", 7]]
    fold.step(_chunk("partial"))
    fold.take()
    fold.stop("cancelled")
    ops = {(op, k): v for op, k, v in fold.take()}
    assert ops[("tool", "tool:x")]["status"] == "cancelled"
    assert ops[("outcome", "perm:n-7")] == "cancelled"
    assert ops[("text", "agent:n-1")] == "partial"
    assert ops[("ended", "turn:q1")]["stop_reason"] == "cancelled"
    assert ops[("session", "status")] == "idle"
    assert not fold.busy


def test_leftovers_close_only_the_open_turn():
    fold = Fold(nonce="n")
    entries = [
        {"key": "perm:a", "entry": {"kind": "permission", "turn": "t2", "permission": {}}},
        {"key": "tool:b", "entry": {"kind": "tool", "turn": "t2", "tool": {"status": "pending"}}},
        {"key": "tool:c", "entry": {"kind": "tool", "turn": "t1", "tool": {"status": "pending"}}},
    ]
    fold.leftovers("t2", entries)
    ops = {(op, k): v for op, k, v in fold.take()}
    assert ops[("outcome", "perm:a")] == "expired"
    assert ops[("tool", "tool:b")]["status"] == "cancelled"
    assert ("tool", "tool:c") not in ops
    assert ops[("ended", "t2")]["error"] == "engine restarted"
