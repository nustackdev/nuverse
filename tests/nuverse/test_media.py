"""nuverse's media: the File kind, the single file Cells and the gallery, run on a real store.

A fake tab plays the browser's part of an upload: it holds the picked
files, answers a pull with a progress and a landing, writing the bytes into a
real upload area the way the intake does, and answers a discard. The cells
stream what lands into a real blob store on disk.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

import pytest

import nu
import nuspace
import nustd.blob
from nuspace.kernel.body import Rewrites
from nuspace.places import inside
from nuspace.shapes.content import CELL, entries
from nuspace.web.env import session_env
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session
from nustd.ui.uploads import UploadView
from nuverse.cells.media import audio, camera, file, gallery, image, mic, video
from nuverse.contents.file import FileContent, Hit, MimeIs, kind


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


Space = nuspace.Space
SID = "tab1"
PNG = b"\x89PNG\r\n\x1a\n" + bytes(range(200))
PDF = b"%PDF-1.7\n" + b"x" * 3000


# --- the fake tab ----------------------------------------------------------------------


class _Tab(WsSession):
    """A tab with one file input: the files picked in it, and the browser's half of a pull.

    ``given`` names the input: the media cells' drop zone, or a capture
    cell's ``take``, whose recorded file reads as a picked one.
    """

    def __init__(self, root: Path, *, many: bool = False, given: str = "drop") -> None:
        super().__init__(ws=None)
        self.root = root
        self.many = many
        self.given = given
        self.frames: list[Frame] = []
        self.files: list[dict[str, Any]] = []

    # Session ---------------------------------------------------------------

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)
        if frame.op == "reset":
            # Frames land in order over one socket: the selection is cleared
            # before any read or pick after it.
            self.files = []
        elif frame.op == "remove_file":
            gone = self._targets(frame.payload.get("key"))
            self.files = [f for f in self.files if f not in gone]
            asyncio.get_running_loop().call_soon(self.notify, frame.ref, {"event": "change"})
        elif frame.ref and frame.ref[-1] == self.given and frame.op != "write":
            asyncio.get_running_loop().call_soon(self._handle, frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        if path[-1] != self.given:
            return None
        entries = [self._entry(f) for f in self.files]
        return entries if self.many else (entries[0] if entries else None)

    # the browser -----------------------------------------------------------

    def notify(self, path: tuple[str, ...], payload: object) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))

    def path(self, name: str) -> tuple[str, ...]:
        """Where the node ``name`` is: written to, or inserted by its parent."""
        for f in self.frames:
            if f.ref and f.ref[-1] == name:
                return f.ref
            if (
                f.op == "insert_item"
                and isinstance(f.payload, dict)
                and f.payload.get("key") == name
            ):
                return (*f.ref, name)
        raise StopIteration(name)

    def has(self, name: str) -> bool:
        try:
            self.path(name)
        except StopIteration:
            return False
        return True

    def pick(self, *files: tuple[str, str, bytes]) -> None:
        """Files dropped at once, as ``(name, mime, data)``: they join the selection, one change heard."""
        picked = [
            {
                "key": uuid.uuid4().hex[:8],
                "name": n,
                "mime": m,
                "data": d,
                "token": None,
                "pull": False,
            }
            for n, m, d in files
        ]
        self.files = [*self.files, *picked] if self.many else picked[-1:]
        self.notify(self.path(self.given), {"event": "change"})

    def written(self, name: str) -> list[object]:
        """Every write payload to the node ``name``, in order."""
        return [f.payload for f in self.frames if f.op == "write" and f.ref[-1] == name]

    def ops(self, name: str) -> list[str]:
        return [f.op for f in self.frames if f.ref and f.ref[-1] == name]

    def _entry(self, f: dict[str, Any]) -> dict[str, Any]:
        state = "landed" if f["token"] else "pulling" if f["pull"] else "picked"
        return {
            "key": f["key"],
            "name": f["name"],
            "mime": f["mime"],
            "size": len(f["data"]),
            "modified": 0,
            "state": state,
            "sent": len(f["data"]) if f["token"] else 0,
            "error": "",
        }

    def _targets(self, key: object) -> list[dict[str, Any]]:
        if key is None:
            return list(self.files) if self.many else self.files[:1]
        return [self.files[key]] if isinstance(key, int) and key < len(self.files) else []

    def _handle(self, frame: Frame) -> None:
        path, p = frame.ref, frame.payload if isinstance(frame.payload, dict) else {}
        targets = self._targets(p.get("key"))
        if frame.op == "pull":
            for f in targets:
                self._pull(path, f, p["rid"])
        elif frame.op == "discard":
            f = targets[0] if targets else None
            token = f["token"] if f else None
            event = {"event": "discard", "key": f and f["key"], "rid": p["rid"], "token": token}
            self.notify(path, event)

    def _pull(self, path: tuple[str, ...], f: dict[str, Any], rid: str) -> None:
        f["pull"] = True
        size = len(f["data"])
        if not f["token"]:
            sent = {"event": "progress", "key": f["key"], "rid": rid, "sent": size, "size": size}
            self.notify(path, sent)
            f["token"] = uuid.uuid4().hex
            home = self.root / SID
            home.mkdir(parents=True, exist_ok=True)
            (home / f["token"]).write_bytes(f["data"])
        landed = {
            "event": "upload",
            "key": f["key"],
            "rid": rid,
            "token": f["token"],
            "state": "landed",
            "size": size,
            "error": "",
        }
        self.notify(path, landed)


# --- running a cell ----------------------------------------------------------------------


@pytest.fixture
def blobs(tmp_path: Path) -> nu.Nu:
    """The space's blob store, as files on disk."""
    return nustd.blob.files(nuspace.Blobs, str(tmp_path / "blobs"))


