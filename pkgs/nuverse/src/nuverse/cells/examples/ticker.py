"""A ticker: one stat tile, and a count kept in its own state, one a second while the plane is up."""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.specs import CellSpec

from .. import source


__all__ = ["CELL", "Tick", "out"]


class Tick(nu.Shape):
    """The ticker's state: the seconds counted so far."""

    n = nustd.kv.IntRef.slot()


def out() -> nu.Nu:
    """Count a second at a time, for as long as the cell runs, and show the count."""
    tile, n = nustd.ui.StatRef("seconds"), nuspace.here(Tick).n
    # One short commit per tick, never one held across the loop.
    step = nuspace.atomic(n.set(n.fallback(0) + 1) >> tile.set_value(nu.str(n)))
    return tile.set_label("Seconds this plane was open") >> nu.ForeverDo(nu.DelayedDo(1.0, step))


CELL = CellSpec(
    "ticker",
    "Ticker",
    source(__name__),
    description="A stat tile counting the seconds its plane was open.",
    group="Examples",
    icon="timer",
)
