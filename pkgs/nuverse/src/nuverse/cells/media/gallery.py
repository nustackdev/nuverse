"""A gallery cell: images, videos and sounds dropped in, kept as File items, shown in a grid.

Each file is a :class:`~nuverse.contents.file.FileContent` item in the cell's
own scope, under a fresh, time ordered content key (``nuspace.utils.MintId``),
so search, the items cell and the content lenses see them like any other.

A drop shows a tile per file with a progress bar and pulls each file to the
server. As each lands it streams from the upload intake into the space's
blob store (``nuspace.Blobs.put_stream``): no step holds the whole file. The
item is written in one commit and the file leaves the selection.

The grid is the items: one arm per item, kept in step with the scope
(``nu.ReconcileLatestEach``), newest first. An arm draws its tile by the
file's type (:func:`~nuverse.contents.file.draw`), with a Remove button. A
click erases the item; its blob stays readable, as a removed cell's do.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.places import Here
from nuspace.shapes.content import CELL as AT_CELL
from nuspace.shapes.content import entries
from nuspace.specs import CellSpec
from nuspace.utils import MintId

from ...contents.file import FileContent, draw, slots
from .. import source


__all__ = ["ACCEPT", "BODY", "CELL", "GRID", "Pending", "Tile", "out"]


#: What the drop zone takes: images, videos and sound.
ACCEPT = "image/*,video/*,audio/*"


#: How a tile's image and video look: held to a ratio, so the grid lines up.
IMAGE = {"fit": "cover", "aspect": "4/3", "radius": "md", "zoom": True}
VIDEO = {"aspect": "16/9", "radius": "md"}


class Tile(nustd.ui.Column):
    """One item: its file, then Remove."""

    # The file lands here, in the one slot its type names (:func:`~nuverse.contents.file.slots`).
    shown = nustd.ui.ColumnRef.slot()
    delete = nustd.ui.ButtonRef.slot(label="Remove", icon="trash-2", variant="ghost", size="sm")


class Pending(nustd.ui.Column):
    """A file on its way: its name and how much of it the server has."""

    name = nustd.ui.TextRef.slot(value="")
    bar = nustd.ui.ProgressRef.slot(caption="Uploading")


class Body(nustd.ui.Column):
    """The cell's surface: the drop zone, then the grid."""

    drop = nustd.ui.UploadFilesRef.slot(accept=ACCEPT, prompt="Drop images, videos or sound")
    grid = nustd.ui.GridRef.slot(min_cell_width=240, gap=3)


class View(nu.Shape):
    """The cell's root: its :class:`Body`, the parts spaced apart."""

    body = Body.slot(gap=3)


#: The running cell's surface.
BODY = View.body

GRID, DROP = BODY.grid, BODY.drop


def _items() -> nustd.kv.DictRef:
    """The cell's own file items, by content key."""
    return entries(FileContent, AT_CELL, Here.cell)


# ---- the grid -------------------------------------------------------------------------


def _tile(key: nu.Nu) -> nu.Nu:
    """One item's arm: its tile up while it lives, redrawn when it changes, its Remove heard."""
    k = nu.Str(key)
    item = _items()[k]
    tile = GRID[k].to(Tile.slot(gap=2))
    shown = draw(item, slots(tile.shown, image=IMAGE, video=VIDEO))
    up = GRID.insert(tile, at=0) >> shown >> tile.delete.init()
    live = up >> nu.ParallelAsync(
        nu.ReactEvery(tile.delete.on_click(), nuspace.atomic(item.erase())),
        nu.ReactEvery(item.on_change(), shown),
    )
    leave = nu.TryCatch(GRID.remove(k), catch=lambda _: nu.Noop())
    return nu.TryCatch(live, finally_=leave)


def _grid() -> nu.Nu:
    """One tile per item, kept in step with the cell's items."""
    items = _items()
    # A scope no item landed in yet has no mapping: it holds none.
    keys = nuspace.atomic(nu.list(nu.If(items.exists(), nu.list(items.keys()), [])))
    return nu.ReconcileLatestEach(keys, items.on_children_change(), _tile)


