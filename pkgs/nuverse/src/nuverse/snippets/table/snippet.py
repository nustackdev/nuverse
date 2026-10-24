"""A table cell: one editable grid over its rows, every tab kept live.

The grid is the data: ``nustd.ui.table.sync`` stores what the browser asks
for, cells, rows and columns, and repaints every tab from the store. Each
row is an item of the cell, a :class:`~nuverse.contents.row.RowContent` by
row key, so a search by kind finds it. The order, columns and sort only
configure the grid, so they are the cell's own state. The cell only seeds a
few blank rows the first time it runs.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
import nustd.ui.table
from nu.lang.typeinfo import TypeInfo
from nuspace import ops
from nuspace.content import kind_name
from nuspace.shapes import States

from ...contents.row import Row, RowContent


__all__ = ["Grid", "Sheet", "out", "rows"]


#: The columns a new table starts with. Stored on first run, edited from then on.
COLUMNS = [
    {"key": "name", "label": "Name"},
    {"key": "notes", "label": "Notes"},
    {"key": "done", "label": "Done", "kind": "bool"},
]

#: The blank rows a new table starts with, by key.
SEED = {f"r{i}": {"name": "", "notes": "", "done": False} for i in (1, 2, 3)}


class Sheet(nuspace.CellState):
    """A table cell's state: the layout ``nustd.ui.table.sync`` keeps, and whether it was seeded.

    The rows themselves are the cell's items (:func:`rows`).
    """

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


def rows(cell_id: nu.StrArg) -> nustd.kv.DictRef[str, Row]:
    """A table cell's rows, its :class:`~nuverse.contents.row.RowContent` items, as one mapping.

    Where ``RowContent.at((CELL, cell_id), key)`` is one row, this is all of
    them by row key, the ``DictRef`` ``sync`` takes.
    """
    scope = States.contents[kind_name(RowContent)].cells
    held = nustd.kv.DictRef(cell_id, parent_ref=scope, owner_shape=States)
    held._payload["type_info"] = TypeInfo.from_annotation(dict[str, Row])
    return held


def _here(ref: nu.Nu) -> nu.Nu:
    """``ref`` landed under the running cell, so ``sync`` brackets it on the States store."""
    return ops.cell_state(ops.Here.cell, ref)


def out() -> nu.Nu:
    """Seed once, then the grid as the store holds it, for as long as the cell runs."""
    mine = rows(ops.Here.cell)
    seed = nu.IfDo(
        Sheet.seeded.missing(),
        nu.Sequential(*(mine[k].cells.set(cells) for k, cells in SEED.items()))
        >> Sheet.order.set(list(SEED))
        >> Sheet.seeded.set(True),
    )
    # sync places its own brackets, scoped by where its slots root: rerooted
    # here first, they root at States, not at Sheet.
    grid = nustd.ui.table.sync(
        Grid.table,
        mine,
        _here(Sheet.order),
        _here(Sheet.columns),
        sort=_here(Sheet.sort),
    )
    return ops.atomic_state(_here(seed)) >> grid
