"""What a lens's dropdown lists: a plane's cells, or the planes holding content, as select options.

Each list is bounded: one page of a plane's cells (:data:`MAX_CELLS`), or
one page per content kind of the planes holding its items (:data:`MAX_PLANES`). Nothing here walks every plane or cell of the
space. All are bare reads: their caller brackets them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
from nuspace.specs import content_specs


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = [
    "MAX_CELLS",
    "MAX_PLANES",
    "Unique",
    "cell_options",
    "cell_page",
    "content_planes",
    "option",
    "plane_options",
]


#: How many of a plane's cells one dropdown lists, its first ones in order.
MAX_CELLS = 200

#: How many planes holding a kind's items one dropdown lists, per kind.
MAX_PLANES = 200


def option(id: nu.Nu, name: nu.Nu) -> nu.Dict:
    """A cell or plane as a select option: ``{value: id, label}``, labelled by name, or by id when unnamed."""
    return nu.Dict.of(value=id, label=nu.If(name != "", name, id))


def cell_page(plane: nu.StrArg) -> nu.List:
    """``plane``'s first :data:`MAX_CELLS` cell ids, in order, ``[]`` for no plane. One paged read."""
    cells = nuspace.Space.planes[plane].cells
    return nu.list(nu.If(cells.exists(), nu.list(cells.keys(limit=MAX_CELLS)), []))


def cell_options(plane: nu.StrArg) -> nu.List:
    """``plane``'s first :data:`MAX_CELLS` cells in order, as options. One page, one read per cell listed."""
    listed = cell_page(plane)

    def one(at: nu.Nu) -> nu.Nu:
        cell = nu.Str(at)
        return option(cell, nuspace.Space.cells[cell].name.fallback(""))

    return listed.iter().map(one).to_list()


def _unique(first: object, pages: Sequence[Sequence[object]]) -> list[object]:
    seen: dict[object, None] = {first: None}
    for page in pages:
        seen.update(dict.fromkeys(page))
    return list(seen)


#: ``first``, then every id of ``pages`` not listed yet, in order.
Unique = nu.host(_unique, name="LensUnique")


def content_planes() -> list[nu.Nu]:
    """One page per installed kind of the planes holding its items, ``[]`` for a kind with none: ``State.content_planes[kind].planes``."""

    def page(planes: nu.Ref) -> nu.List:
        return nu.list(nu.If(planes.exists(), nu.list(planes.keys(limit=MAX_PLANES)), []))

    held = nuspace.State.content_planes
    return [page(held[name].planes) for name in content_specs()]


def plane_options(first: nu.StrArg) -> nu.List:
    """``first``, then the planes holding content items, as options. One page per kind, one read per plane."""
    ids = nu.List(Unique(first, nu.List.of(*content_planes())))

    def one(at: nu.Nu) -> nu.Nu:
        plane = nu.Str(at)
        return option(plane, nuspace.Space.planes[plane].name.fallback(""))

    return ids.iter().map(one).to_list()
