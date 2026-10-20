"""What every Owlbridge cell shares: the store, the tables loaded from it, where pages are.

- :class:`Shop`: the one store, in the root plane's state. The tables live in
  it as shards: each a numpy record array's bytes under an int id in
  ``shards``, described in ``index`` (its table, rows, version, where it came
  from). History, the live stream and every import are shards of the same
  three tables.
- :func:`read`: a view of the tables, as a term. It fetches only the shards
  this process has not seen at their current version (the live ones, mostly),
  then runs a :mod:`.calc` function over them. Cells of one page share a
  process, so a page loads the tables once and follows only what moves.
- :func:`on_shop`: a cell's body with :class:`Shop` landed at the root,
  wherever the cell's page is, once the opening history is in.
- :func:`seed`: the first open: two years of history, the catalog, the jobs.
- :func:`start`, :func:`stop`: the stream and the importer, headless jobs.

Cells import this module, so their own sources stay short.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

import nu
import nuspace
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import snap

from . import calc, gen
from .shop import PRODUCTS


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "IMPORTS",
    "LIVE",
    "MADE_BY",
    "Product",
    "Shop",
    "go",
    "on_shop",
    "pack",
    "page_of",
    "read",
    "root_of",
    "seed",
    "start",
    "unpack",
]


#: What the root records as ``made_by``, and the ``made_by`` of the jobs and the customer pages.
MADE_BY, JOB, CUSTOMER = "nudemos.data", "data_job", "data_customer"

#: Where shard ids start: history below, then the stream's, then the imports'.
LIVE, IMPORTS = 1000, 900_000

#: Rows a live shard takes before the stream starts the next one.
CAP = {"lines": 1500, "people": 800, "events": 20000}


class Product(nu.Shape):
    """A row of the catalog sheet: what we sell it for, what it costs us, what is on the shelf."""

    name = nustd.kv.StrRef.slot()
    category = nustd.kv.StrRef.slot()
    price = nustd.kv.FloatRef.slot()
    cost = nustd.kv.FloatRef.slot()
    stock = nustd.kv.IntRef.slot()


class Shop(nuspace.PlaneState):
    """Owlbridge's store: the tables as shards, the catalog, the knobs every page reads."""

    # The tables: shard bytes by id, and per id {table, rows, v, origin, at}.
    shards = nustd.kv.Kh57Ref.slot(bytes)
    index = nustd.kv.DictRef.slot(nustd.kv.PrimitiveDictRef)
    # Moves on every write to the tables: what the dashboards follow.
    beat = nustd.kv.IntRef.slot()
    ready = nustd.kv.BoolRef.slot()
    seeded = nustd.kv.BoolRef.slot()
    # The catalog sheet, by sku.
    products = nustd.kv.DictRef.slot(Product)
    # The shared filters (range, channel, category), the funnel's and the events query.
    filters = nustd.kv.PrimitiveDictRef.slot()
    traffic = nustd.kv.PrimitiveDictRef.slot()
    query = nustd.kv.PrimitiveDictRef.slot()
    # The forecast's assumptions, and the cohort view's metric.
    plan = nustd.kv.PrimitiveDictRef.slot()
    cohort = nustd.kv.StrRef.slot()
    # The stream: how busy, whether to run, where it is, the newest orders, revenue per tick.
    pace = nustd.kv.StrRef.slot()
    stop = nustd.kv.BoolRef.slot()
    stream = nustd.kv.PrimitiveDictRef.slot()
    feed = nustd.kv.PrimitiveListRef.slot()
    sold = nustd.kv.Kh57Ref.slot(float)
    # The importer: the folder it watches, what it has loaded.
    inbox = nustd.kv.StrRef.slot()
    imports = nustd.kv.PrimitiveListRef.slot()
    importer = nustd.kv.PrimitiveDictRef.slot()


# --- where things are -----------------------------------------------------------------------


def _made_by(plane: nu.StrArg) -> nu.Str:
    return Space.planes[plane].props.made_by.fallback("")


def root_of(plane: nu.StrArg) -> nu.Str:
    """The Owlbridge root a plane belongs to: itself, its meta's ``base``, or its parent. Bare read."""
    base = nu.str(Space.planes[plane].meta["base"]).fallback(ops.parent(plane))
    return nu.Str(nu.If(_made_by(plane) == MADE_BY, plane, base))


@nu.host
def _pick_page(kids: list[list[str]], name: str) -> str:
    return next((pid for made, pid in kids if made == name or made.endswith("." + name)), "")


