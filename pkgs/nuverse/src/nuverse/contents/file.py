"""File: one file any cell keeps in the space's blob store, found by its name.

What the image, audio, video and file cells keep, one item each, and the
gallery cell keeps many of. The bytes are a blob (``nuspace.Blobs``), served
at ``nuspace.blobs``; the item holds the blob's id and what the person said
the file was: its name, its mime type, its size. A new file is a new blob:
an item replaced points at the new one and the old one stays readable.

How an item draws follows its mime: an image in the viewer, a video, a sound
in the audio row, any other file as a file row. :func:`draw` puts it on any
surface with those four slots (:class:`Shown`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

import nu
import nuspace
import nustd.kv
import nustd.ui
from nu.lang.sentinels import UNSET, Unset
from nuspace.shapes.content import Content
from nuspace.specs import ContentSpec

from .text import matches


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "AUDIO",
    "CONTENT",
    "FILE",
    "IMAGE",
    "VIDEO",
    "File",
    "FileContent",
    "Hit",
    "MimeIs",
    "Shown",
    "Slots",
    "Surface",
    "draw",
    "kind",
    "slots",
]


#: What a mime's first part names, as :func:`kind` reads it. Any other is a :data:`FILE`.
IMAGE, VIDEO, AUDIO, FILE = "image", "video", "audio", "file"


class File(nu.Shape):
    """A file item: the blob it is kept in, its name, mime type and size in bytes."""

    blob = nustd.kv.StrRef.slot()
    name = nustd.kv.StrRef.slot()
    mime = nustd.kv.StrRef.slot()
    size = nustd.kv.IntRef.slot()


def _mime_is(mime: object, query: object) -> bool:
    asked = str(query).strip().lower()
    held = str(mime).split(";", 1)[0].strip().lower()
    return held == asked or held.startswith(asked.rstrip("/") + "/")


#: Whether ``mime`` is the type ``query`` names, ignoring case: whole (``image/png``)
#: or its first part (``image``, ``image/``). An empty query is any type.
MimeIs = nu.host(_mime_is, name="FileMimeIs")


def _bytes(n: int) -> str:
    """A byte count in decimal units, as the kit's file row reads it: 812 B, 4.2 KB, 1.3 GB."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value, unit = float(max(n, 0)), 0
    while unit < len(units) - 1 and round(value, 0 if unit == 0 or value >= 100 else 1) >= 1000:
        value /= 1000
        unit += 1
    if unit == 0:
        return f"{int(value)} B"
    return f"{value:.0f} {units[unit]}" if value >= 100 else f"{value:.1f} {units[unit]}"


def _hit(name: object, size: object) -> str:
    shown = str(name or "").strip() or "Unnamed file"
    return f"{shown} · {_bytes(size)}" if isinstance(size, int) else shown


#: A file on one line: its name, then its size (``report.pdf · 48.2 KB``).
Hit = nu.host(_hit, name="FileHit")


def kind(mime: nu.StrArg) -> nu.Str:
    """What a mime draws as: :data:`IMAGE`, :data:`VIDEO`, :data:`AUDIO`, else :data:`FILE`."""
    first = nu.Str(mime).lower().split("/")[0]
    media = nu.Or(first == IMAGE, nu.Or(first == VIDEO, first == AUDIO))
    return nu.Str(nu.If(media, first, FILE))


class Surface(Protocol):
    """Where :func:`draw` puts a file: one slot per way it draws."""

    image: nustd.ui.ImageRef
    video: nustd.ui.VideoRef
    audio: nustd.ui.AudioRef
    file: nustd.ui.FileRef


class Shown(nu.Shape):
    """The bare surface a file item's ``render`` draws on, one slot per way it draws."""

    image = nustd.ui.ImageRef.slot(fit="contain", radius="md", zoom=True)
    video = nustd.ui.VideoRef.slot(radius="md")
    audio = nustd.ui.AudioRef.slot()
    file = nustd.ui.FileRef.slot()


@dataclass(frozen=True)
class Slots:
    """A :class:`Surface` under a container, each slot made only when a file draws in it."""

    image: nustd.ui.ImageRef
    video: nustd.ui.VideoRef
    audio: nustd.ui.AudioRef
    file: nustd.ui.FileRef


