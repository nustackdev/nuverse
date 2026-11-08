"""A cell content lens: one cell's items, as kind, then content key, then the item (:mod:`._content_lens`).

It starts on the cell it sits in. A dropdown picks another of its plane's
cells, in order, and follows cells being added or removed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nuspace
from nuspace.places import Here
from nuspace.shapes.content import CELL as CELL_LEVEL
from nuspace.specs import CellSpec

from .. import source
from ._content_lens import picked
from ._options import cell_options


if TYPE_CHECKING:
    import nu


__all__ = ["CELL", "out"]


def out() -> nu.Nu:
    """The dropdown and the picked cell's items as columns, for as long as the cell runs."""
    plane = Here.plane
    moved = nuspace.Space.planes[plane].cells.on_children_change()
    return picked(CELL_LEVEL, cell_options(plane), Here.cell, moved)


CELL = CellSpec(
    "cell_content_lens",
    "Cell content lens",
    source(__name__),
    description="Browses one cell's content items by kind, raw and rendered. This cell first.",
    group="Debugging",
    icon="package",
)
