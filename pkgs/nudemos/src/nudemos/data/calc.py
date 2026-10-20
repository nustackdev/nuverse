"""What every dashboard computes, from the tables as numpy record arrays.

Plain numpy, nothing Nu: each function takes :class:`Tables` and the knobs a
page has, and returns plain data shaped for the widgets (rows, series,
strings). The cells call them through :mod:`.kit`, which keeps the tables
loaded in the page's process.

Money is ``qty * price * (1 - disc)`` per line; margin takes the unit cost off.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

import numpy as np

from .gen import DAY, DTYPES, OFFSET, day_of, midnight
from .shop import (
    CAFES,
    CATEGORIES,
    CHANNELS,
    CITIES,
    DEVICES,
    FIRST,
    KINDS,
    LAST,
    PRODUCTS,
    SKUS,
    SOURCES,
    STAGES,
)


if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")

__all__ = [
    "RANGES",
    "Tables",
    "cohorts",
    "customer",
    "customers",
    "events",
    "forecast",
    "kpis",
    "money",
    "products",
    "revenue",
    "today",
]


#: The date ranges a filter offers, in days (0: everything).
RANGES = {
    "Last 7 days": 7,
    "Last 30 days": 30,
    "Last 90 days": 90,
    "Last 12 months": 365,
    "All time": 0,
}

#: The customer on pop-up market sales: whoever walked up.
WALK_IN = 0

_CAT = np.array([CATEGORIES.index(p["category"]) for p in PRODUCTS])


@dataclass
class Tables:
    """The shop's tables, every shard of each joined in order, and what is derived once from them."""

    lines: np.ndarray
    people: np.ndarray
    events: np.ndarray
    _memo: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> Tables:
        """No rows in any table."""
        return cls(*(np.zeros(0, DTYPES[k]) for k in ("lines", "people", "events")))

    def memo(self, key: str, make: Callable[[], T]) -> T:
        """``make()``, computed once per tables."""
        if key not in self._memo:
            self._memo[key] = make()
        return self._memo[key]

    @property
    def money(self) -> np.ndarray:
        """What each line brought in, after its discount."""
        return self.memo(
            "money", lambda: self.lines["qty"] * self.lines["price"] * (1 - self.lines["disc"])
        )

    @property
    def margin(self) -> np.ndarray:
        """What each line left after its unit cost."""
        return self.memo("margin", lambda: self.money - self.lines["qty"] * self.lines["cost"])

    @property
    def day(self) -> np.ndarray:
        """Each line's local day number."""
        return self.memo("day", lambda: day_of(self.lines["ts"].astype(np.int64)))

    def person_row(self, ids: np.ndarray) -> np.ndarray:
        """Rows in ``people`` for customer ids, -1 for ids it does not hold."""

        def index() -> tuple[np.ndarray, np.ndarray]:
            order = np.argsort(self.people["id"], kind="stable")
            return self.people["id"][order], order

        keys, order = self.memo("people_index", index)
        pos = np.clip(np.searchsorted(keys, ids), 0, max(len(keys) - 1, 0))
        found = len(keys) > 0
        hit = (keys[pos] == ids) if found else np.zeros(len(ids), bool)
        return np.where(hit, order[pos] if found else -1, -1)

    def name(self, pid: int) -> str:
        """A customer's name: a person's, a cafe's, or the pop-up market's walk-ins."""
        if pid == WALK_IN:
            return "Walk-in, pop-up market"
        row = self.person_row(np.array([pid]))[0]
        if row < 0:
            return f"Customer {pid}"
        p = self.people[row]
        if p["kind"] == 2:
            return CAFES[p["last"] % len(CAFES)]
        return f"{FIRST[p['first'] % len(FIRST)]} {LAST[p['last'] % len(LAST)]}"


# --- formatting -----------------------------------------------------------------------------


def money(x: float, cents: bool = False) -> str:
    """``$12,480``, ``$1.2M``; with ``cents`` ``$38.40``."""
    if cents:
        return f"${x:,.2f}"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.2f}M"
    return f"${x:,.0f}"


def pct(x: float, digits: int = 1) -> str:
    return f"{x * 100:.{digits}f}%"


def delta(now: float, before: float) -> tuple[str, str]:
    """A change as ``("+12.4% vs prior", "up")``."""
    if not before:
        return "", "flat"
    d = now / before - 1
    return (
        f"{'+' if d >= 0 else ''}{d * 100:.1f}% vs prior",
        "up" if d > 0.005 else "down" if d < -0.005 else "flat",
    )


def _ms(day: int) -> int:
    """A local day number as the epoch ms of its midnight, for time axes."""
    return int((day * DAY - OFFSET) * 1000)


