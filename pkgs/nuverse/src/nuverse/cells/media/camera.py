"""A camera cell: a photo or a video taken in place, kept as file content, live across tabs.

The take is a :class:`~nuverse.contents.file.FileContent` item: the cell's
own ``value`` unless its Config points it elsewhere (:mod:`._capture`). Its
Config picks photo or video, kept in the cell's own state.

The kept photo or video shows above. A camera frame is as big as the
picture, so while there is one kept the camera stays out of the way behind a
"New photo" (or "New video") button; closed without a take, it goes back.
With nothing kept the camera shows at once.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.specs import CellSpec

from ...contents.file import FileContent, draw
from .. import source
from .._editing import editor, setting
from ._capture import keep, order, parts, shown


if TYPE_CHECKING:
    from ...contents.file import File


__all__ = ["CELL", "MODE", "PARTS", "Shot", "out"]


MODES = [{"value": "photo", "label": "Photo"}, {"value": "video", "label": "Video"}]


class Shot(nu.Shape):
    """A camera cell's state: photo or video."""

    mode = nustd.kv.StrRef.slot()


#: The control: the kept take, the button that brings the camera back, the camera, the bar, a note.
PARTS = parts(
    nustd.ui.CameraCaptureRef.slot(size="sm", max_duration=300),
    between={"again": nustd.ui.ButtonRef.slot(label="New photo", variant="secondary", size="sm")},
)
AGAIN = PARTS.control.again

SHOWN = shown(PARTS)

#: Photo or video, under the editor's settings.
MODE = setting(
    "mode", "Mode", nustd.ui.SegmentedControlRef.slot(options=MODES, value="photo", size="sm")
)


def _mode(shot: Shot) -> nu.Str:
    """The cell's mode: video when it says so, else photo."""
    raw = nu.Str(shot.mode.fallback("photo"))
    return nu.Str(nu.If(raw == "video", "video", "photo"))


def _edit(item: File) -> nu.Nu:
    """The kept take shown, the camera out of its way while it is, and each take kept."""
    held = nu.Str(item.blob.fallback("")) != ""
    # Something kept: the camera waits behind the button. Nothing: the camera, at once.
    tucked = nu.IfDo(
        held,
        PARTS.take.hide() >> AGAIN.display(),
        AGAIN.hide() >> PARTS.take.display(),
    )
    show = draw(item, SHOWN) >> tucked

    def moved(event: nu.Nu) -> nu.Nu:
        # Closed (or kept and reset) with a take kept: back behind the button.
        return nu.IfDo(nu.Str(nu.Dict(event)["status"]) == "idle", tucked)

    return show >> nu.ParallelAsync(
        keep(item, PARTS),
        nu.ReactEvery(item.on_change(), show),
        nu.ReactEvery(AGAIN.on_click(), AGAIN.hide() >> PARTS.take.display()),
        nu.ReactEvery(PARTS.take.on_status(), moved),
    )


def out() -> nu.Nu:
    """The camera, the kept take and Config, for as long as the cell runs."""
    shot = nuspace.here(Shot)

    def apply() -> nu.Nu:
        mode = _mode(shot)
        label = nu.If(mode == "video", "New video", "New photo")
        return MODE.set(mode) >> PARTS.take.set_mode(mode) >> AGAIN.set_label(label)

    first = order(PARTS, ("shown", "again", "take", "bar", "note")) >> AGAIN.hide() >> apply()
    return editor(
        FileContent,
        _edit,
        first=first,
        also=(
            nu.ReactEvery(MODE.on_change(), shot.mode.set(nu.ToStr(MODE))),
            nu.ReactEvery(shot.mode.on_change(), apply()),
        ),
    )


CELL = CellSpec(
    "camera",
    "Camera",
    source(__name__),
    description="A photo or a video taken in place, kept as file content in the blob store.",
    group="Media",
    icon="camera",
)
