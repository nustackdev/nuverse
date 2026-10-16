"""nudemos: found through the entry point, its Planes seeded, and their cells run on a real store."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

import nu
import nuspace
import nustd.kv
from nudemos import counter, movies, sampled, tour
from nuspace import Plane, ops
from nuspace.shapes import Reroot, Space, reroot
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Callable


DEMOS = [counter, sampled]
MOVIES = [movies]
SPECS = [tour.PLANE, *(m.PLANE for m in (*DEMOS, *MOVIES))]
SOURCES = [source for spec in SPECS for _, source in spec.cells]


class _Counter(nuspace.CellState):
    """The counter cell's state, as its source declares it."""

    value = nustd.kv.IntRef.slot()


class _Series(nuspace.PlaneState):
    """The sampled plane's state, as its cells declare it."""

    cursor = nustd.kv.IntRef.slot()


class _Browser(WsSession):
    """A session with no socket. Keeps the frames it is sent, answers reads from ``values``."""

    def __init__(self, values: dict | None = None) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []
        self.values = values or {}

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        return self.values[path[-1]]

    def drawn(self, name: str) -> list:
        """Every payload sent to the ref ``name``, in order."""
        return [f.payload for f in self.frames if f.ref[-1] == name]


async def _until(check: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.02)


async def _cells(store, plane: str) -> dict:
    """``{cell name: cell id}`` of a plane."""
    return {c["name"]: c["id"] for c in await store.read(ops.cell_rows(plane))}


async def _load(store, plane: str, cell: str) -> nu.Nu:
    """The cell's program, loaded through the kernel's rewrites, a session's among them."""
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot(plane, cell), env.rewrite)
    load = Space.cells[cell].prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite)
    return await store.run(nustd.kv.Snapshot(load, scope=Space))


async def _run(store, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell's program run as the kernel runs it, inside its ``Here`` frame."""
    term = nu.Frame(ops.Here, await _load(store, plane, cell), plane=plane, cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))


async def _stop(*tasks: asyncio.Task) -> None:
    for task in tasks:
        task.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, asyncio.CancelledError) for r in results), results


# --- the specs -------------------------------------------------------------------------------


def test_discovery_finds_the_tour_and_the_demos():
    from nuspace.ext import discover

    (ext,) = [e for e in discover() if e.name == "nudemos"]
    assert [p.name for p in ext.planes] == [
        "demos",
        "counter",
        "sampled",
        "movies",
        "mnist",
        "memes",
        "agents",
    ]


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_each_spec_is_a_demo(spec: Plane):
    from nuspace.system.backends import BACKENDS

    assert spec.group == "Demos"
    assert spec.icon
    assert spec.description
    assert spec.backend in BACKENDS
    assert spec.backend == "async"
    assert spec.meta["editable"] is True
    names = [name for name, _ in spec.cells]
    assert names
    assert len(set(names)) == len(names)


def test_the_tour_nests_the_demos():
    assert tour.PLANE.children == tuple(m.PLANE for m in DEMOS)
    assert all(not m.PLANE.children for m in DEMOS)


# --- creating them ---------------------------------------------------------------------------


@pytest.mark.parametrize("module", [*DEMOS, *MOVIES], ids=lambda m: m.PLANE.name)
async def test_each_demo_is_created_with_its_cells(store, module):
    spec = module.PLANE
    await store.run(ops.create_plane(spec, plane_id="p1"))
    (row,) = [r for r in await store.read(ops.plane_rows()) if r["id"] == "p1"]
    assert row["name"] == spec.label
    assert row["props"] == {"system": False, "ui": True, "made_by": spec.name, "backend": "async"}
    assert row["meta"] == {**spec.meta, "icon": f"lucide:{spec.icon}"}
    cells = await store.read(ops.cell_rows("p1"))
    assert [(c["name"], c["prog"]) for c in cells] == list(spec.cells)
    assert all(c["props"]["has_ui"] for c in cells)


async def test_the_tour_is_created_with_the_demos_under_it(store):
    await store.run(ops.create_plane(tour.PLANE, plane_id="t"))
    assert [c["name"] for c in await store.read(ops.cell_rows("t"))] == ["intro"]
    kids = await store.read(ops.children("t"))
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert [rows[k]["props"]["made_by"] for k in kids] == ["counter", "sampled"]
    assert all(rows[k]["parent"] == "t" for k in kids)
    for kid, module in zip(kids, DEMOS, strict=True):
        cells = await store.read(ops.cell_rows(kid))
        assert [(c["name"], c["prog"]) for c in cells] == list(module.PLANE.cells)


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: str(hash(s)))
async def test_each_cell_loads_through_the_kernel_rewrites(store, source):
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    term = await _load(store, "p", "c")
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


# --- running them ----------------------------------------------------------------------------


async def test_the_counter_ticks_once_a_second_however_many_tabs(store):
    await store.run(ops.create_plane(counter.PLANE, plane_id="p"))
    cid = (await _cells(store, "p"))["count"]
    one, two = _Browser(), _Browser()
    tabs = [await _run(store, "p", cid, one), await _run(store, "p", cid, two)]
    try:
        await asyncio.sleep(3.3)
    finally:
        await _stop(*tabs)
    count = await store.read(reroot(_Counter.value, "p", cid))
    assert 2 <= count <= 4
    # Both tabs follow the one count, whichever ticked.
    for tab in (one, two):
        shown = [p["value"] for p in tab.drawn("count") if "value" in p]
        assert shown[-1] == str(count)


async def test_the_counter_carries_on_from_its_state(store):
    await store.run(ops.create_plane(counter.PLANE, plane_id="p"))
    cid = (await _cells(store, "p"))["count"]
    await store.run(ops.atomic_state(reroot(_Counter.value, "p", cid).set(41)))
    tab = _Browser()
    task = await _run(store, "p", cid, tab)
    try:
        await _until(lambda: any(p.get("value") == "42" for p in tab.drawn("count")))
    finally:
        await _stop(task)


async def test_sampled_feeds_in_batches_and_charts_a_sample(store):
    await store.run(ops.create_plane(sampled.PLANE, plane_id="p"))
    ids = await _cells(store, "p")
    feed, chart = _Browser(), _Browser()
    tasks = [await _run(store, "p", ids["feed"], feed), await _run(store, "p", ids["chart"], chart)]
    try:
        await _until(lambda: len(chart.drawn("chart")) >= 2)
        cursor = await store.read(reroot(_Series.cursor, "p", ""))
    finally:
        await _stop(*tasks)
    assert cursor > 0
    assert cursor % 25 == 0
    *_, drawn = chart.drawn("chart")
    (series,) = drawn["series"]
    points = series["data"]
    keys = [x for x, _ in points]
    assert 0 < len(keys) <= 200
    assert keys == sorted(keys)
    assert all(-11.0 <= y <= 11.0 for _, y in points)
