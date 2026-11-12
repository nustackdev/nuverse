"""nudemos: found through the entry point, its Planes made from their specs, and their cells run on a real store."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import zlib
from typing import TYPE_CHECKING

import pytest

import nu
import nu.prog
import nuspace
import nustd.kv
from nudemos import agents, counter, data, movies, ops, recipes, research, sampled, tour
from nuspace import Space
from nuspace.places import inside
from nuspace.specs import PlaneSpec, SpecCells
from nuspace.web import Web
from nuspace.web.env import session_env
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Callable


DEMOS = [counter, sampled]
MOVIES = [movies]
SPECS = [tour.PLANE, *(m.PLANE for m in (*DEMOS, *MOVIES))]
SOURCES = [source for spec in SPECS for _, source in spec.cells]


def _every_cell(spec: PlaneSpec) -> list[tuple[str, str]]:
    """``(name, source)`` of every cell a spec and its children seed."""
    return [*spec.cells, *(c for child in spec.children for c in _every_cell(child))]


#: The demos keyed once per space, and every cell their roots seed: built as the kernel builds them.
KEYED = [ops, research, data]
KEYED_SOURCES = [s for m in (*KEYED, agents, recipes) for _, s in _every_cell(m.PLANE)]


class _Counter(nu.Shape):
    """The counter cell's state, as its source declares it."""

    value = nustd.kv.IntRef.slot()


class _Series(nu.Shape):
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
    """``{cell name: cell id}`` of a plane made from a spec: what its plane state keeps."""
    return await store.read(nuspace.at.plane(id=plane).state(SpecCells).ids.extract())


async def _load(store, plane: str, cell: str) -> nu.Nu:
    """The cell's program, loaded as the kernel loads it, through a session's rewrite."""
    env = session_env("127.0.0.1:9")("s1")
    load = Space.cells[cell].prog.load(scope={"plane": plane, "cell": cell}, rewrite=env.rewrite)
    return await store.read(load)


async def _run(store, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell's program run as the kernel runs it, inside its ``Here`` frame."""
    term = inside(await _load(store, plane, cell), plane=plane, cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))


async def _stop(*tasks: asyncio.Task) -> None:
    for task in tasks:
        task.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, asyncio.CancelledError) for r in results), results


# --- the specs -------------------------------------------------------------------------------


def test_discovery_finds_the_tour_and_the_demos():
    from nuspace.specs import discover

    ext = discover()["nudemos"]
    assert [p.name for p in ext.planes] == [
        "nudemos.tour",
        "nudemos.counter",
        "nudemos.sampled",
        "nudemos.movies",
        "nudemos.mnist",
        "nudemos.memes",
        "nudemos.agents",
        "nudemos.knowledge",
        "nudemos.research",
        "nudemos.design",
        "nudemos.data",
        "nudemos.ops",
        "nudemos.recipes",
    ]


def test_the_extension_loads_without_its_extras():
    # Each demo's heavy libraries are extras: the extension, every spec and its
    # key, loads without them, so a bare install still lists every demo.
    blocked = ("numpy", "nulog", "torch", "torchvision", "PIL")
    script = (
        "import sys\n"
        f"for name in {blocked!r}:\n"
        "    sys.modules[name] = None\n"
        "import nudemos\n"
        "print(len(nudemos.extension().planes))\n"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "13"


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: s.name)
def test_each_spec_is_a_demo(spec: PlaneSpec):
    from nuspace.kernel.backends import BACKENDS

    assert spec.group == "Demos"
    assert spec.icon
    assert spec.description
    assert spec.backend in BACKENDS
    assert spec.backend == "async"
    assert spec.web is not None
    assert spec.web.editable is True
    names = [name for name, _ in spec.cells]
    assert names
    assert len(set(names)) == len(names)


def test_the_tour_nests_the_demos():
    assert tour.PLANE.children == tuple(m.PLANE for m in DEMOS)
    assert all(not m.PLANE.children for m in DEMOS)


def test_demos_meant_once_per_space_are_keyed_by_package():
    keys = [m.PLANE.key for m in KEYED]
    assert keys == ["nudemos_ops", "nudemos_research", "nudemos_data"]
    assert all(not m.PLANE.key for m in (*DEMOS, tour, agents, recipes))


# --- creating them ---------------------------------------------------------------------------


@pytest.mark.parametrize("module", [*DEMOS, *MOVIES], ids=lambda m: m.PLANE.name)
async def test_each_demo_is_created_with_its_cells(store, module):
    spec = module.PLANE
    await store.run(nuspace.specs.add_plane(spec, "p1"))
    row = await store.read(Space.planes["p1"].extract())
    assert row["name"] == spec.label
    assert row["spec"] == f"nudemos.{spec.name}"
    assert row["backend"] == "async"
    assert row["icon"] == f"lucide:{spec.icon}"
    shown = await store.read(Web.planes["p1"].extract())
    assert shown == {"editable": True, "full_width": spec.web.full_width, "compact": False}
    ids = await _cells(store, "p1")
    # In the spec's order on the plane, each found by its name in the plane's state.
    placed = await store.read(Space.planes["p1"].cells.keys(limit=20))
    assert placed == [ids[name] for name, _ in spec.cells]
    for name, prog in spec.cells:
        cell = await store.read(Space.cells[ids[name]].extract())
        assert (cell["name"], cell["prog"], cell["plane"]) == (name, prog, "p1")
        assert cell["fabrics"] == ["ui"]


