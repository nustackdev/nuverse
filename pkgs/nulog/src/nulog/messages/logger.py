"""Python-``logging``-shaped facades over :func:`.ops.append`.

Two surfaces, one wire underneath:

- :class:`Logger` + :func:`getLogger` -- the bound class-based surface. The
  logger *name* IS the stream name; each method returns a Nu Command tree
  carrying that name.
- Module-level :func:`info` / :func:`debug` / :func:`log` / ... -- one-off
  writes to the ``root`` stream, mirroring ``logging.info`` and friends.

Both fan into :func:`.ops.append` on
``Messages.streams[name].entries``::

    from nulog import getLogger

    log = getLogger("app")

    tree = (
        log.info("server started")
        >> log.warning("cache miss for %s", key)
        >> log.error("checkout failed", extra={"code": 500})
    )
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .ops import append
from .types import CRITICAL, DEBUG, ERROR, INFO, WARNING


if TYPE_CHECKING:
    import nu


__all__ = [
    "Logger",
    "critical",
    "debug",
    "error",
    "getLogger",
    "info",
    "log",
    "warn",
    "warning",
]


class Logger:
    """Bound logger. Mirrors ``nustd.logging.Logger`` / ``logging.Logger``.

    ``getLogger(__name__)`` at module top, then ``log.info(...)`` at call sites.
    Each method returns a Nu Command tree carrying the bound stream name.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        """Bind this Logger to stream ``name``."""
        self._name = name

    @property
    def name(self) -> str:
        """The stream name this logger is bound to."""
        return self._name

    def log(
        self,
        level: nu.IntArg | nu.StrArg,
        msg: nu.StrArg,
        *args: object,
        extra: dict[str, object] | None = None,
    ) -> nu.Nu:
        """Build a persistent entry at ``level``."""
        return append(self._name, level, msg, args, extra)

    def debug(self, msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent DEBUG entry."""
        return append(self._name, DEBUG, msg, args, extra)

    def info(self, msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent INFO entry."""
        return append(self._name, INFO, msg, args, extra)

    def warning(
        self, msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None
    ) -> nu.Nu:
        """Build a persistent WARNING entry."""
        return append(self._name, WARNING, msg, args, extra)

    warn = warning

    def error(self, msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
        """Build a persistent ERROR entry."""
        return append(self._name, ERROR, msg, args, extra)

    def critical(
        self, msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None
    ) -> nu.Nu:
        """Build a persistent CRITICAL entry."""
        return append(self._name, CRITICAL, msg, args, extra)

    fatal = critical

    def __repr__(self) -> str:
        return f"nulog.Logger(name={self._name!r})"


def getLogger(name: str | None = None) -> Logger:  # noqa: N802
    """Return a bound :class:`Logger`. Mirrors ``logging.getLogger``."""
    return Logger(name if name is not None else "root")


# --- module-level root-stream facade --------------------------------------

_root = Logger("root")


def debug(msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream DEBUG entry. Mirrors ``logging.debug``."""
    return _root.debug(msg, *args, extra=extra)


def info(msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream INFO entry. Mirrors ``logging.info``."""
    return _root.info(msg, *args, extra=extra)


def warning(msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream WARNING entry. Mirrors ``logging.warning``."""
    return _root.warning(msg, *args, extra=extra)


warn = warning


def error(msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream ERROR entry. Mirrors ``logging.error``."""
    return _root.error(msg, *args, extra=extra)


def critical(msg: nu.StrArg, *args: object, extra: dict[str, object] | None = None) -> nu.Nu:
    """Root-stream CRITICAL entry. Mirrors ``logging.critical``."""
    return _root.critical(msg, *args, extra=extra)


def log(
    level: nu.IntArg | nu.StrArg,
    msg: nu.StrArg,
    *args: object,
    extra: dict[str, object] | None = None,
) -> nu.Nu:
    """Root-stream entry at ``level``. Mirrors ``logging.log``."""
    return _root.log(level, msg, *args, extra=extra)
