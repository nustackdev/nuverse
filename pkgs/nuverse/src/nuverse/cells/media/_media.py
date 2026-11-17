"""What the single file Cells share: a drop zone over one File item, and the file drawn above it.

An image, video, audio or file cell keeps one
:class:`~nuverse.contents.file.FileContent` item: the cell's own ``value``
unless its Config points it elsewhere, as any editor's (:mod:`.._editing`).
Its control is a :class:`Box`: the file drawn by its type
(:func:`~nuverse.contents.file.draw`), a progress bar while one goes up, the
drop zone, and a note when one fails.

A file dropped streams from the upload intake into the space's blob store
(``nuspace.Blobs.put_stream``), and the item is pointed at the new blob in
one commit, so every tab and every cell on the item shows it. The drop zone
lets the file go once it is kept. Dropped over a kept file, the new one
replaces it; the old blob stays readable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
import nustd.ui

from ...contents.file import File, FileContent, draw, slots
from .._editing import ENTRY, editor


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["BAR", "CONTROL", "DROP", "NOTE", "SHOWN", "Box", "cell", "keeping"]


class Box(nustd.ui.Column):
    """A single file cell's control: the file, the bar while one goes up, the drop zone, a note."""

    # The file lands here, in the one slot its type names (:func:`~nuverse.contents.file.slots`).
    shown = nustd.ui.ColumnRef.slot(gap=2)
    bar = nustd.ui.ProgressRef.slot(caption="Uploading")
    drop = nustd.ui.UploadFileRef.slot(size="sm")
    note = nustd.ui.TextRef.slot()


#: The control, in the editor's Field.
CONTROL = ENTRY.control.to(Box.slot(gap=2))

BAR, DROP, NOTE = CONTROL.bar, CONTROL.drop, CONTROL.note

#: Where the file draws, by its type.
SHOWN = slots(
    CONTROL.shown, image={"fit": "contain", "radius": "md", "zoom": True}, video={"radius": "md"}
)

#: The box's parts in the order they draw, the bar hidden until a file goes up.
ORDER = nu.Sequential(*(CONTROL.insert(part) for part in ("shown", "bar", "drop", "note")))


def keeping(item: File, given: nu.Nu, bar: nu.Nu, note: nu.Nu) -> nu.Nu:
    """A file handed to ``given`` streamed into the blob store and kept in ``item``, for as long as it runs.

    ``given`` is any input whose value is one file and whose bytes read with
    ``open()``: an upload drop zone, or a mic or camera capture whose take
    reads as an upload. ``bar`` shows the bytes going up, ``note`` a failure.
    Once kept, the input lets the file go and is reset.
    """

    def keep(f: nu.Dict) -> nu.Nu:
        put = nuspace.Blobs.put_stream(given.open(), mime=f["mime"], name=f["name"])

        def kept(bid: nu.Nu) -> nu.Nu:
            fields = nu.Dict.of(blob=bid, name=f["name"], mime=f["mime"], size=f["size"])
            return nuspace.atomic(item.set(fields))

        going = note.set("") >> bar.set(0.0, caption=nu.Str("Uploading ") + f["name"])
        stored = bar.display() >> going >> nu.let(put, kept)
        done = bar.hide() >> given.discard() >> given.reset()

        def failed(err: nu.Nu) -> nu.Nu:
            return bar.hide() >> note.set(nu.Str("Could not keep the file: ") + nu.str(err))

        return nu.TryCatch(stored >> done, catch=failed)

    def moved(event: nu.Nu) -> nu.Nu:
        ev = nu.Dict(event)
        size = nu.Float(ev["size"])
        return nu.IfDo(size > 0, bar.set_value(nu.Float(ev["sent"]) / size))

    # A value cleared (a reset, a remove, a take deleted) reads NULL: nothing to keep.
    picked = nu.IfDo(nu.IsNull(given), nu.Noop(), nu.let(given, lambda f: keep(nu.Dict(f))))
    return nu.ParallelAsync(
        nu.ReactLatest(given.on_change(), picked),
        nu.ReactEvery(given.on_progress(), moved),
    )


def _edit(empty: str, filled: str) -> Callable[[File], nu.Nu]:
    """The body :func:`editor` runs over the item: the file shown, and a drop kept into it."""

    def edit(item: File) -> nu.Nu:
        held = nu.Str(item.blob.fallback(""))
        show = draw(item, SHOWN) >> DROP.set_prompt(nu.If(held == "", empty, filled))
        return show >> nu.ParallelAsync(
            keeping(item, DROP, BAR, NOTE),
            nu.ReactEvery(item.on_change(), show),
        )

    return edit


def cell(*, accept: str, empty: str, filled: str) -> nu.Nu:
    """A whole single file cell: its file, drop zone and Config, for as long as it runs.

    Args:
        accept: What the drop zone takes, as the browser's ``accept``
            (``image/*``); "" takes any file.
        empty: The drop zone's prompt while the item holds no file.
        filled: Its prompt once it holds one.
    """
    first = ORDER >> BAR.hide() >> DROP.set_accept(accept)
    return editor(FileContent, _edit(empty, filled), first=first)