# ---- uploads --------------------------------------------------------------------------


def _pending(key: nu.Nu) -> Pending:
    """The progress tile of the upload ``key``, apart from the items' keys."""
    return GRID[nu.Str("upload-") + nu.Str(key)].to(Pending.slot(gap=2))


def _picked() -> nu.Nu:
    """A progress tile and a pull for every newly picked file."""

    def start(i: nu.Nu, entry: nu.Nu) -> nu.Nu:
        f = nu.Dict(entry)
        tile = _pending(f["key"])
        return nu.IfDo(
            nu.Eq(f["state"], "picked"),
            GRID.insert(tile, at=0) >> tile.name.set(f["name"]) >> DROP.file(i).pull(),
        )

    return nu.ForEachDo(nu.Enumerate(nu.Iter(DROP)), lambda e: start(e[0], e[1]))


def _moved(event: nu.Nu) -> nu.Nu:
    """A pull moving: its bar to the share sent."""
    ev = nu.Dict(event)
    size = nu.Float(ev["size"])
    return nu.IfDo(size > 0, _pending(ev["key"]).bar.set_value(nu.Float(ev["sent"]) / size))


def _landed(event: nu.Nu) -> nu.Nu:
    """A pull ended: a landed file streamed into the store, kept as an item and let go."""
    ev = nu.Dict(event)
    key, tile = ev["key"], _pending(ev["key"])

    def find(selection: nu.Nu) -> nu.Nu:
        sel = nu.List(selection)
        keys = nu.List(nu.Collect(nu.Map(nu.Iter(sel), lambda f: f["key"])))
        # ``open`` pulls too, and its landing is heard here after the first one
        # kept the file and let it go: only a file still picked is kept.
        return nu.IfDo(keys.contains(key), nu.let(keys.index(key), lambda i: store(i, sel[i])))

    def store(i: nu.Nu, entry: nu.Nu) -> nu.Nu:
        f = nu.Dict(entry)
        file = DROP.file(i)
        put = nuspace.Blobs.put_stream(file.open(), mime=f["mime"], name=f["name"])

        def kept(bid: nu.Nu, minted: nu.Nu) -> nu.Nu:
            fields = nu.Dict.of(blob=bid, name=f["name"], mime=f["mime"], size=f["size"])
            return nuspace.atomic(_items()[nu.Str(minted)].set(fields))

        stored = nu.let(put, lambda bid: nu.let(MintId("f"), lambda minted: kept(bid, minted)))
        done = GRID.remove(nu.Str("upload-") + nu.Str(key)) >> file.discard() >> DROP.remove(i)

        def failed(err: nu.Nu) -> nu.Nu:
            return tile.bar.set(0.0, caption=nu.Str("Failed: ") + nu.str(err))

        storing = tile.bar.set(1.0, caption="Storing", indeterminate=True)
        return nu.TryCatch(storing >> stored >> done, catch=failed)

    return nu.IfDo(
        nu.Eq(ev["state"], "landed"),
        nu.let(DROP, find),
        tile.bar.set(0.0, caption=nu.Str("Failed: ") + nu.str(ev["error"])),
    )


def out() -> nu.Nu:
    """The drop zone and the grid, for as long as the cell runs."""
    order = nu.Sequential(*(BODY.insert(part) for part in ("drop", "grid")))
    uploads = nu.ParallelAsync(
        nu.ReactEvery(DROP.on_change(), lambda _: _picked()),
        nu.ReactEvery(DROP.on_progress(), _moved),
        nu.ReactEvery(DROP.on_upload(), _landed),
    )
    return nuspace.bracketed(order >> nu.ParallelAsync(_grid(), uploads))


CELL = CellSpec(
    "gallery",
    "Gallery",
    source(__name__),
    description="Images, videos and sound dropped in a grid, kept as file content.",
    group="Media",
    icon="images",
)
