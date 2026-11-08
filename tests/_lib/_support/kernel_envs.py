"""Env pieces the space tests register. A module of its own so a worker can import it.

A rewrite crosses into the worker inside the body, so pickle has to find its
class by module name there. ``tests/_lib`` is on ``sys.path`` (pytest's
``pythonpath``), and spawned workers inherit it.
"""

from __future__ import annotations

import nu
from nuspace.kernel import Env
from nustd.ui.core import Frame, WsSession


class Connection(nu.Shape):
    """What the test session env holds around a body: the connection id."""

    sid = nu.StrRef.slot()


class Unseen(WsSession):
    """A ui session no browser is on: what a cell draws goes nowhere. Made on the worker."""

    def __init__(self) -> None:
        super().__init__(ws=None)

    async def send(self, frame: Frame) -> None:
        """Nothing to send to."""


def session(sid: str) -> Env:
    """What the web device registers, minus the device: a ui session no tab is on, and the connection in a frame."""
    return Env(
        wrap=lambda body: nu.Provide(Unseen, {}, body=nu.Frame(Connection, body, sid=sid)),
        label=f"session:{sid}",
    )
