"""A table cell: one editable grid over the cell's rows, every tab kept live.

The rows are the data: each one a :class:`~nuverse.contents.row.RowContent`
item of the cell, by row key, so a search by kind finds them and any
program reads and writes them by address
(``nuspace.at.cell(id=c).content(RowContent)[key]``). The order, the
columns and the sort are how this grid shows them, view preferences, so
they are the cell's own state (:class:`Sheet`): a row no order names (eg
one a program added) shows last. ``nustd.ui.table.sync`` stores what the
browser asks for and repaints every tab from the store. The cell seeds a
few blank rows the first time it runs.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
import nustd.ui.table
from nuspace.places import Here
from nuspace.specs import CellSpec, kind_name

from ...contents.row import Row, RowContent
from .. import source


__all__ = ["CELL", "COLUMNS", "SEED", "Grid", "Rows", "Sheet", "out", "rows"]


#: The columns a new table starts with. Stored on first run, edited from then on.
COLUMNS = [
    {"key": "name", "label": "Name"},
    {"key": "notes", "label": "Notes"},
    {"key": "done", "label": "Done", "kind": "bool"},
]

#: The blank rows a new table starts with, by key.
SEED = {f"r{i}": {"name": "", "notes": "", "done": False} for i in (1, 2, 3)}


class Sheet(nu.Shape):
    """A table cell's view of its rows: their order, the columns, the sort, and whether it was seeded."""

    order = nustd.kv.ListRef.slot(str)
    columns = nustd.kv.ListRef.slot(object)
    sort = nustd.kv.ObjectRef.slot()
    seeded = nustd.kv.BoolRef.slot()


class Rows(nu.Shape):
    """A cell's row items as one typed mapping: what ``nustd.ui.table.sync`` reads and writes.

    ``entries`` is where a place keeps its items of a kind, typed by
    :class:`~nuverse.contents.row.Row`, so it is a ref ``sync`` can bracket
    and index (``rows[key].cells``).
    """

    entries = nustd.kv.DictRef.slot(Row)


def rows(cell: nu.StrArg) -> nustd.kv.DictRef:
    """``cell``'s rows: ``State.content_cells["nuverse.Row"].cells[cell].entries``, typed by :class:`Row`.

    The same items ``nuspace.at.cell(id=cell).content(RowContent)`` holds.
    """
    return Rows.entries.with_parent(nuspace.State.content_cells[kind_name(RowContent)].cells[cell])


class Grid(nustd.ui.Column):
    """The cell's surface: one table with every request turned on."""

    table = nustd.ui.TableRef.slot(
        columns=COLUMNS,
        label="Table",
        selection="multi",
        editable=True,
        addable=True,
        deletable=True,
        draggable=True,
        columns_editable=True,
    )


def out() -> nu.Nu:
    """Seed once, then the grid as the store holds it, for as long as the cell runs."""
    held, sheet = rows(Here.cell), nuspace.here(Sheet)
    seed = nu.IfDo(
        sheet.seeded.is_null(),
        nu.Sequential(*(held[k].cells.set(cells) for k, cells in SEED.items()))
        >> sheet.order.set(list(SEED))
        >> sheet.seeded.set(True),
    )
    # sync places its own brackets, on the store its rows root at: State.
    grid = nustd.ui.table.sync(Grid.table, held, sheet.order, sheet.columns, sort=sheet.sort)
    return nuspace.atomic(seed) >> grid


CELL = CellSpec(
    "table",
    "Table",
    source(__name__),
    description="An editable data table, each row kept as row content of the cell.",
    group="Content",
    icon="table",
)
