"""A nulog store opened at a path read at run time, read only, under its own tags.

:func:`~nulog.presets.store_ro` takes its path as Python, when the tree is
built. A viewer whose path is a setting only learns it while it runs, and a
``Provide`` takes its kwargs as plain values, never terms. :class:`Opened`
is the bracket for that: its path is a child, evaluated on entry, and the
store is opened there for the body and closed after.

The store is bound under the nulog root shapes as tags (:class:`Messages`,
:class:`Metrics`), the way a space's own stores are bound under ``Space``
and ``States``: kv refs find their navigator by root shape, so a read of
``Messages.streams`` lands here and a space's own reads never do. Brackets
over it name the tag too: ``nustd.kv.Snapshot(read, scope=Messages)``.

Always a RocksDB secondary, so it is safe on a store another process is
writing: it catches up with the writer each time a snapshot opens. Its own
small directory is a fresh temp one, removed when the bracket closes.
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING

from virtuals import Navigator

import nu
import nustd.kv
from nu.core.spans.bracket import _LifecycleBracket

from ..messages import Messages
from ..metrics import Metrics
from .fmt import look_of


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator
    from contextlib import AbstractContextManager

    from nu.lang.runtime import Context, Runtime


__all__ = ["TAGS", "NotAStore", "Opened", "aopened", "opened"]


#: What the store is bound under: the first carries the whole stack, the rest its navigator.
TAGS = (Messages, Metrics)


class NotAStore(ValueError):  # noqa: N818 -- names what the path is not
    """Raised when the path an :class:`Opened` reads is not a RocksDB store."""


def _stack(path: str, secondary: str) -> nu.With:
    """The kv stack over ``path``, a secondary keeping its state in ``secondary``."""
    return nustd.kv.rocksdb_navigator(path, tags=TAGS[:1], read_only=True, secondary_path=secondary)


def _checked(path: object) -> str:
    """``path`` made absolute, refused unless a store is there: a RocksDB open would make one."""
    seen = look_of(str(path or ""))
    if seen["state"] != "ok":
        raise NotAStore(seen["note"])
    return seen["path"]


@contextmanager
def opened(ctx: Context, path: object) -> Iterator[None]:
    """The store at ``path`` bound on ``ctx`` for the ``with`` body, closed after. Sync.

    Raises:
        NotAStore: Nothing at ``path``, or something other than a store.
    """
    where = _checked(path)
    secondary = tempfile.mkdtemp(prefix="nulog-view-")
    try:
        with _stack(where, secondary)._open(ctx):
            nav = ctx.fabrics.get(Navigator, TAGS[0])
            with _also(ctx, nav):
                yield
    finally:
        shutil.rmtree(secondary, ignore_errors=True)


@asynccontextmanager
async def aopened(ctx: Context, path: object) -> AsyncIterator[None]:
    """:func:`opened`, under the async runtime."""
    where = _checked(path)
    secondary = tempfile.mkdtemp(prefix="nulog-view-")
    try:
        async with _stack(where, secondary)._aopen(ctx):
            nav = ctx.fabrics.get(Navigator, TAGS[0])
            with _also(ctx, nav):
                yield
    finally:
        shutil.rmtree(secondary, ignore_errors=True)


def _also(ctx: Context, nav: Navigator) -> AbstractContextManager[None]:
    """The one navigator bound under :class:`Metrics` too, so both roots find it."""
    return ctx.fabrics.bind(Navigator, nav, TAGS[1])


class Opened(_LifecycleBracket):
    """Runs ``body`` with the nulog store at ``path`` open, read only.

    Args:
        path: A term yielding the store's directory, read once on entry.
            ``~`` expands, a relative path is taken from the process's cwd.
        body: Runs with the store bound under :data:`TAGS`. Its reads bracket
            themselves: ``nustd.kv.Snapshot(read, scope=Messages)``, and
            ``scope=Metrics`` for metrics.

    Raises:
        NotAStore: Nothing at ``path``, or not a RocksDB store. Check with
            :func:`~nulog.planes.fmt.look` first to say so instead.

    Notes:
        - The body is a scalar: a stream body is not held open across its drain.
        - Read only: a write in the body fails.

    Yields:
        Whatever ``body`` yields.
    """

    def __init__(self, path: nu.StrArg, body: nu.Nu) -> None:
        super().__init__(body, nu.Str(path) if isinstance(path, str) else path)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        body, path = children

        def thunk(rt: Runtime) -> object:
            with opened(rt.ctx, path(rt)):
                return body(rt)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        body, path = children

        async def athunk(rt: Runtime) -> object:
            async with aopened(rt.ctx, await path(rt)):
                return await body(rt)

        return athunk
