"""Row: one table row any cell keeps, found by the words in its cells.

A table cell keeps each of its rows as an item of its own, by row key.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.ui
import nustd.ui.table
from nu.lang.sentinels import UNSET, Unset

from .text import matches


__all__ = ["CONTENT", "SEPARATOR", "Line", "Row", "RowContent", "RowHit", "RowView", "line"]


#: What stands between two cells of a row drawn on one line.
SEPARATOR = " · "


class Row(nustd.ui.table.Row):
    """A row item: its cells by column key, as ``nustd.ui.table.sync`` stores them.

    The table preset's row as is, so the items a table keeps are the rows
    its grid syncs.
    """


class RowView(nustd.ui.Column):
    """A row drawn whole: its cells on one line."""

    text = nustd.ui.TextRef.slot()


class RowHit(nustd.ui.Row):
    """A row in search results: its cells on one line."""

    text = nustd.ui.TextRef.slot()


def _cells(item: Row) -> nu.Dict:
    """The row's cells by column key, ``{}`` for a row never written."""
    return nu.Dict(nu.Dict(item.cells.extract()).fallback({}))


def _line(cells: dict) -> str:
    shown = (str(v).strip() for v in cells.values() if not isinstance(v, bool))
    return SEPARATOR.join(v for v in shown if v)


#: A row's cells on one line: the texts and numbers, :data:`SEPARATOR` between.
#: A tick box says nothing without its column, so it is left out.
Line = nu.host(_line, name="RowLine")


def line(item: Row) -> nu.Str:
    """The row's cells on one line (see :data:`Line`)."""
    return nu.Str(Line(_cells(item)))


class RowContent(nuspace.Content[Row], name="Row"):
    """The row kind: matched by the words in any of its cells, drawn on one line."""

    @classmethod
    def match(cls, item: Row, *, text: nu.StrArg | Unset = UNSET) -> nu.Bool:
        """Whether ``text`` stands in any cell as whole words, ignoring case.

        Asked nothing, every row holding a cell. A row never written is
        nothing to find.
        """
        cells = _cells(item)
        if text is UNSET:
            return nu.Bool(cells.len() > 0)
        return nu.Bool(cells.values().iter().map(lambda v: matches(nu.ToStr(v), text)).any())

    @classmethod
    def render(cls, item: Row) -> nu.Nu:
        """The row's cells on one line."""
        return RowView.text.set(line(item))

    @classmethod
    def render_hit(cls, item: Row) -> nu.Nu:
        """The row's cells on one line."""
        return RowHit.text.set(line(item))


#: The spec nuverse registers the kind with, as ``nuverse.Row``.
CONTENT = nuspace.ContentSpec(
    RowContent, description="A table row, found by the words in its cells."
)
