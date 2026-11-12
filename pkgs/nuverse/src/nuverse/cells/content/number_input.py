"""A number input cell: one number, a Number item, edited in place and kept live both ways.

The number is a :class:`~nuverse.contents.number.NumberContent` item: the
cell's own ``value`` unless its Config points it elsewhere
(:mod:`._editing`). Its label is the cell's name, and its bounds (0 to 100
until set) and step configure the cell, so they are its own state. All are
edited under Config, and every one of them is live.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.specs import CellSpec

from ...contents.number import Number, NumberContent
from .. import source
from ._editing import ENTRY, bounded, editor


__all__ = ["CELL", "CONTROL", "Bounds", "out"]


class Bounds(nu.Shape):
    """A number input's state: the bounds and step its number is edited within."""

    min = nustd.kv.FloatRef.slot()
    max = nustd.kv.FloatRef.slot()
    step = nustd.kv.FloatRef.slot()


#: The control, in the editor's Field.
CONTROL = ENTRY.control.to(nustd.ui.NumberInputRef.slot())


def _edit(item: Number) -> nu.Nu:
    """The item's number in the input, both ways."""
    value = item.value
    return CONTROL.set_value(value.fallback(0.0)) >> nu.ParallelAsync(
        nu.ReactEvery(CONTROL.on_change(), value.set(nu.ToFloat(CONTROL))),
        nu.ReactEvery(value.on_change(), CONTROL.set_value(value)),
    )


def out() -> nu.Nu:
    """The number input and its Config, for as long as the cell runs."""
    show, reactions = bounded(nuspace.here(Bounds), CONTROL)
    return editor(NumberContent, _edit, first=show, also=reactions)


CELL = CellSpec(
    "number_input",
    "Number input",
    source(__name__),
    description="A number kept as number content, with its bounds and step under Config.",
    group="Inputs",
    icon="hash",
)
