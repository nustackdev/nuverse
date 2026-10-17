"""Read + write primitives over the message store.

Write:
- :func:`append` -- the write-tree primitive. Every logger method, every
  ``std_compat`` rewrite, every direct write funnels through here.

Read:
- :func:`tail`  -- newest N, newest-first. O(n) via a bounded reverse-cursor
  scan (``reversed_values``), safe against arbitrarily large streams.
- :func:`slice` -- forward ``islice`` over ``.values()``. O(``stop``), no
  full-stream materialization. Non-negative bounds only; for "last N",
  use :func:`tail`.

Rows: ``{"ts_us": int, "level": str, "msg": str, "fields": dict}``.

Callers who want level or substring filtering do it *outside* the read
(``[r for r in rows if r["level"] == "error"]``). No index-less full-scan
predicates live in this module -- this is not Elasticsearch.
"""

from __future__ import annotations

import nu
import nustd

from .interactions import level_name, percent_format
from .shapes import Messages


__all__ = [
    "append",
    "slice",
    "tail",
]


# --- write -----------------------------------------------------------------


def append(
    stream: nu.StrArg,
    level: nu.IntArg | nu.StrArg,
    msg: nu.StrArg,
    args: tuple[object, ...],
    extra: nu.DictArg[str, object] | None,
) -> nu.Nu:
    """Build the Command tree that appends one entry to ``stream``."""
    return Messages.streams[stream].entries.set_item(
        nustd.uuid.uuid4().hex(),
        nu.Dict.of(
            ts_us=nustd.time.time_ns() // 1000,
            level=level_name(level),
            msg=percent_format(msg, *args),
            fields=extra or {},
        ),
    )


# --- read ------------------------------------------------------------------


def _row(entry: nu.Attr) -> nu.Dict:
    """The ``{ts_us, level, msg, fields}`` row projected off one stored entry."""
    return nu.Dict.of(
        ts_us=entry["ts_us"],
        level=entry["level"],
        msg=entry["msg"],
        fields=entry["fields"],
    )


def tail(stream: nu.StrArg, n: nu.IntArg) -> nu.List:
    """The newest ``n`` entries of ``stream``, newest-first.

    O(n) via a bounded reverse-cursor scan over the log index: reads
    exactly n entries regardless of stream size.
    """
    newest = Messages.streams[stream].entries.reversed_values()
    return nu.Iterator(nustd.itertools.islice(newest, n)).map(_row).to_list()


def slice(
    stream: nu.StrArg,
    start: nu.IntArg,
    stop: nu.IntArg,
    step: nu.IntArg = 1,
) -> nu.List:
    """Positional forward slice of ``stream``: ``islice(entries, start, stop, step)``.

    O(``stop``): walks the value stream via ``itertools.islice`` and stops
    early, with no full-stream materialization. Non-negative bounds only;
    for "last N" use :func:`tail`.
    """
    entries = Messages.streams[stream].entries.values()
    return nu.Iterator(nustd.itertools.islice(entries, start, stop, step)).map(_row).to_list()
