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
from nuspace import Cell

from ...contents.number import Number, NumberContent
from .. import source
from ._editing import SECTIONS, Where, bounded, editor


__all__ = ["CELL", "Bounds", "out"]


class Bounds(nuspace.CellState):
    """A number input's state: the bounds and step its number is edited within."""

    min = nustd.kv.FloatRef.slot()
    max = nustd.kv.FloatRef.slot()
    step = nustd.kv.FloatRef.slot()


class Entry(nustd.ui.Field):
    input = nustd.ui.NumberInputRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")
    min = nustd.ui.NumberInputRef.slot(label="Min")
    max = nustd.ui.NumberInputRef.slot(label="Max", default=100)
    step = nustd.ui.NumberInputRef.slot(label="Step", min=0, step=0.1, default=1)


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)
    item = Where.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=SECTIONS)


def _edit(item: Number) -> nu.Nu:
    """The item's number in the input, both ways."""
    value, entry = item.value, Box.entry.input
    return entry.set_value(value.fallback(0.0)) >> nu.ParallelAsync(
        nu.ReactForever(entry.on_change(), value.set(nu.ToFloat(entry))),
        nu.ReactForever(value.on_change(), entry.set_value(value)),
    )


def out() -> nu.Nu:
    """The number input and its Config, for as long as the cell runs."""
    show, reactions = bounded(Bounds, Box.entry.input, Box.config.settings)
    return editor(NumberContent, Box, _edit, first=show, also=reactions)


CELL = Cell(
    "number_input",
    "Number input",
    source(__name__),
    description="A number kept as number content, with its bounds and step under Config.",
    group="Inputs",
    icon="hash",
)
