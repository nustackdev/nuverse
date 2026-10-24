"""A text input cell: one line of text, its own text item, edited in place, synced both ways.

The text is the cell's :data:`ITEM`, a
:class:`~nuverse.contents.text.TextContent` item.

Its label is the cell's name, edited under Config. Live: a change from any
tab, or an op, shows everywhere.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.ui
from nuspace import ops

from ...contents.text import TextContent


__all__ = ["ITEM", "out"]


#: The id of the cell's text item.
ITEM = "value"


class Entry(nustd.ui.Field):
    input = nustd.ui.InputRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=[{"id": "settings", "label": "Config"}])


def out() -> nu.Nu:
    """The text and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    value = TextContent.cell(ITEM).value
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    return ops.bracketed(
        entry.input.set(value.fallback(""))
        >> show_name()
        >> nu.ParallelAsync(
            nu.ReactForever(entry.input.on_change(), value.set(nu.ToStr(entry.input))),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            nu.ReactForever(value.on_change(), entry.input.set(nu.str(value))),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
