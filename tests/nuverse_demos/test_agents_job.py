"""nuverse-demos agents: one agent's job loop on a real store, against a fake Claude Code.

No test here starts ``claude``. The SDK symbols the cc fabric calls are
swapped for a fake process that answers each prompt with a little turn: a
text block, a tool call, its result and the run's accounting. A prompt with
``slow`` in it says its first block and then hangs, for a stop to cut.
"""

from __future__ import annotations

import asyncio

import pytest


pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

import nu
from nuspace import ops
from nuspace.shapes import Reroot, Space, reroot
from nustd.cc import fabric
from nustd.kv import Snapshot
from nuverse_demos.agents.job import CARRY, job_source
from nuverse_demos.agents.state import JOB, Agent
from nuverse_demos.agents.views import events_of


SPEC = {
    "name": "tester",
    "cwd": "/tmp",
    "model": "fake",
    "mode": "acceptEdits",
    "brief": "build it",
}


class Claude:
    """The CLI as far as these tests need it: processes, prompts, transcripts by id."""

    def __init__(self) -> None:
        self.clients: list[FakeClient] = []
        self.transcripts: dict[str, list[str]] = {}

    def info(self, sid: str, directory: str | None = None) -> object | None:
        del directory
        return object() if sid in self.transcripts else None

    def prompts(self) -> list[str]:
        return [p for c in self.clients for p in c.prompts]


class FakeClient:
    def __init__(self, claude: Claude, options: object) -> None:
        self.claude, self.options = claude, options
        self.sid = options.session_id or options.resume
        self.prompts: list[str] = []
        self.disconnected = False
        claude.clients.append(self)

    async def connect(self) -> None:
        pass

    async def query(self, prompt: str) -> None:
        self.prompts.append(prompt)
        self.claude.transcripts.setdefault(self.sid, []).append(prompt)

    async def receive_response(self):
        prompt = self.prompts[-1]
        yield SystemMessage(subtype="init", data={"session_id": self.sid, "model": "fake"})
        yield AssistantMessage(content=[TextBlock(text=f"on it: {prompt}")], model="fake")
        if "slow" in prompt:
            await asyncio.sleep(60)
        yield AssistantMessage(
            content=[
                ToolUseBlock(id=f"t{len(self.prompts)}", name="Bash", input={"command": "ls"})
            ],
            model="fake",
        )
        yield UserMessage(
            content=[ToolResultBlock(tool_use_id=f"t{len(self.prompts)}", content="a\nb")]
        )
        yield ResultMessage(
            subtype="success",
            duration_ms=1500,
            duration_api_ms=1000,
            is_error=False,
            num_turns=2,
            session_id=self.sid,
            result=f"did: {prompt}",
            total_cost_usd=0.25,
            usage={"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 20},
        )

    async def disconnect(self) -> None:
        self.disconnected = True


@pytest.fixture
def claude(monkeypatch: pytest.MonkeyPatch) -> Claude:
    world = Claude()
    monkeypatch.setattr(fabric, "ClaudeSDKClient", lambda options: FakeClient(world, options))
    monkeypatch.setattr(fabric, "get_session_info", world.info)
    return world


async def _job(store, idle: float, **spec: object) -> str:
    source = job_source({**SPEC, **spec}, idle=idle)
    await store.run(
        ops.add_plane("job", backend="mp", ui=False, made_by=JOB)
        >> ops.add_cell("job", source, cell_id="job_main", name="run")
    )
    return "job_main"


async def _start(store, cell: str) -> asyncio.Task:
    load = Space.cells[cell].prog.load(
        scope={"plane": "job", "cell": cell}, rewrite=Reroot("job", cell)
    )
    term = nu.Frame(ops.Here, await store.run(Snapshot(load, scope=Space)), plane="job", cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx))


async def _log(store) -> list[dict]:
    return events_of(await store.read(nu.list(_state(Agent.log))))


def _state(ref: nu.Nu) -> nu.Nu:
    return reroot(ref, "job", "job_main")


