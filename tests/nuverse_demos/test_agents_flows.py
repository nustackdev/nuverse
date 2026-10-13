"""nuverse-demos agents: the flows on a real store, the agents' side played by the test.

No supervisor runs here, so an agent a flow makes never starts: its page and
job are made and recorded, and the test writes into the agent's state what a
real one would (an answer, a status), the way the flow reads it.
"""

from __future__ import annotations

import asyncio

import nu
from nuspace import ops
from nuspace.shapes import Reroot, Space, reroot
from nustd.kv import Snapshot
from nuverse_demos.agents.flows import flow_source
from nuverse_demos.agents.state import FLOW, JOB, PAGE, Agent, Flow, made_by


async def _flow(store, kind: str, spec: dict, folder: str) -> asyncio.Task:
    await store.run(ops.add_plane("root", backend="async"))
    source = flow_source(kind, "root", folder, "Run 1", spec)
    await store.run(
        ops.add_plane("flow", backend="async", ui=False, made_by=FLOW)
        >> ops.add_cell("flow", source, cell_id="flow_main", name="flow")
    )
    load = Space.cells["flow_main"].prog.load(
        scope={"plane": "flow", "cell": "flow_main"}, rewrite=Reroot("flow", "flow_main")
    )
    term = nu.Frame(
        ops.Here, await store.run(Snapshot(load, scope=Space)), plane="flow", cell="flow_main"
    )
    return asyncio.create_task(nu.arun(term, store.ctx))


def _flow_state(ref: nu.Nu) -> nu.Nu:
    return reroot(ref, "flow", "flow_main")


async def _until(check, timeout: float = 10.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.05)


async def _agents(store) -> dict:
    return dict(await store.read(nu.dict(_flow_state(Flow.agents.fallback({})))))


async def _answer(store, job: str, text: str, *, count: int = 1) -> None:
    """What a real agent writes when it finishes a turn."""
    state = Agent.answer.set(text) >> Agent.answered.set(count) >> Agent.status.set("idle")
    await store.run(ops.atomic_state(reroot(state, job, f"{job}_main")))


async def test_fanout_asks_every_builder_then_the_judge(store, tmp_path):
    task = await _flow(
        store, "fanout", {"brief": "make a page", "n": 2, "tasks": []}, str(tmp_path)
    )

    async def asked(*roles: str) -> bool:
        return set(roles) <= set(await _agents(store))

    await _until(lambda: asked("builder-1", "builder-2"))
    agents = await _agents(store)
    assert "judge" not in agents
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    pages = await store.read(nu.dict(_flow_state(Flow.pages)))
    for role, job in agents.items():
        assert rows[job]["props"]["made_by"] == JOB
        assert rows[pages[role]]["props"]["made_by"] == PAGE
        assert pages[role] in await store.read(ops.children("root"))
    assert (tmp_path / "builder-1").is_dir()
    assert await store.read(_flow_state(Flow.phase)) == "building"

    await _answer(store, agents["builder-1"], "built one")
    await asyncio.sleep(0.3)
    assert "judge" not in await _agents(store)
    await _answer(store, agents["builder-2"], "built two")
    await _until(lambda: asked("judge"))
    assert await store.read(_flow_state(Flow.phase)) == "judging"

    judge = (await _agents(store))["judge"]
    spec = await store.read(reroot(Agent.spec, judge, f"{judge}_main").fallback({}))
    assert spec == {}  # written by its own job, which never starts here
    judged = await store.read(ops.prog(nu.Str(judge) + "_main"))
    assert "builder-1, builder-2" in judged and f"'cwd': {str(tmp_path)!r}" in judged
    await _answer(store, judge, "Winner: builder-2\nit is better")
    await asyncio.wait_for(task, 10)
    assert await store.read(_flow_state(Flow.status)) == "done"
    assert await store.read(_flow_state(Flow.outcome)) == "Winner: builder-2\nit is better"


