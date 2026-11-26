"""The fold on its own: a turn's items into the trace, chunk batching, entry boundaries, tool patches, a turn's end, leftovers."""

from __future__ import annotations

from _support.agents import entries
from _support.made import MADE

import nu
from nuspace.places import inside
from nuverse import agents
from nuverse.agents import engine


def _chunk(text: str, kind: str = "agent_message_chunk", **kw) -> dict:
    return {"session_update": kind, "content": {"type": "text", "text": text}, **kw}


def _run(body: nu.Nu) -> nu.Nu:
    """``body`` in a run's memory, its keys minted ``<kind>:n-<i>``."""
    return nu.let(
        engine._Run,
        body,
        nonce="n",
        seq=0,
        last="",
        turn="",
        started=0,
        cancel_sent=False,
        perms=nu.Dict.create(),
        slept=False,
        agent="claude",
    )


async def _plane(store) -> str:
    return await store.made(agents.add("claude", "/srv/repo", into=MADE))


async def _turn(store, plane: str, items: list[dict]) -> dict[str, dict]:
    """A turn on prompt ``q1`` folding ``items``; every entry after it, by key."""
    turn = engine._begin(plane, nu.Str("q1"), nu.Str("go")) >> engine._folding(
        plane, nu.Iter(items)
    )
    await store.run(inside(_run(turn), plane=plane))
    return {e["key"]: e for e in await entries(store, plane)}


async def test_chunks_grow_one_entry_and_wait_to_be_written(store):
    p = await _plane(store)
    # The first chunk starts the entry, the next is written; the rest wait out the interval.
    held = await _turn(store, p, [_chunk(c) for c in "abcdefgh"])
    text = held["agent:n-1"]["text"]
    assert text.startswith("ab")
    assert text != "abcdefgh"
    # The turn's end writes what waited.
    p = await _plane(store)
    held = await _turn(store, p, [*map(_chunk, "abcdefgh"), {"stop_reason": "end_turn"}])
    assert held["agent:n-1"]["text"] == "abcdefgh"


async def test_a_new_entry_starts_on_kind_message_id_or_another_entry(store):
    p = await _plane(store)
    image = {
        "session_update": "agent_message_chunk",
        "content": {"type": "image", "data": ""},
        "message_id": "m2",
    }
    held = await _turn(
        store,
        p,
        [
            _chunk("a"),
            _chunk("t", "agent_thought_chunk"),
            _chunk("b", message_id="m2"),
            {"session_update": "tool_call", "tool_call_id": "x", "title": "Run"},
            _chunk("c", message_id="m2"),
            _chunk("u", "user_message_chunk"),
            image,
            {"stop_reason": "end_turn"},
        ],
    )
    assert [e["kind"] for e in held.values()] == [
        "user",
        "agent",
        "thought",
        "agent",
        "tool",
        "agent",
    ]
    # Only text is drawn; anything else is a one-line placeholder.
    assert held["agent:n-4"]["text"] == "c\n[image]\n"


async def test_tool_updates_patch_only_what_they_send(store):
    p = await _plane(store)
    held = await _turn(
        store,
        p,
        [
            {"session_update": "tool_call", "tool_call_id": "x", "title": "Edit", "kind": "edit"},
            {"session_update": "tool_call_update", "tool_call_id": "x", "status": "in_progress"},
            {"session_update": "tool_call_update", "tool_call_id": "x", "content": [{"a": 1}]},
            {"session_update": "tool_call_update", "tool_call_id": "y", "status": "completed"},
        ],
    )
    assert held["tool:x"]["tool"] == {
        "tool_call_id": "x",
        "title": "Edit",
        "kind": "edit",
        "status": "in_progress",
        "content": [{"a": 1}],
    }
    # An unknown id is a create.
    assert held["tool:y"]["tool"]["status"] == "completed"


async def test_a_stop_closes_text_tools_and_permissions(store):
    p = await _plane(store)
    held = await _turn(
        store,
        p,
        [
            {"session_update": "tool_call", "tool_call_id": "x", "title": "Run"},
            {"request_permission": 7, "tool_call": {"tool_call_id": "x"}, "options": []},
            _chunk("partial"),
            {"stop_reason": "cancelled"},
        ],
    )
    assert held["tool:x"]["tool"]["status"] == "cancelled"
    assert held["perm:n-7"]["permission"]["outcome"] == "cancelled"
    assert held["agent:n-1"]["text"] == "partial"
    turn = await store.read(agents.trace(p).turns["turn:q1"].extract())
    assert turn["stop_reason"] == "cancelled"
    assert await store.read(agents.session(p).status) == "idle"


async def test_leftovers_close_only_the_open_turn(store):
    p = await _plane(store)
    trace = agents.trace(p)
    await store.do(
        trace.turns.set_item("t1", {"prompt": "q0", "started_at": 1, "ended_at": 2})
        >> trace.turns.set_item("t2", {"prompt": "q1", "started_at": 3})
        >> trace.entries.set_item(
            "perm:a", {"kind": "permission", "turn": "t2", "permission": {"outcome": ""}}
        )
        >> trace.entries.set_item(
            "tool:b", {"kind": "tool", "turn": "t2", "tool": {"status": "pending"}}
        )
        >> trace.entries.set_item(
            "tool:c", {"kind": "tool", "turn": "t1", "tool": {"status": "pending"}}
        )
    )
    await store.run(inside(engine._close_leftovers(p), plane=p))
    held = {e["key"]: e for e in await entries(store, p)}
    assert held["perm:a"]["permission"]["outcome"] == "expired"
    assert held["tool:b"]["tool"]["status"] == "cancelled"
    assert held["tool:c"]["tool"]["status"] == "pending"
    assert (await store.read(trace.turns["t2"].extract()))["error"] == "engine restarted"
