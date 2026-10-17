"""Write + read primitives over the metric store.

Write:
- :func:`observe` -- append one point to ``Metrics.series[name].points``
  keyed by microsecond epoch. Same-us writes collide (last-write-wins);
  pass an explicit ``ts`` for replay or batches.

Read:
- :func:`range`  -- every point with kh57 key in ``[begin, end)``,
  key-ordered. Indexed; cost is O(number of points in the window).
- :func:`sample` -- kh57 range reservoir sample: up to ``n`` points from
  ``[begin, end)``. Stable under appends outside the window. ~``2n`` reads, not O(series size).

Rows: ``{"ts_us": int, "ts": float, "value": float}``.
"""

from __future__ import annotations

import nu
import nustd

from .shapes import Metrics


__all__ = [
    "observe",
    "range",
    "sample",
]


# --- write -----------------------------------------------------------------


def observe(name: nu.StrArg, value: nu.FloatArg, *, ts: nu.FloatArg | None = None) -> nu.Nu:
    """Append one point to metric ``name``.

    Args:
        name: series name (``"cpu_load"``, ``"http_latency_ms"``, ...).
        value: the sample. Python numbers get wrapped in ``Float``; a
            Nu expression (Ref / Query yielding a float) is cast through
            ``nu.float`` so live-computed values (rates from a loop,
            deltas over scratch counters, etc.) can be observed directly.
        ts: optional wall-clock time (seconds since epoch). When ``None``,
            key + ``ts`` are minted at eval time. Same-microsecond writes
            collide (last-write-wins).
    """
    key_us = nustd.time.time_ns() // 1000 if ts is None else nu.int(nu.float(ts) * 1_000_000)
    return nu.let(
        key_us,
        lambda key: Metrics.series[name].points.set_item(
            key,
            nu.Dict.of(ts=nu.Int(key) / 1_000_000.0, value=nu.float(value)),
        ),
    )


# --- read ------------------------------------------------------------------


def _row(pair: nu.Attr) -> nu.Dict:
    """The ``{ts_us, ts, value}`` row off one ``(key_us, point)`` pair."""
    return nu.Dict.of(ts_us=pair[0], ts=pair[1]["ts"], value=pair[1]["value"])


def range(
    name: nu.StrArg,
    begin: nu.IntArg,
    end: nu.IntArg,
) -> nu.List:
    """Every point in ``name`` with kh57 key in ``[begin, end)``, key-ordered.

    Keys are microsecond epochs, so ``begin`` / ``end`` are microsecond
    bounds. Indexed under the hood: cost is O(number of points in the
    window), not O(series size).
    """
    return Metrics.series[name].points.range(begin, end).iter().map(_row).to_list()


def sample(
    name: nu.StrArg,
    n: nu.IntArg,
    begin: nu.IntArg | None = None,
    end: nu.IntArg | None = None,
) -> nu.List:
    """Up to ``n`` kh57-sampled points from ``name`` in ``[begin, end)``.

    Kh57 range reservoir sampling: stable under appends outside the
    queried range. Cost is ~``2n`` reads, not O(series size); this is what
    kh57 buys.
    """
    return Metrics.series[name].points.sample(n, begin, end).iter().map(_row).to_list()
