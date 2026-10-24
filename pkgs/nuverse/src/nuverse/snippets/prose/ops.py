"""Ops on a text cell: its text set and read.

The text is the cell's :data:`~.snippet.ITEM`, a
:class:`~nuverse.contents.text.TextContent` item, reached from any plane by
its address, the cell's id alone. A write is one commit to the state store
and a running editor shows it. A read is bare: its caller brackets it.
"""

from __future__ import annotations

import nu
from nuspace import ops
from nuspace.content import CELL

from ...contents.text import Text, TextContent
from .snippet import ITEM


__all__ = ["set_text", "text_of"]


def _item(cell_id: nu.StrArg) -> Text:
    """The text cell's item, by its address."""
    return TextContent.at((CELL, cell_id), ITEM)


def set_text(cell_id: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """Replace a text cell's text, markdown. A no-op when the cell is missing.

    Args:
        cell_id: The text cell.
        text: What it holds now, markdown.
    """
    kept = _item(cell_id).value.set(text)
    return ops.atomic_state(nu.IfDo(ops.cell_exists(cell_id), kept))


def text_of(cell_id: nu.StrArg) -> nu.Nu:
    """A text cell's text, ``""`` before anything is written. Bare: wrap it in ``ops.snapshot``.

    Args:
        cell_id: The text cell.
    """
    return _item(cell_id).value.fallback("")
