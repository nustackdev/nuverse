"""The turn and the loop, on a scripted model, the same on the mem store and the kv one."""

from __future__ import annotations

import pytest
from _support.scripted import KV, Mem, Scripted, block

import nu
from nuagent.core import Run, agent, seed, turn
from nuagent.protocol import OK, RUNTIME, prompt


TASK = "Log three things, then finish."


@pytest.fixture(params=["mem", "kv"])
def store(request, tmp_path):
    """A harness factory over one store kind: ``store(world=..., session=...)``."""

    def made(**seeded: dict) -> Mem | KV:
        if request.param == "mem":
            return Mem(**seeded)
        return KV(str(tmp_path / "run.db"), **seeded)

    return made


def one_turn(reply: str, h: Mem | KV, state: nu.Nu | None = None) -> Scripted:
    model = Scripted([reply])
    h.run(seed(h.store, TASK) >> turn(h.store, model.ask, state=state))
    return model


# --- turn --------------------------------------------------------------------


def test_a_turn_writes_every_slot(store):
    h = store()
    reply = h.program("World.log.set(['a'])")
    one_turn(reply, h)
    assert h.session["reply"] == reply
    assert h.session["program"].startswith("import nu")
    assert h.session["outcome"] == {"kind": OK, "value": "None"}


def test_a_turn_appends_the_reply_then_the_observation(store):
    h = store()
    reply = h.program("nu.Int(2) * 3")
    one_turn(reply, h)
    assert h.session["messages"] == [
        {"role": "user", "content": TASK},
        {"role": "assistant", "content": reply},
        {"role": "user", "content": "outcome: 6"},
    ]


def test_the_model_is_asked_with_the_conversation_so_far(store):
    h = store()
    model = one_turn(h.program("nu.Int(1)"), h)
    assert model.seen == [[{"role": "user", "content": TASK}]]


def test_the_program_runs_exactly_once_per_turn(store):
    h = store()
    one_turn(h.program("World.log.init([]) >> World.log.append('x')"), h)
    assert h.world["log"] == ["x"]


def test_the_state_line_shows_the_world_whole(store):
    h = store()
    items = [f"item {i}" for i in range(2000)]
    one_turn(h.program(f"World.log.set({items!r})"), h, state=h.log)
    assert h.session["messages"][-1]["content"] == f"outcome: None\nstate: {items!r}"


def test_a_failure_is_observed_not_raised(store):
    h = store()
    one_turn(h.program("nu.Div(1, 0)"), h)
    assert h.session["outcome"]["kind"] == RUNTIME
    assert h.session["messages"][-1]["content"] == (
        "outcome: RUNTIME FAILED: ZeroDivisionError: division by zero"
    )


# --- loop --------------------------------------------------------------------


def test_the_run_stops_on_the_turn_the_model_sets_done(store):
    h = store()
    model = Scripted([h.program("World.log.set(['a']) >> Run.done.set(True)"), "never asked"])
    h.run(agent(h.store, model, TASK))
    assert len(model.seen) == 1
    assert h.world == {"done": True, "log": ["a"]}


def test_the_run_goes_on_through_failures_until_done(store):
    h = store()
    model = Scripted(
        [
            "Let me think about it.",
            block("import nu\n\ndef out(:\n    pass"),
            h.program("nu.Div(1, 0)"),
            h.program("World.log.set(['a'])"),
            h.program("World.log.append('b') >> Run.done.set(True)"),
        ]
    )
    h.run(agent(h.store, model, TASK))
    assert len(model.seen) == 5
    assert h.world["log"] == ["a", "b"]
    observed = [m["content"] for m in h.session["messages"][2::2]]
    assert [text.split(":")[1].strip() for text in observed] == [
        "NO CODE BLOCK",
        "CONSTRUCTION FAILED",
        "RUNTIME FAILED",
        "None",
        "None",
    ]
    # Each turn writes its outcome whole: nothing of an earlier failure stays.
    assert h.session["outcome"] == {"kind": OK, "value": "None"}


def test_the_conversation_grows_turn_by_turn(store):
    h = store()
    replies = [h.program("nu.Int(1)"), h.program("nu.Int(2)"), h.program("Run.done.set(True)")]
    model = Scripted(replies)
    h.run(agent(h.store, model, TASK))
    assert h.session["messages"] == [
        {"role": "user", "content": TASK},
        {"role": "assistant", "content": replies[0]},
        {"role": "user", "content": "outcome: 1"},
        {"role": "assistant", "content": replies[1]},
        {"role": "user", "content": "outcome: 2"},
        {"role": "assistant", "content": replies[2]},
        {"role": "user", "content": "outcome: None"},
    ]
    assert [len(seen) for seen in model.seen] == [1, 3, 5]


def test_seed_resets_a_finished_world(store):
    h = store(world={"done": True})
    model = Scripted([h.program("Run.done.set(True)")])
    h.run(agent(h.store, model, TASK))
    assert len(model.seen) == 1


def test_the_backend_wraps_the_whole_run_once(store):
    h = store()
    model = Scripted([h.program("nu.Int(1)"), h.program("Run.done.set(True)")])
    term = agent(h.store, model, TASK)
    assert model.wraps == 1
    h.run(term)
    assert len(model.seen) == 2


def test_the_run_is_a_valid_term(store):
    nu.validate(nu.compile(agent(store().store, Scripted([]), TASK)))


def test_a_bound_run_ends_on_its_own(store):
    h = store()
    model = Scripted([h.program("World.log.set(['a'])"), h.program("Run.done.set(True)")])
    nu.run(h.store.bound(agent(h.store, model, prompt() + "\n\n" + TASK)))
    assert len(model.seen) == 2
    assert model.seen[0][0]["content"].startswith("# How you reply")


def test_run_is_one_untagged_bool():
    assert list(Run._slots) == ["done"]


async def test_the_run_is_the_same_on_the_async_runtime(store):
    h = store()
    model = Scripted([h.program("nu.Div(1, 0)"), h.program("Run.done.set(True)")])
    await nu.arun(h.store.bound(agent(h.store, model, TASK)))
    assert len(model.seen) == 2
    assert model.seen[1][-1]["content"].startswith("outcome: RUNTIME FAILED")
