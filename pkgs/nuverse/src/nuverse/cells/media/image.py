"""An image cell: one image, dropped in place and shown in the viewer, kept live across tabs.

The file is a :class:`~nuverse.contents.file.FileContent` item: the
cell's own ``value`` unless its Config points it elsewhere (:mod:`._media`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.specs import CellSpec

from .. import source
from ._media import cell


if TYPE_CHECKING:
    import nu


__all__ = ["CELL", "out"]


def out() -> nu.Nu:
    """The image, its drop zone and Config, for as long as the cell runs."""
    return cell(accept="image/*", empty="Drop an image", filled="Drop an image to replace it")


CELL = CellSpec(
    "image",
    "Image",
    source(__name__),
    description="An image dropped in place, kept as file content in the blob store.",
    group="Media",
    icon="image",
)
