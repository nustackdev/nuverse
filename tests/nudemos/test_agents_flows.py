"""nudemos agents: the flows on a real store, the agents' side played by the test.

No supervisor runs here, so an agent a flow makes never starts: its page and
job are made and recorded, and the test writes into the agent's state what a
real one would (an answer, a status), the way the flow reads it.
"""

from __future__ import annotations

import asyncio

import nu
import nuspace
from nudemos import headless
from nudemos.agents.flows import flow_source
from nudemos.agents.state import (
    FLOW_CELL,
    FLOW_JOB,
    JOB,
    PAGE,
    RUN_CELL,
    agent,
    agents_at,
    flow_of,
    page_at,
    spec_of,
)
from nuspace import Space
from nuspace.places import inside
from nuspace.system import supervisor


#: The plane standing in for the Agents plane: the agents' pages go under it.
AGENTS = "agents"


async def _flow(store, kind: str, spec: dict, folder: str) -> asyncio.Task:
    await store.do(nuspace.plane.add(AGENTS, backend="async"))
    source = flow_source(kind, AGENTS, folder, "Run 1", spec)
    await store.run(
        headless.make(
            "flow",
            parent="root",
            name="flow",
            backend="async",
            spec=FLOW_JOB,
            cells=[(FLOW_CELL, source)],
        )
    )
    cell = await store.read(headless.cell_of("flow", FLOW_CELL))
    load = Space.cells[cell].prog.load(scope={"plane": "flow", "cell": cell})
    term = inside(await store.read(load), plane="flow", cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx))


#: The flow's own state, as the test reads it.
FLOW = flow_of("flow")


async def _until(check, timeout: float = 10.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.05)


async def _agents(store) -> dict:
    # Polled from before the flow begins, so before its agents exist.
    agents = FLOW.agents
    return dict(await store.read(nu.If(agents.exists(), nu.dict(agents), {})))


async def _answer(store, job: str, text: str, *, count: int = 1) -> None:
    """What a real agent writes when it finishes a turn."""
    a = agent(job)
    await store.do(a.answer.set(text) >> a.answered.set(count) >> a.status.set("idle"))


async def _children(store, plane: str) -> list:
    return await store.read(Space.planes[plane].children.keys(limit=50))


async def test_fanout_asks_every_builder_then_the_judge(store, tmp_path):
    task = await _flow(
        store, "fanout", {"brief": "make a page", "n": 2, "tasks": []}, str(tmp_path)
    )

    async def asked(*roles: str) -> bool:
        return set(roles) <= set(await _agents(store))

    await _until(lambda: asked("builder-1", "builder-2"))
    agents = await _agents(store)
    assert "judge" not in agents
    pages = await store.read(nu.dict(FLOW.pages))
    for role, job in agents.items():
        assert await store.read(spec_of(job)) == JOB
        assert await store.read(spec_of(pages[role])) == PAGE
        assert pages[role] in await _children(store, AGENTS)
        # Who finds whom: the page its job, the Agents plane its agents.
        assert await store.read(page_at(pages[role]).job) == job
        assert await store.read(agents_at(AGENTS).jobs[pages[role]]) == job
    assert (tmp_path / "builder-1").is_dir()
    assert await store.read(FLOW.phase) == "building"

    await _answer(store, agents["builder-1"], "built one")
    await asyncio.sleep(0.3)
    assert "judge" not in await _agents(store)
    await _answer(store, agents["builder-2"], "built two")
    await _until(lambda: asked("judge"))
    assert await store.read(FLOW.phase) == "judging"

    judge = (await _agents(store))["judge"]
    spec = await store.read(agent(judge).spec.fallback({}))
    assert spec == {}  # written by its own job, which never starts here
    judged = await store.read(Space.cells[headless.cell_of(judge, RUN_CELL)].prog)
    assert "builder-1, builder-2" in judged and f"'cwd': {str(tmp_path)!r}" in judged
    await _answer(store, judge, "Winner: builder-2\nit is better")
    await asyncio.wait_for(task, 10)
    assert await store.read(FLOW.status) == "done"
    assert await store.read(FLOW.outcome) == "Winner: builder-2\nit is better"


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
    assert await store.read(nu.list(FLOW.roles)) == [
        "researcher",
        "builder",
        "reviewer",
    ]
    from nudemos.agents.orchestrate import flow_view

    view = await store.read(flow_view("flow"))
    assert [a[0] for a in view["agents"]] == ["researcher", "builder", "reviewer"]
    assert view["status"] == "done"
    assert await store.read(FLOW.outcome) == "ship it"
    # Each brief carries the answer before it, baked into the agent's job, and they share the flow's folder.
    builder = await store.read(Space.cells[headless.cell_of(jobs["builder"], RUN_CELL)].prog)
    reviewer = await store.read(Space.cells[headless.cell_of(jobs["reviewer"], RUN_CELL)].prog)
    assert "the plan" in builder and "built it" in reviewer
    assert f"'cwd': {str(tmp_path)!r}" in builder


async def test_a_board_pulls_tasks_into_free_workers(store, tmp_path):
    spec = {"brief": "", "n": 2, "tasks": ["one", "two", "three"]}
    task = await _flow(store, "tasks", spec, str(tmp_path))

    async def board() -> list:
        return list(await store.read(FLOW.tasks.fallback([])))

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
    inbox = await store.read(nu.list(agent(workers["worker-1"]).inbox))
    assert inbox == ["three"]
    assert await _agents(store) == workers
    assert "1 of 3 done" in await store.read(FLOW.phase)
    task.cancel()
    for job in workers.values():
        assert await store.read(spec_of(job)) == JOB


async def test_a_launch_with_a_fixed_id_makes_its_agent_once(store, tmp_path):
    from nudemos.agents.launch import launch

    await store.do(nuspace.plane.add(AGENTS, backend="async"))
    spec = nu.Dict.of(name="a", cwd=str(tmp_path), model="m", mode="plan", brief="b")
    for _ in range(2):
        await store.run(launch(AGENTS, spec, plane_id="p_fixed"))
    assert await _children(store, AGENTS) == ["p_fixed"]
    # The job's id is minted, kept on the page, and found again by the second launch.
    run = await store.read(page_at("p_fixed").job)
    assert await _children(store, "p_fixed") == [run]
    cell = await store.read(headless.cell_of(run, RUN_CELL))
    assert await store.read(Space.planes[run].cells.keys(limit=10)) == [cell]
    assert await store.read(agents_at(AGENTS).jobs.extract()) == {"p_fixed": run}
    # Under the supervisor, which starts it: kept there on the second launch.
    held = supervisor.supervised()[run]
    assert await store.read(held.policy) == supervisor.ON_FAILURE


async def test_a_task_added_to_a_board_lands_open_at_its_end(store):
    from nudemos.agents.orchestrate import add_task

    await store.run(
        headless.make(
            "flow",
            parent="root",
            name="flow",
            backend="async",
            spec=FLOW_JOB,
            cells=[(FLOW_CELL, "def out(c):\n    return None\n")],
        )
    )
    await store.run(add_task("flow", "first"))
    await store.run(add_task("flow", "second"))
    tasks = await store.read(FLOW.tasks)
    assert [(t["task"], t["status"]) for t in tasks] == [("first", "open"), ("second", "open")]
