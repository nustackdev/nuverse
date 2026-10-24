"""A cell content lens: one cell's items, as kind, then item id, then the item (:mod:`._content_lens`).

It starts on the cell it sits in. A dropdown picks another of its plane's
cells, in order, and follows cells being added or removed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import Cell, Space, ops
from nuspace.content import CELL as CELL_LEVEL

from .. import source
from ._content_lens import option, picked


if TYPE_CHECKING:
    import nu


__all__ = ["CELL", "out"]


def out() -> nu.Nu:
    """The dropdown and the picked cell's items as columns, for as long as the cell runs."""
    plane = ops.Here.plane
    options = ops.cell_rows(plane).iter().map(option).to_list()
    return picked(
        CELL_LEVEL, options, ops.Here.cell, Space.planes[plane].cells.on_children_change()
    )


CELL = Cell(
    "cell_content_lens",
    "Cell content lens",
    source(__name__),
    description="Browses one cell's content items by kind, raw and rendered. This cell first.",
    group="Debugging",
    icon="package",
)
