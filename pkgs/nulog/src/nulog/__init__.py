"""nulog -- messages + metrics, all as Nu trees, and Log planes to watch them.

Two submodules share one RocksDB (via ``nustd.kv``): :mod:`nulog.messages`
(append-only, log-indexed streams on ``nustd.kv.DictRef``) and :mod:`nulog.metrics`
(kh57 time series). One bracket to provide the store, one body of
writes-and-reads. The write API mirrors
``nustd.logging`` / Python's ``logging`` 1-1::

    import nu, nustd, nulog

    log = nulog.getLogger("app")

    tree = nu.With(nulog.store("logs.db"),
        body=nustd.kv.Transaction(
            log.info("started", extra={"port": 8080})
            >> log.warning("slow: %s ms", 210)
            >> nulog.observe("cpu_load", 0.42),
        )
        >> nustd.kv.Snapshot(nu.print(nulog.messages.tail("app", 10))),
    )
    nu.run(tree)

Or write app code in ``nustd.logging`` style and swap to persistence with
the :func:`from_std_logging` rewriter (Python's ``logging`` stays the
default sink; the rewriter walks the tree and swaps every log statement
for the equivalent persistent write)::

    import nustd

    log = nustd.logging.getLogger("app")

    body = log.info("started") >> log.warning("slow: %s ms", 210)
    tree = nu.With(nulog.store("logs.db"), body=nustd.kv.Transaction(nulog.from_std_logging(body)))

To watch a store live, install ``nulog[space]``: the Log plane shows under
``+`` in any space, and its Config plane names the store it reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from . import messages, metrics
from .client import Client, init
from .messages import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    LEVELS,
    NOTSET,
    WARN,
    WARNING,
    Logger,
    critical,
    debug,
    error,
    from_std_logging,
    getLogger,
    info,
    log,
    warn,
    warning,
)
from .metrics import observe
from .presets import store, store_ro


if TYPE_CHECKING:
    from nuspace import Extension


__version__ = "0.2.0"

__all__ = [
    "CRITICAL",
    "DEBUG",
    "ERROR",
    "FATAL",
    "INFO",
    "LEVELS",
    "NOTSET",
    "WARN",
    "WARNING",
    "Client",
    "Logger",
    "critical",
    "debug",
    "error",
    "extension",
    "from_std_logging",
    "getLogger",
    "info",
    "init",
    "log",
    "messages",
    "metrics",
    "observe",
    "store",
    "store_ro",
    "warn",
    "warning",
]


def extension() -> Extension:
    """The Log planes, as one nuspace extension."""
    from nuspace import Extension

    from .planes import PLANE

    return Extension(planes=(PLANE,))
