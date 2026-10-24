"""A table cell: one editable grid over the cell's rows, every tab kept live.

The rows are the data: each one a :class:`~nuverse.contents.row.RowContent`
item of the cell, by row key, all of them ``RowContent.items((CELL, cell))``,
so a search by kind finds them and any program reads and writes them by
address. The order, the columns and the sort are how this grid shows them,
view preferences, so they are the cell's own state: a row no order names
(eg one a program added) shows last. ``nustd.ui.table.sync`` stores what the
browser asks for and repaints every tab from the store. The cell seeds a few
blank rows the first time it runs.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
import nustd.ui.table
from nuspace import Snippet, ops
from nuspace.content import CELL

from ...contents.row import RowContent
from .. import source


__all__ = ["COLUMNS", "SEED", "SNIPPET", "Grid", "Sheet", "out"]


#: The columns a new table starts with. Stored on first run, edited from then on.
COLUMNS = [
    {"key": "name", "label": "Name"},
    {"key": "notes", "label": "Notes"},
    {"key": "done", "label": "Done", "kind": "bool"},
]

#: The blank rows a new table starts with, by key.
SEED = {f"r{i}": {"name": "", "notes": "", "done": False} for i in (1, 2, 3)}


class Sheet(nuspace.CellState):
    """A table cell's view of its rows: their order, the columns, the sort, and whether it was seeded."""

    order = nustd.kv.ListRef.slot(str)
    columns = nustd.kv.ListRef.slot(object)
    sort = nustd.kv.ObjectRef.slot()
    seeded = nustd.kv.BoolRef.slot()


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


def _here(ref: nu.Nu) -> nu.Nu:
    """``ref`` landed under the running cell, so ``sync`` brackets it on the States store."""
    return ops.cell_state(ops.Here.cell, ref)


def out() -> nu.Nu:
    """Seed once, then the grid as the store holds it, for as long as the cell runs."""
    rows = RowContent.items((CELL, ops.Here.cell))
    seed = nu.IfDo(
        Sheet.seeded.missing(),
        nu.Sequential(*(rows[k].cells.set(cells) for k, cells in SEED.items()))
        >> Sheet.order.set(list(SEED))
        >> Sheet.seeded.set(True),
    )
    # sync places its own brackets, scoped by where its slots root: rerooted
    # here first, they root at States, not at Sheet.
    grid = nustd.ui.table.sync(
        Grid.table, rows, _here(Sheet.order), _here(Sheet.columns), sort=_here(Sheet.sort)
    )
    return ops.atomic_state(_here(seed)) >> grid


SNIPPET = Snippet(
    "table",
    "Table",
    source(__name__),
    description="An editable data table, each row kept as row content of the cell.",
    group="Content",
    icon="table",
)