async def _until(store, ref: nu.Nu, check, timeout: float = 10.0) -> object:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        value = await store.read(_state(ref))
        if check(value):
            return value
        assert asyncio.get_running_loop().time() < deadline, f"timed out at {value!r}"
        await asyncio.sleep(0.05)


async def test_the_brief_is_the_first_turn_and_every_event_lands(store, claude):
    cell = await _job(store, idle=0.3)
    await asyncio.wait_for(await _start(store, cell), 10)
    assert await store.read(_state(Agent.status)) == "idle"
    log = await _log(store)
    assert [e["type"] for e in log] == ["user", "init", "text", "tool_use", "tool_result", "result"]
    assert log[0]["text"] == "build it"
    assert await store.read(_state(Agent.n)) == len(log)
    assert await store.read(_state(Agent.answer)) == "did: build it"
    assert await store.read(_state(Agent.answered)) == 1
    assert await store.read(_state(Agent.turns)) == 2
    assert await store.read(_state(Agent.calls)) == 1
    assert await store.read(_state(Agent.tokens_in)) == 100
    assert await store.read(_state(Agent.tokens_out)) == 20
    assert await store.read(_state(Agent.cost)) == 0.25
    assert await store.read(_state(Agent.spec)) == SPEC
    (client,) = claude.clients
    assert client.options.session_id == await store.read(_state(Agent.sid))
    assert client.options.model == "fake"
    assert client.disconnected


async def test_saying_something_is_the_next_turn_on_the_same_process(store, claude):
    cell = await _job(store, idle=30.0)
    task = await _start(store, cell)
    await _until(store, Agent.answered.fallback(0), lambda n: n == 1)
    await store.run(ops.atomic_state(_state(Agent.inbox.append("now add a footer"))))
    await _until(store, Agent.answered.fallback(0), lambda n: n == 2)
    assert await store.read(_state(Agent.answer)) == "did: now add a footer"
    assert await store.read(_state(Agent.prompts)) == 2
    (client,) = claude.clients
    assert client.prompts == ["build it", "now add a footer"]
    await store.run(ops.atomic_state(_state(Agent.stop.set(True))))
    await asyncio.wait_for(task, 10)
    assert await store.read(_state(Agent.status)) == "stopped"


async def test_a_stop_cuts_the_turn_and_a_resume_carries_it_on(store, claude):
    cell = await _job(store, idle=0.3, brief="a slow one")
    task = await _start(store, cell)
    await _until(store, Agent.n.fallback(0), lambda n: n >= 3)
    assert await store.read(_state(Agent.status)) == "working"
    await store.run(ops.atomic_state(_state(Agent.stop.set(True))))
    await asyncio.wait_for(task, 10)
    assert await store.read(_state(Agent.status)) == "stopped"
    assert await store.read(_state(Agent.cut)) is True
    (cut,) = claude.clients
    assert cut.disconnected

    # Started again while stopped: it ends at once.
    await asyncio.wait_for(await _start(store, cell), 10)
    assert len(claude.clients) == 1

    # Resumed: the same conversation, the cut turn carried on first.
    await store.run(ops.atomic_state(_state(Agent.stop.set(False))))
    await asyncio.wait_for(await _start(store, cell), 10)
    _, resumed = claude.clients
    assert resumed.options.resume == cut.sid
    assert resumed.prompts == [CARRY]
    assert await store.read(_state(Agent.cut)) is False
    assert await store.read(_state(Agent.answer)) == f"did: {CARRY}"


async def test_a_failed_turn_is_logged_and_the_agent_goes_on(store, claude, monkeypatch):
    async def broken(self, prompt):
        msg = "the api fell over"
        raise RuntimeError(msg)

    monkeypatch.setattr(FakeClient, "query", broken)
    cell = await _job(store, idle=0.3)
    await asyncio.wait_for(await _start(store, cell), 10)
    log = await _log(store)
    assert [e["type"] for e in log] == ["user", "error"]
    assert "the api fell over" in await store.read(_state(Agent.error))
    assert await store.read(_state(Agent.answered)) == 1
    assert await store.read(_state(Agent.status)) == "idle"
