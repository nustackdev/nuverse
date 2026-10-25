"""A select cell: one option, a Text item, picked in place and kept live both ways.

The option picked is a :class:`~nuverse.contents.text.TextContent` item:
the cell's own ``value`` unless its Config points it elsewhere
(:mod:`._editing`). Its label is the cell's name and its options a list
that configures the cell, so its own state. Both are edited under Config,
and both are live.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import CellSpec

from ...contents.text import Text, TextContent
from .. import source
from ._editing import SECTIONS, Where, editor


__all__ = ["CELL", "OPTIONS", "Choice", "out"]


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
    item = Where.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=SECTIONS)


def _edit(item: Text) -> nu.Nu:
    """The item's option picked in the select, both ways."""
    value, entry = item.value, Box.entry.input
    return entry.set(value.fallback("")) >> nu.ParallelAsync(
        nu.ReactForever(entry.on_change(), value.set(nu.ToStr(entry))),
        nu.ReactForever(value.on_change(), entry.set(nu.str(value))),
    )


def out() -> nu.Nu:
    """The select and its Config, for as long as the cell runs."""
    settings = Box.config.settings
    # Seeded once: emptied by hand, the options stay empty.
    seed = nu.IfDo(Choice.seeded.missing(), Choice.options.set(OPTIONS) >> Choice.seeded.set(True))

    def show_options() -> nu.Nu:
        options = nu.list(Choice.options).fallback([])
        return Box.entry.input.set_options(options) >> settings.options.set(options)

    return editor(
        TextContent,
        Box,
        _edit,
        first=seed >> show_options(),
        also=(
            nu.ReactForever(
                settings.options.on_change(), Choice.options.set(nu.List(settings.options))
            ),
            nu.ReactForever(Choice.options.on_change(), show_options()),
        ),
    )


CELL = CellSpec(
    "select",
    "Select",
    source(__name__),
    description="One option of a list kept as text content, its options under Config.",
    group="Inputs",
    icon="list",
)
