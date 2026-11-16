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


__all__ = ["BAR", "CONTROL", "DROP", "NOTE", "SHOWN", "Box", "cell"]


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


def _edit(empty: str, filled: str) -> Callable[[File], nu.Nu]:
    """The body :func:`editor` runs over the item: the file shown, and a drop kept into it."""

    def edit(item: File) -> nu.Nu:
        held = nu.Str(item.blob.fallback(""))
        show = draw(item, SHOWN) >> DROP.set_prompt(nu.If(held == "", empty, filled))

        def keep(f: nu.Dict) -> nu.Nu:
            put = nuspace.Blobs.put_stream(DROP.open(), mime=f["mime"], name=f["name"])

            def kept(bid: nu.Nu) -> nu.Nu:
                fields = nu.Dict.of(blob=bid, name=f["name"], mime=f["mime"], size=f["size"])
                return nuspace.atomic(item.set(fields))

            going = NOTE.set("") >> BAR.set(0.0, caption=nu.Str("Uploading ") + f["name"])
            stored = BAR.display() >> going >> nu.let(put, kept)
            done = BAR.hide() >> DROP.discard() >> DROP.reset()

            def failed(err: nu.Nu) -> nu.Nu:
                return BAR.hide() >> NOTE.set(nu.Str("Could not keep the file: ") + nu.str(err))

            return nu.TryCatch(stored >> done, catch=failed)

        def moved(event: nu.Nu) -> nu.Nu:
            ev = nu.Dict(event)
            size = nu.Float(ev["size"])
            return nu.IfDo(size > 0, BAR.set_value(nu.Float(ev["sent"]) / size))

        # A selection cleared (a reset, a remove) reads NULL: nothing to keep.
        picked = nu.IfDo(nu.IsNull(DROP), nu.Noop(), nu.let(DROP, lambda f: keep(nu.Dict(f))))
        return show >> nu.ParallelAsync(
            nu.ReactLatest(DROP.on_change(), picked),
            nu.ReactEvery(DROP.on_progress(), moved),
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
