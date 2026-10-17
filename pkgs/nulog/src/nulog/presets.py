"""Ready-made brackets: store (kv navigator) and store_ro (its read-only twin)."""

from __future__ import annotations

import tempfile
from typing import TYPE_CHECKING

import nustd


if TYPE_CHECKING:
    import nu


__all__ = ["store", "store_ro"]


def store(path: str) -> nu.With:
    """A bracket providing the RocksDB nulog at ``path``: Codec + Observer + storage + Navigator.

    Always on disk, so the Log planes can read it from a space while this
    process writes. Every ``nulog.getLogger(...)`` / ``.info()`` /
    ``nulog.observe()`` / ``nulog.messages.tail()`` / ... inside the body
    reads and writes through it.
    """
    return nustd.kv.rocksdb_navigator(path)


def store_ro(path: str, *, secondary_path: str | None = None) -> nu.With:
    """Read-only Navigator over the RocksDB nulog at ``path``, secondary mode.

    Always opens as a RocksDB secondary instance that catches up with the
    primary in the background, so a live DB another process is writing is
    safe to read. ``secondary_path`` defaults to a fresh directory under
    the system temp dir (not cleaned up on process exit -- the tail files
    are tiny; pass an explicit path if you want to control lifetime).
    """
    if secondary_path is None:
        secondary_path = tempfile.mkdtemp(prefix="nulog-sec-")
    return nustd.kv.rocksdb_navigator(
        path,
        read_only=True,
        secondary_path=secondary_path,
    )
