"""A date picker cell: one day, a Date item, picked in place and kept live both ways.

The day is a :class:`~nuverse.contents.date.DateContent` item: the cell's
own ``value`` unless its Config points it elsewhere (:mod:`._editing`). Its
label is the cell's name, edited under Config. Cleared, the date is gone.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace.specs import CellSpec

from ...contents.date import Date, DateContent, iso
from .. import source
from ._editing import ENTRY, editor


__all__ = ["CELL", "CONTROL", "out"]


#: The control, in the editor's Field.
CONTROL = ENTRY.control.to(nustd.ui.DatePickerRef.slot())


def _edit(item: Date) -> nu.Nu:
    """The item's day in the picker, both ways: cleared (NULL), the date is gone."""
    day = nu.Str(CONTROL)
    keep = nu.IfDo(day.is_null(), item.value.erase(), item.value.set(day))
    return CONTROL.set(iso(item)) >> nu.ParallelAsync(
        nu.ReactEvery(CONTROL.on_change(), keep),
        nu.ReactEvery(item.value.on_change(), CONTROL.set(iso(item))),
    )


def out() -> nu.Nu:
    """The date picker and its Config, for as long as the cell runs."""
    return editor(DateContent, _edit)


CELL = CellSpec(
    "date_picker",
    "Date picker",
    source(__name__),
    description="A date kept as date content, picked from a calendar.",
    group="Inputs",
    icon="calendar",
)
