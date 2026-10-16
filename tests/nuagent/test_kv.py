"""The kv store: where its brackets sit, what outlives a run, one sqlite file for everything."""

from __future__ import annotations

import pytest
from _support.scripted import KV, Scripted, _Next, program

import nu
import nu.prog
import nustd.kv
from nuagent.core import agent
from nuagent.core.program import Shown
from nuagent.presets.store.kv import KVRun, KVSession, KVStore
from nuagent.presets.store.mem import MemSession, MemStore


TASK = "Log two things, then finish."
KV_REPLIES = [
    program("World.log.set(['a'])", "nustd.kv"),
    program("World.log.append('b') >> Run.done.set(True)", "nustd.kv"),
]

#: What may not run inside a bracket: the model's answer, and the program's build and run.
SLOW = (_Next, nu.prog.Eval, nu.LoadNu)


#: The two brackets ``Atomic`` picks from.
BRACKETS = (nustd.kv.Snapshot, nustd.kv.Transaction)


def _nodes(term: nu.Nu, kinds: tuple[type, ...] | type) -> list[nu.Nu]:
    return [n for n in nu.tree.preorder(term) if isinstance(n, kinds)]


def _brackets(term: nu.Nu) -> list[nu.Nu]:
    return _nodes(term, BRACKETS)


# --- where the brackets sit --------------------------------------------------


def test_no_bracket_holds_the_ask_or_the_program():
    run = agent(KVStore(), Scripted([]), TASK)
    brackets = _brackets(run)
    assert brackets
    for bracket in brackets:
        assert not _nodes(bracket, SLOW), bracket
    assert all(_nodes(run, kind) for kind in SLOW)


def test_every_session_step_and_world_read_is_bracketed():
    scopes = {b.scope for b in _brackets(agent(KVStore(), Scripted([]), TASK))}
    assert scopes == {KVSession, None}


def test_the_mem_store_places_no_brackets():
    assert _brackets(agent(MemStore(), Scripted([]), TASK)) == []


def test_the_program_is_landed_by_the_stores_rewrite():
    (load,) = _nodes(agent(KVStore(), Scripted([]), TASK), nu.LoadNu)
    shown = load._payload["rewrite"]
    assert isinstance(shown, Shown)
    assert shown.landing == KVStore.rewrite


def test_a_built_program_gets_the_bracket_its_writes_call_for():
    shown = Shown(KVStore.rewrite)
    assert isinstance(shown(KVRun.done.set(True)), nustd.kv.Transaction)
    assert isinstance(shown(KVRun.done), nustd.kv.Snapshot)


# --- one file, durable -------------------------------------------------------


@pytest.mark.parametrize("runtime", ["sync", "async"])
async def test_one_sqlite_file_holds_the_session_and_the_world(tmp_path, runtime):
    h = KV(str(tmp_path / "one.db"))
    model = Scripted(list(KV_REPLIES))
    term = h.store.bound(agent(h.store, model, TASK))
    if runtime == "sync":
        nu.run(term)
    else:
        await nu.arun(term)
    h.run(nu.Int(0))
    assert len(model.seen) == 2
    assert h.world == {"done": True, "log": ["a", "b"]}


def test_the_run_outlives_the_process(tmp_path):
    path = str(tmp_path / "run.db")
    first = KV(path)
    first.run(agent(first.store, Scripted(list(KV_REPLIES)), TASK))
    reopened = KV(path)
    reopened.run(nu.Int(0))
    assert reopened.session["messages"][0] == {"role": "user", "content": TASK}
    assert reopened.session["messages"][1:] == [
        {"role": "assistant", "content": KV_REPLIES[0]},
        {"role": "user", "content": "outcome: None"},
        {"role": "assistant", "content": KV_REPLIES[1]},
        {"role": "user", "content": "outcome: None"},
    ]
    assert reopened.session["outcome"] == {"kind": "ok", "value": "None"}
    assert reopened.session["program"].startswith("import nu")


def test_a_second_run_on_the_same_file_reseeds(tmp_path):
    path = str(tmp_path / "run.db")
    KV(path).run(agent(KVStore.sqlite(path), Scripted(list(KV_REPLIES)), TASK))
    again = KV(path)
    model = Scripted([program("World.log.append('c') >> Run.done.set(True)", "nustd.kv")])
    again.run(agent(again.store, model, "Again."))
    assert model.seen == [[{"role": "user", "content": "Again."}]]
    assert again.world == {"done": True, "log": ["a", "b", "c"]}
    assert len(again.session["messages"]) == 3


def test_a_kv_yield_reaches_the_model_as_what_it_holds(tmp_path):
    h = KV(str(tmp_path / "run.db"))
    model = Scripted(
        [
            program("World.log.set(['a', 'b'])", "nustd.kv"),
            program("World.log", "nustd.kv"),
            program("Run.done.set(True)", "nustd.kv"),
        ]
    )
    h.run(agent(h.store, model, TASK, state=h.log))
    observed = [m["content"] for m in h.session["messages"][2::2]]
    assert observed[0] == "outcome: None\nstate: ['a', 'b']"
    assert observed[1] == "outcome: ['a', 'b']\nstate: ['a', 'b']"


def test_mem_and_kv_sessions_have_the_same_slots():
    assert list(KVSession._slots) == list(MemSession._slots)
    assert list(KVRun._slots) == ["done"]
