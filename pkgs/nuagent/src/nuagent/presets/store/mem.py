"""Session memory on nu's mem fabric: for one-off runs and tests, gone when the run ends.

:meth:`MemStore.bound` puts two dicts under a run. One is the session's own,
bound under :class:`MemSession`, so nothing the model writes can reach the
conversation. The other is an untagged scratch world, where the model's own
mem Shapes land, ``Run`` among them. A caller with a world of its own binds
it and frames the session alone.

mem needs no brackets, so both of the store's brackets hand their term back
as it is.

The slots are the ones every store preset has, in the same order, so the
loop never knows which store it runs on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import nu
from nuagent.core import Run


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = ["MemOutcome", "MemSession", "MemStore"]


class MemOutcome(nu.Shape):
    """How the last program went. ``kind`` is one of :data:`nuagent.protocol.KINDS`."""

    kind = nu.StrRef.slot()
    value = nu.StrRef.slot()  #: repr of the yield, for ``ok``
    message = nu.StrRef.slot()  #: what went wrong, for ``construct`` and ``runtime``
    line = nu.IntRef.slot()  #: source line of a ``construct`` failure, when it has one


class MemSession(nu.Shape):
    """One run's working memory: the conversation, the latest reply, its program, how it went."""

    messages = nu.ListRef.slot(dict)  #: ``{role, content}``, appended to, never rebuilt
    reply = nu.StrRef.slot()
    program = nu.ProgramRef.slot()
    outcome = nu.ShapeRef.slot(MemOutcome)


class MemStore:
    """The mem store, as a :class:`nuagent.core.Store`.

    Example:
        store = MemStore()
        nu.run(store.bound(agent(store, backend, task)))
    """

    session: ClassVar[type[nu.Shape]] = MemSession
    run: ClassVar[type[nu.Shape]] = Run

    @staticmethod
    def bracket(body: Nu) -> Nu:
        """``body`` as it is: mem reads and writes need no bracket."""
        return body

    @staticmethod
    def rewrite(term: Nu) -> Nu:
        """``term`` as it is: the world is mem too."""
        return term

    @staticmethod
    def bound(body: Nu) -> Nu:
        """``body`` with a fresh session and a fresh scratch world.

        Args:
            body: the run, usually :func:`nuagent.core.agent` over this store.

        Returns:
            The body inside an untagged world dict and a :class:`MemSession` frame.
        """
        return nu.With(nu.Provide(dict, {}), body=nu.Frame(MemSession, body))
