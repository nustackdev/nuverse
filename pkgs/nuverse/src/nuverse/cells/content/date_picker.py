"""A date picker cell: one day, a Date item, picked in place and kept live both ways.

The day is a :class:`~nuverse.contents.date.DateContent` item: the cell's
own ``value`` unless its Config points it elsewhere (:mod:`._editing`). Its
label is the cell's name, edited under Config. Cleared, the date is gone.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace import CellSpec

from ...contents.date import Date, DateContent, iso
from .. import source
from ._editing import SECTIONS, Where, editor


__all__ = ["CELL", "out"]


class Entry(nustd.ui.Field):
    input = nustd.ui.DatePickerRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)
    item = Where.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=SECTIONS)


def _edit(item: Date) -> nu.Nu:
    """The item's day in the picker, both ways: cleared, the date is gone."""
    entry = Box.entry.input
    day = nu.Str(entry)
    keep = nu.IfDo(day == "", item.value.erase(), item.value.set(day))
    return entry.set(iso(item)) >> nu.ParallelAsync(
        nu.ReactForever(entry.on_change(), keep),
        nu.ReactForever(item.value.on_change(), entry.set(iso(item))),
    )


def out() -> nu.Nu:
    """The date picker and its Config, for as long as the cell runs."""
    return editor(DateContent, Box, _edit)


CELL = CellSpec(
    "date_picker",
    "Date picker",
    source(__name__),
    description="A date kept as date content, picked from a calendar.",
    group="Inputs",
    icon="calendar",
)
