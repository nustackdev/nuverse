"""The agent terms: add, ask, cancel, answer, installed, over an agent plane's state."""

from __future__ import annotations

import shutil
import subprocess
import sys

import pytest
from _support.made import MADE

import nu
import nuspace
from nuspace.errors import Missing, Refused
from nuspace.shapes import Space
from nuspace.specs import SpecCells
from nuspace.web import Web
from nuverse import agents
from nuverse.agents import terms
from nuverse.planes import agent as agent_plane


async def _plane(store, **kw) -> str:
    return await store.made(agents.add("claude", "/srv/repo", into=MADE, **kw))


async def _live(store, plane: str) -> list[str]:
    ids = Space.exec.indexes.live.plane_to_plane_runs[plane].ids
    return await store.read(nu.If(ids.exists(), nu.list(ids.keys()), []))


async def test_add_makes_a_headless_asleep_plane_with_its_spec(store):
    p = await _plane(store, system_prompt="be brief")
    row = await store.read(Space.planes[p].extract())
    assert (row["spec"], row["backend"], row["name"]) == ("nuverse.agent", "async", "Agent")
    assert not await store.read(Web.planes.contains(p))
    cells = await store.read(nuspace.at.plane(id=p).state(SpecCells).ids.extract())
    assert list(cells) == ["engine"]
    assert await store.read(Space.cells[cells["engine"]].prog) == agent_plane.ENGINE
    spec = agents.spec(p)
    held = nu.Dict.of(agent=spec.agent, cwd=spec.cwd, system_prompt=spec.system_prompt)
    assert await store.read(held) == {
        "agent": "claude",
        "cwd": "/srv/repo",
        "system_prompt": "be brief",
    }
    s = agents.session(p)
    assert await store.read(nu.Dict.of(status=s.status, owner=s.owner, sid=s.session_id)) == {
        "status": "asleep",
        "owner": "",
        "sid": "",
    }
    assert await store.read(nu.list(agents.asks(p).prompts.keys())) == []
    assert await store.read(nu.list(agents.trace(p).entries.keys())) == []
    assert await _live(store, p) == []


def test_add_refuses_an_unknown_agent_and_a_relative_cwd():
    with pytest.raises(ValueError, match="no agent preset"):
        agents.add("gpt", "/srv")
    with pytest.raises(ValueError, match="absolute"):
        agents.add("claude", "repo")


async def test_ask_appends_and_wakes_an_asleep_plane(store):
    p = await _plane(store)
    await store.run(agents.ask(p, "why does it flake?", by="user"))
    keys = await store.read(nu.list(agents.asks(p).prompts.keys()))
    assert len(keys) == 1
    prompt = await store.read(agents.asks(p).prompts[keys[0]])
    assert (prompt["text"], prompt["by"]) == ("why does it flake?", "user")
    assert isinstance(prompt["at"], int)
    runs = await _live(store, p)
    assert len(runs) == 1
    assert await store.read(Space.exec.plane_runs[runs[0]].by) == "nuverse.agents"


async def test_ask_leaves_a_live_owner_alone_and_wakes_past_a_dead_one(store):
    p = await _plane(store)
    r = await store.made(nuspace.atomic(nuspace.plane_run.add(p, into=MADE)))
    await store.do(agents.session(p).owner.set(r))
    await store.run(agents.ask(p, "one"))
    await store.run(agents.ask(p, "two"))
    assert await _live(store, p) == [r]
    # The owner's run ended without clearing it: the next ask starts one.
    await store.do(nuspace.plane_run.end(r, "failed", "boom"))
    await store.run(agents.ask(p, "three"))
    runs = await _live(store, p)
    assert len(runs) == 1
    assert runs != [r]
    assert len(await store.read(nu.list(agents.asks(p).prompts.keys()))) == 3


async def test_ask_refuses_blank_text(store):
    p = await _plane(store)
    with pytest.raises(Refused, match="needs text"):
        await store.run(agents.ask(p, "  "))
    assert await _live(store, p) == []


async def test_cancel_stamps_cancel_at(store):
    p = await _plane(store)
    await store.run(agents.cancel(p))
    assert await store.read(agents.asks(p).cancel_at) > 0


async def test_answer_writes_an_offered_option_and_refuses_others(store):
    p = await _plane(store)
    options = [
        {"option_id": "allow", "name": "Allow", "kind": "allow_once"},
        {"option_id": "reject", "name": "Reject", "kind": "reject_once"},
    ]
    entry = {
        "kind": "permission",
        "turn": "t",
        "at": 1,
        "permission": {"request": 1, "options": options},
    }
    await store.do(agents.trace(p).entries.set_item("perm:x", entry))
    with pytest.raises(Refused, match="offers no option"):
        await store.run(agents.answer(p, "perm:x", "always"))
    with pytest.raises(Missing, match="no entry"):
        await store.run(agents.answer(p, "perm:y", "allow"))
    await store.run(agents.answer(p, "perm:x", "allow"))
    permission = await store.read(agents.trace(p).entries["perm:x"].permission.extract())
    assert permission["answer"] == "allow"
    assert permission["options"] == options


async def test_installed_needs_npx_and_the_cli(monkeypatch, store):
    on_path = {"npx", "codex"}
    monkeypatch.setattr(shutil, "which", lambda name: f"/bin/{name}" if name in on_path else None)
    monkeypatch.setattr(terms.importlib.util, "find_spec", lambda name: object())
    assert await store.read(agents.installed()) == ["codex"]
    on_path.add("claude")
    assert await store.read(agents.installed()) == ["claude", "codex"]
    on_path.discard("npx")
    assert await store.read(agents.installed()) == []


def test_nuverse_loads_without_the_acp_sdk():
    """The agent cell and plane are offered with no ACP SDK: the cell says so, nothing fails to load."""
    script = (
        "import sys; sys.modules['acp'] = None\n"
        "import nuverse; nuverse.extension()\n"
        "from nuverse import agents; print(sorted(agents.PRESETS))\n"
    )
    done = subprocess.run(  # noqa: S603 - our own interpreter on a fixed script
        [sys.executable, "-c", script], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    assert "claude" in done.stdout
