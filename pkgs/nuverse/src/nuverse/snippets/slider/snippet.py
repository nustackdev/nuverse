"""A slider cell: one number, its own number item, dragged in place, synced both ways.

The number is the cell's :data:`ITEM`, a
:class:`~nuverse.contents.number.NumberContent` item. Its label is the
cell's name, and its range and step configure the cell, so they are its own
state. Both are edited under Config, and every one of them is live: a change
from any tab, or an op, shows everywhere.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops

from ...contents.number import NumberContent


__all__ = ["ITEM", "Range", "out"]


#: The id of the cell's number item.
ITEM = "value"


class Range(nuspace.CellState):
    """A slider cell's state: the range and step its number moves within."""

    min = nustd.kv.FloatRef.slot()
    max = nustd.kv.FloatRef.slot()
    step = nustd.kv.FloatRef.slot()


class Entry(nustd.ui.Field):
    input = nustd.ui.SliderRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")
    min = nustd.ui.NumberInputRef.slot(label="Min")
    max = nustd.ui.NumberInputRef.slot(label="Max", default=100)
    step = nustd.ui.NumberInputRef.slot(label="Step", min=0, step=0.1, default=1)


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=[{"id": "settings", "label": "Config"}])


def out() -> nu.Nu:
    """The slider and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    value = NumberContent.cell(ITEM).value
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")
    low, high, step = Range.min.fallback(0.0), Range.max.fallback(100.0), Range.step.fallback(1.0)

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    def show_min() -> nu.Nu:
        return entry.input.set_min(low) >> settings.min.set_value(low)

    def show_max() -> nu.Nu:
        return entry.input.set_max(high) >> settings.max.set_value(high)

    def show_step() -> nu.Nu:
        return entry.input.set_step(step) >> settings.step.set_value(step)

    return ops.bracketed(
        show_min()
        >> show_max()
        >> show_step()
        >> entry.input.set_value(value.fallback(0.0))
        >> show_name()
        >> nu.ParallelAsync(
            nu.ReactForever(entry.input.on_change(), value.set(nu.ToFloat(entry.input))),
            nu.ReactForever(settings.min.on_change(), Range.min.set(nu.ToFloat(settings.min))),
            nu.ReactForever(settings.max.on_change(), Range.max.set(nu.ToFloat(settings.max))),
            nu.ReactForever(settings.step.on_change(), Range.step.set(nu.ToFloat(settings.step))),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            nu.ReactForever(value.on_change(), entry.input.set_value(value)),
            nu.ReactForever(Range.min.on_change(), show_min()),
            nu.ReactForever(Range.max.on_change(), show_max()),
            nu.ReactForever(Range.step.on_change(), show_step()),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
