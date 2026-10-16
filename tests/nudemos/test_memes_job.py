"""nudemos memes: the sync job's loop on a real store, against a fake chain. Offline.

The job's cell runs in this process, as the kernel would run it, and its
JSON-RPC calls land on :class:`FakeChain` instead of the network: a tip that
moves one slot a call, two real blocks from the fixtures, a skipped slot,
and a rate limit on the first block asked for.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import nu
import nustd.http
import nustd.kv
from nudemos.memes import PLANE, control
from nudemos.memes import book as booklib
from nudemos.memes.chain import decode_block
from nudemos.memes.state import Control, Memes, at_root, job_cell, job_of
from nuspace import ops
from nuspace.shapes import Reroot, Space


FIXTURES = Path(__file__).parent / "fixtures" / "memes"
TRADES = json.loads((FIXTURES / "block_456413524.json").read_text())
LAUNCH = json.loads((FIXTURES / "block_456413622_create.json").read_text())
#: The coin the launch block makes.
CAP = decode_block(LAUNCH, 456413622)["events"][0]["mint"]


class FakeChain:
    """What the job's calls reach: the tip moves a slot each time it is asked."""

    def __init__(self, tip: int = 999) -> None:
        self.tip = tip
        self.calls: list[str] = []
        self.limited = False

    async def __call__(self, verb: str, path: str, **wire: object) -> object:
        body = wire["json"]
        method, params = body["method"], body.get("params") or []
        self.calls.append(method)
        await asyncio.sleep(0.01)
        if method == "getSlot":
            self.tip += 1
            return {"result": self.tip}
        if method == "getMultipleAccounts":
            return {"result": {"value": [None for _ in params[0]]}}
        slot = params[0]
        if not self.limited:
            self.limited = True
            raise RuntimeError(
                "Client error '429 Too Many Requests' for url 'https://rpc.example/?api-key=SECRET'"
            )
        if slot == 999:
            return {"error": {"code": -32007, "message": f"Slot {slot} was skipped"}}
        if slot == 998:
            return {"result": TRADES}
        if slot == 1000:
            return {"result": LAUNCH}
        return {"result": {"blockTime": 1791888300, "transactions": []}}


@pytest.fixture
def chain(monkeypatch):
    fake = FakeChain()

    async def arequest(self, verb, path, **wire):
        assert path == "https://rpc.example"
        return await fake(verb, path, **wire)

    monkeypatch.setattr(nustd.http.HttpFabric, "arequest", arequest)
    monkeypatch.setattr(booklib, "EVERY", 0.3)
    monkeypatch.setenv(booklib.ENV, "https://rpc.example")
    return fake


async def _until(check, timeout: float = 30.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.05)


async def _run_job(store) -> asyncio.Task:
    """The job's one cell, run as the kernel runs it: loaded with its rewrites, in its ``Here`` frame."""
    job = await store.read(job_of("m"))
    cell = await store.read(job_cell(job))
    load = Space.cells[cell].prog.load(
        scope={"plane": job, "cell": cell}, rewrite=Reroot(job, cell)
    )
    term = nu.Frame(
        ops.Here, await store.run(nustd.kv.Snapshot(load, scope=Space)), plane=job, cell=cell
    )
    return asyncio.create_task(nu.arun(term, store.ctx))


def _at(term: nu.Nu) -> nu.Nu:
    return at_root("m", term)


async def test_starting_makes_the_job_once_under_the_root(store):
    await store.run(ops.create_plane(PLANE, plane_id="m"))
    await store.run(control.start("m") >> control.start("m"))
    kids = await store.read(ops.children("m"))
    assert kids[-1] == "m.sync" and kids.count("m.sync") == 1
    assert await store.read(Space.planes["m.sync"].props.backend) == "mp"
    assert await store.read(Space.planes["m.sync"].props.ui) is False
    assert await store.read(ops.cells("m.sync")) == ["m.sync_main"]
    assert await store.read(_at(Control.stop)) is False
    await store.run(control.stop("m"))
    assert await store.read(_at(Control.stop)) is True


async def test_the_job_follows_the_chain_backs_off_and_stops(store, chain):
    await store.run(ops.create_plane(PLANE, plane_id="m") >> control.start("m"))
    task = await _run_job(store)

    async def launched():
        return await store.read(_at(Memes.tokens.contains(CAP)))

    await _until(launched)
    await _until(lambda: _points(store))
    await store.run(control.stop("m"))
    await asyncio.wait_for(task, 20)

    stats = await store.read(_at(Memes.stats))
    assert stats["status"] == "stopped"
    totals = stats["totals"]
    assert totals["skipped"] >= 1 and totals["blocks"] >= 2
    assert totals["trades"] == 7 and totals["launches"] == 1
    assert totals["errors"] == 1
    assert stats["rpc"] == "rpc.example"
    (error,) = await store.read(_at(Memes.errors))
    assert "429" in error["message"] and "SECRET" not in error["message"]

    cap = await store.read(_at(Memes.tokens[CAP]))
    assert (cap["name"], cap["symbol"], cap["trades"]) == ("dog wif cap", "cap", 1)
    board = await store.read(_at(Memes.board))
    assert board["new"][0]["mint"] == CAP
    tape = await store.read(_at(Memes.tape))
    assert tape[0]["mint"] == CAP and len(tape) == 4  # SOL trades only: 3 are in other quotes
    assert len(await store.read(_at(Memes.trades[CAP]))) == 1
    assert await store.read(_at(Memes.beat)) > 0
    sync = await store.read(_at(Memes.sync))
    assert sync["cursor"] > 1000 and sync["epoch"] == 0
    assert {"getSlot", "getBlock", "getMultipleAccounts"} <= set(chain.calls)

    # Run again: it picks up where it stopped, a stopped sync ends at once until the flag clears.
    task = await _run_job(store)
    await asyncio.wait_for(task, 20)
    await store.run(ops.atomic_state(_at(Control.stop.set(False))))
    task = await _run_job(store)

    async def moved():
        return (await store.read(_at(Memes.sync)))["cursor"] > sync["cursor"]

    await _until(moved)
    await store.run(control.stop("m"))
    await asyncio.wait_for(task, 20)
    again = await store.read(_at(Memes.stats))
    assert again["totals"]["trades"] == 7  # the old blocks are not read twice
    assert await store.read(_at(Memes.tokens.contains(CAP)))


async def _points(store) -> bool:
    return len(await store.read(_at(Memes.blocks_s.sample(10)))) >= 1


async def test_starting_over_from_a_slot_reads_from_there(store, chain):
    await store.run(ops.create_plane(PLANE, plane_id="m"))
    await store.run(control.restart("m", 998))
    assert await store.read(_at(Control.epoch)) == 1
    chain.limited = True
    task = await _run_job(store)

    async def read_it():
        return (await store.read(_at(Memes.stats.fallback({})))).get("totals", {}).get(
            "trades", 0
        ) >= 7

    await _until(read_it)
    await store.run(control.stop("m"))
    await asyncio.wait_for(task, 20)
    stats = await store.read(_at(Memes.stats))
    assert stats["mode"] == "from" and "jumped" not in stats["totals"]
    assert stats["cursor"] > 1000  # every block from 998 on, in order
