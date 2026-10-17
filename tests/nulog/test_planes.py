"""The Log planes: registered, seeded, and every cell run against a real nulog store on disk.

Each cell runs as the kernel runs it, in a session whose browser keeps what
it is sent (and answers reads from a dict). The store is a RocksDB nulog a
test writes first; the cells open it read only, as a secondary, under its
own tags, beside the space's in memory stores.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

import nu
import nulog
import nustd.kv
from nulog import planes
from nulog.planes import state
from nuspace import ops
from nuspace.ext import space_registry
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.protocol import OP_NOTIFY
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from pathlib import Path


ROOT = "log"


class _Browser(WsSession):
    """A session with no socket. Keeps the frames it is sent, answers reads from ``values``."""

    def __init__(self, values: dict | None = None) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []
        self.values = values or {}

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    def drawn(self, name: str) -> list:
        """Every payload sent to the ref ``name``, in order."""
        return [f.payload for f in self.frames if f.ref and f.ref[-1] == name]

    async def aread(self, path: tuple[str, ...]) -> object:
        for n in (2, 1):
            if path[-n:] in self.values:
                return self.values[path[-n:]]
        return self.values.get(path[-1], "")

    def notify(self, name: str | tuple[str, ...], payload: object, value: object = None) -> bool:
        """The person acts on the ref whose address ends ``name``: it reads ``value`` from now on, and it notifies.

        False while nothing listens on it yet.
        """
        tail = (name,) if isinstance(name, str) else tuple(name)
        paths = [p for p in self._subs if p[-len(tail) :] == tail]
        if not paths:
            return False
        if value is not None:
            self.values[tail] = value
        for path in paths:
            self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))
        return True

    def rows(self, name: str = "table") -> list:
        """The rows of the last full set of ``name``'s rows."""
        sets = [p for p in self.drawn(name) if isinstance(p, dict) and "rows" in p]
        sets += [{"rows": p} for p in self.drawn(name) if isinstance(p, list)]
        return sets[-1]["rows"] if sets else []


def _write(path: Path, n: int = 5) -> str:
    """A nulog store at ``path``: ``app`` with ``n`` entries, ``db`` with one error, a ``cpu`` series."""
    log, db = nulog.getLogger("app"), nulog.getLogger("db")
    writes = [log.info("tick %s", i, extra={"i": i}) for i in range(n)]
    writes += [log.warning("slow: %s ms", 210), db.error("lost the connection")]
    writes += [nulog.observe("cpu", 0.1 * i) for i in range(1, 4)]
    nu.run(nu.With(nulog.store(str(path)), body=nustd.kv.Transaction(nu.Sequential(*writes))))
    return str(path)


async def _seed(store, path: str = "", root: str = ROOT) -> dict:
    """The Log tree under ``root``, pointed at ``path``; its planes' ids by spec name."""
    await store.run(ops.create_plane(planes.PLANE, plane_id=root))
    if path:
        await store.run(state.point(root, path))
    kids = await store.read(ops.children(root))
    names = [c.name for c in planes.PLANE.children]
    return {"nulog": root, **dict(zip(names, kids, strict=True))}


async def _cells(store, plane: str) -> dict:
    return {c["name"]: c["id"] for c in await store.read(ops.cell_rows(plane))}