def _date(ts: int, fmt: str = "%b %d") -> str:
    return datetime.fromtimestamp(ts).strftime(fmt).replace(" 0", " ")


# --- filters --------------------------------------------------------------------------------


def window(t: Tables, days: int, now: float) -> np.ndarray:
    """Lines in the last ``days`` days (today counting as one), all of them for 0."""
    if not days:
        return np.ones(len(t.lines), bool)
    return t.day > day_of(int(now)) - days


def picked(t: Tables, f: dict, now: float) -> np.ndarray:
    """Lines a filter keeps: range, channel, category."""
    keep = window(t, RANGES.get(f.get("range", ""), 30), now)
    if f.get("channel", "All") in CHANNELS:
        keep &= t.lines["channel"] == CHANNELS.index(f["channel"])
    if f.get("category", "All") in CATEGORIES:
        keep &= _CAT[t.lines["sku"]] == CATEGORIES.index(f["category"])
    return keep


def before(t: Tables, f: dict, now: float) -> np.ndarray:
    """The same filter, one range earlier: what a delta compares against."""
    days = RANGES.get(f.get("range", ""), 30)
    if not days:
        return np.zeros(len(t.lines), bool)
    shifted = {**f}
    keep = picked(t, shifted, now - days * DAY)
    return keep & ~window(t, days, now)


def _orders(t: Tables, keep: np.ndarray) -> int:
    return len(np.unique(t.lines["order"][keep]))


def totals(t: Tables, keep: np.ndarray) -> dict[str, float]:
    revenue = float(t.money[keep].sum())
    orders = _orders(t, keep)
    return {
        "revenue": revenue,
        "orders": orders,
        "aov": revenue / orders if orders else 0.0,
        "margin": float(t.margin[keep].sum()) / revenue if revenue else 0.0,
        "units": int(t.lines["qty"][keep].sum()),
        "customers": len(np.unique(t.lines["customer"][keep])),
    }


# --- the overview ---------------------------------------------------------------------------


def feed(lines: np.ndarray, name: Callable[[int], str], limit: int = 24) -> list[dict[str, Any]]:
    """The newest ``limit`` orders among ``lines``, newest first, as the overview's feed rows."""
    money_ = lines["qty"] * lines["price"] * (1 - lines["disc"])
    out = []
    for o in np.unique(lines["order"])[::-1][:limit]:
        k = lines["order"] == o
        items = ", ".join(
            f"{int(q)} x {PRODUCTS[s]['name']}" if q > 1 else PRODUCTS[s]["name"]
            for s, q in zip(lines["sku"][k], lines["qty"][k], strict=True)
        )
        out.append(
            {
                "order": f"#{int(o)}",
                "time": datetime.fromtimestamp(int(lines["ts"][k].max())).strftime("%H:%M:%S"),
                "customer": name(int(lines["customer"][k][0])),
                "items": items,
                "channel": CHANNELS[int(lines["channel"][k][0])],
                "total": round(float(money_[k].sum()), 2),
            }
        )
    return out