def page_of(root: nu.StrArg, name: str) -> nu.Str:
    """The id of the page under the root made from the Plane named ``name``, eg ``data_revenue``. Bare read."""
    kids = ops.children(root).iter().map(lambda p: nu.List.of(_made_by(nu.Str(p)), p)).to_list()
    return nu.Str(_pick_page(kids, name))


@nu.host
def _page_map(kids: list[list[str]]) -> dict[str, str]:
    return {made.rsplit(".", 1)[-1].removeprefix("data_"): "/" + pid for made, pid in kids}


def pages(root: nu.StrArg) -> nu.Dict:
    """``{revenue: "/<id>", funnel: ..., ...}``: a link to every page under the root. Bare read."""
    kids = ops.children(root).iter().map(lambda p: nu.List.of(_made_by(nu.Str(p)), p)).to_list()
    return nu.Dict(_page_map(kids))


def at(root: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`Shop`, landed on the root's state. Bare."""
    return ops.plane_state(root, term)


def on_shop(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root)`` with :class:`Shop` landed at the root, once the opening history is in."""

    def landed(root: nu.ObjectRef) -> nu.Nu:
        r = nu.Str(root)
        ready = nu.WaitReactive(
            snap(at(r, Shop.ready.on_change())), snap(at(r, Shop.ready.fallback(False)))
        )
        return ready >> ops.bracketed(at(r, build(r)))

    return nu.let(snap(root_of(plane)), landed)


def go(nav: nu.Nu, uri: nu.StrArg) -> nu.Nu:
    """Navigate the shell to ``uri`` (the shell follows back and forward only: push, push, back)."""
    return nu.let(uri, lambda u: nav.set(u) >> nav.set(nu.Str(u) + "?open") >> nav.back())


# --- shards ---------------------------------------------------------------------------------


def pack(arr: np.ndarray) -> bytes:
    """A table's rows as shard bytes."""
    return np.ascontiguousarray(arr).tobytes()


def unpack(table: str, blob: bytes) -> np.ndarray:
    """Shard bytes as the table's rows, read only."""
    return np.frombuffer(blob, dtype=gen.DTYPES[table])


#: This process's shards, by id: ``(version, table, rows)``.
_CACHE: dict[int, tuple[int, str, np.ndarray]] = {}
#: The last tables built per set of tables, with the shard versions they were built from.
_BUILT: dict[tuple[str, ...], tuple[tuple, calc.Tables]] = {}


@nu.host
def stale(index: dict[str, dict], tables: list[str]) -> list[int]:
    """Shard ids of ``tables`` this process has not loaded at their current version."""
    want = set(tables)
    return [
        int(k)
        for k, e in index.items()
        if e.get("table") in want and _CACHE.get(int(k), (-1,))[0] != e.get("v", 0)
    ]


@nu.host
def absorb(sid: int, index: dict[str, dict], blob: bytes) -> int:
    """Shard ``sid`` loaded from its bytes, at the version the index gives it."""
    e = index.get(str(sid), {})
    _CACHE[int(sid)] = (
        int(e.get("v", 0)),
        e.get("table", ""),
        unpack(e.get("table", "lines"), blob),
    )
    return int(sid)


def tables(index: dict[str, dict], which: tuple[str, ...]) -> calc.Tables:
    """The tables in ``which`` from this process's shards, the rest empty. Built again only when a shard moved."""
    ids = sorted(int(k) for k, e in index.items() if e.get("table") in which and int(k) in _CACHE)
    sig = tuple((i, _CACHE[i][0]) for i in ids)
    kept = _BUILT.get(which)
    if kept and kept[0] == sig:
        return kept[1]
    parts: dict[str, list[np.ndarray]] = {k: [] for k in gen.DTYPES}
    for i in ids:
        parts[_CACHE[i][1]].append(_CACHE[i][2])
    joined = {k: np.concatenate(v) if v else np.zeros(0, gen.DTYPES[k]) for k, v in parts.items()}
    t = calc.Tables(joined["lines"], joined["people"], joined["events"])
    _BUILT[which] = (sig, t)
    return t


@nu.host
def shaped(
    name: str, which: list[str], index: dict, loaded: list[int], args: list[object]
) -> object:
    """``calc.<name>(tables, *args, now)`` over the shards loaded, ``None`` before any are."""
    del loaded  # read first, so the shards are in before this runs
    t = tables(index, tuple(which))
    if not len(t.lines) and "lines" in which:
        return None
    return getattr(calc, name)(t, *args, time.time())


def loaded(which: tuple[str, ...]) -> tuple[nu.Nu, nu.Nu]:
    """The index, and the stale shards of ``which`` fetched into this process. Over :class:`Shop`."""
    index = Shop.index.extract()
    ids = nu.List(stale(index, list(which)))
    got = ids.iter().map(lambda i: absorb(i, index, Shop.shards[nu.Int(i)])).to_list()
    return index, got


def read(name: str, *args: object, tables: tuple[str, ...] = ("lines", "people")) -> nu.Nu:
    """``calc.<name>`` over the tables, as a term. Over :class:`Shop`, unbracketed (``redraws`` snaps it)."""
    index, got = loaded(tables)
    return shaped(name, list(tables), index, got, nu.List.of(*args))


@nu.host
def merged(d: dict, extra: dict) -> dict:
    """``d`` with ``extra`` over it."""
    return {**(d or {}), **(extra or {})}


@nu.host
def prepend(item: object, items: list, keep: int) -> list:
    """``item`` first, then ``items``, ``keep`` at most."""
    return [item, *(items or [])][:keep]


def changes() -> list[nu.Nu]:
    """What a dashboard follows: the tables, and the shared filters."""
    return [Shop.beat.on_change(), Shop.filters.on_change()]


# --- the first open -------------------------------------------------------------------------


#: Filters, traffic filters, the events query and the plan a fresh space opens with.
FILTERS = {"range": "Last 30 days", "channel": "All", "category": "All"}
TRAFFIC = {"range": "Last 30 days", "source": "All", "device": "All"}
QUERY = {"range": "All time", "kind": "All", "source": "All", "device": "All", "sku": "All"}
PLAN = {"price": 0, "marketing": 0, "churn": 6.5, "cafes": 0, "months": 12}


@nu.host
def opening(now: float) -> dict[str, Any]:
    """The history as shards: lines and events by month, people in one. Ids from 1."""
    h = gen.history(now)
    shards: list[list[Any]] = []
    index: dict[str, dict] = {}

    def add(table: str, rows: np.ndarray, origin: str) -> None:
        sid = len(shards) + 1
        shards.append([sid, pack(rows)])
        index[str(sid)] = {
            "table": table,
            "rows": len(rows),
            "v": 1,
            "origin": origin,
            "at": int(now),
        }

    for table in ("lines", "events"):
        rows = h[table]
        month = calc._month_key(rows["ts"])
        for m in np.unique(month):
            add(table, rows[month == m], "history")
    add("people", h["people"], "history")
    top = {
        k: int(h[k][c].max())
        for k, c in (("lines", "order"), ("people", "id"), ("events", "session"))
    }
    stream = {
        "shard": LIVE,
        "order": top["lines"] + 1,
        "person": top["people"] + 1,
        "session": top["events"] + 1,
        "live": {},
    }
    # The feed opens on the newest orders of the history, so the overview's table is never empty.
    t = calc.Tables(h["lines"], h["people"], h["events"])
    feed = calc.feed(h["lines"][-400:], t.name, 12)
    return {
        "shards": shards,
        "index": [[k, e] for k, e in index.items()],
        "stream": stream,
        "feed": feed,
    }


@nu.host
def inbox_dir() -> str:
    """``inbox`` in this space's directory, found from the store file the process holds open; else in the cwd."""
    try:
        for fd in Path("/proc/self/fd").iterdir():
            path = fd.readlink()
            if path.name == "state.sqlite":
                return str(path.parent / "inbox")
    except OSError:
        pass
    return str(Path.cwd() / "inbox")


def _catalog() -> nu.Nu:
    def one(p: dict) -> nu.Nu:
        row = Shop.products[p["sku"]]
        return (
            row.name.set(p["name"])
            >> row.category.set(p["category"])
            >> row.price.set(p["price"])
            >> row.cost.set(p["cost"])
            >> row.stock.set(p["stock"])
        )

    return nu.Sequential(*(one(p) for p in PRODUCTS))


def seed(root: nu.Str) -> nu.Nu:
    """The first open: the history, the catalog, the knobs, the jobs. Once, whichever tab gets there first."""

    def write(o: nu.ObjectRef) -> nu.Nu:
        d = nu.Dict(o)
        shards = nu.ForEachDo(
            d["shards"], lambda s: Shop.shards.set_item(nu.Int(nu.List(s)[0]), nu.List(s)[1])
        )
        index = nu.ForEachDo(
            d["index"], lambda kv: Shop.index[nu.Str(nu.List(kv)[0])].set(nu.List(kv)[1])
        )
        knobs = (
            _catalog()
            >> Shop.filters.set(FILTERS)
            >> Shop.traffic.set(TRAFFIC)
            >> Shop.query.set(QUERY)
            >> Shop.plan.set(PLAN)
            >> Shop.cohort.set("Retention")
            >> Shop.pace.set("Busy")
            >> Shop.stop.set(False)
            >> Shop.stream.set(d["stream"])
            >> Shop.feed.set(d["feed"])
            >> Shop.imports.set([])
            >> Shop.inbox.set(inbox_dir())
        )
        return ops.atomic_state(
            at(root, shards >> index >> knobs >> Shop.beat.set(1) >> Shop.ready.set(True))
        )

    def first(mine: nu.ObjectRef) -> nu.Nu:
        take = nu.IfDo(Shop.seeded.missing(), Shop.seeded.set(True) >> mine.set(True))
        build = nu.let(opening(time.time()), write) >> start(root)
        return ops.atomic_state(at(root, take)) >> nu.IfDo(nu.Bool(mine), build)

    return nu.let(False, first)


# --- the jobs -------------------------------------------------------------------------------


def job_of(root: nu.StrArg, name: str) -> nu.Str:
    """A job's plane id: fixed under the root, ``<root>.stream`` or ``<root>.importer``."""
    return nu.Str(root) + "." + name


def _job(root: nu.StrArg, name: str, source: str) -> nu.Nu:
    job = job_of(root, name)
    made = ops.add_plane(
        job, backend="mp", name=name, parent=root, ui=False, made_by=JOB, meta=nu.Dict.of(base=root)
    ) >> ops.add_cell(job, source, cell_id=job + "_main", name=name)
    return nu.IfDo(nu.Bool(snap(ops.plane_exists(job))).not_(), made)


def start(root: nu.StrArg) -> nu.Nu:
    """Both jobs made if they are not there, the stream's stop cleared, both supervised."""
    from .jobs import IMPORTER, STREAM

    clear = ops.atomic_state(at(root, Shop.stop.set(False)))
    return (
        _job(root, "stream", STREAM)
        >> _job(root, "importer", IMPORTER)
        >> clear
        >> nuspace.supervise(job_of(root, "stream"))
        >> nuspace.supervise(job_of(root, "importer"))
    )


def stop(root: nu.StrArg) -> nu.Nu:
    """Ask the stream to stop: it ends its loop at the next tick and says so."""
    return ops.atomic_state(at(root, Shop.stop.set(True)))


def live(root: nu.StrArg, name: str) -> nu.Bool:
    """Whether a job has a run now. Bare read."""
    return nu.Bool(Space.kernel.planes_running.contains(job_of(root, name)))


# --- metrics and customer pages -------------------------------------------------------------


def metric(value: Callable[[calc.Tables, np.ndarray], float], fmt: str = "money") -> nu.Nu:
    """A metric a cell defines as ``value(t, keep)``, over the shared filters, as a term. Over :class:`Shop`.

    ``fmt`` is how it reads: ``money``, ``pct``, ``count`` or ``ratio``.
    """

    def run(index: dict, got: list[int], f: dict) -> dict[str, Any] | None:
        del got
        t = tables(index, ("lines", "people"))
        return calc.metric(t, value, f or FILTERS, fmt, time.time()) if len(t.lines) else None

    index, got = loaded(("lines", "people"))
    return nu.host(run, name=f"Metric_{value.__name__}")(index, got, Shop.filters.fallback({}))


def customer_page(root: nu.StrArg, cid: nu.StrArg) -> nu.Str:
    """A customer's page id: the root's, then the customer's id."""
    return nu.Str(root) + ".customer." + nu.Str(cid)


def open_customer(
    root: nu.StrArg, cid: nu.StrArg, name: nu.StrArg, under: nu.StrArg, nav: nu.Nu
) -> nu.Nu:
    """Open a customer's page, made under ``under`` (the Customers page) the first time."""
    from nuspace import Plane

    from .pages import CUSTOMER_CELLS

    spec = Plane(CUSTOMER, "Customer", cells=CUSTOMER_CELLS, backend="async")
    pid = customer_page(root, cid)
    meta = nu.Dict.of(base=root, customer=cid, icon="lucide:user", editable=True, full_width=True)
    make = ops.create_plane(spec, parent=under, name=name, plane_id=pid) >> ops.set_plane_meta(
        pid, meta
    )
    return nu.IfDo(nu.Bool(snap(ops.plane_exists(pid))).not_(), make) >> go(nav, nu.Str("/") + pid)


def subject(plane: nu.StrArg) -> nu.Str:
    """What a page is about, from its meta: a customer page's customer id."""
    return nu.str(Space.planes[plane].meta["customer"]).fallback("0")
