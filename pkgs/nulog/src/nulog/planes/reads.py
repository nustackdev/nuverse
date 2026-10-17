"""The viewer's reads, as Nu terms: each bounded, each in its own snapshot.

Every read costs what it returns, never what the store holds:

- :func:`streams`, :func:`series`: the names, the first :data:`~.consts.KEYS_CAP` in key order.
- :func:`entries`: ``count`` entries off one end of a stream, a bounded
  cursor scan (:func:`nulog.messages.tail` or :func:`nulog.messages.slice`).
- :func:`points`: a kh57 sample of a window, about twice ``n`` reads
  (:func:`nulog.metrics.sample`).
- :func:`newest`: the newest entry of each stream and a recent point of each
  series, for the overview. One entry, or a small sample, per name.

Each read opens its own snapshot under its root's tag, inside an
:class:`~.store.Opened` bracket: a snapshot is where a secondary catches up
with the writer, so every read sees the newest commits.
"""

from __future__ import annotations

import nu
import nustd.itertools
import nustd.kv
import nustd.time

from .. import messages as _messages
from .. import metrics as _metrics
from ..messages import Messages
from ..metrics import Metrics
from . import consts


__all__ = ["entries", "newest", "points", "series", "streams"]


#: Seconds back the overview looks for a series' latest point, and how many it samples there.
RECENT, RECENT_N = 300, 32


def _now_us() -> nu.Nu:
    return nustd.time.time_ns() // 1000


def streams(cap: nu.IntArg = consts.KEYS_CAP) -> nu.Nu:
    """Up to ``cap`` stream names, in key order."""
    names = nustd.itertools.islice(Messages.streams.iter(), cap)
    return nustd.kv.Snapshot(nu.Collect(names), scope=Messages)


def series(cap: nu.IntArg = consts.KEYS_CAP) -> nu.Nu:
    """Up to ``cap`` metric series names, in key order."""
    names = nustd.itertools.islice(Metrics.series.iter(), cap)
    return nustd.kv.Snapshot(nu.Collect(names), scope=Metrics)


def entries(stream: nu.StrArg, mode: nu.StrArg, count: nu.IntArg) -> nu.Nu:
    """``count`` entries of ``stream``: the newest first for ``tail``, else the oldest first.

    ``count`` is held to ``[MIN_COUNT, MAX_COUNT]`` here too: the browser
    holds its field there, but a read never trusts it.
    """
    n = nu.Int(count)
    n = nu.If(
        n < consts.MIN_COUNT, consts.MIN_COUNT, nu.If(n > consts.MAX_COUNT, consts.MAX_COUNT, n)
    )
    read = nu.If(
        nu.Str(mode) == consts.MODE_TAKE,
        _messages.slice(stream, 0, n),
        _messages.tail(stream, n),
    )
    return nustd.kv.Snapshot(read, scope=Messages)


def points(name: nu.StrArg, window: nu.IntArg, n: nu.IntArg = consts.SAMPLE_LIMIT) -> nu.Nu:
    """Up to ``n`` sampled points of ``name`` from the last ``window`` seconds, 0 for all of it.

    Rows as :func:`nulog.metrics.sample` gives them, ``{ts_us, ts, value}``, unordered.
    """
    w = nu.Int(window)
    begin = nu.If(w > 0, _now_us() - w * 1_000_000, 0)
    return nustd.kv.Snapshot(_metrics.sample(name, n, begin), scope=Metrics)


def newest(names: nu.Nu, kinds: nu.Nu) -> nu.Nu:
    """The overview's read: ``[[stream, [entry]], ...]`` and ``[[series, [point, ...]], ...]``.

    Args:
        names: Stream names, as :func:`streams` read them.
        kinds: Series names, as :func:`series` read them.
    """
    recent = _now_us() - RECENT * 1_000_000
    per_stream = nu.List(names).iter().map(lambda s: nu.List.of(s, _messages.tail(nu.Str(s), 1)))
    per_series = (
        nu.List(kinds)
        .iter()
        .map(lambda m: nu.List.of(m, _metrics.sample(nu.Str(m), RECENT_N, recent)))
    )
    return nu.List.of(
        nustd.kv.Snapshot(per_stream.to_list(), scope=Messages),
        nustd.kv.Snapshot(per_series.to_list(), scope=Metrics),
    )