async def _until(check: Callable[[], bool], timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def _settles(store, term: nu.Nu, check: Callable[[object], bool]) -> object:
    deadline = asyncio.get_running_loop().time() + 5.0
    while not check(value := await store.read(term)):
        assert asyncio.get_running_loop().time() < deadline, f"timed out on {value!r}"
        await asyncio.sleep(0.01)
    return value


async def _spec_cell(store, spec: object, cell: str = "c", plane: str = "p") -> None:
    if not await store.read(nuspace.plane.exists(plane)):
        await store.do(nuspace.plane.add(id=plane, backend="async"))
    await store.do(nuspace.specs.add_cell(plane, spec, id=cell))


async def _running(store, tab: _Tab, blobs: nu.Nu, cell: str = "c", plane: str = "p"):
    """The cell's program, loaded as the kernel loads it, run with the tab, its uploads and the store."""
    env = session_env("127.0.0.1:9")("s1")
    prog = Space.cells[cell].prog
    load = prog.load(scope={"plane": plane, "cell": cell}, rewrite=Rewrites(env.rewrite))
    term = inside(await store.run(nuspace.atomic(load)), plane=plane, cell=cell)
    ctx = store.ctx.bind(Session, tab).bind(UploadView, UploadView(tab.root, SID))
    return asyncio.create_task(nu.arun(nu.With(blobs, body=term), ctx))


async def _blob(store, blobs: nu.Nu, bid: str) -> bytes:
    return await store.run(nu.With(blobs, body=nuspace.Blobs.get(bid)))


def _item(cell: str = "c", key: str = "value") -> nu.Nu:
    return nuspace.at.cell(id=cell).content(FileContent)[key]


async def _listening() -> None:
    await asyncio.sleep(0.1)


# --- the File kind -----------------------------------------------------------------------


def test_a_mime_draws_as_its_first_part_or_as_a_file():
    for mime, way in [
        ("image/png", "image"),
        ("VIDEO/mp4", "video"),
        ("audio/mpeg", "audio"),
        ("application/pdf", "file"),
        ("", "file"),
    ]:
        assert nu.run(kind(mime))[0] == way, mime


def test_a_type_asked_is_the_whole_mime_or_its_first_part():
    for mime, asked, hit in [
        ("image/png", "image", True),
        ("image/png", "image/", True),
        ("image/png", "IMAGE/PNG", True),
        ("image/png; q=1", "image/png", True),
        ("image/png", "imag", False),
        ("video/mp4", "image", False),
    ]:
        assert nu.run(MimeIs(mime, asked))[0] is hit, (mime, asked)


def test_a_hit_reads_the_name_then_the_size():
    assert nu.run(Hit("report.pdf", 48_200))[0] == "report.pdf · 48.2 KB"
    assert nu.run(Hit("big.zip", 1_204_000_000))[0] == "big.zip · 1.2 GB"
    assert nu.run(Hit("tiny", 812))[0] == "tiny · 812 B"
    assert nu.run(Hit("", None))[0] == "Unnamed file"


async def test_a_file_matches_by_the_words_in_its_name_and_by_type(store):
    item = _item()
    await _spec_cell(store, image.CELL)
    held = {"blob": "b1", "name": "Quarterly report.pdf", "mime": "application/pdf", "size": 9}
    await store.do(item.set(held))
    for text, type_, hit in [
        ("report", None, True),
        ("QUARTERLY", "application", True),
        ("port", None, False),
        (None, "image", False),
        (None, "application/pdf", True),
    ]:
        asked = {k: v for k, v in (("text", text), ("type", type_)) if v is not None}
        assert await store.read(FileContent.match(item, **asked)) is hit, asked


async def test_a_file_never_given_one_is_nothing_to_find(store):
    await _spec_cell(store, image.CELL)
    await store.do(_item().set({"name": "draft"}))
    assert await store.read(FileContent.match(_item())) is False


# --- the single file cells ---------------------------------------------------------------


async def test_an_image_dropped_is_kept_in_the_blob_store_and_shown(store, tmp_path, blobs):
    await _spec_cell(store, image.CELL)
    tab = _Tab(tmp_path / "area")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: tab.has("drop"))
        assert {"accept": "image/*"} in tab.written("drop")
        assert {"prompt": "Drop an image"} in tab.written("drop")
        await _listening()
        tab.pick(("lizard.png", "image/png", PNG))

        bid = await _settles(store, _item().blob.fallback(""), bool)
        assert await store.read(_item().name) == "lizard.png"
        assert await store.read(_item().mime) == "image/png"
        assert await store.read(_item().size) == len(PNG)
        assert await _blob(store, blobs, bid) == PNG

        src = f"/blobs/{bid}"
        await _until(lambda: {"src": src} in tab.written("image"))
        assert {"download": f"{src}?download=1"} in tab.written("image")
        await _until(lambda: {"prompt": "Drop an image to replace it"} in tab.written("drop"))
        # The bar came up for the upload and went away; the drop zone let it go.
        assert "display" in tab.ops("bar")
        assert tab.ops("bar")[-1] == "hide"
        await _until(lambda: "reset" in tab.ops("drop"))
        assert "discard" in tab.ops("drop")
    finally:
        task.cancel()


