"""Log-level types and constants.

Level integers mirror Python's ``logging`` module 1-1 -- ``DEBUG``, ``INFO``,
``WARNING`` (with ``WARN`` alias), ``ERROR``, ``CRITICAL`` (with ``FATAL``
alias), and ``NOTSET``.
"""

from __future__ import annotations

import logging as _pylogging


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
    "_LEVEL_NAMES",
]


DEBUG = _pylogging.DEBUG
INFO = _pylogging.INFO
WARNING = _pylogging.WARNING
WARN = _pylogging.WARNING
ERROR = _pylogging.ERROR
CRITICAL = _pylogging.CRITICAL
FATAL = _pylogging.CRITICAL
NOTSET = _pylogging.NOTSET


LEVELS: tuple[str, ...] = ("debug", "info", "warning", "error", "critical")


_LEVEL_NAMES: dict[int, str] = {
    DEBUG: "debug",
    INFO: "info",
    WARNING: "warning",
    ERROR: "error",
    CRITICAL: "critical",
    NOTSET: "notset",
}
