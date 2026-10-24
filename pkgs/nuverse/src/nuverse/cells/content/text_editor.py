"""A text editor cell: one editable markdown surface over a Text item, kept live both ways.

Registered as ``nuverse.text``, the Cell nuspace's document editing works
on: typing into an empty line starts one, and its cells are the plane's text
cells, written like a document. So it draws the surface alone, no Config:
it edits the cell's own ``value``, a
:class:`~nuverse.contents.text.TextContent` item, unless a program points
it elsewhere through its :class:`~._editing.Target`.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace import Cell, ops

from ...contents.text import Text, TextContent
from .. import source
from ._editing import editing


__all__ = ["CELL", "out"]


def _edit(item: Text) -> nu.Nu:
    """The item's markdown on the surface, both ways."""
    text, body = item.value, nustd.ui.MarkdownRef("text")
    return (
        body.set(text.fallback(""))
        >> body.set_editable(True)
        >> body.set_placeholder("Write, or press / for cells")
        >> nu.ParallelAsync(
            # This tab typed: keep it. Every other tab, and every program
            # reading the text, hears it through the store.
            nu.ReactForever(body.on_change(), text.set(nu.Str(body))),
            # Somebody else typed, or a program set it: show it. The echo
            # back to the author is a no-op, the text is already what it says.
            nu.ReactForever(text.on_change(), body.set(nu.str(text))),
        )
    )


def out() -> nu.Nu:
    """The editor over the cell's item, for as long as the cell runs."""
    # Brackets placed per step: each read and each keystroke's write is its own.
    return ops.bracketed(editing(TextContent, _edit))


CELL = Cell(
    "text",
    "Text",
    source(__name__),
    description="Text a person reads and edits, markdown kept as text content.",
    group="Content",
    icon="type",
)
