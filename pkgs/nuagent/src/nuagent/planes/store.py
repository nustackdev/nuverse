"""The loop's store inside a space: the session and the world both in the engine's plane state.

A :class:`nuagent.core.Store` whose session is :class:`~.state.Chat` and whose
run is :class:`~.state.Run`, both ``PlaneState``. The engine builds its loop
while it runs (it needs the settings first), and a term built then is not
the one the kernel rerooted, so both brackets land their term under the
running cell first, through :class:`~nuspace.ops.Here`, as the kernel would
have.

- ``bracket``: the loop's own short steps, one commit on States
  (:func:`nuspace.ops.atomic_state`).
- ``rewrite``: anything on the world, the model's program among them,
  through :func:`nuspace.ops.bracketed`: a bracket per step where the
  program has none, the ones it brings kept. A program written for the
  space brackets itself (the nuspace skill says so), and one that does not
  still runs.

Neither is held across the backend's answer or the program's run: the loop
keeps that rule, and ``bracketed`` gives each step of a program its own.
``bound`` is the term as it is: the cell run already binds both stores.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from nuspace import ops
from nuspace.shapes import reroot

from .state import Chat, Run


if TYPE_CHECKING:
    import nu


__all__ = ["SpaceStore", "here"]


def here(term: nu.Nu) -> nu.Nu:
    """``term`` with its state chains under the running cell and its plane. Bare."""
    return reroot(term, ops.Here.plane, ops.Here.cell)


class SpaceStore:
    """The engine plane's state, as a :class:`nuagent.core.Store`. Only inside a cell run."""

    session: ClassVar[type[Chat]] = Chat
    run: ClassVar[type[Run]] = Run

    @staticmethod
    def bracket(body: nu.Nu) -> nu.Nu:
        """``body`` landed on the engine's plane state, one commit."""
        return ops.atomic_state(here(body))

    @staticmethod
    def rewrite(term: nu.Nu) -> nu.Nu:
        """``term`` landed under the engine's cell and plane, bracketed per step."""
        return ops.bracketed(term)

    @staticmethod
    def bound(body: nu.Nu) -> nu.Nu:
        """``body`` as it is: the stores are the space's, bound around every cell run."""
        return body