def today(t: Tables, now: float) -> dict[str, Any]:
    """Today so far against the same hours a week ago, hour by hour, cumulative."""
    d0 = midnight(now)
    hours = int((now - d0) // 3600) + 1
    out: dict[str, list] = {"Today": [], "Same day last week": []}
    for label, start in (("Today", d0), ("Same day last week", d0 - 7 * DAY)):
        m = (t.lines["ts"] >= start) & (t.lines["ts"] < start + DAY)
        h = ((t.lines["ts"][m] - start) // 3600).astype(int)
        cum = np.cumsum(np.bincount(h, weights=t.money[m], minlength=24)[:24])
        upto = hours if label == "Today" else 24
        out[label] = [[f"{k:02d}:00", round(float(cum[k]), 2)] for k in range(upto)]
    return out


def kpis(t: Tables, now: float) -> dict[str, dict[str, str]]:
    """The overview's tiles: value, delta, trend each."""
    d0 = midnight(now)
    ts = t.lines["ts"]
    todays = ts >= d0
    week_ago = (ts >= d0 - 7 * DAY) & (ts < now - 7 * DAY)
    f30 = {"range": "Last 30 days"}
    now30, was30 = picked(t, f30, now), before(t, f30, now)
    a, b = totals(t, now30), totals(t, was30)
    rev_today, rev_week = float(t.money[todays].sum()), float(t.money[week_ago].sum())
    ev = t.events
    e30 = ev["ts"] >= d0 - 29 * DAY
    e60 = (ev["ts"] >= d0 - 59 * DAY) & ~e30
    conv = lambda m: float((ev["kind"][m] == 4).sum()) / max(1, int((ev["kind"][m] == 0).sum()))  # noqa: E731
    subs_now, subs_then = _subscribers(t, now), _subscribers(t, now - 30 * DAY)

    def tile(value: str, d: tuple[str, str]) -> dict[str, str]:
        return {"value": value, "delta": d[0], "trend": d[1]}

    return {
        "today": tile(money(rev_today), _same(rev_today, rev_week)),
        "orders": tile(f"{_orders(t, todays):,}", _same(_orders(t, todays), _orders(t, week_ago))),
        "revenue": tile(money(a["revenue"]), delta(a["revenue"], b["revenue"])),
        "aov": tile(money(a["aov"], cents=True), delta(a["aov"], b["aov"])),
        "conversion": tile(pct(conv(e30), 2), delta(conv(e30), conv(e60))),
        "subscribers": tile(f"{subs_now:,}", delta(subs_now, subs_then)),
        "margin": tile(pct(a["margin"]), delta(a["margin"], b["margin"])),
        "new": tile(
            f"{int((t.people['ts'] >= d0).sum()):,}",
            _same(
                float((t.people["ts"] >= d0).sum()),
                float(((t.people["ts"] >= d0 - 7 * DAY) & (t.people["ts"] < now - 7 * DAY)).sum()),
            ),
        ),
    }


def _same(now: float, then: float) -> tuple[str, str]:
    d, trend = delta(now, then)
    return d.replace("vs prior", "vs last week"), trend


def _subscribers(t: Tables, at: float) -> int:
    """Subscribers with a renewal in the 35 days before ``at``."""
    m = (t.lines["channel"] == 1) & (t.lines["ts"] <= at) & (t.lines["ts"] > at - 35 * DAY)
    return len(np.unique(t.lines["customer"][m]))


def overview(t: Tables, now: float) -> dict[str, Any]:
    """The overview's two charts: today by the hour, the last 30 days by channel."""
    return {"today": today(t, now), "month": daily(t, 30, now)}


def daily(t: Tables, days: int, now: float) -> dict[str, list]:
    """Revenue per day over the last ``days`` days, a series per channel."""
    end = day_of(int(now))
    m = t.day > end - days
    out = {}
    for c, name in enumerate(CHANNELS):
        k = m & (t.lines["channel"] == c)
        if not k.any() and name == "Pop-up":
            continue
        per = np.bincount(t.day[k] - (end - days + 1), weights=t.money[k], minlength=days)[:days]
        out[name] = [[_ms(end - days + 1 + i), round(float(v), 2)] for i, v in enumerate(per)]
    return out


# --- revenue --------------------------------------------------------------------------------


def revenue(t: Tables, f: dict, now: float) -> dict[str, Any]:
    """The revenue page: tiles, the curve by channel, by category, and the months as a sheet."""
    keep, was = picked(t, f, now), before(t, f, now)
    a, b = totals(t, keep), totals(t, was)
    days = (
        RANGES.get(f.get("range", ""), 30) or int(day_of(int(now)) - t.day.min() + 1)
        if len(t.day)
        else 1
    )
    week = days > 120
    bucket = (t.day // 7 * 7) if week else t.day
    series = {}
    lo = int(bucket[keep].min()) if keep.any() else 0
    for c, name in enumerate(CHANNELS):
        k = keep & (t.lines["channel"] == c)
        if not k.any() and (f.get("channel", "All") != "All" or name == "Pop-up"):
            continue
        step = 7 if week else 1
        per = np.bincount(
            (bucket[k] - lo) // step,
            weights=t.money[k],
            minlength=(int(bucket[keep].max()) - lo) // step + 1 if keep.any() else 0,
        )
        series[name] = [[_ms(lo + i * step), round(float(v), 2)] for i, v in enumerate(per)]
    by_cat = np.bincount(
        _CAT[t.lines["sku"][keep]], weights=t.money[keep], minlength=len(CATEGORIES)
    )
    cats = [
        [c, round(float(v), 2)]
        for c, v in sorted(zip(CATEGORIES, by_cat, strict=True), key=lambda x: -x[1])
    ]
    tiles = {
        "revenue": (money(a["revenue"]), *delta(a["revenue"], b["revenue"])),
        "orders": (f"{a['orders']:,}", *delta(a["orders"], b["orders"])),
        "aov": (money(a["aov"], cents=True), *delta(a["aov"], b["aov"])),
        "margin": (pct(a["margin"]), *delta(a["margin"], b["margin"])),
        "units": (f"{a['units']:,}", *delta(a["units"], b["units"])),
    }
    year = picked(t, {**f, "range": "All time"}, now) & (t.lines["ts"] >= _month_start(now, 12))
    return {"tiles": tiles, "series": series, "cats": cats, "months": months(t, year), "week": week}


def _month_start(now: float, back: int) -> int:
    """The first second of the month ``back`` months before this one."""
    d = datetime.fromtimestamp(now)
    m = d.year * 12 + d.month - 1 - back
    return int(datetime(m // 12, m % 12 + 1, 1).timestamp())


def months(t: Tables, keep: np.ndarray) -> list[dict[str, Any]]:
    """The last twelve calendar months under the filter: revenue, orders, AOV, margin, change on the month before.

    The month is a derived column like the rest: computed from the lines, never stored.
    """
    ts = t.lines["ts"][keep]
    if not len(ts):
        return []
    key = _month_key(ts)
    rows, prev = [], None
    for m in np.unique(key):
        sel = np.zeros(len(t.lines), bool)
        sel[np.flatnonzero(keep)[key == m]] = True
        tt = totals(t, sel)
        label = datetime(int(m) // 12, int(m) % 12 + 1, 1).strftime("%b %Y")
        rows.append(
            {
                "month": label + (" so far" if m == key.max() else ""),
                "revenue": round(tt["revenue"]),
                "orders": tt["orders"],
                "aov": round(tt["aov"], 2),
                "margin": round(tt["margin"] * 100, 1),
                "change": round((tt["revenue"] / prev - 1) * 100, 1) if prev else None,
            }
        )
        prev = tt["revenue"]
    return rows[::-1][:12]


def _month_key(ts: np.ndarray) -> np.ndarray:
    """Year * 12 + month - 1 for each timestamp, local time."""
    days = (ts.astype(np.int64) + OFFSET) // DAY
    dt = days.astype("datetime64[D]").astype("datetime64[M]").astype(np.int64)
    return dt + 1970 * 12


# --- funnel ---------------------------------------------------------------------------------


def _event_mask(t: Tables, q: dict, now: float) -> np.ndarray:
    ev = t.events
    days = RANGES.get(q.get("range", ""), 30)
    keep = ev["ts"] >= midnight(now) - (days - 1) * DAY if days else np.ones(len(ev), bool)
    if q.get("source", "All") in SOURCES:
        keep &= ev["source"] == SOURCES.index(q["source"])
    if q.get("device", "All") in DEVICES:
        keep &= ev["device"] == DEVICES.index(q["device"])
    return keep


def funnel(t: Tables, q: dict, now: float) -> dict[str, Any]:
    """Sessions down the funnel, and the purchase rate by source, by device, by day."""
    started = time.perf_counter()
    ev, keep = t.events, _event_mask(t, q, now)
    kind = ev["kind"][keep]
    # A session reached a stage if it has an event of it: count distinct sessions per stage.
    stages = []
    for k, name in enumerate(STAGES):
        n = len(np.unique(ev["session"][keep][kind == k])) if k else int((kind == 0).sum())
        stages.append([name, n])

    def rate(m: np.ndarray) -> float:
        return float(((ev["kind"] == 4) & m).sum()) / max(1, int(((ev["kind"] == 0) & m).sum()))

    base = _event_mask(t, {"range": q.get("range", "")}, now)
    by_source = [
        [s, round(rate(base & (ev["source"] == i)) * 100, 2)] for i, s in enumerate(SOURCES)
    ]
    by_device = [
        [d, round(rate(base & (ev["device"] == i)) * 100, 2)] for i, d in enumerate(DEVICES)
    ]
    d = day_of(ev["ts"][keep].astype(np.int64))
    lo = int(d.min()) if len(d) else 0
    sess = np.bincount(d - lo, weights=(kind == 0), minlength=1)
    buys = np.bincount(d - lo, weights=(kind == 4), minlength=len(sess))
    carts = np.bincount(d - lo, weights=(kind == 2), minlength=len(sess))
    trend = {
        "Purchase rate": [
            [_ms(lo + i), round(float(b / s * 100), 2) if s else 0]
            for i, (b, s) in enumerate(zip(buys, sess, strict=True))
        ],
        "Cart abandonment": [
            [_ms(lo + i), round(float((1 - b / c) * 100), 1) if c else 0]
            for i, (b, c) in enumerate(zip(buys, carts, strict=True))
        ],
    }
    steps = [
        {
            "stage": name,
            "sessions": n,
            "of_prev": round(n / stages[i - 1][1] * 100, 1) if i and stages[i - 1][1] else 100.0,
            "of_all": round(n / stages[0][1] * 100, 2) if stages[0][1] else 0,
        }
        for i, (name, n) in enumerate(stages)
    ]
    took = (time.perf_counter() - started) * 1000
    return {
        "stages": stages,
        "by_source": by_source,
        "by_device": by_device,
        "trend": trend,
        "steps": steps,
        "scanned": len(ev),
        "ms": took,
    }


# --- cohorts --------------------------------------------------------------------------------


def cohorts(t: Tables, metric: str, now: float, n: int = 12) -> dict[str, Any]:
    """The last ``n`` monthly cohorts of first orders, and what share came back (or spent) each month after."""
    if not len(t.lines):
        return {"x": [], "y": [], "cells": [], "curves": {}, "rows": []}
    month = _month_key(t.lines["ts"])
    cust = t.lines["customer"]
    order = np.argsort(t.lines["ts"], kind="stable")
    first_seen: dict[int, int] = {}
    for c, m in zip(cust[order].tolist(), month[order].tolist(), strict=True):
        first_seen.setdefault(c, m)
    ids = np.array(list(first_seen.keys()))
    firsts = np.array(list(first_seen.values()))
    lookup = dict(zip(ids.tolist(), firsts.tolist(), strict=True))
    born = np.array([lookup[c] for c in cust.tolist()])
    age = month - born
    last = int(month.max())
    cohort_months = list(range(last - n + 1, last + 1))
    x = [f"M{k}" for k in range(n)]
    y, cells, rows, curves = [], [], [], {}
    for i, cm in enumerate(cohort_months):
        size = int((firsts == cm).sum())
        label = datetime(cm // 12, cm % 12 + 1, 1).strftime("%b %Y")
        y.append(label)
        inc = born == cm
        row = {"cohort": label, "customers": size}
        spend = []
        for k in range(n):
            if cm + k > last:
                continue
            m = inc & (age == k)
            spent = float(t.money[m].sum()) / size if size else 0.0
            back = len(np.unique(cust[m])) / size * 100 if size else 0.0
            spend.append(spent)
            v = spent if metric == "Revenue per customer" else back
            cells.append([f"M{k}", label, round(v, 2 if metric == "Revenue per customer" else 1)])
            if k in (1, 3, 6):
                row[f"m{k}"] = round(v, 1)
        if i % 3 == 2 or cm == last:
            curves[label] = [
                [f"M{k}", round(float(np.sum(spend[: k + 1])), 2)] for k in range(len(spend))
            ]
        rows.append(row)
    return {
        "x": x,
        "y": y[::-1],
        # Newest cohort first: the y axis runs up, so the oldest ends on top, as a cohort table reads.
        "cells": sorted(cells, key=lambda c: -y.index(c[1])),
        "curves": curves,
        "rows": rows[::-1],
    }


# --- customers ------------------------------------------------------------------------------


def customers(t: Tables, f: dict, now: float, top: int = 40) -> dict[str, Any]:
    """The best customers in the filter, the mix by kind, new against returning by week."""
    keep = picked(t, f, now)
    cust = t.lines["customer"][keep]
    ids, inv = np.unique(cust, return_inverse=True)
    spend = np.bincount(inv, weights=t.money[keep])
    orders_of = {}
    o = t.lines["order"][keep]
    pairs = np.unique(np.stack([inv, o]), axis=1)
    counts = np.bincount(pairs[0], minlength=len(ids))
    best = np.argsort(-spend)[:top]
    rows_of = t.person_row(ids[best])
    ts = t.lines["ts"]
    rows = []
    for rank, (b, r) in enumerate(zip(best, rows_of, strict=True)):
        cid = int(ids[b])
        mine = t.lines["customer"] == cid
        p = t.people[r] if r >= 0 else None
        rows.append(
            {
                "key": str(cid),
                "rank": rank + 1,
                "name": t.name(cid),
                "kind": KINDS[p["kind"]] if p is not None else "Retail",
                "city": CITIES[p["city"]][0] if p is not None else "",
                "orders": int(counts[b]),
                "spend": round(float(spend[b]), 2),
                "lifetime": round(float(t.money[mine].sum()), 2),
                "last": _date(int(ts[mine].max()), "%b %d, %Y"),
            }
        )
    del orders_of
    rows_all = t.person_row(ids)
    kinds = np.where(
        rows_all >= 0, t.people["kind"][np.clip(rows_all, 0, None)] if len(t.people) else 0, 0
    )
    mix = [[KINDS[k], round(float(spend[kinds == k].sum()), 2)] for k in range(len(KINDS))]
    first_ts = {}
    for c, x in zip(t.lines["customer"].tolist(), ts.tolist(), strict=True):
        if c not in first_ts or x < first_ts[c]:
            first_ts[c] = x
    wk = day_of(ts[keep].astype(np.int64)) // 7
    is_new = np.array(
        [first_ts[c] >= x - 3600 for c, x in zip(cust.tolist(), ts[keep].tolist(), strict=True)]
    )
    weeks = np.unique(wk)
    nr = {
        "New": [
            [_ms(int(w) * 7), round(float(t.money[keep][(wk == w) & is_new].sum()))] for w in weeks
        ],
        "Returning": [
            [_ms(int(w) * 7), round(float(t.money[keep][(wk == w) & ~is_new].sum()))] for w in weeks
        ],
    }
    return {"rows": rows, "mix": mix, "new_returning": nr, "count": len(ids)}


def who(t: Tables, cid: str, now: float) -> str:
    """A customer's name, for their page's title."""
    return t.name(int(cid))


def customer(t: Tables, cid: int, now: float) -> dict[str, Any]:
    """One customer: who they are, what they spent and when, what they buy, every order."""
    mine = t.lines["customer"] == cid
    r = t.person_row(np.array([cid]))[0]
    p = t.people[r] if r >= 0 else None
    ts = t.lines["ts"][mine]
    spend = float(t.money[mine].sum())
    orders = np.unique(t.lines["order"][mine])
    kind = KINDS[p["kind"]] if p is not None else "Retail"
    since = int(p["ts"]) if p is not None else int(ts.min()) if len(ts) else int(now)
    rows = []
    for o in orders[::-1][:60]:
        k = mine & (t.lines["order"] == o)
        items = ", ".join(
            f"{int(q)} x {PRODUCTS[s]['name']}"
            for s, q in zip(t.lines["sku"][k], t.lines["qty"][k], strict=True)
        )
        rows.append(
            {
                "order": f"#{int(o)}",
                "date": _date(int(t.lines["ts"][k][0]), "%b %d, %Y %H:%M"),
                "channel": CHANNELS[int(t.lines["channel"][k][0])],
                "items": items,
                "total": round(float(t.money[k].sum()), 2),
            }
        )
    by_sku = np.bincount(t.lines["sku"][mine], weights=t.money[mine], minlength=len(SKUS))
    buys = [
        [PRODUCTS[i]["name"], round(float(v), 2)]
        for i, v in sorted(enumerate(by_sku), key=lambda x: -x[1])
        if v > 0
    ][:8]
    order = np.argsort(ts)
    cum = np.cumsum(t.money[mine][order])
    curve = [[int(x) * 1000, round(float(v), 2)] for x, v in zip(ts[order], cum, strict=True)]
    # Where they rank among everyone, by lifetime spend.
    ids, inv = np.unique(t.lines["customer"], return_inverse=True)
    totals_all = np.bincount(inv, weights=t.money)
    rank = int((totals_all > spend).sum()) + 1
    return {
        "name": t.name(cid),
        "line": "  ·  ".join(
            x
            for x in (
                kind,
                CITIES[p["city"]][0] if p is not None else "",
                f"first came via {SOURCES[p['source']]}"
                if p is not None and p["kind"] != 2
                else "wholesale account",
                f"customer since {_date(since, '%B %Y')}",
            )
            if x
        ),
        "tiles": {
            "lifetime": money(spend, cents=spend < 1000),
            "orders": f"{len(orders):,}",
            "aov": money(spend / len(orders), cents=True) if len(orders) else "-",
            "last": _date(int(ts.max()), "%b %d") if len(ts) else "-",
            "rank": f"#{rank:,} of {len(ids):,}",
        },
        "rows": rows,
        "buys": buys,
        "curve": curve,
    }


# --- products -------------------------------------------------------------------------------


def metric(
    t: Tables,
    value: Callable[[Tables, np.ndarray], float],
    f: dict,
    fmt: str,
    now: float,
    weeks: int = 26,
) -> dict[str, Any]:
    """A metric, as a cell defines it: ``value(t, keep)`` over the lines a filter keeps.

    Its value over the filter's range against the range before, and week by
    week over the last ``weeks`` weeks for the sparkline.
    """
    keep, was = picked(t, f, now), before(t, f, now)
    a, b = float(value(t, keep)), float(value(t, was)) if was.any() else 0.0
    end = day_of(int(now))
    spark = []
    for w in range(weeks, 0, -1):
        k = (t.day > end - w * 7) & (t.day <= end - (w - 1) * 7)
        spark.append(round(float(value(t, k)), 4) if k.any() else 0)
    shown = {
        "money": money(a, cents=a < 1000),
        "pct": pct(a),
        "count": f"{a:,.0f}",
        "ratio": f"{a:.2f}",
    }[fmt]
    d, trend = delta(a, b)
    return {"value": shown, "delta": d, "trend": trend, "spark": spark}


def products(t: Tables, catalog: dict[str, dict], f: dict, now: float) -> list[dict[str, Any]]:
    """The catalog as a sheet: what we set (price, cost, stock), then what the data says under the filters."""
    days = RANGES.get(f.get("range", ""), 30)
    keep = picked(t, {**f, "category": "All"}, now)
    units = np.bincount(t.lines["sku"][keep], weights=t.lines["qty"][keep], minlength=len(SKUS))
    rev = np.bincount(t.lines["sku"][keep], weights=t.money[keep], minlength=len(SKUS))
    span = days or max(1, int(day_of(int(now)) - t.day.min() + 1)) if len(t.day) else 1
    rows = []
    for i, sku in enumerate(SKUS):
        c = catalog.get(sku, PRODUCTS[i])
        price, cost, stock = (
            float(c.get("price") or 0),
            float(c.get("cost") or 0),
            int(c.get("stock") or 0),
        )
        per_day = units[i] / span
        rows.append(
            {
                "sku": sku,
                "name": c.get("name") or PRODUCTS[i]["name"],
                "category": PRODUCTS[i]["category"],
                "price": round(price, 2),
                "cost": round(cost, 2),
                "margin": round((1 - cost / price) * 100, 1) if price else None,
                "units": int(units[i]),
                "revenue": round(float(rev[i])),
                "stock": stock,
                "cover": round(stock / per_day) if per_day and stock else None,
            }
        )
    return rows


# --- events ---------------------------------------------------------------------------------


def events(t: Tables, q: dict, now: float, limit: int = 50) -> dict[str, Any]:
    """The raw events table under a query: how many match, how long it took, when they happen, the newest rows."""
    started = time.perf_counter()
    ev = t.events
    keep = _event_mask(t, q, now)
    if q.get("kind", "All") in STAGES:
        keep &= ev["kind"] == STAGES.index(q["kind"])
    if q.get("sku", "All") in SKUS:
        keep &= ev["sku"] == SKUS.index(q["sku"])
    idx = np.flatnonzero(keep)
    took = (time.perf_counter() - started) * 1000
    sel = ev[idx]
    local = sel["ts"].astype(np.int64) + OFFSET
    hour = (local // 3600) % 24
    dow = ((local // DAY) + 3) % 7
    grid = np.bincount(dow * 24 + hour, minlength=7 * 24).reshape(7, 24)
    heat = [[h, 6 - d, int(grid[d, h])] for d in range(7) for h in range(24)]
    d = local // DAY
    lo = int(d.min()) if len(d) else 0
    per = np.bincount(d - lo) if len(d) else np.zeros(0)
    newest = sel[::-1][:limit]
    rows = [
        {
            "time": datetime.fromtimestamp(int(e["ts"])).strftime("%b %d %H:%M:%S"),
            "session": int(e["session"]),
            "event": STAGES[e["kind"]],
            "source": SOURCES[e["source"]],
            "device": DEVICES[e["device"]],
            "product": PRODUCTS[e["sku"]]["name"] if e["sku"] >= 0 else "",
        }
        for e in newest
    ]
    return {
        "total": len(ev),
        "matched": len(idx),
        "sessions": len(np.unique(sel["session"])),
        "ms": round(took, 1),
        "heat": heat,
        "daily": [[_ms(lo + i), int(v)] for i, v in enumerate(per)],
        "rows": rows,
    }


# --- forecast -------------------------------------------------------------------------------


#: How demand answers a price change: a 1% rise sells about this many % fewer units.
ELASTICITY = -1.4


def monthly(t: Tables, now: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Revenue and gross profit per calendar month, the current month scaled up to a whole one."""
    key = _month_key(t.lines["ts"])
    lo, hi = int(key.min()), int(key.max())
    rev = np.bincount(key - lo, weights=t.money, minlength=hi - lo + 1)
    gp = np.bincount(key - lo, weights=t.margin, minlength=hi - lo + 1)
    d = datetime.fromtimestamp(now)
    days_in = (
        datetime(d.year + d.month // 12, d.month % 12 + 1, 1) - datetime(d.year, d.month, 1)
    ).days
    done = (now - datetime(d.year, d.month, 1).timestamp()) / DAY
    scale = days_in / max(done, 1.0)
    rev[-1] *= scale
    gp[-1] *= scale
    return np.arange(lo, hi + 1), rev, gp


def price_index(t: Tables, catalog: dict[str, dict], now: float) -> float:
    """What the catalog charges now against what the last 90 days sold at, weighted by revenue: 1.0 is no change."""
    keep = window(t, 90, now) & (t.lines["channel"] != 3)
    listed = t.lines["qty"] * t.lines["price"]
    rev = np.bincount(t.lines["sku"][keep], weights=listed[keep], minlength=len(SKUS))
    units = np.bincount(t.lines["sku"][keep], weights=t.lines["qty"][keep], minlength=len(SKUS))
    paid = np.divide(rev, units, out=np.zeros(len(SKUS)), where=units > 0)
    now_price = np.array(
        [
            float((catalog.get(s) or {}).get("price") or PRODUCTS[i]["price"])
            for i, s in enumerate(SKUS)
        ]
    )
    base = np.where(paid > 0, paid, now_price)
    return float((rev * now_price / base).sum() / rev.sum()) if rev.sum() else 1.0


def forecast(t: Tables, plan: dict, catalog: dict[str, dict], now: float) -> dict[str, Any]:
    """Twelve months ahead from the history: a trend and a season fitted, then the plan's what-ifs on top.

    The fit is least squares on log monthly revenue: a straight trend and a
    term per calendar month. The plan moves it: a price change sells fewer
    or more units (:data:`ELASTICITY`), marketing spend brings new customers
    with diminishing returns, subscriber churn compounds on the subscription
    share, and a wholesale account adds a cafe's monthly order.
    """
    months_, rev, gp = monthly(t, now)
    full = months_[1:]  # the first month is partial
    y = np.log(np.maximum(rev[1:], 1))
    n = len(full)
    cal = full % 12
    fit = np.column_stack(
        [np.ones(n), np.arange(n)] + [(cal == m).astype(float) for m in range(1, 12)]
    )
    w = np.linspace(0.6, 1.0, n)  # recent months count more
    beta, *_ = np.linalg.lstsq(fit * w[:, None], y * w, rcond=None)
    resid = y - fit @ beta
    sigma = float(np.sqrt(np.sum(resid**2) / max(1, n - fit.shape[1])))
    ahead = int(plan.get("months", 12))
    fut = np.arange(full[-1] + 1, full[-1] + 1 + ahead)
    ahead_x = np.column_stack(
        [np.ones(ahead), np.arange(n, n + ahead)]
        + [((fut % 12) == m).astype(float) for m in range(1, 12)]
    )
    base = np.exp(ahead_x @ beta)
    margin = float(gp[-7:-1].sum() / rev[-7:-1].sum())
    sheet = price_index(t, catalog or {}, now)
    price = (1 + float(plan.get("price", 0)) / 100) * sheet - 1
    spend = float(plan.get("marketing", 0)) / 100
    churn = float(plan.get("churn", 6.5)) / 100
    cafes = int(plan.get("cafes", 0))
    sub_share = float(t.money[t.lines["channel"] == 1].sum() / max(1.0, t.money.sum()))
    k = np.arange(1, ahead + 1)
    volume = (1 + price) ** ELASTICITY
    price_lift = (1 + price) * volume
    ramp = 1 - np.exp(-k / 3)  # new customers take a few months to show
    growth = (
        1 + (np.sign(spend) * (abs(1 + spend) ** 0.35 - 1) if spend > -1 else -0.5) * 0.45 * ramp
    )
    subs = sub_share * ((1 - churn) / (1 - 0.065)) ** k + (1 - sub_share)
    wholesale = cafes * 1150.0
    planned = base * price_lift * growth * subs + wholesale
    # The plan's margin: a price rise is all margin on the units still sold.
    plan_margin = 1 - (1 - margin) / (1 + price) if price > -1 else margin
    hist = [
        [_month_label(m), round(float(v))] for m, v in zip(months_[-13:], rev[-13:], strict=True)
    ]
    labels = [_month_label(m) for m in fut]
    band_lo = planned * np.exp(-1.28 * sigma * np.sqrt(k / 3))
    band_hi = planned * np.exp(1.28 * sigma * np.sqrt(k / 3))
    rows = [
        {
            "month": lab,
            "baseline": round(float(b)),
            "plan": round(float(p)),
            "change": round(float(p / b - 1) * 100, 1),
            "gross": round(float(p * plan_margin)),
            "low": round(float(lo)),
            "high": round(float(hi)),
        }
        for lab, b, p, lo, hi in zip(labels, base, planned, band_lo, band_hi, strict=True)
    ]
    last12 = float(rev[-13:-1].sum())
    return {
        "history": hist,
        "baseline": [[lab, round(float(v))] for lab, v in zip(labels, base, strict=True)],
        "plan": [[lab, round(float(v))] for lab, v in zip(labels, planned, strict=True)],
        "rows": rows,
        "tiles": {
            "next": money(float(planned.sum())),
            "vs_base": delta(float(planned.sum()), float(base.sum()))[0].replace(" vs prior", "")
            or "+0.0%",
            "growth": delta(float(planned.sum()), last12)[0].replace(" vs prior", ""),
            "gross": money(float((planned * plan_margin).sum())),
            "margin": pct(plan_margin),
            "sheet": f"{(sheet - 1) * 100:+.1f}%",
            "fit": f"trend {np.expm1(beta[1] * 12) * 100:+.0f}% a year, error ±{sigma * 100:.0f}% a month",
        },
    }


def _month_label(m: int) -> str:
    return datetime(int(m) // 12, int(m) % 12 + 1, 1).strftime("%b %y")
