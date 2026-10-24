"""A text input cell: one line of text, a Text item, edited in place and kept live both ways.

The text is a :class:`~nuverse.contents.text.TextContent` item: the cell's
own ``value`` unless its Config points it elsewhere (:mod:`._editing`). Its
label is the cell's name, edited under Config. A change from any tab, any
editor of the same item, or a program shows everywhere.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace import Cell

from ...contents.text import Text, TextContent
from .. import source
from ._editing import SECTIONS, Where, editor


__all__ = ["CELL", "out"]


class Entry(nustd.ui.Field):
    input = nustd.ui.InputRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)
    item = Where.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=SECTIONS)


def _edit(item: Text) -> nu.Nu:
    """The item's text in the input, both ways."""
    value, entry = item.value, Box.entry.input
    return entry.set(value.fallback("")) >> nu.ParallelAsync(
        nu.ReactForever(entry.on_change(), value.set(nu.ToStr(entry))),
        nu.ReactForever(value.on_change(), entry.set(nu.str(value))),
    )


def out() -> nu.Nu:
    """The text input and its Config, for as long as the cell runs."""
    return editor(TextContent, Box, _edit)


CELL = Cell(
    "text_input",
    "Text input",
    source(__name__),
    description="A line of text kept as text content, the cell's own or any other.",
    group="Inputs",
    icon="pen-tool",
)
