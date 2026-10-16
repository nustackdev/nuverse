"""The turn and the loop, on a scripted model and the mem store."""

from __future__ import annotations

from _support.scripted import Mem, Scripted, block, program

import nu
from nuagent.core import Run, agent, seed, turn
from nuagent.presets.store.mem import MemSession, bound
from nuagent.protocol import OK, RUNTIME, prompt


TASK = "Log three things, then finish."


def one_turn(reply: str, mem: Mem, state: nu.Nu | None = None) -> Scripted:
    model = Scripted([reply])
    mem.run(seed(MemSession, TASK) >> turn(MemSession, model.ask, state=state))
    return model


# --- turn --------------------------------------------------------------------


def test_a_turn_writes_every_slot():
    mem = Mem()
    reply = program("World.log.set(['a'])")
    one_turn(reply, mem)
    assert mem.session["reply"] == reply
    assert mem.session["program"].startswith("import nu")
    assert mem.session["outcome"] == {"kind": OK, "value": "None"}


def test_a_turn_appends_the_reply_then_the_observation():
    mem = Mem()
    reply = program("nu.Int(2) * 3")
    one_turn(reply, mem)
    assert mem.session["messages"] == [
        {"role": "user", "content": TASK},
        {"role": "assistant", "content": reply},
        {"role": "user", "content": "outcome: 6"},
    ]


def test_the_model_is_asked_with_the_conversation_so_far():
    mem = Mem()
    model = one_turn(program("nu.Int(1)"), mem)
    assert model.seen == [[{"role": "user", "content": TASK}]]


def test_the_program_runs_exactly_once_per_turn():
    mem = Mem()
    one_turn(program("World.log.init([]) >> World.log.append('x')"), mem)
    assert mem.world["log"] == ["x"]


def test_the_state_line_shows_the_world_whole():
    mem = Mem()
    world = nu.ListRef[str]("log")
    items = [f"item {i}" for i in range(2000)]
    one_turn(program(f"World.log.set({items!r})"), mem, state=world)
    assert mem.session["messages"][-1]["content"] == f"outcome: None\nstate: {items!r}"


def test_a_failure_is_observed_not_raised():
    mem = Mem()
    one_turn(program("nu.Div(1, 0)"), mem)
    assert mem.session["outcome"]["kind"] == RUNTIME
    assert mem.session["messages"][-1]["content"] == (
        "outcome: RUNTIME FAILED: ZeroDivisionError: division by zero"
    )


# --- loop --------------------------------------------------------------------


def test_the_run_stops_on_the_turn_the_model_sets_done():
    mem = Mem()
    model = Scripted([program("World.log.set(['a']) >> Run.done.set(True)"), "never asked"])
    mem.run(agent(MemSession, model, TASK))
    assert len(model.seen) == 1
    assert mem.world == {"done": True, "log": ["a"]}


def test_the_run_goes_on_through_failures_until_done():
    mem = Mem()
    model = Scripted(
        [
            "Let me think about it.",
            block("import nu\n\ndef out(:\n    pass"),
            program("nu.Div(1, 0)"),
            program("World.log.set(['a'])"),
            program("World.log.append('b') >> Run.done.set(True)"),
        ]
    )
    mem.run(agent(MemSession, model, TASK))
    assert len(model.seen) == 5
    assert mem.world["log"] == ["a", "b"]
    observed = [m["content"] for m in mem.session["messages"][2::2]]
    assert [text.split(":")[1].strip() for text in observed] == [
        "NO CODE BLOCK",
        "CONSTRUCTION FAILED",
        "RUNTIME FAILED",
        "None",
        "None",
    ]
    # Each turn writes its outcome whole: nothing of an earlier failure stays.
    assert mem.session["outcome"] == {"kind": OK, "value": "None"}


def test_the_conversation_grows_turn_by_turn():
    mem = Mem()
    replies = [program("nu.Int(1)"), program("nu.Int(2)"), program("Run.done.set(True)")]
    model = Scripted(replies)
    mem.run(agent(MemSession, model, TASK))
    assert mem.session["messages"] == [
        {"role": "user", "content": TASK},
        {"role": "assistant", "content": replies[0]},
        {"role": "user", "content": "outcome: 1"},
        {"role": "assistant", "content": replies[1]},
        {"role": "user", "content": "outcome: 2"},
        {"role": "assistant", "content": replies[2]},
        {"role": "user", "content": "outcome: None"},
    ]
    assert [len(seen) for seen in model.seen] == [1, 3, 5]


def test_seed_resets_a_finished_world():
    mem = Mem(world={"done": True})
    model = Scripted([program("Run.done.set(True)")])
    mem.run(agent(MemSession, model, TASK))
    assert len(model.seen) == 1


def test_the_backend_wraps_the_whole_run_once():
    model = Scripted([program("nu.Int(1)"), program("Run.done.set(True)")])
    term = agent(MemSession, model, TASK)
    assert model.wraps == 1
    Mem().run(term)
    assert len(model.seen) == 2


def test_the_run_is_a_valid_term():
    nu.validate(nu.compile(agent(MemSession, Scripted([]), TASK)))


def test_a_mem_bound_run_ends_on_its_own():
    model = Scripted([program("World.log.set(['a'])"), program("Run.done.set(True)")])
    nu.run(bound(agent(MemSession, model, prompt() + "\n\n" + TASK)))
    assert len(model.seen) == 2
    assert model.seen[0][0]["content"].startswith("# How you reply")


def test_run_is_one_untagged_bool():
    assert list(Run._slots) == ["done"]


async def test_the_run_is_the_same_on_the_async_runtime():
    model = Scripted([program("nu.Div(1, 0)"), program("Run.done.set(True)")])
    await nu.arun(bound(agent(MemSession, model, TASK)))
    assert len(model.seen) == 2
    assert model.seen[1][-1]["content"].startswith("outcome: RUNTIME FAILED")
