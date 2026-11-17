"""What the capture Cells share: a take recorded in the tab, kept as the cell's File item.

A mic or camera cell keeps one :class:`~nuverse.contents.file.FileContent`
item, as an audio or image cell does (:mod:`._media`): the cell's own
``value`` unless its Config points it elsewhere. The kept file draws above
by its type (:func:`~nuverse.contents.file.draw`), from the blob store, so
every tab and every cell on the item shows it.

A take reads as an upload (``nustd.ui.MicCaptureRef``,
``nustd.ui.CameraCaptureRef``), so keeping one is the drop zone's keep
(:func:`._media.keeping`): the take streams from the upload intake into the
space's blob store, the item is pointed at the new blob in one commit, and
the capture lets the take go and resets, ready for the next. A new take
replaces the kept one; the old blob stays readable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui

from ...contents.file import slots
from .._editing import ENTRY
from ._media import keeping


if TYPE_CHECKING:
    from nu.domains.shape import Slot

    from ...contents.file import File


__all__ = ["Parts", "keep", "order", "parts", "shown"]


class Parts:
    """A capture cell's control, as refs: where the file draws, the bar, the capture, the note."""

    def __init__(self, control: nu.Nu) -> None:
        self.control = control
        self.shown = control.shown
        self.bar = control.bar
        self.take = control.take
        self.note = control.note


def parts(take: Slot, *, between: dict[str, Slot] | None = None) -> Parts:
    """The control of a capture cell around ``take``, in the editor's Field.

    Args:
        take: The capture's slot: a ``MicCaptureRef`` or ``CameraCaptureRef``.
        between: More parts drawn between the kept file and the capture,
            by name (the camera's button that brings the camera back).
    """
    fields: dict[str, object] = {
        # The file lands here, in the one slot its type names (:func:`slots`).
        "shown": nustd.ui.ColumnRef.slot(gap=2),
        **(between or {}),
        "take": take,
        "bar": nustd.ui.ProgressRef.slot(caption="Uploading"),
        "note": nustd.ui.TextRef.slot(),
    }
    box = type("CaptureBox", (nustd.ui.Column,), fields)
    return Parts(ENTRY.control.to(box.slot(gap=2)))


def shown(p: Parts) -> nu.Nu:
    """Where the kept file draws, by its type, as the media cells draw theirs."""
    return slots(
        p.shown, image={"fit": "contain", "radius": "md", "zoom": True}, video={"radius": "md"}
    )


def order(p: Parts, names: tuple[str, ...]) -> nu.Nu:
    """The control's parts up as declared, in the order they draw, the bar hidden until a take goes up.

    Init, not only insert: the capture is never written before a person
    uses it, and a part nothing writes is never drawn.
    """
    return nu.Sequential(*(getattr(p.control, n).init() for n in names)) >> p.bar.hide()


def keep(item: File, p: Parts) -> nu.Nu:
    """Each take kept into ``item`` through the blob store, for as long as it runs."""
    return keeping(item, p.take, p.bar, p.note)
