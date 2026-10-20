"""Two years of Owlbridge, made up the same way every time: customers, orders, web events.

Plain numpy, nothing Nu. :func:`history` is what the space opens with; the
stream job keeps it going with :func:`orders_now` and :func:`events_now`,
and :func:`sample_csv` writes the exports the Imports page drops in the inbox.

The shop grows about 45% a year, peaks for the holidays, dips in the summer,
sells more on weekdays and in the evening. Retail customers come back now and
then, subscribers renew monthly until they churn, cafes order every couple of
weeks. Every number is drawn from a seeded generator: the same day gives the
same shop.

Tables are numpy record arrays, one dtype each (:data:`DTYPES`):

- ``lines``: one row per order line, an order its lines sharing ``order``.
- ``people``: one row per customer, when and how they first came.
- ``events``: one row per web event, a session its events sharing ``session``.
"""

from __future__ import annotations

import bisect
import csv
import io
import random
import time
from datetime import datetime

import numpy as np

from .shop import CAFES, CHANNELS, CITIES, DEVICES, FIRST, LAST, PRODUCTS, SKUS, SOURCES, STAGES


__all__ = [
    "DAY",
    "DTYPES",
    "OFFSET",
    "WHOLESALE",
    "day_of",
    "events_now",
    "history",
    "midnight",
    "orders_now",
    "sample_csv",
]


DAY = 86400

#: Seconds east of UTC on this machine: days start at local midnight.
OFFSET = int(datetime.now().astimezone().utcoffset().total_seconds())

#: What a cafe pays, as a share of the retail price.
WHOLESALE = 0.62

DTYPES: dict[str, np.dtype] = {
    "lines": np.dtype(
        [
            ("order", "<i4"),
            ("ts", "<i4"),
            ("customer", "<i4"),
            ("sku", "i1"),
            ("qty", "<i2"),
            ("price", "<f4"),
            ("cost", "<f4"),
            ("channel", "i1"),
            ("disc", "<f4"),
        ]
    ),
    "people": np.dtype(
        [
            ("id", "<i4"),
            ("ts", "<i4"),
            ("kind", "i1"),
            ("city", "i1"),
            ("first", "<i2"),
            ("last", "<i2"),
            ("source", "i1"),
        ]
    ),
    "events": np.dtype(
        [
            ("ts", "<i4"),
            ("session", "<i4"),
            ("kind", "i1"),
            ("source", "i1"),
            ("device", "i1"),
            ("sku", "i1"),
        ]
    ),
}

_PRICE = np.array([p["price"] for p in PRODUCTS], dtype=np.float32)
_COST = np.array([p["cost"] for p in PRODUCTS], dtype=np.float32)
_BASKET = np.array([p["weight"] for p in PRODUCTS], dtype=float)
_BASKET /= _BASKET.sum()
_BASKET_C = list(np.cumsum(_BASKET))
_BEANS = [i for i, p in enumerate(PRODUCTS) if p["category"] in ("Blends", "Single origin")]
_SIZES = list(np.cumsum([0.52, 0.30, 0.13, 0.05]))
_BAGS = list(np.cumsum([0.72, 0.22, 0.06]))
_CITY_W = np.array([w for _, w in CITIES], dtype=float) / sum(w for _, w in CITIES)
_CITY_C = list(np.cumsum(_CITY_W))

#: Sessions by source, and how much better or worse than average each converts.
_SOURCE_W = np.array([0.31, 0.17, 0.09, 0.16, 0.07, 0.20])
_SOURCE_C = list(np.cumsum(_SOURCE_W))
_SOURCE_LIFT = np.array([1.0, 0.55, 2.1, 0.8, 1.35, 1.25])
_DEVICE_W = np.array([0.61, 0.33, 0.06])
_DEVICE_LIFT = np.array([0.8, 1.45, 0.9])

#: Share of a day's orders by local hour: a morning bump, an evening peak.
_HOURS = np.array(
    [
        1,
        0.6,
        0.4,
        0.3,
        0.4,
        0.8,
        1.6,
        2.8,
        3.6,
        3.9,
        4.0,
        4.1,
        4.4,
        4.2,
        4.0,
        3.9,
        4.1,
        4.6,
        5.3,
        6.2,
        6.6,
        6.0,
        4.4,
        2.4,
    ]
)
_HOURS = _HOURS / _HOURS.sum()
_WEEK = np.array([1.08, 1.06, 1.04, 1.05, 0.98, 0.88, 0.91])  # Monday first


