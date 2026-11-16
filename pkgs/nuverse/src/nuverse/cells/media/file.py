"""A file cell: any one file, dropped in place, to open or save, kept live across tabs.

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
    """The file, its drop zone and Config, for as long as the cell runs."""
    return cell(accept="", empty="Drop a file", filled="Drop a file to replace it")


CELL = CellSpec(
    "file",
    "File",
    source(__name__),
    description="Any file dropped in place, kept as file content in the blob store.",
    group="Media",
    icon="file",
)
