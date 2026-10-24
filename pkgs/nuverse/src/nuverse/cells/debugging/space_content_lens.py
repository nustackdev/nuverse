"""A space content lens: the space's own items, as kind, then item id, then the item (:mod:`._content_lens`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace import Cell
from nuspace.content import SPACE

from .. import source
from ._content_lens import browse


if TYPE_CHECKING:
    import nu


__all__ = ["CELL", "out"]


def out() -> nu.Nu:
    """The space's items as columns, and the item at the cursor drawn, for as long as the cell runs."""
    return browse(SPACE, "")


CELL = Cell(
    "space_content_lens",
    "Space content lens",
    source(__name__),
    description="Browses the space's own content items by kind, raw and rendered.",
    group="Debugging",
    icon="library",
)
