"""What every Owlbridge cell shares: the store, the tables loaded from it, where pages are.

- :class:`Shop`: the one store, in the root plane's state (:data:`SHOP`). The tables live in
  it as shards: each a numpy record array's bytes under an int id in
  ``shards``, described in ``index`` (its table, rows, version, where it came
  from). History, the live stream and every import are shards of the same
  three tables.
- :func:`read`: a view of the tables, as a term. It fetches only the shards
  this process has not seen at their current version (the live ones, mostly),
  then runs a :mod:`.calc` function over them. Cells of one page share a
  process, so a page loads the tables once and follows only what moves.
- :func:`on_shop`: a cell's body over :data:`SHOP`, wherever the cell's
  page is, once the opening history is in. One Owlbridge per space: its
  root is keyed :data:`KEY`, so every cell finds it in one index read.
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
import nustd.ui
from nuspace import Space
from nuspace.devices import web
from nuspace.specs import PlaneSpec, WebOptions
from nuspace.utils import MintId

from .. import headless
from . import calc, gen
from .shop import PRODUCTS


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "IMPORTS",
    "KEY",
    "LIVE",
    "ROOT_ID",
    "SHOP",
    "Product",
    "Shop",
    "on_shop",
    "pack",
    "page_of",
    "read",
    "seed",
    "start",
    "unpack",
]


#: ``spec`` of the jobs and of the customer pages.
JOB, CUSTOMER = "data_job", "data_customer"

#: The root's key: one Owlbridge per space.
KEY = "nudemos_data"

#: The root's id, one index read. NULL while the space has no Owlbridge.
ROOT_ID = Space.indexes.plane_keys[KEY]

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


class Shop(nu.Shape):
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
    # The planes it made, by minted id: its two jobs by name, a customer's page by customer id.
    jobs = nustd.kv.DictRef.slot(str)
    customers = nustd.kv.DictRef.slot(str)


#: Owlbridge's store, in the root's state: what every cell and job reads and writes.
SHOP = nuspace.at.plane(KEY).state(Shop)


# --- where things are -----------------------------------------------------------------------


def _spec(plane: nu.StrArg) -> nu.Str:
    return Space.planes[plane].spec.fallback("")


def _children(root: nu.StrArg) -> nu.List:
    """``[[spec, id], ...]`` of the root's pages, in order. A read of its own children, a dozen."""
    kids = Space.planes[root].children.keys()
    return nu.List(kids).iter().map(lambda p: nu.List.of(_spec(nu.Str(p)), p)).to_list()


@nu.host
def _pick_page(kids: list[list[str]], name: str) -> str:
    return next((pid for made, pid in kids if made == name or made.endswith("." + name)), "")


def page_of(root: nu.StrArg, name: str) -> nu.Str:
    """The id of the page under the root made from the Plane named ``name``, eg ``data_revenue``. Bare read."""
    return nu.Str(_pick_page(_children(root), name))


@nu.host
def _page_map(kids: list[list[str]]) -> dict[str, str]:
    return {made.rsplit(".", 1)[-1].removeprefix("data_"): "/" + pid for made, pid in kids}


def pages(root: nu.StrArg) -> nu.Dict:
    """``{revenue: "/<id>", funnel: ..., ...}``: a link to every page under the root. Bare read."""
    return nu.Dict(_page_map(_children(root)))


def on_shop(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root)``, bracketed step by step over :data:`SHOP`, once the opening history is in.

    ``plane`` is the plane the cell runs on; every plane finds the one root by its key.
    """
    del plane

    def landed(root: nu.ObjectRef) -> nu.Nu:
        r = nu.Str(root)
        # Level: a missed notification would leave the page waiting for good.
        ready = nu.WaitUntil(
            nuspace.atomic(SHOP.ready.on_change()),
            nuspace.atomic(SHOP.ready.fallback(False)),
            after=nu.RECHECK_AFTER,
            every=nu.RECHECK_EVERY,
        )
        return ready >> nuspace.bracketed(build(r))

    return nu.let(nuspace.atomic(ROOT_ID), landed)


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
    """The index, and the stale shards of ``which`` fetched into this process. Over :data:`SHOP`."""
    index = SHOP.index.extract()
    ids = nu.List(stale(index, list(which)))
    got = ids.iter().map(lambda i: absorb(i, index, SHOP.shards[nu.Int(i)])).to_list()
    return index, got


def read(name: str, *args: object, tables: tuple[str, ...] = ("lines", "people")) -> nu.Nu:
    """``calc.<name>`` over the tables, as a term. Over :data:`SHOP`, unbracketed (the cell brackets it)."""
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
    return [SHOP.beat.on_change(), SHOP.filters.on_change()]


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
        row = SHOP.products[p["sku"]]
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
            d["shards"], lambda s: SHOP.shards.set_item(nu.Int(nu.List(s)[0]), nu.List(s)[1])
        )
        index = nu.ForEachDo(
            d["index"], lambda kv: SHOP.index[nu.Str(nu.List(kv)[0])].set(nu.List(kv)[1])
        )
        knobs = (
            _catalog()
            >> SHOP.filters.set(FILTERS)
            >> SHOP.traffic.set(TRAFFIC)
            >> SHOP.query.set(QUERY)
            >> SHOP.plan.set(PLAN)
            >> SHOP.cohort.set("Retention")
            >> SHOP.pace.set("Busy")
            >> SHOP.stop.set(False)
            >> SHOP.stream.set(d["stream"])
            >> SHOP.feed.set(d["feed"])
            >> SHOP.imports.set([])
            >> SHOP.inbox.set(inbox_dir())
            # Made empty, so the pages read it before the stream's first tick.
            >> SHOP.sold.init(nu.Dict.create())
        )
        return nuspace.atomic(shards >> index >> knobs >> SHOP.beat.set(1) >> SHOP.ready.set(True))

    def first(mine: nu.ObjectRef) -> nu.Nu:
        take = nu.IfDo(SHOP.seeded.is_null(), SHOP.seeded.set(True) >> mine.set(True))
        build = nu.let(opening(time.time()), write) >> start(root)
        return nuspace.atomic(take) >> nu.IfDo(nu.Bool(mine), build)

    return nu.let(False, first)


# --- the jobs -------------------------------------------------------------------------------


def job_of(root: nu.StrArg, name: str) -> nu.Str:
    """A job's plane id, ``stream`` or ``importer``, NULL before it is first started. Bare read."""
    del root
    return nu.Str(SHOP.jobs[name])


