"""What the views show, shaped from what the reads return. Plain Python, then Nu atoms over it.

Every ``*_of`` function takes plain values (rows a read returned, the clock)
and returns plain values (table rows, tiles, chart points), so the rules
live where a test reaches them without a store. The ``@nu.host`` atoms below
are the same functions as terms, for the cells to call on what they read.

Filters here only ever see what one read returned: a slice of ``count``
entries, a sample of points. Nothing in this module walks a stream.
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any

import nu

from . import consts


__all__ = [
    "ago",
    "bounded",
    "bounded_of",
    "chart",
    "chart_of",
    "clock",
    "entry",
    "entry_of",
    "fields_text",
    "look",
    "look_of",
    "messages",
    "messages_of",
    "options",
    "options_of",
    "overview",
    "overview_of",
    "pick",
    "pick_of",
    "status",
    "status_of",
]


# ---- small words -----------------------------------------------------------


def clock(ts_us: int | None, now: float | None = None) -> str:
    """``ts_us`` on the local clock: ``14:03:07.120``, with the day in front when not today."""
    if not ts_us or ts_us <= 0:
        return ""
    moment = _dt.datetime.fromtimestamp(ts_us / 1_000_000)
    ms = (ts_us // 1000) % 1000
    shown = moment.strftime("%H:%M:%S.") + f"{ms:03d}"
    today = _dt.datetime.fromtimestamp(now if now is not None else moment.timestamp()).date()
    return shown if moment.date() == today else moment.strftime("%b %d ") + shown


def ago(ts_us: int | None, now: float) -> str:
    """How long before ``now`` (seconds) ``ts_us`` was: ``just now``, ``12s ago``, ``3m ago``."""
    if not ts_us or ts_us <= 0:
        return "-"
    s = max(0.0, now - ts_us / 1_000_000)
    if s < 1:
        return "just now"
    if s < 60:
        return f"{int(s)}s ago"
    if s < 3600:
        return f"{int(s // 60)}m ago"
    if s < 86400:
        return f"{int(s // 3600)}h {int(s % 3600 // 60)}m ago"
    return f"{int(s // 86400)}d ago"


def fields_text(fields: dict | None) -> str:
    """A fields dict on one line: ``port=8080 user="ann"``. Strings bare when they read plainly."""
    if not fields:
        return ""
    parts = []
    for k, v in fields.items():
        plain = isinstance(v, str) and v and " " not in v
        parts.append(f"{k}={v if plain else json.dumps(v, separators=(',', ':'), default=str)}")
    return " ".join(parts)


def _number(v: float) -> str:
    """A value for a tile: four significant digits, no float noise."""
    if not math.isfinite(v):
        return str(v)
    if v != 0 and (abs(v) >= 1e6 or abs(v) < 1e-3):
        return f"{v:.3e}"
    return f"{v:,.4g}" if abs(v) < 1e4 else f"{v:,.0f}"


# ---- the store at a path ---------------------------------------------------


def look_of(path: str | None) -> dict[str, str]:
    """What sits at ``path``: ``{state, path, title, note}``.

    ``state`` is ``unset`` (no path saved), ``missing`` (nothing there),
    ``other`` (a directory, but not a RocksDB store) or ``ok``. ``path`` is
    it expanded and made absolute. Only ``ok`` is safe to open: a RocksDB
    open would make a fresh store anywhere else.
    """
    raw = (path or "").strip()
    if not raw:
        return {
            "state": "unset",
            "path": "",
            "title": "No store picked",
            "note": "Set the path to a nulog store on the Config plane.",
        }
    where = Path(raw).expanduser().resolve()
    shown = str(where)
    if not where.exists():
        return {
            "state": "missing",
            "path": shown,
            "title": "Nothing at this path",
            "note": f"{shown} does not exist. Check the path in Config.",
        }
    if not where.is_dir() or not (where / "CURRENT").is_file():
        return {
            "state": "other",
            "path": shown,
            "title": "Not a nulog store",
            "note": f"{shown} is not a RocksDB store. Point Config at the directory nulog.store(path) writes.",
        }
    return {"state": "ok", "path": shown, "title": "Open, read only", "note": shown}


def status_of(seen: dict, streams: int, series: int, every: float) -> dict[str, Any]:
    """The bar over every plane: ``{tone, pill, line, pulse}`` from a look and the counts."""
    if seen["state"] != "ok":
        tone = "neutral" if seen["state"] == "unset" else "danger"
        return {"tone": tone, "pill": seen["title"], "line": seen["note"], "pulse": False}
    s = "" if streams == 1 else "s"
    home = str(Path.home())
    where = "~" + seen["path"][len(home) :] if seen["path"].startswith(home + "/") else seen["path"]
    line = f"{streams} stream{s}, {series} series, read every {every:g}s from {where}"
    return {"tone": "ok", "pill": "reading", "line": line, "pulse": True}


def overview_of(newest: list, series: list, now: float) -> dict[str, Any]:
    """The root's two tables: each stream with its newest entry, each series with its latest point.

    ``newest`` is ``[[stream, [entry]], ...]`` (the entry list empty for an
    empty stream), ``series`` is ``[[name, [point, ...]], ...]``, a small
    sample of the recent past: its latest point is the series' latest, or
    close to it on a series written many times a second.
    """
    streams = []
    for name, got in newest or ():
        e = (got or [{}])[0]
        streams.append(
            {
                "stream": str(name),
                "newest": ago(e.get("ts_us"), now),
                "level": e.get("level", ""),
                "message": e.get("msg", ""),
            }
        )
    points = []
    for name, got in series or ():
        p = max(got or (), key=lambda q: q.get("ts_us") or 0, default={})
        points.append(
            {
                "series": str(name),
                "latest": _number(float(p["value"])) if p.get("value") is not None else "-",
                "at": ago(p.get("ts_us"), now) if p else "nothing recent",
            }
        )
    return {"streams": streams, "series": points}


# ---- pickers and fields ----------------------------------------------------


def options_of(keys: list | None) -> list[dict[str, str]]:
    """Stream or series names as select options, sorted."""
    return [{"value": str(k), "label": str(k)} for k in sorted(keys or (), key=str)]


def pick_of(keys: list | None, current: str | None) -> str:
    """What a picker shows: ``current`` while it is still there, else the first name, else ``""``."""
    names = sorted((str(k) for k in keys or ()), key=str)
    if current and current in names:
        return current
    return names[0] if names else ""


def bounded_of(raw: object, default: float, lo: float, hi: float) -> float:
    """A number typed in a field, held to ``[lo, hi]``; ``default`` when it is not a number."""
    try:
        v = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if not math.isfinite(v):
        return default
    return min(max(v, lo), hi)


# ---- messages --------------------------------------------------------------


def _row(e: dict, now: float) -> dict[str, Any]:
    return {
        "key": str(e.get("ts_us", "")),
        "time": clock(e.get("ts_us"), now),
        "level": e.get("level", ""),
        "message": e.get("msg", ""),
        "fields": fields_text(e.get("fields")),
    }


def messages_of(entries: list | None, level: str, text: str, now: float) -> dict[str, Any]:
    """The messages view from one read: ``{rows, tiles, empty}``.

    ``level`` ("all" or a level name) and ``text`` (a substring of the
    message, any case) keep rows of this read only, never of the stream.
    ``empty`` says why there are no rows, "" when there are some.
    """
    read = list(entries or ())
    needle = (text or "").strip().lower()
    kept = [
        e
        for e in read
        if (level in ("", consts.DEFAULT_LEVEL) or e.get("level") == level)
        and (not needle or needle in str(e.get("msg", "")).lower())
    ]
    warnings = sum(1 for e in read if e.get("level") == "warning")
    errors = sum(1 for e in read if e.get("level") in ("error", "critical"))
    newest = max((e.get("ts_us") or 0 for e in read), default=0)
    empty = ""
    if not read:
        empty = "This stream has no entries yet."
    elif not kept:
        empty = f"None of the {len(read)} entries read match the filters."
    return {
        "rows": [_row(e, now) for e in kept],
        "tiles": {
            "shown": {"value": f"{len(kept):,}", "delta": f"of {len(read):,} read"},
            "warnings": {"value": f"{warnings:,}", "delta": "in this read"},
            "errors": {"value": f"{errors:,}", "delta": "in this read"},
            "newest": {"value": ago(newest, now), "delta": clock(newest, now)},
        },
        "empty": empty,
    }


def entry_of(entries: list | None, key: str) -> dict[str, Any] | None:
    """The entry a table row stands for, by its key, spelled out for the JSON viewer. None if gone."""
    for e in entries or ():
        if str(e.get("ts_us", "")) == str(key):
            ts = e.get("ts_us") or 0
            when = _dt.datetime.fromtimestamp(ts / 1_000_000).isoformat(timespec="microseconds")
            return {
                "title": f"{e.get('level', '')} at {clock(ts)}",
                "time": when,
                "ts_us": ts,
                "level": e.get("level", ""),
                "message": e.get("msg", ""),
                "fields": dict(e.get("fields") or {}),
            }
    return None


# ---- metrics ---------------------------------------------------------------


def _tile(value: str, delta: str = "", trend: str = "flat") -> dict[str, str]:
    return {"value": value, "delta": delta, "trend": trend}


def chart_of(points: list | None, now: float) -> dict[str, Any]:
    """The metrics view from one sample: ``{points, tiles, empty}``.

    ``points`` comes back ``[[epoch ms, value], ...]`` in time order, for a
    time axis. The tiles read the sample, not the series: the latest point
    drawn, and the spread of what was drawn. Every tile is ``{value, delta, trend}``.
    """
    drawn = sorted(
        (int(p["ts_us"]), float(p["value"])) for p in points or () if p.get("value") is not None
    )
    if not drawn:
        return {
            "points": [],
            "tiles": {k: _tile("-") for k in ("latest", "low", "high", "mean", "drawn")},
            "empty": "No points in this window.",
        }
    values = [v for _, v in drawn]
    last_ts, last = drawn[-1]
    first = values[0]
    trend = "up" if last > first else "down" if last < first else "flat"
    return {
        "points": [[ts // 1000, v] for ts, v in drawn],
        "tiles": {
            "latest": _tile(_number(last), ago(last_ts, now), trend),
            "low": _tile(_number(min(values))),
            "high": _tile(_number(max(values))),
            "mean": _tile(_number(sum(values) / len(values))),
            "drawn": _tile(f"{len(values):,}", f"of up to {consts.SAMPLE_LIMIT}"),
        },
        "empty": "",
    }


# ---- as Nu atoms -----------------------------------------------------------


@nu.host
def look(path: str | None) -> dict[str, str]:
    """:func:`look_of`, as a term."""
    return look_of(path)


@nu.host
def status(seen: dict, streams: int, series: int, every: float) -> dict[str, Any]:
    """:func:`status_of`, as a term."""
    return status_of(seen, streams, series, every)


@nu.host
def overview(newest: list, series: list, now: float) -> dict[str, Any]:
    """:func:`overview_of`, as a term."""
    return overview_of(newest, series, now)


@nu.host
def options(keys: list | None) -> list[dict[str, str]]:
    """:func:`options_of`, as a term."""
    return options_of(keys)


@nu.host
def pick(keys: list | None, current: str | None) -> str:
    """:func:`pick_of`, as a term."""
    return pick_of(keys, current)


@nu.host
def bounded(raw: object, default: float, lo: float, hi: float) -> float:
    """:func:`bounded_of`, as a term."""
    return bounded_of(raw, default, lo, hi)


@nu.host
def messages(entries: list | None, level: str, text: str, now: float) -> dict[str, Any]:
    """:func:`messages_of`, as a term."""
    return messages_of(entries, level, text, now)


@nu.host
def entry(entries: list | None, key: str) -> dict[str, Any] | None:
    """:func:`entry_of`, as a term."""
    return entry_of(entries, key)


@nu.host
def chart(points: list | None, now: float) -> dict[str, Any]:
    """:func:`chart_of`, as a term."""
    return chart_of(points, now)