async def test_a_file_dropped_over_one_replaces_it_and_the_old_blob_stays(store, tmp_path, blobs):
    await _spec_cell(store, image.CELL)
    tab = _Tab(tmp_path / "area")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: tab.has("drop"))
        await _listening()
        tab.pick(("one.png", "image/png", PNG))
        first = await _settles(store, _item().blob.fallback(""), bool)
        await _until(lambda: "reset" in tab.ops("drop"))
        tab.pick(("two.png", "image/png", PNG[::-1]))
        second = await _settles(store, _item().blob.fallback(""), lambda b: b not in ("", first))
        assert await store.read(_item().name) == "two.png"
        assert await _blob(store, blobs, second) == PNG[::-1]
        assert await _blob(store, blobs, first) == PNG
        await _until(lambda: {"src": f"/blobs/{second}"} in tab.written("image"))
    finally:
        task.cancel()


async def test_a_file_written_by_a_program_draws_by_its_type(store, tmp_path, blobs):
    await _spec_cell(store, image.CELL)
    tab = _Tab(tmp_path / "area")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: tab.has("drop"))
        await _listening()
        held = {"blob": "b1", "name": "notes.pdf", "mime": "application/pdf", "size": 3009}
        await store.do(_item().set(held))
        want = {
            "src": "/blobs/b1",
            "name": "notes.pdf",
            "size": 3009,
            "mime": "application/pdf",
            "download": "/blobs/b1?download=1",
        }
        await _until(lambda: want in tab.written("file"))
        # The other ways it could draw are cleared, so a kind change never retypes a node.
        assert "remove" in tab.ops("image")
    finally:
        task.cancel()


@pytest.mark.parametrize(
    ("spec", "accept", "name", "mime", "slot"),
    [
        (video.CELL, "video/*", "clip.mp4", "video/mp4", "video"),
        (audio.CELL, "audio/*", "take.mp3", "audio/mpeg", "audio"),
        (file.CELL, "", "notes.pdf", "application/pdf", "file"),
    ],
)
async def test_each_single_file_cell_takes_its_kind_and_draws_it(
    store, tmp_path, blobs, spec, accept, name, mime, slot
):
    await _spec_cell(store, spec)
    tab = _Tab(tmp_path / "area")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: {"accept": accept} in tab.written("drop"))
        await _listening()
        tab.pick((name, mime, PDF))
        bid = await _settles(store, _item().blob.fallback(""), bool)
        assert await _blob(store, blobs, bid) == PDF
        await _until(lambda: any(w.get("src") == f"/blobs/{bid}" for w in tab.written(slot)))
    finally:
        task.cancel()


