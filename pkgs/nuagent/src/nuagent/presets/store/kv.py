"""Session memory on ``nustd.kv``: durable runs, a conversation that outlives the process.

Two stores under a run, both kv. The session's is tagged by
:class:`KVSession`, so nothing the model writes can reach the conversation.
The world's is untagged, the default every untagged kv Shape lands in: the
model's own Shapes, and :class:`KVRun` it ends the run through. They may be
one sqlite file. That is safe because no bracket is ever held across the
backend's answer or the program's run, so the two never wait on each other.

**The brackets are placed here, not by the loop.** ``nustd.kv.Atomic`` picks
a ``Snapshot`` or a ``Transaction`` from its body's own writes, at build
time. :meth:`KVStore.bracket` wraps the loop's short session steps on
:class:`KVSession`'s store, :meth:`KVStore.rewrite` wraps world terms on the
untagged one. The model's program is a world term the loop cannot see until
it is built, so it reaches ``rewrite`` through ``LoadNu``'s own ``rewrite``
slot: built first, bracketed after, so ``Atomic`` sees its writes.

**One bracket per program.** The model's whole program runs in one
bracket. A program that writes and also waits on something slow (a model
call, a sleep) holds the world's write lock for as long as that takes.

The slots are the ones every store preset has, in the same order, so the
loop never knows which store it runs on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import nu
import nustd.kv


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu


__all__ = ["KVOutcome", "KVRun", "KVSession", "KVStore"]


class KVOutcome(nu.Shape):
    """How the last program went. ``kind`` is one of :data:`nuagent.protocol.KINDS`."""

    kind = nustd.kv.StrRef.slot()
    value = nustd.kv.StrRef.slot()  #: repr of the yield, for ``ok``
    message = nustd.kv.StrRef.slot()  #: what went wrong, for ``construct`` and ``runtime``
    line = nustd.kv.IntRef.slot()  #: source line of a ``construct`` failure, when it has one


class KVSession(nu.Shape):
    """One run's working memory: the conversation, the latest reply, its program, how it went."""

    messages = nustd.kv.ListRef.slot(dict)  #: ``{role, content}``, appended to, never rebuilt
    reply = nustd.kv.StrRef.slot()
    program = nustd.kv.ProgramRef.slot()
    outcome = nustd.kv.ShapeRef.slot(KVOutcome)


class KVRun(nu.Shape):
    """The run itself, on the kv world. Untagged for the same reason as ``nuagent.core.Run``."""

    done = nustd.kv.BoolRef.slot()


class KVStore:
    """A kv store, as a :class:`nuagent.core.Store`.

    Args:
        navigator: a ``nustd.kv`` navigator preset, called once for the
            session (tagged :class:`KVSession`) and once for the world
            (untagged). Omitted, two in-memory stacks.
        **options: the preset's own kwargs, the same for both
            (``path=``, ``busy_timeout=``, ...).

    Example:
        store = KVStore.sqlite("run.db")
        await nu.arun(store.bound(agent(store, backend, task)))
    """

    session: ClassVar[type[nu.Shape]] = KVSession
    run: ClassVar[type[nu.Shape]] = KVRun

    def __init__(
        self, navigator: Callable[..., Nu] = nustd.kv.memory_navigator, **options: object
    ) -> None:
        self.navigator = navigator
        self.options = options

    @classmethod
    def sqlite(cls, path: str, **options: object) -> KVStore:
        """Session and world on one sqlite file at ``path``."""
        return cls(nustd.kv.sqlite_navigator, path=path, **options)

    @staticmethod
    def bracket(body: Nu) -> Nu:
        """``body`` in a Snapshot or a Transaction on the session's store, by its writes."""
        return nustd.kv.Atomic(body, scope=KVSession)

    @staticmethod
    def rewrite(term: Nu) -> Nu:
        """``term`` in a Snapshot or a Transaction on the world's store, by its writes."""
        return nustd.kv.Atomic(term)

    def bound(self, body: Nu) -> Nu:
        """``body`` with the session's store and the world's bound around it."""
        session = self.navigator(tags=(KVSession,), **self.options)
        return nu.With(session, self.navigator(**self.options), body=body)