async def test_the_tour_is_created_with_the_demos_under_it(store):
    await store.run(nuspace.specs.add_plane(tour.PLANE, "t"))
    assert set(await _cells(store, "t")) == {"intro"}
    kids = await store.read(Space.planes["t"].children.keys(limit=10))
    specs = [await store.read(Space.planes[k].spec) for k in kids]
    assert specs == ["nudemos.counter", "nudemos.sampled"]
    for kid, module in zip(kids, DEMOS, strict=True):
        assert await store.read(Space.planes[kid].parent) == "t"
        assert set(await _cells(store, kid)) == {name for name, _ in module.PLANE.cells}


async def test_a_keyed_demo_is_found_by_its_key_and_made_once(store):
    await store.run(nuspace.specs.add_plane(ops.PLANE, "o1"))
    assert await store.read(Space.indexes.plane_keys["nudemos_ops"]) == "o1"
    with pytest.raises(nuspace.errors.Exists):
        await store.run(nuspace.specs.add_plane(ops.PLANE, "o2"))


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: f"{zlib.crc32(s.encode()):08x}")
async def test_each_cell_loads_through_the_session_rewrite(store, source):
    await store.do(nuspace.plane.add("p", backend="async") >> nuspace.cell.add("p", source, id="c"))
    term = await _load(store, "p", "c")
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


@pytest.mark.parametrize("source", KEYED_SOURCES, ids=lambda s: f"{zlib.crc32(s.encode()):08x}")
def test_each_root_cell_of_the_bigger_demos_builds(source):
    brace = nu.prog.PyBrace()
    term = brace.construct(source, scope={"plane": "p", "cell": "c"})
    assert isinstance(term, nu.Nu), term
    nu.validate(nu.compile(term))


# --- running them ----------------------------------------------------------------------------


async def test_the_counter_ticks_once_a_second_however_many_tabs(store):
    await store.run(nuspace.specs.add_plane(counter.PLANE, "p"))
    cid = (await _cells(store, "p"))["count"]
    one, two = _Browser(), _Browser()
    tabs = [await _run(store, "p", cid, one), await _run(store, "p", cid, two)]
    try:
        await asyncio.sleep(3.3)
    finally:
        await _stop(*tabs)
    count = await store.read(nuspace.at.cell(id=cid).state(_Counter).value)
    assert 2 <= count <= 4
    # Both tabs follow the one count, whichever ticked.
    for tab in (one, two):
        shown = [p["value"] for p in tab.drawn("count") if "value" in p]
        assert shown[-1] == str(count)


async def test_the_counter_carries_on_from_its_state(store):
    await store.run(nuspace.specs.add_plane(counter.PLANE, "p"))
    cid = (await _cells(store, "p"))["count"]
    await store.do(nuspace.at.cell(id=cid).state(_Counter).value.set(41))
    tab = _Browser()
    task = await _run(store, "p", cid, tab)
    try:
        await _until(lambda: any(p.get("value") == "42" for p in tab.drawn("count")))
    finally:
        await _stop(task)


async def test_sampled_feeds_in_batches_and_charts_a_sample(store):
    await store.run(nuspace.specs.add_plane(sampled.PLANE, "p"))
    ids = await _cells(store, "p")
    feed, chart = _Browser(), _Browser()
    tasks = [await _run(store, "p", ids["feed"], feed), await _run(store, "p", ids["chart"], chart)]
    try:
        await _until(lambda: len(chart.drawn("chart")) >= 2)
        cursor = await store.read(nuspace.at.plane(id="p").state(_Series).cursor)
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


# The way a demo moves the page: a HistoryRef slot in the cell's View, pushed
# a pane URL. The row clicks and launches across the demos all do this.
PUSHES = """\
import nu
import nu.prog
import nuspace.web as web
import nustd.ui


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    head = nustd.ui.HeadingRef.slot(level=4)


def out(plane):
    return View.head.set("Opening") >> View.history.push(web.href(plane + ".run", {"id": 7})) >> nu.ForeverDo(nu.Delay(3600.0))
"""


async def test_a_cell_moves_the_page_with_a_history_ref_under_itself(store):
    await store.do(nuspace.plane.add("p", backend="async") >> nuspace.cell.add("p", PUSHES, id="c"))
    tab = _Browser()
    task = await _run(store, "p", "c", tab)
    try:
        await _until(lambda: bool(tab.drawn("history")))
    finally:
        await _stop(task)
    (frame,) = [f for f in tab.frames if f.ref[-1] == "history"]
    assert frame.payload == {"action": "push", "uri": "/p.run?id=7"}
    # Rooted under the cell like any other Ref it draws, typed for the kit's History.
    assert frame.ref[-2:] == ("c", "history")
    assert frame.chain[-1][1] == "HistoryRef"
