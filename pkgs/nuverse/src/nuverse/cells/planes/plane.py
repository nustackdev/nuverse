"""A plane cell: a new empty plane under its own, and a link to it in its place.

The first run makes the plane, an empty one nested under the cell's own,
and keeps its id in the cell's state. Every run after finds it there, so
a restart or a reload never makes a second one. The link follows the
plane: rename it or change its icon and the link draws again.
"""

from __future__ import annotations

import nu
import nuspace
import nuspace.web
import nustd.kv
import nustd.ui
from nuspace.places import Here
from nuspace.specs import EMPTY_PLANE, CellSpec

from .. import source


__all__ = ["CELL", "NAME", "Made", "out"]


#: What a new plane is called until it is renamed.
NAME = "Untitled"


class Made(nu.Shape):
    """The cell's state: the id of the plane it made."""

    plane = nustd.kv.StrRef.slot()


LINK = nustd.ui.PageLinkRef("plane")


def _make(held: nu.Ref) -> nu.Nu:
    """An empty plane under the cell's own, its id into ``held``. Brackets itself."""
    return nu.let(
        nu.Str(Here.plane),
        lambda parent: nuspace.specs.add_plane(
            EMPTY_PLANE, parent=nu.Str(parent), name=NAME, into=held
        ),
    )


def _shown(plane: nu.Nu) -> nu.Nu:
    """The link to ``plane``, drawn again whenever its row changes."""
    pid = nu.Str(plane)
    draw = nuspace.web.link(LINK, pid)
    return nuspace.bracketed(draw >> nu.ReactEvery(nuspace.plane.on_change(pid), draw))


def out() -> nu.Nu:
    """Make the plane on the first run, then show the link to it for as long as the cell runs."""
    held = nuspace.here(Made).plane
    first = nu.let(
        nuspace.atomic(held.fallback("")), lambda made: nu.IfDo(nu.Str(made) == "", _make(held))
    )
    return first >> nu.let(nuspace.atomic(held), _shown)


CELL = CellSpec(
    "plane",
    "Plane",
    source(__name__),
    description="A new plane under this one, and a link to it here.",
    group="Planes",
    icon="file-plus",
)
