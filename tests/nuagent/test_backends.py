"""The backends on fakes: llm sends the whole conversation, cc the newest message in one session.

No network and no ``claude``. The llm fake stands in for the http calls of
``LLMFabric``; the cc fake is the CLI as far as a session needs it:
transcripts by id, and its two refusals (``--session-id`` on an id that has a
transcript, ``--resume`` on one that has none).
"""

from __future__ import annotations

import subprocess
import sys
import uuid

import pytest
from _support.scripted import Mem, program

import nu
from nuagent.core import agent
from nuagent.presets.store.kv import KVStore
from nuagent.presets.store.mem import MemSession, MemStore


claude_agent_sdk = pytest.importorskip("claude_agent_sdk")
pytest.importorskip("httpx")

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock  # noqa: E402

from nuagent.presets.backends.cc import REPLAY, ClaudeCode, flattened  # noqa: E402
from nuagent.presets.backends.llm import LLM  # noqa: E402
from nustd.cc import fabric as cc_fabric  # noqa: E402
from nustd.llm import LLMFabric  # noqa: E402


TASK = "Log two things, then finish."
STORE = MemStore()
REPLIES = [program("World.log.set(['a'])"), program("World.log.append('b') >> Run.done.set(True)")]


# --- llm ---------------------------------------------------------------------


