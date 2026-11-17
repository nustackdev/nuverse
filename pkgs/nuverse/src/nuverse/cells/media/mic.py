"""A mic cell: a sound recorded in place, kept as file content and played with its waveform, live across tabs.

The recording is a :class:`~nuverse.contents.file.FileContent` item: the
cell's own ``value`` unless its Config points it elsewhere (:mod:`._capture`).
The kept sound plays above; the recorder sits under it, ready for the next
take, which replaces the kept one once it is stopped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui
from nuspace.specs import CellSpec

from ...contents.file import FileContent, draw
from .. import source
from .._editing import editor
from ._capture import keep, order, parts, shown


if TYPE_CHECKING:
    from ...contents.file import File


__all__ = ["CELL", "PARTS", "out"]


#: The control: the kept sound, the recorder, the bar while a take goes up, a note.
PARTS = parts(nustd.ui.MicCaptureRef.slot(size="sm", max_duration=600))

SHOWN = shown(PARTS)


def _edit(item: File) -> nu.Nu:
    """The kept sound shown, and each take kept into the item."""
    show = draw(item, SHOWN)
    return show >> nu.ParallelAsync(keep(item, PARTS), nu.ReactEvery(item.on_change(), show))


def out() -> nu.Nu:
    """The recorder, the kept sound and Config, for as long as the cell runs."""
    first = order(PARTS, ("shown", "take", "bar", "note"))
    return editor(FileContent, _edit, first=first)


CELL = CellSpec(
    "mic",
    "Microphone",
    source(__name__),
    description="A sound recorded in place, kept as file content in the blob store.",
    group="Media",
    icon="mic",
)
