"""What the cells show that is not a computation over the tables: status lines, links, labels.

Plain functions as host terms, shaped for the widgets.
"""

from __future__ import annotations

from typing import Any

import nu


__all__ = ["status", "ways"]


@nu.host
def status(stream: dict, live: bool, index: dict, pace: str, now: float) -> dict[str, Any]:
    """The stream's status line: a tone, whether it pulses, and what it says."""
    rows = {"lines": 0, "events": 0, "people": 0}
    for e in index.values():
        rows[e.get("table", "")] = rows.get(e.get("table", ""), 0) + int(e.get("rows") or 0)
    tables = f"{rows['lines']:,} order lines  ·  {rows['people']:,} customers  ·  {rows['events']:,} web events"
    ago = now - float(stream.get("at") or 0)
    if live and stream.get("status") == "running":
        when = "just now" if ago < 3 else f"{ago:.0f}s ago"
        return {
            "tone": "ok",
            "pulse": True,
            "line": f"Live: orders arriving at a {pace.lower()} pace, last tick {when}  ·  {tables}",
        }
    if stream.get("status") == "stopped":
        return {"tone": "neutral", "pulse": False, "line": f"Stream paused  ·  {tables}"}
    return {"tone": "warn", "pulse": False, "line": f"Stream starting  ·  {tables}"}


#: The pages, in the order the overview lists them: key, label, what it is for.
PAGES = [
    ("revenue", "Revenue", "by day, channel and category"),
    ("funnel", "Funnel", "from session to purchase"),
    ("cohorts", "Cohorts", "who comes back"),
    ("customers", "Customers", "the best ones, a page each"),
    ("products", "Products", "the catalog sheet"),
    ("forecast", "Forecast", "the next twelve months, what-ifs"),
    ("metrics", "Metrics", "a cell per metric"),
    ("events", "Events", "every web event, queried"),
    ("imports", "Imports", "exports dropped in the inbox"),
    ("sources", "Sources", "the tables and the stream"),
]


@nu.host
def ways(pages: dict[str, str]) -> str:
    """The overview's map of the space: a link per page, with what it is for."""
    parts = [f"[{label}]({pages[key]}) {what}" for key, label, what in PAGES if key in pages]
    return "  ·  ".join(parts)


@nu.host
def top_head(count: int) -> str:
    return f"Top customers in range, of {count:,} who ordered. Click one to open their page."


@nu.host
def days(f: dict) -> int:
    """The shared filter's range in days, 0 for all time."""
    from .calc import RANGES

    return RANGES.get((f or {}).get("range", ""), 30)


@nu.host
def outlook(v: dict) -> list[list]:
    """Actual, baseline and plan as rows across the months: the plan and baseline start where the actuals end."""
    hist, base, plan = v["history"], v["baseline"], v["plan"]
    rows = [[m, x, None, None] for m, x in hist]
    rows[-1][2] = rows[-1][3] = rows[-1][1]
    rows += [[m, None, b, p] for (m, b), (_, p) in zip(base, plan, strict=True)]
    return rows


@nu.host
def fit_line(tiles: dict) -> str:
    return (
        f"Fitted on every month so far: {tiles['fit']}. Prices are the slider on top of the Products sheet, "
        f"which charges {tiles['sheet']} on what the last 90 days sold at. A price change moves units by an elasticity of -1.4, "
        "marketing brings new customers with diminishing returns, churn compounds on the subscriptions."
    )


@nu.host
def count(n: int) -> str:
    return f"{n:,}"


@nu.host
def took(ms: float) -> str:
    return f"{ms:.1f} ms"


@nu.host
def matched(v: dict) -> str:
    return (
        f"{v['matched']:,} of {v['total']:,} events match, from {v['sessions']:,} sessions  ·  "
        f"scanned in {v['ms']:.1f} ms"
    )


@nu.host
def since(seconds: float) -> int:
    import time

    return int(time.time() - seconds)


@nu.host
def recent(points: dict | list | None) -> list[list]:
    """A kh57 sample (``[[ts, value], ...]`` or a mapping) as time points in ms."""
    items = points.items() if isinstance(points, dict) else points or []
    return [[int(k) * 1000, round(float(v), 2)] for k, v in items]


SCHEMA = """\
**lines**: order, ts, customer, sku, qty, price, cost, channel, disc. One row per order line.  \n\
**people**: id, ts, kind, city, first, last, source. One row per customer.  \n\
**events**: ts, session, kind, source, device, sku. One row per step a web session took.

Each table is a set of shards: numpy rows stored as bytes in this space's state, one per month of history, \
one per import, and live ones the stream rewrites as orders land. A page loads the shards once and then \
only the ones that moved."""


@nu.host
def sources(index: dict[str, dict]) -> dict[str, Any]:
    """The tables and the newest shards, from the index."""
    import time

    from .gen import DTYPES

    def ago(at: int) -> str:
        s = max(0, int(time.time()) - int(at))
        return (
            "just now"
            if s < 5
            else f"{s}s ago"
            if s < 120
            else f"{s // 60} min ago"
            if s < 7200
            else f"{s // 3600} h ago"
        )

    tables = []
    for name in ("lines", "people", "events"):
        mine = [e for e in index.values() if e.get("table") == name]
        rows = sum(int(e.get("rows") or 0) for e in mine)
        kinds = {}
        for e in mine:
            o = e.get("origin", "")
            key = "imports" if o.startswith("import") else o
            kinds[key] = kinds.get(key, 0) + int(e.get("rows") or 0)
        tables.append(
            {
                "table": name,
                "rows": rows,
                "shards": len(mine),
                "size": f"{rows * DTYPES[name].itemsize / 1e6:.1f} MB",
                "from": ", ".join(f"{k} {v:,}" for k, v in kinds.items()),
                "latest": ago(max((int(e.get("at") or 0) for e in mine), default=0)),
            }
        )
    newest = sorted(index.items(), key=lambda kv: (-int(kv[1].get("at") or 0), -int(kv[0])))[:10]
    shards = [
        {
            "id": int(k),
            "table": e.get("table"),
            "rows": e.get("rows"),
            "origin": e.get("origin"),
            "v": e.get("v"),
            "at": ago(e.get("at") or 0),
        }
        for k, e in newest
    ]
    return {"tables": tables, "shards": shards}
