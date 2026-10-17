"""Log-message store layout.

One shape tree: :class:`Messages` at the root, keyed by stream name, each
stream an append-only, log-indexed ``DictRef`` of :class:`LogEntry`.

No kh57 key encoding on the message path -- ordering is positional (append time),
which is chronological by construction.
Kh57 stays on the metric side because that's where reservoir sampling earns its keep.
"""

from __future__ import annotations

from virtuals.views import LazyLogIndexedDictView

import nu
import nustd


__all__ = [
    "LogEntry",
    "MessageStream",
    "Messages",
]


class LogEntry(nu.Shape):
    """One log line -- immutable.

    ``ts_us`` is absolute epoch microseconds captured at eval time. ``fields``
    is a whole-blob dict of structured kwargs, stored opaquely via
    :class:`~nustd.kv.PrimitiveDictRef` (no per-key decomposition).
    """

    ts_us = nustd.kv.IntRef.slot()
    level = nustd.kv.StrRef.slot()
    msg = nustd.kv.StrRef.slot()
    fields = nustd.kv.PrimitiveDictRef.slot()


class MessageStream(nu.Shape):
    """One named stream -- append-only sequence of :class:`LogEntry`.

    A ``DictRef`` laid out as a :class:`LazyLogIndexedDictView` rather than
    a positional list, so parallel writers never contend on the same
    rocksdb row: each entry lands under its own unique key, and the view
    keeps insertion order in a log index beside it.
    """

    entries = nustd.kv.DictRef.slot(LogEntry, view=LazyLogIndexedDictView)


class Messages(nu.Shape):
    """The message store root -- every stream, keyed by name."""

    streams = nustd.kv.DictRef.slot(MessageStream)
