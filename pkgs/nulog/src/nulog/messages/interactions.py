"""Value-only seams for the write path -- raw host atoms + typed wrappers.

- ``*Host`` -- bare :func:`nu.host` atoms bound to the Python impl. Both
  are pure functions of their inputs.
- Typed snake_case wrappers (:func:`level_name`, :func:`percent_format`)
  -- return a real :class:`~nu.forms.Str` Form so downstream expressions
  type-infer as strings instead of ``object``.
"""

from __future__ import annotations

import nu

from .types import _LEVEL_NAMES


__all__ = [
    "LevelNameHost",
    "PercentFormatHost",
    "level_name",
    "percent_format",
]


# --- raw impls (plain Python) ------------------------------------------------


def _level_name_impl(level: int | str) -> str:
    """Normalize a level (int or name) into the canonical lowercase name."""
    if isinstance(level, int) and not isinstance(level, bool):
        return _LEVEL_NAMES.get(level, "info")
    if isinstance(level, str):
        low = level.lower()
        return "warning" if low == "warn" else low
    return "info"


def _percent_format_impl(msg: str, *args: object) -> str:
    """``msg % args`` if args are present, else ``str(msg)``.

    Mirrors ``logging.LogRecord.getMessage``.
    """
    if not args:
        return msg
    try:
        return msg % args
    except (TypeError, ValueError):
        return msg + " " + " ".join(str(a) for a in args)


# --- raw host atoms (untyped -- factory calls) -------------------------------

LevelNameHost = nu.host(_level_name_impl, name="LevelName")
PercentFormatHost = nu.host(_percent_format_impl, name="PercentFormat")


# --- typed wrappers (public) -------------------------------------------------


def level_name(level: nu.IntArg | nu.StrArg) -> nu.Str:
    """Normalize a level (int or name) into the canonical lowercase name."""
    return nu.Str(LevelNameHost(level))


def percent_format(msg: nu.StrArg, *args: object) -> nu.Str:
    """``msg % args`` at eval time, mirroring ``logging.LogRecord.getMessage``."""
    return nu.Str(PercentFormatHost(msg, *args))
