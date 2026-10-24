"""A select cell: one option, its own text item, picked in place, synced both ways.

The option picked is the cell's :data:`ITEM`, a
:class:`~nuverse.contents.text.TextContent` item. Its label is the cell's
name and its options a list that configures the cell, so its own state.
Both are edited under Config, and both are live: a change from any tab, or
an op, shows everywhere.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import ops

from ...contents.text import TextContent


__all__ = ["ITEM", "Choice", "out"]


#: The id of the cell's text item: the option picked.
ITEM = "value"


#: The options a new select starts with.
OPTIONS = ["One", "Two", "Three"]


class Choice(nuspace.CellState):
    """A select cell's state: the options to pick from."""

    options = nustd.kv.ListRef.slot(str)
    seeded = nustd.kv.BoolRef.slot()


class Entry(nustd.ui.Field):
    input = nustd.ui.SelectRef.slot(placeholder="Pick one")


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")
    options = nustd.ui.TagInputRef.slot(label="Options", placeholder="Add an option")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=[{"id": "settings", "label": "Config"}])


def out() -> nu.Nu:
    """The choice and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    value = TextContent.cell(ITEM).value
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")
    # Seeded once: emptied by hand, the options stay empty.
    seed = nu.IfDo(Choice.seeded.missing(), Choice.options.set(OPTIONS) >> Choice.seeded.set(True))

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    def show_options() -> nu.Nu:
        options = nu.list(Choice.options).fallback([])
        return entry.input.set_options(options) >> settings.options.set(options)

    return ops.bracketed(
        seed
        >> show_options()
        >> entry.input.set(value.fallback(""))
        >> show_name()
        >> nu.ParallelAsync(
            nu.ReactForever(entry.input.on_change(), value.set(nu.ToStr(entry.input))),
            nu.ReactForever(
                settings.options.on_change(), Choice.options.set(nu.List(settings.options))
            ),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            nu.ReactForever(value.on_change(), entry.input.set(nu.str(value))),
            nu.ReactForever(Choice.options.on_change(), show_options()),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