class _Endpoint:
    """The chat endpoint: one scripted reply per call, and every body it was sent."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.sent: list[list[dict]] = []
        self.overrides: list[dict] = []
        self.opened = 0

    def answer(self, messages: list[dict], overrides: dict) -> dict:
        self.sent.append(messages)
        self.overrides.append(overrides)
        return {"text": self.replies[len(self.sent) - 1]}


@pytest.fixture
def endpoint(monkeypatch):
    world = _Endpoint(REPLIES)

    def chat(self, messages, **overrides):
        return world.answer(messages, overrides)

    async def achat(self, messages, **overrides):
        return world.answer(messages, overrides)

    async def asetup(self, ctx):
        world.opened += 1

    monkeypatch.setattr(LLMFabric, "chat", chat)
    monkeypatch.setattr(LLMFabric, "achat", achat)
    monkeypatch.setattr(LLMFabric, "asetup", asetup)
    return world


async def test_llm_sends_the_whole_conversation_every_call(endpoint):
    mem = Mem()
    backend = LLM("ollama", host="nowhere", model="m", request={"temperature": 0})
    ctx = nu.Context().bind(dict, mem.session, MemSession).bind(dict, mem.world)
    await nu.arun(agent(STORE, backend, TASK), ctx)
    assert mem.world["log"] == ["a", "b"]
    assert [len(sent) for sent in endpoint.sent] == [1, 3]
    assert endpoint.sent[1] == mem.session["messages"][:3]
    assert all(type(m) is dict for sent in endpoint.sent for m in sent)
    assert endpoint.overrides == [{"temperature": 0}] * 2


async def test_llm_opens_the_endpoint_once_for_the_run(endpoint):
    await nu.arun(STORE.bound(agent(STORE, LLM("bind", base_url="http://x", model="m"), TASK)))
    assert endpoint.opened == 1
    assert len(endpoint.sent) == 2


async def test_llm_keeps_the_opening_a_user_message_and_puts_system_first(endpoint):
    backend = LLM("vllm", base_url="http://x", model="m", system="Be brief.")
    await nu.arun(STORE.bound(agent(STORE, backend, TASK)))
    assert endpoint.sent[0] == [
        {"role": "system", "content": "Be brief."},
        {"role": "user", "content": TASK},
    ]


async def test_llm_sends_plain_dicts_off_a_kv_conversation(endpoint):
    endpoint.replies = [
        program("World.log.set(['a'])", "nustd.kv"),
        program("World.log.append('b') >> Run.done.set(True)", "nustd.kv"),
    ]
    store = KVStore()
    await nu.arun(store.bound(agent(store, LLM("bind", base_url="http://x", model="m"), TASK)))
    assert [len(sent) for sent in endpoint.sent] == [1, 3]
    assert all(type(m) is dict for sent in endpoint.sent for m in sent)


def test_llm_refuses_a_preset_nustd_lacks():
    with pytest.raises(ValueError, match=r"unknown nustd\.llm preset"):
        LLM("nope")


# --- cc ----------------------------------------------------------------------


class _Claude:
    """The CLI: transcripts by id, one scripted reply per prompt across every process."""

    def __init__(self, script: list[str]) -> None:
        self.script = script
        self.transcripts: dict[str, list[str]] = {}
        self.clients: list[_Client] = []
        self.prompts: list[str] = []

    def info(self, sid, directory=None):
        return object() if sid in self.transcripts else None

    def client(self, options):
        made = _Client(self, options)
        self.clients.append(made)
        return made

    def opened(self, options) -> str:
        if options.session_id is not None:
            assert options.session_id not in self.transcripts, "Session ID is already in use."
            return options.session_id
        if options.resume is not None:
            assert options.resume in self.transcripts, "No conversation found with session ID"
            return options.resume
        return str(uuid.uuid4())

    def said(self, sid: str, prompt: str) -> str:
        self.prompts.append(prompt)
        self.transcripts.setdefault(sid, []).append(prompt)
        return self.script[len(self.prompts) - 1]


class _Client:
    """One ``claude`` process: the options it opened with, the prompts it was sent."""

    def __init__(self, claude: _Claude, options) -> None:
        self.claude = claude
        self.options = options
        self.sid: str | None = None
        self.prompts: list[str] = []

    async def connect(self):
        self.sid = self.claude.opened(self.options)

    async def query(self, prompt):
        self.prompts.append(prompt)
        self.text = self.claude.said(self.sid, prompt)

    async def receive_response(self):
        for message in _replied(self.text, self.sid):
            yield message

    async def disconnect(self):
        pass


def _replied(text: str, sid: str) -> list:
    return [
        AssistantMessage(content=[TextBlock(text=text)], model="fake"),
        ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id=sid,
            result=text,
        ),
    ]


@pytest.fixture
def claude(monkeypatch):
    world = _Claude(REPLIES * 2)

    async def query(*, prompt, options):
        sid = world.opened(options)
        for message in _replied(world.said(sid, prompt), sid):
            yield message

    monkeypatch.setattr(cc_fabric, "ClaudeSDKClient", world.client)
    monkeypatch.setattr(cc_fabric, "get_session_info", world.info)
    monkeypatch.setattr(cc_fabric, "query", query)
    return world


def _messages(n: int) -> list[dict]:
    roles = ["user", "assistant"]
    return [{"role": roles[i % 2], "content": f"m{i}"} for i in range(n)]


async def test_cc_runs_the_whole_run_in_one_session_on_one_minted_id(claude):
    mem = Mem()
    ctx = nu.Context().bind(dict, mem.session, MemSession).bind(dict, mem.world)
    await nu.arun(agent(STORE, ClaudeCode(model="m"), TASK), ctx)
    assert mem.world["log"] == ["a", "b"]
    (client,) = claude.clients
    sid = client.options.session_id
    assert str(uuid.UUID(sid)) == sid
    assert client.options.resume is None
    assert client.options.model == "m"
    assert client.options.system_prompt == {"type": "preset", "preset": "claude_code"}


async def test_cc_sends_the_newest_message_only(claude):
    mem = Mem()
    ctx = nu.Context().bind(dict, mem.session, MemSession).bind(dict, mem.world)
    await nu.arun(agent(STORE, ClaudeCode(), TASK), ctx)
    messages = mem.session["messages"]
    assert claude.prompts == [TASK, messages[2]["content"]]
    assert claude.prompts[1] == "outcome: None"


def test_cc_on_the_sync_runtime_keeps_one_id_across_processes(claude):
    nu.run(STORE.bound(agent(STORE, ClaudeCode(), TASK)))
    assert claude.clients == []
    (sid,) = claude.transcripts
    assert claude.transcripts[sid] == [TASK, "outcome: None"]


class _Keep(nu.Shape):
    """Where a caller keeps the conversation id across runs."""

    sid = nu.StrRef.slot()


async def test_cc_mints_into_a_sid_ref_once_and_resumes_from_it(claude):
    keep: dict = {}
    for _ in range(2):
        mem = Mem()
        ctx = nu.Context().bind(dict, mem.session, MemSession).bind(dict, mem.world)
        term = agent(STORE, ClaudeCode(sid=_Keep.sid), TASK)
        await nu.arun(term, ctx.bind(dict, keep, _Keep))
    sid = keep["sid"]
    opened, resumed = claude.clients
    assert (opened.options.session_id, opened.options.resume) == (sid, None)
    assert (resumed.options.session_id, resumed.options.resume) == (None, sid)
    assert claude.transcripts[sid] == opened.prompts + resumed.prompts


def _asked(mem: Mem, backend: ClaudeCode) -> object:
    return mem.run(backend.wrap(MemSession.reply.set(backend.ask(MemSession.messages))))


def test_cc_replays_the_conversation_once_into_a_fresh_session(claude):
    mem = Mem(session={"messages": _messages(3)})
    _asked(mem, ClaudeCode(sid=str(uuid.uuid4())))
    (prompt,) = claude.prompts
    assert prompt == REPLAY + "[user]\nm0\n\n[assistant]\nm1\n\n[user]\nm2"


def test_cc_sends_the_newest_message_into_a_held_session(claude):
    sid = str(uuid.uuid4())
    claude.transcripts[sid] = ["m0", "m2"]
    mem = Mem(session={"messages": _messages(3)})
    _asked(mem, ClaudeCode(sid=sid))
    assert claude.prompts == ["m2"]


def test_cc_sends_the_opening_alone_into_a_fresh_session(claude):
    mem = Mem(session={"messages": _messages(1)})
    _asked(mem, ClaudeCode())
    assert claude.prompts == ["m0"]


def test_flattened_is_the_replay_head_then_each_message():
    term = flattened(nu.List.of(*_messages(2)))
    assert nu.run(term)[0] == REPLAY + "[user]\nm0\n\n[assistant]\nm1"


def test_both_runs_are_valid_terms():
    for backend in (ClaudeCode(), LLM("ollama", model="m")):
        nu.validate(nu.compile(STORE.bound(agent(STORE, backend, TASK))))


def test_cc_replays_once_then_sends_the_newest_again(claude):
    backend = ClaudeCode(sid=str(uuid.uuid4()))
    asked = MemSession.reply.set(backend.ask(MemSession.messages))
    later = MemSession.messages.append(nu.Dict.of(role="user", content="m3"))
    Mem(session={"messages": _messages(3)}).run(backend.wrap(asked >> later >> asked))
    assert claude.prompts[0].startswith(REPLAY)
    assert claude.prompts[1] == "m3"


def test_the_core_and_mem_store_import_no_backend():
    probe = (
        "import sys, nuagent.core, nuagent.presets.store.mem\n"
        "heavy = ('claude_agent_sdk', 'nustd.cc', 'nustd.llm', 'httpx')\n"
        "print([m for m in sys.modules if m.startswith(heavy)])"
    )
    ran = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)  # noqa: S603
    assert ran.stdout.strip() == "[]"
