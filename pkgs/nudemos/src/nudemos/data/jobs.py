"""The two jobs: the stream that keeps the shop selling, and the importer that loads what lands in the inbox.

Each is a headless plane under the root with one cell, run in its own
process and kept up by the supervisor. Both write shards into the root's
:class:`~.kit.Shop`, the same way the history was written, and move
``Shop.beat``, which every dashboard follows.

- :data:`STREAM`: every two seconds, a few orders and web sessions at the
  pace the Sources page sets, sold at the prices the Products sheet holds
  now. They go into the open live shard of each table (rewritten whole, a
  new one started when it is full), the feed, the stock, and a revenue point.
- :data:`IMPORTER`: watches ``inbox/`` in the space's folder. A CSV landing
  there (a wholesale order sheet, a marketplace settlement, a pop-up till
  export) is parsed, checked row by row, and loaded as a shard of its own;
  the file moves to ``inbox/done/`` and the import is logged with what it
  kept and what it turned down.

:func:`step` and :func:`load_csv` are plain functions over numpy, called as
host terms, so the tests run them without a space.
"""

from __future__ import annotations

import csv
import io
import os
import random
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

import nu

from . import calc, gen, kit
from .calc import WALK_IN
from .shop import CAFES, CITIES, FIRST, LAST, PRODUCTS, SKUS


__all__ = ["IMPORTER", "PACES", "STREAM", "load_csv", "step"]


#: Orders a second the stream sells at, by the pace the Sources page picks.
PACES = {"Quiet": 0.03, "Busy": 0.1, "Launch day": 0.5}

#: Sessions per order: what the web store converts at, roughly.
SESSIONS_PER_ORDER = 26


def _rows(table: str, sid: int | None) -> np.ndarray:
    hit = kit._CACHE.get(sid) if sid is not None else None
    return hit[2] if hit else np.zeros(0, gen.DTYPES[table])


def _poisson(r: random.Random, lam: float) -> int:
    n, p, limit = 0, 1.0, np.exp(-min(lam, 60))
    while True:
        p *= r.random()
        if p <= limit:
            return n
        n += 1


def step(
    index: dict[str, dict],
    stream: dict,
    catalog: dict[str, dict],
    feed: list,
    pace: str,
    now: float,
) -> dict[str, Any]:
    """One tick of the stream: what to write. Plain, over this process's shards (:data:`kit._CACHE`)."""
    r = random.Random(int(now * 1000))  # noqa: S311 -- made up data
    rng = np.random.default_rng(int(now * 1000))
    st = {**stream, "live": dict(stream.get("live") or {})}
    t = int(now)
    dt = min(10.0, max(0.5, now - float(st.get("at") or now - 2)))
    rate = PACES.get(pace, PACES["Busy"])
    n = _poisson(r, rate * dt)
    prices = [float((catalog.get(s) or p)["price"]) for s, p in zip(SKUS, PRODUCTS, strict=True)]
    known = int(st["person"]) - 1
    new = gen.orders_now(r, t, n, prices, int(st["order"]), int(st["person"]), known)
    ev = gen.events_now(rng, t, _poisson(r, rate * dt * SESSIONS_PER_ORDER), int(st["session"]))
    st["order"] = int(st["order"]) + n
    st["person"] = int(st["person"]) + len(new["people"])
    st["session"] = int(st["session"]) + (
        int(ev["session"].max()) - int(st["session"]) + 1 if len(ev) else 0
    )
    shards, entries = [], []
    for table, rows in (("lines", new["lines"]), ("people", new["people"]), ("events", ev)):
        if not len(rows):
            continue
        sid = st["live"].get(table)
        cur = _rows(table, sid)
        if sid is None or len(cur) + len(rows) > kit.CAP[table]:
            sid, cur = int(st["shard"]), np.zeros(0, gen.DTYPES[table])
            st["shard"] = sid + 1
        merged = np.concatenate([cur, rows])
        v = int((index.get(str(sid)) or {}).get("v", 0)) + 1
        kit._CACHE[sid] = (v, table, merged)
        shards.append([sid, kit.pack(merged)])
        entries.append(
            [str(sid), {"table": table, "rows": len(merged), "v": v, "origin": "live", "at": t}]
        )
        st["live"][table] = sid
    lines = new["lines"]
    money = lines["qty"] * lines["price"] * (1 - lines["disc"])
    sold = (
        np.bincount(lines["sku"], weights=lines["qty"], minlength=len(SKUS))
        if len(lines)
        else np.zeros(len(SKUS))
    )
    stock = [
        [s, max(0, int((catalog.get(s) or {}).get("stock") or 0) - int(sold[i]))]
        for i, s in enumerate(SKUS)
        if sold[i] and PRODUCTS[i]["category"] != "Subscription"
    ]
    names = {int(p["id"]): p for p in new["people"]}
    tables = kit.tables(index, ("people",))

    def name(who: int) -> str:
        p = names.get(who)
        return f"{FIRST[p['first']]} {LAST[p['last']]} (new)" if p is not None else tables.name(who)

    fresh = calc.feed(lines, name)
    st["at"] = now
    st["status"] = "running"
    st["rate"] = rate
    return {
        "shards": shards,
        "index": entries,
        "stream": st,
        "stock": stock,
        "feed": (fresh[::-1] + list(feed))[:24],
        "sold": round(float(money.sum()), 2),
        "at": t,
        "moved": bool(shards),
    }


