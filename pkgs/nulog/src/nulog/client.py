"""Imperative Python bridge -- hold a nulog store open, run trees against it.

Each write builds the same ``@nu`` Command tree the standalone builders return,
wraps it in :class:`nustd.kv.Transaction`, drives it against a persistent
:class:`nu.Context` bound to a Navigator over the storage. Each read wraps
the Query in :class:`nustd.kv.Snapshot`, drives it, returns the value.

Usage::

    import nulog

    with nulog.init("logs.db") as log:
        log.info("started", extra={"port": 8080})
        log.observe("cpu_load", 0.42)
        rows = log.tail("root", 10)
        pts = log.sample("cpu_load", 500)

Always a RocksDB store on disk. The Client is a plain context manager -- ``close()`` unwinds the
storage stack; leaking it leaks the RocksDB handle until process exit.
"""

from __future__ import annotations

from contextlib import ExitStack
from typing import TYPE_CHECKING

from virtuals import Navigator

import nu
import nustd

from . import messages as _messages
from . import metrics as _metrics


if TYPE_CHECKING:
    from types import TracebackType

    # `typing.Self` is 3.11+, and this package supports 3.10. Annotations are
    # strings here (`from __future__ import annotations`), so the name is only
    # ever needed by a type checker -- nothing imports it at runtime.
    from typing_extensions import Self


__all__ = ["Client", "init"]


class Client:
    """Handle over an open nulog store; imperative wrapper around Nu trees.

    Constructed by :func:`init`; do not instantiate directly.
    """

    def __init__(self, ctx: nu.Context, stack: ExitStack) -> None:
        self._ctx = ctx
        self._stack = stack

    # --- messages: writes ---------------------------------------------------

    def log(
        self,
        level: int | str,
        msg: str,
        *args: object,
        stream: str = "root",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Append one entry to ``stream`` at ``level``."""
        self._write(_messages.append(stream, level, msg, args, extra))

    def debug(
        self,
        msg: str,
        *args: object,
        stream: str = "root",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Append a DEBUG entry."""
        self._write(_messages.append(stream, _messages.DEBUG, msg, args, extra))

    def info(
        self,
        msg: str,
        *args: object,
        stream: str = "root",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Append an INFO entry."""
        self._write(_messages.append(stream, _messages.INFO, msg, args, extra))

    def warning(
        self,
        msg: str,
        *args: object,
        stream: str = "root",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Append a WARNING entry."""
        self._write(_messages.append(stream, _messages.WARNING, msg, args, extra))

    warn = warning

    def error(
        self,
        msg: str,
        *args: object,
        stream: str = "root",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Append an ERROR entry."""
        self._write(_messages.append(stream, _messages.ERROR, msg, args, extra))

    def critical(
        self,
        msg: str,
        *args: object,
        stream: str = "root",
        extra: dict[str, object] | None = None,
    ) -> None:
        """Append a CRITICAL entry."""
        self._write(_messages.append(stream, _messages.CRITICAL, msg, args, extra))

    # --- messages: reads ----------------------------------------------------

    def tail(self, stream: str, n: int) -> list[dict]:
        """The newest ``n`` entries of ``stream``, newest-first (O(n))."""
        return self._read(_messages.tail(stream, n))

    def slice(self, stream: str, start: int, stop: int, step: int = 1) -> list[dict]:
        """Positional forward slice of ``stream`` (O(stop))."""
        return self._read(_messages.slice(stream, start, stop, step))

    # --- metrics: writes ----------------------------------------------------

    def observe(self, name: str, value: float, *, ts: float | None = None) -> None:
        """Append one point to metric ``name``."""
        self._write(_metrics.observe(name, value, ts=ts))

    # --- metrics: reads -----------------------------------------------------

    def range(self, name: str, begin: int, end: int) -> list[dict]:
        """Every point in ``name`` with key in ``[begin, end)`` (µs), key-ordered."""
        return self._read(_metrics.range(name, begin, end))

    def sample(
        self,
        name: str,
        n: int,
        begin: int | None = None,
        end: int | None = None,
    ) -> list[dict]:
        """Up to ``n`` kh57-sampled points from ``name`` in ``[begin, end)`` (µs)."""
        return self._read(_metrics.sample(name, n, begin, end))

    # --- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Unwind the storage stack; safe to call more than once."""
        self._stack.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --- internals ----------------------------------------------------------

    def _write(self, tree: nu.Nu) -> None:
        nu.run(nustd.kv.Transaction(tree), self._ctx)

    def _read(self, tree: nu.Nu) -> object:
        value, _ = nu.run(nustd.kv.Snapshot(tree), self._ctx)
        return value


def init(path: str) -> Client:
    """Open a nulog store; return a :class:`Client` bound to it.

    Args:
        path: The RocksDB directory. Created if it is not there.

    Prefer the context-manager form so the storage handle unwinds
    deterministically::

        with nulog.init("logs.db") as log:
            log.info("hello")
    """
    stack = ExitStack()
    storage = stack.enter_context(nustd.kv.rocksdb_storage(path))
    ctx = nu.Context().bind(Navigator, Navigator(storage))
    return Client(ctx, stack)
