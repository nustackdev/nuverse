"""A video cell: one video, dropped in place and played, kept live across tabs.

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
    """The video, its drop zone and Config, for as long as the cell runs."""
    return cell(accept="video/*", empty="Drop a video", filled="Drop a video to replace it")


CELL = CellSpec(
    "video",
    "Video",
    source(__name__),
    description="A video dropped in place, kept as file content in the blob store.",
    group="Media",
    icon="video",
)
