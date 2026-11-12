"""A checkbox cell: one on or off, a Flag item, ticked in place and kept live both ways.

The on or off is a :class:`~nuverse.contents.flag.FlagContent` item: the
cell's own ``value`` unless its Config points it elsewhere
(:mod:`._editing`). Its label is the cell's name, edited under Config.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace.specs import CellSpec

from ...contents.flag import Flag, FlagContent
from .. import source
from ._editing import ENTRY, editor


__all__ = ["CELL", "CONTROL", "out"]


#: The control, in the editor's Field.
CONTROL = ENTRY.control.to(nustd.ui.CheckboxRef.slot())


def _edit(item: Flag) -> nu.Nu:
    """The item's on or off in the checkbox, both ways."""
    value = item.value
    return CONTROL.set(value.fallback(False)) >> nu.ParallelAsync(
        nu.ReactEvery(CONTROL.on_change(), value.set(nu.ToBool(CONTROL))),
        nu.ReactEvery(value.on_change(), CONTROL.set(value)),
    )


def out() -> nu.Nu:
    """The checkbox and its Config, for as long as the cell runs."""
    return editor(FlagContent, _edit)


CELL = CellSpec(
    "checkbox",
    "Checkbox",
    source(__name__),
    description="An on or off kept as flag content, the cell's own or any other.",
    group="Inputs",
    icon="square-check-big",
)