# --- the capture cells -------------------------------------------------------------------

WEBM = b"\x1aE\xdf\xa3" + bytes(range(120))


def _seen(tab: _Tab, name: str) -> bool | None:
    """Whether ``name`` was last displayed (True) or hidden (False), None if neither yet."""
    moves = [op for op in tab.ops(name) if op in ("display", "hide")]
    return moves[-1] == "display" if moves else None


def _shot(cell: str = "c") -> nu.Nu:
    return nuspace.at.cell(id=cell).state(camera.Shot)


async def test_a_mic_take_is_kept_in_the_blob_store_and_plays_above(store, tmp_path, blobs):
    await _spec_cell(store, mic.CELL)
    tab = _Tab(tmp_path / "area", given="take")
    task = await _running(store, tab, blobs)
    try:
        # The recorder is drawn on start, before anything writes it.
        await _until(lambda: "init" in tab.ops("take"))
        await _listening()
        tab.pick(("recording-2026-11-17-140322.webm", "audio/webm", WEBM))

        bid = await _settles(store, _item().blob.fallback(""), bool)
        assert await store.read(_item().name) == "recording-2026-11-17-140322.webm"
        assert await store.read(_item().mime) == "audio/webm"
        assert await _blob(store, blobs, bid) == WEBM
        await _until(lambda: any(w.get("src") == f"/blobs/{bid}" for w in tab.written("audio")))
        # The bar went up and away; the recorder let the take go, ready for the next.
        assert tab.ops("bar")[-1] == "hide"
        await _until(lambda: "reset" in tab.ops("take"))
        assert "discard" in tab.ops("take")
    finally:
        task.cancel()


async def test_a_mic_take_over_a_kept_one_replaces_it(store, tmp_path, blobs):
    await _spec_cell(store, mic.CELL)
    tab = _Tab(tmp_path / "area", given="take")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: tab.has("take"))
        await _listening()
        tab.pick(("one.webm", "audio/webm", WEBM))
        first = await _settles(store, _item().blob.fallback(""), bool)
        await _until(lambda: "reset" in tab.ops("take"))
        tab.pick(("two.webm", "audio/webm", WEBM[::-1]))
        second = await _settles(store, _item().blob.fallback(""), lambda b: b not in ("", first))
        assert await store.read(_item().name) == "two.webm"
        assert await _blob(store, blobs, second) == WEBM[::-1]
        assert await _blob(store, blobs, first) == WEBM
    finally:
        task.cancel()


async def test_a_camera_shows_at_once_with_nothing_kept(store, tmp_path, blobs):
    await _spec_cell(store, camera.CELL)
    tab = _Tab(tmp_path / "area", given="take")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: _seen(tab, "take") is True)
        assert "init" in tab.ops("take")
        assert _seen(tab, "again") is False
        assert {"mode": "photo"} in tab.written("take")
    finally:
        task.cancel()


async def test_a_camera_photo_is_kept_and_the_camera_waits_behind_a_button(store, tmp_path, blobs):
    await _spec_cell(store, camera.CELL)
    tab = _Tab(tmp_path / "area", given="take")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: "display" in tab.ops("take"))
        await _listening()
        tab.pick(("photo-2026-11-17-140322.jpg", "image/jpeg", PNG))

        bid = await _settles(store, _item().blob.fallback(""), bool)
        assert await store.read(_item().mime) == "image/jpeg"
        assert await _blob(store, blobs, bid) == PNG
        await _until(lambda: {"src": f"/blobs/{bid}"} in tab.written("image"))
        # Kept: the camera goes behind the button.
        await _until(lambda: _seen(tab, "take") is False and _seen(tab, "again") is True)

        # The button brings it back; closed without a take, it goes back again.
        await _listening()
        tab.notify(tab.path("again"), {"event": "click"})
        await _until(lambda: _seen(tab, "take") is True and _seen(tab, "again") is False)
        await _listening()
        tab.notify(tab.path("take"), {"event": "status", "status": "live", "error": ""})
        tab.notify(tab.path("take"), {"event": "status", "status": "idle", "error": ""})
        await _until(lambda: _seen(tab, "take") is False and _seen(tab, "again") is True)
    finally:
        task.cancel()


