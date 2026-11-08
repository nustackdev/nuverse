"""The loop's store inside a space: the session and the world both in the engine's plane state.

A :class:`nuagent.core.Store` whose session is :class:`~.state.Chat` and whose
run is :class:`~.state.Run`, both read through the running plane's place,
``nuspace.at.plane.state(...)``: the engine's own state, whichever engine
runs. The place reads ``Here.plane`` when the term runs, so the loop built
while the engine runs lands on that engine with no rewrite.

- ``bracket``: the loop's own short steps, one commit
  (:func:`nuspace.atomic`).
- ``rewrite``: anything on the world, the model's program among them,
  through :func:`nuspace.bracketed`: a bracket per step where the
  program has none, the ones it brings kept. A program written for the
  space brackets itself (the nuspace skill says so), and one that does not
  still runs.

Neither is held across the backend's answer or the program's run: the loop
keeps that rule, and ``bracketed`` gives each step of a program its own.
``bound`` is the term as it is: the cell run already binds the stores.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import nuspace

from .state import Chat, Run


if TYPE_CHECKING:
    import nu


__all__ = ["SpaceStore"]


class SpaceStore:
    """The engine plane's state, as a :class:`nuagent.core.Store`. Only inside a cell run."""

    session: ClassVar[Chat] = nuspace.at.plane.state(Chat)
    run: ClassVar[Run] = nuspace.at.plane.state(Run)

    @staticmethod
    def bracket(body: nu.Nu) -> nu.Nu:
        """``body`` on the engine's plane state, one commit."""
        return nuspace.atomic(body)

    @staticmethod
    def rewrite(term: nu.Nu) -> nu.Nu:
        """``term`` bracketed per step, the brackets it brings kept."""
        return nuspace.bracketed(term)

    @staticmethod
    def bound(body: nu.Nu) -> nu.Nu:
        """``body`` as it is: the stores are the space's, bound around every cell run."""
        return body