tick = nu.host(step, name="StreamStep")


# --- the importer ---------------------------------------------------------------------------


def pending(inbox: str) -> list[str]:
    """CSV files waiting in the inbox, oldest first."""
    try:
        files = [p for p in Path(inbox).iterdir() if p.suffix.lower() == ".csv" and p.is_file()]
    except OSError:
        return []
    return [p.name for p in sorted(files, key=lambda p: p.stat().st_mtime)]


def _when(text: str) -> int:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(text.strip(), fmt).timestamp()) + (
                12 * 3600 if fmt == "%Y-%m-%d" else 0
            )
        except ValueError:
            continue
    raise ValueError(f"no date in {text!r}")


def load_csv(
    name: str, text: str, counters: dict, cafes: dict[str, int], now: float
) -> dict[str, Any]:
    """A CSV export parsed and checked: the lines and people it adds, and the rows it turned down.

    Three shapes, told apart by their header: a wholesale sheet (cafe, sku,
    bags), a marketplace settlement (order id, buyer, city), a till export
    (time, item, qty, price). Anything else is turned down whole.
    """
    started = time.perf_counter()
    rows = list(csv.reader(io.StringIO(text)))
    head = [h.strip().lower() for h in rows[0]] if rows else []
    body = rows[1:]
    order, person = int(counters.get("order", 5_000_000)), int(counters.get("person", 5_000_000))
    lines: list[tuple] = []
    people: list[tuple] = []
    bad: list[str] = []
    orders: dict[str, int] = {}
    buyers: dict[str, int] = {}
    kind = "unknown"

    def sku_of(text: str) -> int:
        if text.strip() not in SKUS:
            raise ValueError(f"unknown sku {text.strip()!r}")
        return SKUS.index(text.strip())

    def number(text: str) -> float:
        try:
            return float(text)
        except ValueError:
            raise ValueError(f"not a number: {text!r}") from None

    for n, row in enumerate(body, start=2):
        if not any(c.strip() for c in row):
            continue
        rec = dict(zip(head, row, strict=False))
        try:
            if {"cafe", "sku", "bags"} <= set(head):
                kind = "wholesale"
                cafe = rec["cafe"].strip()
                if cafe not in cafes:
                    raise ValueError(f"no wholesale account for {cafe!r}")
                s, qty = sku_of(rec["sku"]), int(number(rec["bags"]))
                key = f"{cafe}|{rec['date']}"
                if key not in orders:
                    orders[key] = order
                    order += 1
                price = number(rec.get("unit_price") or str(PRODUCTS[s]["price"] * gen.WHOLESALE))
                lines.append(
                    (
                        orders[key],
                        _when(rec["date"]),
                        cafes[cafe],
                        s,
                        qty,
                        price,
                        PRODUCTS[s]["cost"],
                        3,
                        0.0,
                    )
                )
            elif {"order_id", "buyer", "sku"} <= set(head):
                kind = "marketplace"
                s, qty, price = (
                    sku_of(rec["sku"]),
                    int(number(rec["qty"])),
                    number(rec["item_price"]),
                )
                buyer = rec["buyer"].strip()
                if buyer not in buyers:
                    first, _, last = buyer.partition(" ")
                    fi = FIRST.index(first) if first in FIRST else 0
                    li = next(
                        (i for i, x in enumerate(LAST) if x.startswith(last.strip(". ")[:1])), 0
                    )
                    city = next(
                        (i for i, (c, _) in enumerate(CITIES) if c == rec.get("city", "").strip()),
                        0,
                    )
                    buyers[buyer] = person
                    people.append((person, _when(rec["placed_at"]), 0, city, fi, li, 5))
                    person += 1
                oid = rec["order_id"].strip()
                if oid not in orders:
                    orders[oid] = order
                    order += 1
                lines.append(
                    (
                        orders[oid],
                        _when(rec["placed_at"]),
                        buyers[buyer],
                        s,
                        qty,
                        price,
                        PRODUCTS[s]["cost"],
                        2,
                        0.0,
                    )
                )
            elif {"time", "item", "qty", "price"} <= set(head):
                kind = "pop-up"
                s, qty, price = sku_of(rec["item"]), int(number(rec["qty"])), number(rec["price"])
                lines.append(
                    (order, _when(rec["time"]), WALK_IN, s, qty, price, PRODUCTS[s]["cost"], 4, 0.0)
                )
                order += 1
            else:
                bad.append("the header matches no export we know")
                break
        except (KeyError, ValueError) as e:
            bad.append(f"row {n}: {e}")
    la = np.array(lines, dtype=gen.DTYPES["lines"]) if lines else np.zeros(0, gen.DTYPES["lines"])
    pa = (
        np.array(people, dtype=gen.DTYPES["people"])
        if people
        else np.zeros(0, gen.DTYPES["people"])
    )
    money = float((la["qty"] * la["price"]).sum()) if len(la) else 0.0
    return {
        "lines": la,
        "people": pa,
        "counters": {**counters, "order": order, "person": person},
        "log": {
            "file": name,
            "kind": kind,
            "rows": len([r for r in body if any(c.strip() for c in r)]),
            "loaded": len(lines),
            "rejected": len(bad),
            "orders": len({ln[0] for ln in lines}),
            "revenue": round(money, 2),
            "errors": bad[:6],
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "pid": os.getpid(),
            "at": int(now),
        },
    }


