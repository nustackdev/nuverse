"""A plane content lens: one plane's own items, as kind, then content key, then the item (:mod:`._content_lens`).

It starts on the plane its cell sits on. A dropdown picks another: the
planes holding content items, a page per kind (never every plane of the
space), listed again as a plane first gets an item of a kind.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace.places import Here
from nuspace.shapes.content import PLANE
from nuspace.specs import CellSpec, content_specs

from .. import source
from ._content_lens import picked
from ._options import plane_options


__all__ = ["CELL", "out"]


def out() -> nu.Nu:
    """The dropdown and the picked plane's items as columns, for as long as the cell runs."""
    held = nuspace.State.content_planes
    moved = nu.OnAny(*(held[name].planes.on_children_change() for name in content_specs()))
    return picked(PLANE, plane_options(Here.plane), Here.plane, moved)


CELL = CellSpec(
    "plane_content_lens",
    "Plane content lens",
    source(__name__),
    description="Browses one plane's own content items by kind, raw and rendered. This plane first.",
    group="Debugging",
    icon="folder-open",
)
