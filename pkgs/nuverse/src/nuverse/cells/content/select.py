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
from nuspace.specs import CellSpec

from ...contents.text import Text, TextContent
from .. import source
from ._editing import ENTRY, SETTINGS, editor


__all__ = ["CELL", "CONTROL", "OPTIONS", "OPTIONS_INPUT", "Choice", "out"]


#: The options a new select starts with.
OPTIONS = ["One", "Two", "Three"]


class Choice(nu.Shape):
    """A select cell's state: the options to pick from."""

    options = nustd.kv.ListRef.slot(str)
    seeded = nustd.kv.BoolRef.slot()


#: The control, in the editor's Field.
CONTROL = ENTRY.control.to(nustd.ui.SelectRef.slot(placeholder="Pick one"))

#: The options, under the editor's settings.
OPTIONS_INPUT = SETTINGS["options"].to(
    nustd.ui.TagInputRef.slot(label="Options", placeholder="Add an option")
)


def _edit(item: Text) -> nu.Nu:
    """The item's option picked in the select, both ways."""
    value = item.value
    return CONTROL.set(value.fallback("")) >> nu.ParallelAsync(
        nu.ReactEvery(CONTROL.on_change(), value.set(nu.ToStr(CONTROL))),
        nu.ReactEvery(value.on_change(), CONTROL.set(nu.str(value))),
    )


def out() -> nu.Nu:
    """The select and its Config, for as long as the cell runs."""
    choice = nuspace.here(Choice)
    # Seeded once: emptied by hand, the options stay empty.
    seed = nu.IfDo(choice.seeded.is_null(), choice.options.set(OPTIONS) >> choice.seeded.set(True))

    def show_options() -> nu.Nu:
        options = nu.list(choice.options).fallback([])
        return CONTROL.set_options(options) >> OPTIONS_INPUT.set(options)

    return editor(
        TextContent,
        _edit,
        first=seed >> show_options(),
        also=(
            nu.ReactEvery(OPTIONS_INPUT.on_change(), choice.options.set(nu.List(OPTIONS_INPUT))),
            nu.ReactEvery(choice.options.on_change(), show_options()),
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