@nu.host
def waiting(inbox: str) -> list[str]:
    """:func:`pending`, as a term."""
    return pending(inbox)


@nu.host
def ingest(inbox: str, name: str, index: dict, importer: dict, now: float) -> dict[str, Any]:
    """One file from the inbox, loaded: the shards to write, the index entries, the log line."""
    path = Path(inbox) / name
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        text = ""
        note = str(e)
    else:
        note = ""
    people = kit.tables(index, ("people",)).people
    cafes = {CAFES[int(p["last"]) % len(CAFES)]: int(p["id"]) for p in people[people["kind"] == 2]}
    counters = dict(importer.get("counters") or {})
    out = load_csv(name, text, counters, cafes, now)
    shard = int(counters.get("shard", kit.IMPORTS))
    shards, entries = [], []
    for table in ("lines", "people"):
        rows = out[table]
        if len(rows):
            shards.append([shard, kit.pack(rows)])
            entries.append(
                [
                    str(shard),
                    {
                        "table": table,
                        "rows": len(rows),
                        "v": 1,
                        "origin": f"import: {name}",
                        "at": int(now),
                    },
                ]
            )
            shard += 1
    log = {**out["log"], "shards": [int(s) for s, _ in shards]}
    if note:
        log["errors"] = [note]
    state = {
        **importer,
        "counters": {**out["counters"], "shard": shard},
        "files": int(importer.get("files") or 0) + 1,
        "last": int(now),
    }
    return {"shards": shards, "index": entries, "log": log, "importer": state}


@nu.host
def archive(inbox: str, name: str) -> str:
    """Move an imported file into ``inbox/done/``, kept as it came."""
    done = Path(inbox) / "done"
    done.mkdir(parents=True, exist_ok=True)
    src = Path(inbox) / name
    if src.exists():
        shutil.move(str(src), str(done / name))
    return name