async def test_a_chain_hands_each_answer_to_the_next(store, tmp_path):
    task = await _flow(store, "chain", {"brief": "a page", "n": 1, "tasks": []}, str(tmp_path))
    jobs: dict = {}
    for role, said in (
        ("researcher", "the plan"),
        ("builder", "built it"),
        ("reviewer", "ship it"),
    ):

        async def made(role: str = role) -> bool:
            return role in await _agents(store)

        await _until(made)
        jobs = await _agents(store)
        await _answer(store, jobs[role], said)
    await asyncio.wait_for(task, 10)
    assert set(jobs) == {"researcher", "builder", "reviewer"}
    assert await store.read(nu.list(_flow_state(Flow.roles))) == [
        "researcher",
        "builder",
        "reviewer",
    ]
    from nuverse_demos.agents.orchestrate import flow_view

    view = await store.read(flow_view("flow"))
    assert [a[0] for a in view["agents"]] == ["researcher", "builder", "reviewer"]
    assert view["status"] == "done"
    assert await store.read(_flow_state(Flow.outcome)) == "ship it"
    # Each brief carries the answer before it, baked into the agent's job, and they share the flow's folder.
    builder = await store.read(ops.prog(nu.Str(jobs["builder"]) + "_main"))
    reviewer = await store.read(ops.prog(nu.Str(jobs["reviewer"]) + "_main"))
    assert "the plan" in builder and "built it" in reviewer
    assert f"'cwd': {str(tmp_path)!r}" in builder


async def test_a_board_pulls_tasks_into_free_workers(store, tmp_path):
    spec = {"brief": "", "n": 2, "tasks": ["one", "two", "three"]}
    task = await _flow(store, "tasks", spec, str(tmp_path))

    async def board() -> list:
        return list(await store.read(_flow_state(Flow.tasks.fallback([]))))

    async def doing(n: int) -> bool:
        return sum(t["status"] == "doing" for t in await board()) == n

    async def made() -> bool:
        return await doing(2) and len(await _agents(store)) == 2

    await _until(made)
    tasks = await board()
    assert [(t["task"], t["by"]) for t in tasks] == [
        ("one", "worker-1"),
        ("two", "worker-2"),
        ("three", ""),
    ]
    workers = await _agents(store)

    # worker-1 finishes: its task closes, and it takes the third.
    await _answer(store, workers["worker-1"], "did one")

    async def third() -> bool:
        return (await board())[2]["by"] == "worker-1"

    await _until(third)
    tasks = await board()
    assert tasks[0]["status"] == "done" and tasks[0]["answer"] == "did one"
    # Told, not made again: its inbox holds the task.
    inbox = await store.read(
        nu.list(reroot(Agent.inbox, workers["worker-1"], f"{workers['worker-1']}_main"))
    )
    assert inbox == ["three"]
    assert await _agents(store) == workers
    assert "1 of 3 done" in await store.read(_flow_state(Flow.phase))
    task.cancel()
    for job in workers.values():
        assert await store.read(made_by(nu.Str(job))) == JOB


async def test_a_launch_with_a_fixed_id_makes_its_agent_once(store, tmp_path):
    from nuverse_demos.agents.launch import launch

    await store.run(ops.add_plane("root", backend="async"))
    spec = nu.Dict.of(name="a", cwd=str(tmp_path), model="m", mode="plan", brief="b")
    for _ in range(2):
        await store.run(launch("root", spec, plane_id="p_fixed"))
    assert await store.read(ops.children("root")) == ["p_fixed"]
    assert await store.read(ops.children("p_fixed")) == ["p_fixed_run"]
    assert await store.read(ops.cells("p_fixed_run")) == ["p_fixed_run_main"]


async def test_a_task_added_to_a_board_lands_open_at_its_end(store):
    from nuverse_demos.agents.orchestrate import add_task

    await store.run(
        ops.add_plane("flow", backend="async")
        >> ops.add_cell("flow", "def out(c):\n    return None\n", cell_id="flow_main")
    )
    await store.run(add_task("flow", "first"))
    await store.run(add_task("flow", "second"))
    tasks = await store.read(_flow_state(Flow.tasks))
    assert [(t["task"], t["status"]) for t in tasks] == [("first", "open"), ("second", "open")]