def midnight(ts: float) -> int:
    """The local midnight starting the day ``ts`` is in, as unix seconds."""
    return int((ts + OFFSET) // DAY * DAY - OFFSET)


def day_of(ts: np.ndarray | int) -> np.ndarray | int:
    """Local day numbers (days since the epoch) for unix seconds."""
    return (ts + OFFSET) // DAY


def _season(day: np.ndarray) -> np.ndarray:
    """How busy a day is against the year's average: holidays high, summer low."""
    doy = (day + 4) % 365.25 / 365.25
    # Distances on the circle of the year, so December runs into January without a step.
    near = lambda c: (doy - c + 0.5) % 1 - 0.5  # noqa: E731
    holiday = np.exp(-((near(0.94) * 11) ** 2)) * 0.75
    summer = -np.exp(-((near(0.55) * 7) ** 2)) * 0.18
    return 1 + holiday + summer


def _pace(day: np.ndarray, end_day: int) -> np.ndarray:
    """Growth, season and weekday together: 1 is an average day a year ago."""
    years = (day - end_day) / 365.0
    weekday = _WEEK[(day + 3) % 7]
    return np.exp(np.log(1.45) * (years + 1)) * _season(day) * weekday


def _pick(rng: random.Random, weights: list[float]) -> int:
    """One position drawn by cumulative ``weights``: a scalar draw without numpy's overhead."""
    return bisect.bisect(weights, rng.random() * weights[-1])


def _when(rng: np.random.Generator, day0: int, n: int) -> np.ndarray:
    """``n`` times on the local day starting ``day0``, by the hours orders come in."""
    hours = rng.choice(24, size=n, p=_HOURS)
    return day0 + hours * 3600 + rng.integers(0, 3600, size=n)


class _Book:
    """Lines and people as they are written, then made arrays."""

    def __init__(self) -> None:
        self.lines: list[tuple] = []
        self.people: list[tuple] = []
        self.order = 0

    def person(self, pid: int, ts: int, kind: int, r: random.Random, source: int) -> None:
        city = _pick(r, _CITY_C)
        first = r.randrange(len(FIRST)) if kind != 2 else -1
        last = r.randrange(len(LAST)) if kind != 2 else r.randrange(len(CAFES))
        self.people.append((pid, ts, kind, city, first, last, source))

    def sale(
        self,
        ts: int,
        customer: int,
        channel: int,
        items: list[tuple[int, int, float]],
        disc: float = 0.0,
    ) -> None:
        self.order += 1
        for sku, qty, price in items:
            self.lines.append(
                (self.order, ts, customer, sku, qty, price, float(_COST[sku]), channel, disc)
            )

    def arrays(self) -> dict[str, np.ndarray]:
        lines = np.array(self.lines, dtype=DTYPES["lines"])
        lines = lines[np.argsort(lines["ts"], kind="stable")]
        # Orders numbered by time, so a later order has a higher number.
        _, first = np.unique(lines["order"], return_index=True)
        rank = np.empty(len(first), dtype=np.int32)
        rank[np.argsort(first)] = np.arange(1, len(first) + 1, dtype=np.int32)
        lines["order"] = rank[np.searchsorted(np.unique(lines["order"]), lines["order"])] + 1000
        people = np.array(self.people, dtype=DTYPES["people"])
        return {"lines": lines, "people": people[np.argsort(people["ts"], kind="stable")]}


def _basket(r: random.Random, prices: np.ndarray) -> list[tuple[int, int, float]]:
    """A web basket: one to four products, beans often two bags."""
    n = 1 + _pick(r, _SIZES)
    skus = list(dict.fromkeys(_pick(r, _BASKET_C) for _ in range(n)))
    return [(int(s), 1 + _pick(r, _BAGS) if s in _BEANS else 1, float(prices[s])) for s in skus]


def history(now: float, seed: int = 7) -> dict[str, np.ndarray]:
    """Two years of the shop up to ``now``: ``{lines, people, events}`` as record arrays.

    Events cover the last year only: there are a lot of them.
    """
    rng, r = np.random.default_rng(seed), random.Random(seed)  # noqa: S311 -- made up data
    end = int(now)
    end_day = int(day_of(end))
    days = np.arange(end_day - 730, end_day + 1)
    pace = _pace(days, end_day)
    book = _Book()
    pid = 0

    def add_person(ts: int, kind: int, source: int) -> int:
        nonlocal pid
        pid += 1
        book.person(pid, ts, kind, r, source)
        return pid

    retail_new = rng.poisson(29 * pace)
    subs_new = rng.poisson(3.1 * pace)
    for i, day in enumerate(days):
        day0 = int(day * DAY - OFFSET)
        # Retail: a first order, then now and then another, less likely each time.
        for ts in _when(rng, day0, int(retail_new[i])):
            source = _pick(r, _SOURCE_C)
            market = r.random() < 0.18
            who = add_person(int(ts), 0, source)
            t, again = int(ts), 0.42 if not market else 0.12
            while t <= end:
                disc = 0.1 if (source == 2 and r.random() < 0.5) else 0.0
                book.sale(t, who, 2 if market else 0, _basket(r, _PRICE), disc)
                if r.random() > again:
                    break
                t += int(r.expovariate(1 / (48 * DAY))) + DAY
                again *= 0.86
        # Subscribers: a bag (or two) a month until they stop.
        for ts in _when(rng, day0, int(subs_new[i])):
            who = add_person(int(ts), 1, _pick(r, _SOURCE_C))
            sku = 7 if r.random() < 0.72 else 8
            t = int(ts)
            while t <= end:
                bean = r.choice(_BEANS)
                extra = [(bean, 1, float(_PRICE[bean]))] if r.random() < 0.07 else []
                book.sale(t, who, 1, [(sku, 1, float(_PRICE[sku])), *extra])
                if r.random() < 0.065:
                    break
                t += 30 * DAY + r.randrange(-2, 3) * 3600
    # Cafes: a few dozen, signing on over the two years, ordering beans in bulk every couple of weeks.
    for c in range(len(CAFES)):
        start = int((days[0] + r.randrange(0, 640)) * DAY - OFFSET + 10 * 3600)
        who = add_person(start, 2, 4)
        book.people[-1] = (*book.people[-1][:5], c, 4)
        t, size = start, r.uniform(0.6, 1.6)
        while t <= end:
            items = [
                (
                    s,
                    max(2, int(r.gauss(14, 5) * size * (0.5 if s != 0 else 1))),
                    round(float(_PRICE[s]) * WHOLESALE, 2),
                )
                for s in r.sample(_BEANS, r.randrange(1, 4))
            ]
            book.sale(t, who, 3, items)
            t += int(r.gauss(14, 3) * DAY)
    out = book.arrays()
    out["events"] = _events(rng, days[-365:], end, end_day, start_session=1)
    return out


def _events(
    rng: np.random.Generator, days: np.ndarray, end: int, end_day: int, start_session: int
) -> np.ndarray:
    """Web sessions on ``days`` up to ``end``, each a row per step it took down the funnel."""
    per_day = rng.poisson(1650 * _pace(days, end_day))
    n = int(per_day.sum())
    day0 = np.repeat(days * DAY - OFFSET, per_day)
    hours = rng.choice(24, size=n, p=_HOURS)
    ts = day0 + hours * 3600 + rng.integers(0, 3600, size=n)
    source = rng.choice(len(SOURCES), size=n, p=_SOURCE_W)
    device = rng.choice(len(DEVICES), size=n, p=_DEVICE_W)
    keep = ts <= end
    ts, source, device = ts[keep], source[keep], device[keep]
    return _sessions(rng, ts, source, device, start_session)


def _sessions(
    rng: np.random.Generator, ts: np.ndarray, source: np.ndarray, device: np.ndarray, first: int
) -> np.ndarray:
    """Each session as its events: how far down the funnel it got, a product per view."""
    n = len(ts)
    lift = _SOURCE_LIFT[source] * _DEVICE_LIFT[device]
    p = [0.64, 0.12, 0.56, 0.6]  # view | session, cart | view, checkout | cart, purchase | checkout
    depth = np.ones(n, dtype=np.int64)
    u = rng.random((n, 4))
    alive = np.ones(n, dtype=bool)
    for k, pk in enumerate(p):
        alive &= u[:, k] < np.clip(pk * lift ** (0.5 if k else 0.25), 0, 0.97)
        depth += alive
    views = np.where(depth >= 2, rng.choice([1, 2, 3], size=n, p=[0.6, 0.28, 0.12]), 0)
    count = 1 + views + np.clip(depth - 2, 0, None)
    total = int(count.sum())
    row = np.repeat(np.arange(n), count)
    step = np.arange(total) - np.repeat(np.cumsum(count) - count, count)
    kind = np.where(step == 0, 0, np.where(step <= views[row], 1, step - views[row] + 1))
    ev = np.empty(total, dtype=DTYPES["events"])
    ev["ts"] = ts[row] + step * rng.integers(20, 160, size=total)
    ev["session"] = first + row
    ev["kind"] = kind
    ev["source"] = source[row]
    ev["device"] = device[row]
    ev["sku"] = np.where(kind == 0, -1, rng.choice(len(SKUS), size=total, p=_BASKET))
    return ev[np.argsort(ev["ts"], kind="stable")]


# --- what the stream sells now --------------------------------------------------------------


def orders_now(
    r: random.Random, now: int, n: int, prices: list[float], order0: int, person0: int, known: int
) -> dict[str, np.ndarray]:
    """``n`` orders landing at ``now``, at today's ``prices``: lines, and the new customers among them.

    Half come from someone new, the rest from the ``known`` customers already there.
    """
    book = _Book()
    book.order = order0 - 1
    price = np.array(prices, dtype=np.float32)
    for _ in range(n):
        ts = now - r.randrange(0, 3)
        roll = r.random()
        if roll < 0.55 or known <= 0:
            who = person0 + len(book.people)
            kind = 1 if roll < 0.08 else 0
            source = _pick(r, _SOURCE_C)
            book.person(who, ts, kind, r, source)
            channel = 1 if kind == 1 else (2 if r.random() < 0.18 else 0)
        else:
            who, kind, channel = r.randrange(1, known + 1), 0, 0
        items = [(7, 1, float(price[7]))] if channel == 1 else _basket(r, price)
        book.sale(ts, who, channel, items, 0.1 if r.random() < 0.06 else 0.0)
    lines = (
        np.array(book.lines, dtype=DTYPES["lines"]) if book.lines else np.zeros(0, DTYPES["lines"])
    )
    people = (
        np.array(book.people, dtype=DTYPES["people"])
        if book.people
        else np.zeros(0, DTYPES["people"])
    )
    return {"lines": lines, "people": people}


def events_now(rng: np.random.Generator, now: int, n: int, first: int) -> np.ndarray:
    """``n`` web sessions starting in the last few seconds before ``now``, as their events."""
    ts = now - rng.integers(0, 4, size=n)
    source = rng.choice(len(SOURCES), size=n, p=_SOURCE_W)
    device = rng.choice(len(DEVICES), size=n, p=_DEVICE_W)
    ev = _sessions(rng, ts, source, device, first)
    ev["ts"] = np.minimum(ev["ts"], now)
    return ev


# --- exports landing in the inbox -----------------------------------------------------------


#: The exports the Imports page can drop, by name: who sends them and what they hold.
EXPORTS = {
    "wholesale": "Wholesale order sheet from the cafes",
    "marketplace": "Marketplace settlement export",
    "popup": "Pop-up market till export, with two bad rows",
}


def sample_csv(kind: str, now: float, seed: int) -> tuple[str, str]:
    """A CSV export as ``(file name, text)``: real looking rows the importer parses and loads."""
    rng = np.random.default_rng(seed)
    stamp = time.strftime("%Y-%m-%d", time.localtime(now))
    out = io.StringIO()
    w = csv.writer(out)
    if kind == "wholesale":
        w.writerow(["date", "cafe", "sku", "bags", "unit_price"])
        for cafe in rng.choice(len(CAFES), size=6, replace=False):
            for s in rng.choice(_BEANS, size=int(rng.integers(1, 4)), replace=False):
                w.writerow(
                    [
                        stamp,
                        CAFES[cafe],
                        SKUS[s],
                        int(rng.integers(6, 30)),
                        f"{_PRICE[s] * WHOLESALE:.2f}",
                    ]
                )
        return f"wholesale-{stamp}-{seed % 1000:03d}.csv", out.getvalue()
    if kind == "marketplace":
        w.writerow(["order_id", "placed_at", "buyer", "city", "sku", "qty", "item_price"])
        for k in range(int(rng.integers(40, 70))):
            t = time.strftime("%Y-%m-%d %H:%M", time.localtime(now - rng.integers(0, 3 * DAY)))
            s = int(rng.choice(len(SKUS), p=_BASKET))
            buyer = f"{FIRST[rng.integers(len(FIRST))]} {LAST[rng.integers(len(LAST))][0]}."
            city = CITIES[int(rng.choice(len(CITIES), p=_CITY_W))][0]
            w.writerow(
                [
                    f"MK-{seed % 97:02d}{k:04d}",
                    t,
                    buyer,
                    city,
                    SKUS[s],
                    int(rng.choice([1, 1, 2])),
                    f"{_PRICE[s]:.2f}",
                ]
            )
        return f"marketplace-settlement-{stamp}-{seed % 1000:03d}.csv", out.getvalue()
    w.writerow(["time", "item", "qty", "price"])
    for k in range(int(rng.integers(18, 30))):
        t = time.strftime("%Y-%m-%d %H:%M", time.localtime(now - rng.integers(0, 6 * 3600)))
        s = int(rng.choice(len(SKUS), p=_BASKET))
        w.writerow(
            [
                t,
                SKUS[s] if k not in (4, 11) else "LK-??",
                int(rng.choice([1, 1, 2])),
                f"{_PRICE[s]:.2f}" if k != 11 else "n/a",
            ]
        )
    return f"popup-till-{stamp}-{seed % 1000:03d}.csv", out.getvalue()


#: For the cells: names of channels, stages, as the tables number them.
NAMES = {"channel": CHANNELS, "stage": STAGES, "source": SOURCES, "device": DEVICES}
