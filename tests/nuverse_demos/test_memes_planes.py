"""nuverse-demos memes: every plane's cells, run against a store the sync has written. Offline.

The root's state is seeded the way the job writes it, a :class:`~.book.Book`
flush over the fixture blocks, and each cell runs as the kernel runs it, in
a session whose browser keeps what it is sent.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from pathlib import Path

import pytest

import nu
import nustd.http
import nustd.kv
from nuspace import Plane, ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.session import Session
from nuverse_demos.memes import PLANE, cells, token
from nuverse_demos.memes.book import Book
from nuverse_demos.memes.chain import decode_block
from nuverse_demos.memes.job import written
from nuverse_demos.memes.state import TOKEN, at_root, token_page


FIXTURES = Path(__file__).parent / "fixtures" / "memes"
BLOCKS = {
    456413524: json.loads((FIXTURES / "block_456413524.json").read_text()),
    456413622: json.loads((FIXTURES / "block_456413622_create.json").read_text()),
}
#: The coin the launch block makes.
CAP = decode_block(BLOCKS[456413622], 456413622)["events"][0]["mint"]


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """No call leaves the test: a token page asking for its picture gets refused."""

    async def refused(self, verb, path, **wire):
        raise ConnectionError(f"offline: {path}")

    monkeypatch.setattr(nustd.http.HttpFabric, "arequest", refused)


class _Browser(WsSession):
    """A session with no socket. Keeps the frames it is sent."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        return ""

    def drawn(self, name: str) -> list:
        return [f.payload for f in self.frames if f.ref and f.ref[-1] == name]


def _small(spec: Plane) -> Plane:
    """``spec`` with two launch cards, not twelve: the same cells, a smaller program to check."""
    cells = tuple((name, src.replace("\nN = 12\n", "\nN = 2\n")) for name, src in spec.cells)
    return dataclasses.replace(spec, cells=cells, children=tuple(map(_small, spec.children)))


#: The memes tree as the tests make it: :func:`_small`, so a run stays quick.
SMALL = _small(PLANE)


async def _seed(store) -> None:
    """The root ``m`` and its children, and the state a sync over the fixtures writes."""
    await store.run(ops.create_plane(SMALL, plane_id="m"))
    book = Book(clock=lambda: 1791888300.0)
    book.tip, book.tip_at, book.epoch = 456413700, book.clock(), 0
    for slot, block in BLOCKS.items():
        book.cursor = slot
        book.on_reply({"what": "block", "slot": slot, "sent": book.clock()}, {"result": block})
    await store.run(ops.atomic_state(at_root("m", written(book.flush()))))


async def _cells(store, plane: str) -> dict:
    return {c["name"]: c["id"] for c in await store.read(ops.cell_rows(plane))}


async def _drive(store, plane: str, cell: str, quiet: float = 0.25, most: float = 8.0) -> _Browser:
    """Run the cell as the kernel would till it draws and goes quiet, then cancel it. Raises what it raised."""
    browser = _Browser()
    env = session_env("127.0.0.1:9")("s1")
    load = Space.cells[cell].prog.load(
        scope={"plane": plane, "cell": cell}, rewrite=Rewrites(Reroot(plane, cell), env.rewrite)
    )
    term = nu.Frame(
        ops.Here, await store.run(nustd.kv.Snapshot(load, scope=Space)), plane=plane, cell=cell
    )
    task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))
    loop = asyncio.get_running_loop()
    deadline, seen, still = loop.time() + most, -1, loop.time()
    while loop.time() < deadline and not task.done():
        await asyncio.sleep(0.02)
        if len(browser.frames) != seen:
            seen, still = len(browser.frames), loop.time()
        elif seen > 0 and loop.time() - still >= quiet:
            break
    if task.done():
        task.result()  # a cell that ended raised, or drew once and parked: either way, say so
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    return browser


async def test_every_cell_runs_and_draws(store):
    # One seed for every plane: making the memes tree is most of a test's time.
    await _seed(store)
    kids = await store.read(ops.children("m"))
    planes = [(SMALL, "m"), *zip(SMALL.children, kids, strict=True)]
    runs = []
    for spec, plane in planes:
        ids = await _cells(store, plane)
        runs += [(f"{spec.name}.{name}", _drive(store, plane, ids[name])) for name, _ in spec.cells]
    drawn = dict(
        zip([n for n, _ in runs], await asyncio.gather(*(r for _, r in runs)), strict=True)
    )
    for name, browser in drawn.items():
        assert browser.frames, f"{name} drew nothing"

    # The bar offers Start while nothing runs, with no notice.
    bar = drawn["memes.sync"]
    assert bar.drawn("pill")[0]["label"] in ("idle", "down")
    assert bar.drawn("toggle")[-1]["label"] == "Start"
    assert bar.drawn("notice")[-1] == ""

    # The tokens table lists the launch first: only coins whose launch the sync saw have a date.
    tokens = drawn["memes_overview.tokens"]
    rows = [p["rows"] for p in tokens.drawn("table") if isinstance(p, dict) and "rows" in p][-1]
    assert [(r["mint"], r["token"], r["curve"]) for r in rows] == [(CAP, "cap", rows[0]["curve"])]
    assert rows[0]["age"] != "-"

    # Coins' own images are off until the Sync plane's switch is on.
    settings = drawn["memes_sync.settings"]
    assert settings.drawn("show")[-1] is False


async def test_a_token_page_shows_its_token(store):
    await _seed(store)
    page = await store.read(token_page("m", CAP))
    spec = Plane(TOKEN, "Token", cells=token.CELLS, backend="async")
    await store.run(
        ops.create_plane(spec, parent="m", name=CAP, plane_id=page)
        >> ops.set_plane_meta(page, nu.Dict.of(base="m", mint=CAP))
    )
    ids = await _cells(store, page)
    head, numbers, trades = await asyncio.gather(
        *(_drive(store, page, ids[name]) for name in ("head", "numbers", "trades"))
    )
    assert head.drawn("title")[-1]["label"] == "dog wif cap"
    assert head.drawn("face")[0]["src"].startswith("data:image/svg+xml")
    assert await store.read(ops.plane_title(page)) == "cap"
    assert numbers.drawn("mc")[-1]["value"].endswith(" SOL")
    rows = [p["rows"] for p in trades.drawn("table") if isinstance(p, dict) and "rows" in p][-1]
    assert [r["side"] for r in rows] == ["▲ BUY"]


def test_the_planes_hang_as_the_docs_say():
    assert [c.name for c in PLANE.children] == ["memes_overview", "memes_monitor", "memes_sync"]
    assert [n for n, _ in PLANE.cells] == ["intro", "sync", "tiles", "pulse", "launches"]
    assert all(dict(p.cells)["sync"] == cells.BAR for p in PLANE.children)
    assert PLANE.group == "Demos" and PLANE.backend == "async"
    assert "\nN = 2\n" in dict(SMALL.cells)["launches"]
