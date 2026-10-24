"""A text cell: one editable markdown surface over a text item of its own, synced both ways.

What the person wrote is the cell's :data:`ITEM`, a
:class:`~nuverse.contents.text.TextContent` item, not in the prog, so ops
reach it from anywhere and a search by kind finds it. The viewer draws it
like any other cell.
"""

from __future__ import annotations

import nu
import nustd.ui
from nuspace import ops

from ...contents.text import TextContent


__all__ = ["ITEM", "out"]


#: The id of the cell's text item: the markdown it holds.
ITEM = "text"


def out() -> nu.Nu:
    """The editor over the cell's :data:`ITEM`, both ways, for as long as the cell runs."""
    text = TextContent.cell(ITEM).value
    body = nustd.ui.MarkdownRef("text")
    # Brackets placed per step: each read and each keystroke's write is its own.
    return ops.bracketed(
        body.set(text.fallback(""))
        >> body.set_editable(True)
        >> body.set_placeholder("Write, or press / for cells")
        >> nu.ParallelAsync(
            # This tab typed: keep it. Every other tab on the plane, and every
            # op reading the text, hears it through the store.
            nu.ReactForever(body.on_change(), text.set(nu.Str(body))),
            # Somebody else typed, or an op set it: show it. The echo back to
            # the author is a no-op, the text is already what it says.
            nu.ReactForever(text.on_change(), body.set(nu.str(text))),
        )
    )
