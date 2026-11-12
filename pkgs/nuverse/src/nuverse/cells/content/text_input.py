"""A text input cell: one line of text, a Text item, edited in place and kept live both ways.

The text is a :class:`~nuverse.contents.text.TextContent` item: the cell's
own ``value`` unless its Config points it elsewhere (:mod:`._editing`). Its
label is the cell's name, edited under Config. A change from any tab, any
editor of the same item, or a program shows everywhere.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace.specs import CellSpec

from ...contents.text import Text, TextContent
from .. import source
from ._editing import ENTRY, editor


__all__ = ["CELL", "CONTROL", "out"]


#: The control, in the editor's Field.
CONTROL = ENTRY.control.to(nustd.ui.InputRef.slot())


def _edit(item: Text) -> nu.Nu:
    """The item's text in the input, both ways."""
    value = item.value
    return CONTROL.set(value.fallback("")) >> nu.ParallelAsync(
        nu.ReactEvery(CONTROL.on_change(), value.set(nu.ToStr(CONTROL))),
        nu.ReactEvery(value.on_change(), CONTROL.set(nu.str(value))),
    )


def out() -> nu.Nu:
    """The text input and its Config, for as long as the cell runs."""
    return editor(TextContent, _edit)


CELL = CellSpec(
    "text_input",
    "Text input",
    source(__name__),
    description="A line of text kept as text content, the cell's own or any other.",
    group="Inputs",
    icon="pen-tool",
)