async def test_a_camera_mode_is_kept_in_the_cell_and_names_its_button(store, tmp_path, blobs):
    await _spec_cell(store, camera.CELL)
    tab = _Tab(tmp_path / "area", given="take")
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: {"mode": "photo"} in tab.written("take"))
        await _listening()
        await store.do(_shot().mode.set("video"))
        await _until(lambda: {"mode": "video"} in tab.written("take"))
        await _until(lambda: {"label": "New video"} in tab.written("again"))
    finally:
        task.cancel()


# --- the gallery -------------------------------------------------------------------------


def _files(cell: str = "c") -> nu.Nu:
    return entries(FileContent, CELL, cell)


def _keys(cell: str = "c") -> nu.Nu:
    items = _files(cell)
    return nu.list(nu.If(items.exists(), nu.list(items.keys()), []))


async def test_a_gallery_keeps_each_file_dropped_as_an_item_and_tiles_it(store, tmp_path, blobs):
    await _spec_cell(store, gallery.CELL)
    tab = _Tab(tmp_path / "area", many=True)
    task = await _running(store, tab, blobs)
    try:
        # The drop zone and the grid come on screen before any file: placed is not drawn.
        await _until(lambda: "init" in tab.ops("drop") and "init" in tab.ops("grid"))
        await _listening()
        tab.pick(("lizard.png", "image/png", PNG), ("clip.mp4", "video/mp4", PDF))

        keys = await _settles(store, _keys(), lambda k: len(k) == 2)
        kept = {
            await store.read(_files()[k].name): await store.read(_files()[k].blob) for k in keys
        }
        assert set(kept) == {"lizard.png", "clip.mp4"}
        assert await _blob(store, blobs, kept["lizard.png"]) == PNG
        assert await _blob(store, blobs, kept["clip.mp4"]) == PDF
        assert await store.read(_files()[keys[0]].mime) in {"image/png", "video/mp4"}

        # A tile per item, drawn by its type; the progress tiles gone, the files let go.
        await _until(lambda: {"src": f"/blobs/{kept['lizard.png']}"} in tab.written("image"))
        await _until(lambda: {"src": f"/blobs/{kept['clip.mp4']}"} in tab.written("video"))
        await _until(lambda: not tab.files)
        grid = tab.path("grid")
        gone = [f.payload["key"] for f in tab.frames if f.op == "remove_item" and f.ref == grid]
        assert len([k for k in gone if k.startswith("upload-")]) == 2
        # Only the slot a file draws in is made: no empty player beside it.
        made = {
            f.ref[-1]
            for f in tab.frames
            if f.ref[: len(grid)] == grid and len(f.ref) > len(grid) + 2
        }
        assert made <= {"image", "video", "audio", "file", "bar", "name"}
        assert not any(f.op == "init" and f.ref[-1] in {"audio", "file"} for f in tab.frames)
    finally:
        task.cancel()


async def test_a_gallery_tile_removed_erases_its_item_and_keeps_its_blob(store, tmp_path, blobs):
    await _spec_cell(store, gallery.CELL)
    tab = _Tab(tmp_path / "area", many=True)
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: tab.has("drop"))
        await _listening()
        tab.pick(("lizard.png", "image/png", PNG))
        [key] = await _settles(store, _keys(), lambda k: len(k) == 1)
        bid = await store.read(_files()[key].blob)
        await _until(lambda: tab.has("delete"))
        await _listening()
        tab.notify(tab.path("delete"), {"event": "click"})
        await _settles(store, _keys(), lambda k: k == [])
        assert await _blob(store, blobs, bid) == PNG
        grid = tab.path("grid")
        await _until(
            lambda: any(
                f.op == "remove_item" and f.ref == grid and f.payload == {"key": key}
                for f in tab.frames
            )
        )
    finally:
        task.cancel()


async def test_a_gallery_shows_items_a_program_wrote_before_it_ran(store, tmp_path, blobs):
    await _spec_cell(store, gallery.CELL)
    held = {"blob": "b9", "name": "take.mp3", "mime": "audio/mpeg", "size": 10}
    await store.do(_files()["f1"].set(held))
    tab = _Tab(tmp_path / "area", many=True)
    task = await _running(store, tab, blobs)
    try:
        await _until(lambda: any(w.get("src") == "/blobs/b9" for w in tab.written("audio")))
        assert any(w.get("title") == "take.mp3" for w in tab.written("audio"))
    finally:
        task.cancel()