def _job(root: nu.StrArg, name: str, source: str) -> nu.Nu:
    """Job ``name`` under the root, made once and supervised: its id minted and kept first."""
    held = SHOP.jobs[name]

    def made(job: nu.ObjectRef) -> nu.Nu:
        jid = nu.Str(job)
        make = headless.make(
            jid, parent=root, name=name, backend="mp", spec=JOB, cells=[(name, source)]
        )
        return headless.once(jid, make) >> headless.supervise(jid)

    claimed = nuspace.atomic(held.init(MintId("p")))
    return claimed >> nu.let(nuspace.atomic(held), made)


def start(root: nu.StrArg) -> nu.Nu:
    """Both jobs made if they are not there, the stream's stop cleared, both supervised."""
    from .jobs import IMPORTER, STREAM

    clear = nuspace.atomic(SHOP.stop.set(False))
    return clear >> _job(root, "stream", STREAM) >> _job(root, "importer", IMPORTER)


def stop(root: nu.StrArg) -> nu.Nu:
    """Ask the stream to stop: it ends its loop at the next tick and says so."""
    del root
    return nuspace.atomic(SHOP.stop.set(True))


def live(root: nu.StrArg, name: str) -> nu.Bool:
    """Whether a job has a live run, False before it is first started. Bare read."""
    held = SHOP.jobs[name]
    return nu.Bool(nu.If(held.exists(), headless.live(job_of(root, name)), False))


# --- metrics and customer pages -------------------------------------------------------------


def metric(value: Callable[[calc.Tables, np.ndarray], float], fmt: str = "money") -> nu.Nu:
    """A metric a cell defines as ``value(t, keep)``, over the shared filters, as a term. Over :data:`SHOP`.

    ``fmt`` is how it reads: ``money``, ``pct``, ``count`` or ``ratio``.
    """

    def run(index: dict, got: list[int], f: dict) -> dict[str, Any] | None:
        del got
        t = tables(index, ("lines", "people"))
        return calc.metric(t, value, f or FILTERS, fmt, time.time()) if len(t.lines) else None

    index, got = loaded(("lines", "people"))
    return nu.host(run, name=f"Metric_{value.__name__}")(index, got, SHOP.filters.fallback({}))


def customer_page(root: nu.StrArg, cid: nu.StrArg) -> nu.Str:
    """A customer's page id, NULL before it is first opened. Bare read."""
    del root
    return nu.Str(SHOP.customers[cid])


def open_customer(
    root: nu.StrArg, cid: nu.StrArg, name: nu.StrArg, under: nu.StrArg, history: nustd.ui.HistoryRef
) -> nu.Nu:
    """Open a customer's page on ``history``, made under ``under`` (the Customers page) the first time.

    Its id is minted and kept in the store first, so a second open finds it.
    """
    from .pages import CUSTOMER_CELLS

    spec = PlaneSpec(
        CUSTOMER,
        "Customer",
        icon="user",
        cells=CUSTOMER_CELLS,
        web=WebOptions(editable=True, full_width=True),
        backend="async",
    )
    held = SHOP.customers[cid]

    def opened(page: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(page)
        about = nuspace.atomic(nuspace.plane.set_meta(pid, nu.Dict.of(customer=cid)))
        make = nuspace.specs.add_plane(spec, pid, parent=under, name=name) >> about
        return headless.once(pid, make) >> history.push(web.href(pid))

    claimed = nuspace.atomic(held.init(MintId("p")))
    return claimed >> nu.let(nuspace.atomic(held), opened)


def subject(plane: nu.StrArg) -> nu.Str:
    """What a page is about, from its meta: a customer page's customer id."""
    return nu.str(Space.planes[plane].meta["customer"].fallback("0"))
