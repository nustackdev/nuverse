"""A plane content lens: one plane's own items, as kind, then item id, then the item (:mod:`._content_lens`).

It starts on the plane its cell sits on. A dropdown picks another; it lists
every plane and follows planes being added or removed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import Cell, Space, ops
from nuspace.content import PLANE

from .. import source
from ._content_lens import option, picked


if TYPE_CHECKING:
    import nu


__all__ = ["CELL", "out"]


def out() -> nu.Nu:
    """The dropdown and the picked plane's items as columns, for as long as the cell runs."""
    options = ops.plane_rows().iter().map(option).to_list()
    return picked(PLANE, options, ops.Here.plane, Space.planes.on_children_change())


CELL = Cell(
    "plane_content_lens",
    "Plane content lens",
    source(__name__),
    description="Browses one plane's own content items by kind, raw and rendered. This plane first.",
    group="Debugging",
    icon="folder-open",
)