def _run(store, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell, run as the kernel runs it, in its own task."""

    async def go() -> None:
        env = session_env("127.0.0.1:9")("s1")
        load = Space.cells[cell].prog.load(
            scope={"plane": plane, "cell": cell},
            rewrite=Rewrites(Reroot(plane, cell), env.rewrite),
        )
        term = nu.Frame(
            ops.Here,
            await store.run(nustd.kv.Snapshot(load, scope=Space)),
            plane=plane,
            cell=cell,
        )
        await nu.arun(term, store.ctx.bind(Session, browser))

    return asyncio.create_task(go())


async def _until(browser: _Browser, seen, most: float = 8.0) -> None:
    """Wait until ``seen(browser)`` holds. Fails the test after ``most`` seconds."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + most
    while not seen(browser):
        if loop.time() > deadline:
            pytest.fail(
                f"never drawn; last frames: {[(f.ref, f.payload) for f in browser.frames[-6:]]}"
            )
        await asyncio.sleep(0.02)


async def _stop(task: asyncio.Task) -> None:
    if task.done():
        task.result()  # a cell that ended raised: say so
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


# ---- registration -----------------------------------------------------------


def test_the_extension_registers_the_log_plane():
    reg = space_registry(extensions=[nulog.extension()], discover=False)
    assert "nulog" in reg.planes
    spec = reg.planes["nulog"]
    assert [c.name for c in spec.children] == ["nulog_messages", "nulog_metrics", "nulog_config"]
    assert spec.backend == "async" and all(c.backend == "async" for c in spec.children)


def test_the_entry_point_finds_it():
    assert "nulog" in space_registry().planes


def test_every_plane_opens_with_the_bar():
    for spec in (planes.PLANE, *planes.PLANE.children):
        assert dict(spec.cells)["bar"] == planes.BAR, spec.name


# ---- the cells, on a store --------------------------------------------------


async def test_every_cell_runs_and_draws(store, tmp_path):
    ids = await _seed(store, _write(tmp_path / "logs.db"))
    specs = [planes.PLANE, *planes.PLANE.children]
    drawn: dict[str, _Browser] = {}
    tasks = []
    for spec in specs:
        cells = await _cells(store, ids[spec.name])
        for name, _ in spec.cells:
            browser = drawn[f"{spec.name}.{name}"] = _Browser()
            tasks.append(_run(store, ids[spec.name], cells[name], browser))
    try:
        await _until(
            drawn["nulog.bar"], lambda b: any(p.get("label") == "reading" for p in b.drawn("pill"))
        )
        await _until(drawn["nulog_messages.messages"], lambda b: len(b.rows()) == 6)
        await _until(drawn["nulog_metrics.metrics"], lambda b: b.drawn("chart"))
        await _until(drawn["nulog.overview"], lambda b: b.drawn("table"))
        await _until(drawn["nulog_config.config"], lambda b: b.drawn("check"))
    finally:
        for t in tasks:
            await _stop(t)
    for name, browser in drawn.items():
        assert browser.frames, f"{name} drew nothing"

    # The bar says where it reads from, and links Config from every plane but Config.
    line = drawn["nulog.bar"].drawn("line")[-1]
    assert "2 streams, 1 series" in line and "logs.db" in line
    assert drawn["nulog.bar"].drawn("config")
    assert not drawn["nulog_config.bar"].drawn("config")

    # Messages: the first stream picked, its newest entry first, the tiles over it.
    m = drawn["nulog_messages.messages"]
    assert "app" in m.drawn("choice")
    rows = m.rows()
    assert rows[0]["message"] == "slow: 210 ms" and rows[0]["level"] == "warning"
    assert rows[-1]["fields"] == "i=0"
    assert m.drawn("warnings")[-1]["value"] == "1"

    assert any(
        [x["value"] for x in o["options"]] == ["app", "db"]
        for o in m.drawn("choice")
        if isinstance(o, dict) and o.get("options")
    )

    # Metrics: three points, in time order, the latest on its tile.
    c = drawn["nulog_metrics.metrics"]
    assert c.drawn("latest")[-1]["value"] == "0.3"
    assert c.drawn("drawn")[-1]["value"] == "3"

    # The overview lists both streams and the series.
    o = drawn["nulog.overview"]
    tables = {f.ref[-2]: f.payload["rows"] for f in o.frames if f.ref[-1] == "table"}
    assert [r["stream"] for r in tables["streams"]] == ["app", "db"]
    assert tables["streams"][1]["level"] == "error"
    assert [(r["series"], r["latest"]) for r in tables["series"]] == [("cpu", "0.3")]

    # Config shows the saved path and says the store opens.
    s = drawn["nulog_config.config"]
    assert s.drawn("path")[-1].endswith("logs.db")
    assert s.drawn("check")[-1]["variant"] == "ok"


async def test_messages_filter_the_read_and_open_an_entry(store, tmp_path):
    ids = await _seed(store, _write(tmp_path / "logs.db"))
    cells = await _cells(store, ids["nulog_messages"])
    b = _Browser()
    task = _run(store, ids["nulog_messages"], cells["messages"], b)
    try:
        await _until(b, lambda b: len(b.rows()) == 6)
        # Level: warnings only, of the same read.
        await _act(b, ("level", "choice"), "warning", value="warning")
        await _until(b, lambda b: [r["level"] for r in b.rows()] == ["warning"])
        assert b.drawn("shown")[-1] == {"value": "1", "delta": "of 6 read"}
        # Back to all, then text: any case, in the message.
        await _act(b, ("level", "choice"), "all", value="all")
        await _act(b, ("text", "choice"), "TICK 3", value="TICK 3")
        await _until(b, lambda b: [r["message"] for r in b.rows()] == ["tick 3"])
        # Oldest first, two of them.
        await _act(b, ("text", "choice"), "", value="")
        await _act(b, ("mode", "choice"), "take", value="take")
        await _act(b, ("count", "choice"), 2.0, value=2.0)
        await _until(b, lambda b: [r["message"] for r in b.rows()] == ["tick 0", "tick 1"])
        # A row clicked: the entry whole, its fields as JSON.
        key = b.rows()[1]["key"]
        await _act(b, "table", {"event": "row", "key": key, "row_index": 1})
        await _until(b, lambda b: b.drawn("json"))
        assert b.drawn("entry")[-1]["open"] is True
        shown = b.drawn("json")[-1]["value"]
        assert shown["message"] == "tick 1" and shown["fields"] == {"i": 1}
    finally:
        await _stop(task)


async def test_no_path_and_a_bad_path_say_so(store, tmp_path):
    ids = await _seed(store)
    cells = await _cells(store, ids["nulog_messages"])
    unset, bar = _Browser(), _Browser()
    tasks = [
        _run(store, ids["nulog_messages"], cells["messages"], unset),
        _run(store, ids["nulog_messages"], cells["bar"], bar),
    ]
    try:
        await _until(unset, lambda b: b.drawn("empty"))
        assert unset.drawn("empty")[-1]["label"] == "No store picked"
        # A bad path: the cells start over on the save and say what is wrong, nothing crashes.
        await store.run(state.point(ROOT, str(tmp_path / "nope")))
        await _until(unset, lambda b: b.drawn("empty")[-1]["label"] == "Nothing at this path")
        await _until(bar, lambda b: b.drawn("pill")[-1]["label"] == "Nothing at this path")
        assert bar.drawn("dot")[-1]["tone"] == "danger"
    finally:
        for t in tasks:
            await _stop(t)


async def test_a_saved_path_moves_every_cell_without_a_restart(store, tmp_path):
    first = _write(tmp_path / "one.db", n=2)
    second = _write(tmp_path / "two.db", n=7)
    ids = await _seed(store, first)
    msgs = await _cells(store, ids["nulog_messages"])
    form = await _cells(store, ids["nulog_config"])
    reading = _Browser()
    # The form as a person filled it in: the second store, a faster pace, a smaller read.
    filled = _Browser({"path": f"  {second}  ", "every": 0.3, "count": 4, "choice": "60"})
    tasks = [
        _run(store, ids["nulog_messages"], msgs["messages"], reading),
        _run(store, ids["nulog_config"], form["config"], filled),
    ]
    try:
        await _until(reading, lambda b: len(b.rows()) == 3)
        await _until(filled, lambda b: b.drawn("save"))
        await _until(filled, lambda b: b.drawn("path") and b.drawn("path")[-1] == first)
        await _act(filled, "save", {"event": "click"})
        # Saved, trimmed and held to bounds, and the messages cell reads the new store, 4 at a time.
        await _until(reading, lambda b: len(b.rows()) == 4 and b.rows()[1]["message"] == "tick 6")
        saved = await store.read(state.config(ROOT))
        assert saved["path"] == second
        assert (saved["every"], saved["count"], saved["window"]) == (0.3, 4, "60")
        assert saved["saved"] >= 2
    finally:
        for t in tasks:
            await _stop(t)


async def test_each_log_plane_reads_its_own_store(store, tmp_path):
    one = await _seed(store, _write(tmp_path / "one.db", n=2), root="log_one")
    two = await _seed(store, _write(tmp_path / "two.db", n=7), root="log_two")
    a, b = _Browser(), _Browser()
    tasks = [
        _run(
            store,
            one["nulog_messages"],
            (await _cells(store, one["nulog_messages"]))["messages"],
            a,
        ),
        _run(
            store,
            two["nulog_messages"],
            (await _cells(store, two["nulog_messages"]))["messages"],
            b,
        ),
    ]
    try:
        # 2 ticks and a warning in one, 7 and a warning in the other: newest first, each its own.
        await _until(a, lambda br: len(br.rows()) == 3)
        await _until(b, lambda br: len(br.rows()) == 8)
        assert (await store.read(state.config("log_one")))["path"].endswith("one.db")
        assert (await store.read(state.config("log_two")))["path"].endswith("two.db")
    finally:
        for t in tasks:
            await _stop(t)


async def _act(browser: _Browser, name: str, payload: object, value: object = None) -> None:
    """``browser.notify``, once something listens on ``name``."""
    await _until(browser, lambda b: b.notify(name, payload, value))
