"""nulog.messages -- log-message store: types + core write/read + facades.

Module layout:

Core (what a log IS):
- :mod:`.shapes`       -- store layout (``Messages`` / ``MessageStream`` / ``LogEntry``).
- :mod:`.interactions` -- host atoms + typed seams (``level_name`` / ``percent_format``).
- :mod:`.ops`          -- write + read primitives (``append`` / ``tail`` / ``slice``).

DX (Python-logging-shaped facades):
- :mod:`.logger`       -- ``Logger`` class + ``getLogger`` + module-level root facade
  (``info`` / ``debug`` / ``log`` / ...).

std compat:
- :mod:`.std_compat`   -- ``from_std_logging`` rewrites ``nustd.logging`` atoms into persistent writes.

Types:
- :mod:`.types`        -- level int constants + canonical name tuple.
"""

from __future__ import annotations

from .interactions import level_name, percent_format
from .logger import (
    Logger,
    critical,
    debug,
    error,
    getLogger,
    info,
    log,
    warn,
    warning,
)
from .ops import append, slice, tail
from .shapes import LogEntry, Messages, MessageStream
from .std_compat import from_std_logging
from .types import (
    CRITICAL,
    DEBUG,
    ERROR,
    FATAL,
    INFO,
    LEVELS,
    NOTSET,
    WARN,
    WARNING,
)


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
    "LogEntry",
    "Logger",
    "MessageStream",
    "Messages",
    "append",
    "critical",
    "debug",
    "error",
    "from_std_logging",
    "getLogger",
    "info",
    "level_name",
    "log",
    "percent_format",
    "slice",
    "tail",
    "warn",
    "warning",
]
