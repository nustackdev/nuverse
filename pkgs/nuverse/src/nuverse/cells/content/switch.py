"""A switch cell: one on or off, a Flag item, flipped in place and kept live both ways.

The on or off is a :class:`~nuverse.contents.flag.FlagContent` item: the
cell's own ``value`` unless its Config points it elsewhere
(:mod:`._editing`). Its label is the cell's name, edited under Config.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace import CellSpec

from ...contents.flag import Flag, FlagContent
from .. import source
from ._editing import SECTIONS, Where, editor


__all__ = ["CELL", "out"]


class Entry(nustd.ui.Field):
    input = nustd.ui.SwitchRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)
    item = Where.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=SECTIONS)


def _edit(item: Flag) -> nu.Nu:
    """The item's on or off in the switch, both ways."""
    value, entry = item.value, Box.entry.input
    return entry.set(value.fallback(False)) >> nu.ParallelAsync(
        nu.ReactForever(entry.on_change(), value.set(nu.ToBool(entry))),
        nu.ReactForever(value.on_change(), entry.set(value)),
    )


def out() -> nu.Nu:
    """The switch and its Config, for as long as the cell runs."""
    return editor(FlagContent, Box, _edit)


CELL = CellSpec(
    "switch",
    "Switch",
    source(__name__),
    description="An on or off kept as flag content, the cell's own or any other.",
    group="Inputs",
    icon="toggle-right",
)