def slots(
    under: nustd.ui.ColumnRef,
    *,
    image: dict[str, Any] | None = None,
    video: dict[str, Any] | None = None,
) -> Slots:
    """The four slots as children of ``under`` (a column), keyed by way.

    A declared Shape's slots all draw when it is put on screen; these come up
    only when written, so a file shows in its one slot and no empty player
    flashes in the others. ``image`` and ``video`` are their slots' looks.
    """
    return Slots(
        image=under["image"].to(nustd.ui.ImageRef.slot(**(image or {}))),
        video=under["video"].to(nustd.ui.VideoRef.slot(**(video or {}))),
        audio=under["audio"].to(nustd.ui.AudioRef.slot()),
        file=under["file"].to(nustd.ui.FileRef.slot()),
    )


def draw(item: File, at: Surface) -> nu.Nu:
    """``item`` on ``at``, in the slot its mime names, the other three erased.

    A slot's node keeps its type once drawn, so a file that changes kind
    draws in another slot instead of the same one. An item with no blob
    draws nothing.
    """
    bid = nu.Str(item.blob.fallback(""))
    mime = nu.Str(item.mime.fallback(""))
    name = nu.Str(item.name.fallback(""))
    src, saved = nuspace.blobs.url(bid), nuspace.blobs.url(bid, download=True)
    ways = {
        IMAGE: at.image.set_src(src) >> at.image.set_alt(name) >> at.image.set_download(saved),
        VIDEO: at.video.set_src(src) >> at.video.set_download(saved),
        AUDIO: at.audio.set(src, title=name) >> at.audio.set_download(saved),
        FILE: at.file.set(src, name=name, size=item.size.fallback(None), mime=mime, download=saved),
    }
    slots = {IMAGE: at.image, VIDEO: at.video, AUDIO: at.audio, FILE: at.file}

    def only(way: str) -> nu.Nu:
        others = (slot.erase() for other, slot in slots.items() if other != way)
        return nu.Sequential(*others, ways[way])

    drawn = nu.let(kind(mime), lambda k: _pick(nu.Str(k), only))
    none = nu.Sequential(*(slot.erase() for slot in slots.values()))
    return nu.IfDo(bid == "", none, drawn)


def _pick(k: nu.Str, only: Callable[[str], nu.Nu]) -> nu.Nu:
    return nu.IfDo(
        k == IMAGE,
        only(IMAGE),
        nu.IfDo(k == VIDEO, only(VIDEO), nu.IfDo(k == AUDIO, only(AUDIO), only(FILE))),
    )


class FileContent(Content[File], name="File"):
    """The file kind: matched by the words in its name and by its type, drawn by its type."""

    @classmethod
    def match(
        cls,
        item: File,
        *,
        text: nu.StrArg | Unset = UNSET,
        type: nu.StrArg | Unset = UNSET,
    ) -> nu.Bool:
        """Whether ``text`` stands in the name as whole words, and the mime is ``type``.

        Asked nothing, every item holding a file. An item never given a
        file is nothing to find.
        """
        held = item.blob.exists()
        asks: list[nu.Nu] = [held]
        if text is not UNSET:
            asks.append(matches(nu.str(item.name.fallback("")), text))
        if type is not UNSET:
            asks.append(MimeIs(nu.str(item.mime.fallback("")), type))
        found = asks[0]
        for ask in asks[1:]:
            found = nu.And(found, ask)
        return nu.Bool(found)

    @classmethod
    def render(cls, item: File) -> nu.Nu:
        """The file whole: the image, the video, the sound or the file row."""
        return draw(item, Shown)

    @classmethod
    def render_hit(cls, item: File) -> nu.Nu:
        """The file's name and size on one line."""
        return nustd.ui.TextRef("hit").set(
            nu.Str(Hit(item.name.fallback(""), item.size.fallback(None)))
        )


#: The spec nuverse registers the kind with, as ``nuverse.File``.
CONTENT = ContentSpec(FileContent, description="A file kept in the blob store, found by its name.")
