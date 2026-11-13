"""A slider cell: one number, a Number item, dragged in place and kept live both ways.

The number is a :class:`~nuverse.contents.number.NumberContent` item: the
cell's own ``value`` unless its Config points it elsewhere
(:mod:`._editing`). Its label is the cell's name, and its range and step
configure the cell, so they are its own state, edited under Config.
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


__all__ = ["CELL", "CONTROL", "Range", "out"]


class Range(nu.Shape):
    """A slider's state: the range and step its number moves within."""

    min = nustd.kv.FloatRef.slot()
    max = nustd.kv.FloatRef.slot()
    step = nustd.kv.FloatRef.slot()


#: The control, in the editor's Field.
CONTROL = ENTRY.control.to(nustd.ui.SliderRef.slot())


def _edit(item: Number) -> nu.Nu:
    """The item's number on the slider, both ways."""
    value = item.value
    return CONTROL.set(value.fallback(0.0)) >> nu.ParallelAsync(
        nu.ReactEvery(CONTROL.on_change(), value.set(nu.ToFloat(CONTROL))),
        nu.ReactEvery(value.on_change(), CONTROL.set(value.fallback(0.0))),
    )


def out() -> nu.Nu:
    """The slider and its Config, for as long as the cell runs."""
    show, reactions = bounded(nuspace.here(Range), CONTROL)
    return editor(NumberContent, _edit, first=show, also=reactions)


CELL = CellSpec(
    "slider",
    "Slider",
    source(__name__),
    description="A number on a slider kept as number content, its range under Config.",
    group="Inputs",
    icon="gauge",
)