@nu.host
def ensure(inbox: str) -> str:
    Path(inbox).mkdir(parents=True, exist_ok=True)
    return inbox


@nu.host
def pid() -> int:
    return os.getpid()


# --- the cells ------------------------------------------------------------------------------


STREAM = """\
import nu
import nustd.time
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.data import kit
from nudemos.data.jobs import tick
from nudemos.data.kit import Shop, at

#: Seconds between two ticks.
EVERY = 2.0


def written(w):
    d = nu.Dict(w)
    each = lambda key, write: nu.ForEachDo(d[key], lambda x: write(nu.List(x)))
    return (
        each("shards", lambda s: Shop.shards.set_item(nu.Int(s[0]), s[1]))
        >> each("index", lambda e: Shop.index[nu.Str(e[0])].set(e[1]))
        >> each("stock", lambda s: Shop.products[nu.Str(s[0])].stock.set(nu.Int(s[1])))
        >> Shop.stream.set(d["stream"]) >> Shop.feed.set(d["feed"])
        >> Shop.sold.set_item(nu.Int(d["at"]), nu.Float(d["sold"]))
        >> nu.IfDo(nu.Bool(d["moved"]), Shop.beat.set(Shop.beat.fallback(0) + 1))
    )


def turn(root):
    # The shards this process has not seen come in first, outside the commit; the tick reads and writes in one.
    def go(got):
        index = Shop.index.extract()
        step = tick(index, Shop.stream.fallback({}), Shop.products.extract(), Shop.feed.fallback([]),
                    Shop.pace.fallback("Busy"), nustd.time.time())
        return ops.atomic_state(at(root, nu.let(step, written)))

    return nu.let(snap(at(root, kit.loaded(("lines", "people", "events"))[1])), go)


def said(root, status):
    return ops.atomic_state(at(root, Shop.stream.set(kit.merged(Shop.stream.fallback({}), nu.Dict.of(status=status)))))


def out(plane):
    def run(root):
        going = snap(at(root, Shop.stop.fallback(False)).not_())
        return said(root, "running") >> nu.WhileDo(going, turn(root) >> nu.Delay(EVERY)) >> said(root, "stopped")

    return nu.let(snap(kit.root_of(plane)), lambda root: run(nu.Str(root)))
"""


IMPORTER = """\
import nu
import nustd.time
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.data import kit
from nudemos.data.jobs import archive, ensure, ingest, pid, waiting
from nudemos.data.kit import Shop, at

#: Seconds between two looks at the inbox.
EVERY = 1.5


def written(w):
    d = nu.Dict(w)
    each = lambda key, write: nu.ForEachDo(d[key], lambda x: write(nu.List(x)))
    log = kit.prepend(d["log"], Shop.imports.fallback([]), 40)
    return (
        each("shards", lambda s: Shop.shards.set_item(nu.Int(s[0]), s[1]))
        >> each("index", lambda e: Shop.index[nu.Str(e[0])].set(e[1]))
        >> Shop.imports.set(log) >> Shop.importer.set(d["importer"])
        >> Shop.beat.set(Shop.beat.fallback(0) + 1)
    )


def one(root, inbox, name):
    # Parsed and checked here, in this job's own process, loaded in one commit, then the file put away.
    def load(got):
        made = ingest(inbox, name, Shop.index.extract(), Shop.importer.fallback({}), nustd.time.time())
        return ops.atomic_state(at(root, nu.let(made, written))) >> archive(inbox, name)

    return nu.let(snap(at(root, kit.loaded(("people",))[1])), load)


def look(root, inbox):
    return nu.ForEachDo(nu.List(waiting(inbox)), lambda name: one(root, inbox, nu.Str(name))) >> nu.Delay(EVERY)


def out(plane):
    def run(root, inbox):
        hello = ops.atomic_state(at(root, Shop.importer.set(
            kit.merged(Shop.importer.fallback({}), nu.Dict.of(status="watching", pid=pid(), since=nustd.time.time()))
        )))
        return ensure(inbox) >> hello >> nu.ForeverDo(look(root, inbox))

    def landed(root):
        r = nu.Str(root)
        return nu.let(snap(at(r, Shop.inbox.fallback(""))), lambda inbox: run(r, nu.Str(inbox)))

    return nu.let(snap(kit.root_of(plane)), landed)
"""
