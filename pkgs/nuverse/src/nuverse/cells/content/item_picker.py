"""An item picker cell: picks one item of a kind and keeps its address, linking to it.

Its Config names the kind, by name, from the installed kinds
(:mod:`._editing`); left as it is, text. It lists every item of the kind,
from every scope, as ``Content.find`` walks them, each drawn with its kind's
``render_hit`` and a Pick button. The picked item's address,
``{"kind", "scope": [level, id], "key"}``
(:func:`nuspace.shapes.content.address`), is the cell's own state,
:data:`LINK`: a program follows the link with
``nuspace.specs.content_spec(kind).kind`` and
:func:`~nuspace.shapes.content.entries`. One item relates to another by
address, never by holding it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.shapes.content import kind_name
from nuspace.specs import CellSpec
from nustd.ui.core import SectionRef

from .. import source
from ._editing import (
    DEFAULT_KIND,
    TARGET,
    ForKind,
    KindField,
    drawing,
    kind_of,
    kind_options,
    where,
)


if TYPE_CHECKING:
    from nuspace.shapes.content import Content


__all__ = ["CELL", "LINK", "Link", "out"]


class Link(nu.Shape):
    """The item picked: its address, plain data. Missing until one is picked."""

    address = nustd.kv.PrimitiveDictRef.slot()


#: The running cell's picked address (:class:`Link`).
LINK = nuspace.here(Link).address


class Which(nustd.ui.Column):
    """Config: which kind it picks from."""

    kind = KindField.slot(label="Kind")


class Config(nustd.ui.Accordion):
    which = Which.slot(gap=3)


class Picked(nustd.ui.Row):
    hit = nustd.ui.Column.slot()
    unpick = nustd.ui.ButtonRef.slot(label="Clear", icon="x", variant="ghost")


class View(nustd.ui.Column):
    picked = Picked.slot(gap=2, align="center")
    none = nustd.ui.TextRef.slot()
    # Where the candidates built for the kind land.
    candidates = nustd.ui.Column.slot(gap=1)
    note = nustd.ui.TextRef.slot()
    config = Config.slot(sections=[{"id": "which", "label": "Config"}])


class Candidate(nustd.ui.Row):
    """One item that can be picked: its hit, where it lives, and Pick."""

    hit = nustd.ui.Column.slot()
    where = nustd.ui.TextRef.slot()
    pick = nustd.ui.ButtonRef.slot(label="Pick", variant="ghost")


class Candidates(nustd.ui.Column):
    empty = nustd.ui.EmptyStateRef.slot()
    rows = nustd.ui.Column.slot(gap=1)


def _drawn(address: nu.Nu, under: nu.Nu, *, catch: nu.Nu) -> nu.Nu:
    """The item at ``address`` drawn as a hit under ``under``; ``catch`` when it cannot be."""
    at = nu.Dict(address)
    scope = nu.List(at["scope"])
    drawn = drawing(at["kind"], scope[0], scope[1], at["key"], under, hit=True)
    return nu.TryCatch(drawn, catch=lambda _: catch)


def _candidates(kind: type[Content[Any]]) -> nu.Nu:
    """Every item of ``kind``, each with Pick, listed again whenever an item of the kind changes."""

    def row(i: nu.Nu) -> nu.Nu:
        return SectionRef(
            nu.Str("c") + nu.str(i), section_cls=Candidate, parent_ref=Candidates.rows
        )

    def drawn(entry: nu.Nu) -> nu.Nu:
        i, address = nu.List(entry)[0], nu.Dict(nu.List(nu.List(entry)[1])[0])
        scope = nu.List(address["scope"])
        where = (
            nu.str(scope[0])
            + nu.Str(" ")
            + nu.str(scope[1])
            + nu.Str(" · ")
            + nu.str(address["key"])
        )
        unknown = row(i).hit.erase()
        return row(i).where.set(where) >> _drawn(address, row(i).hit, catch=unknown)

    def acts(entry: nu.Nu) -> nu.Nu:
        i, address = nu.List(entry)[0], nu.List(nu.List(entry)[1])[0]
        return nu.ReactEvery(row(i).pick.on_click(), LINK.set(address))

    def listed(found: nu.Nu) -> nu.Nu:
        entries = nu.List(found).iter().enumerate().to_list()
        none = Candidates.empty.set(
            label="Nothing to pick", description="No items of this kind yet."
        )
        draw = (
            Candidates.rows.erase()
            >> Candidates.empty.erase()
            >> nu.ForEachDo(entries, drawn)
            >> nu.IfDo(nu.List(found).len() == 0, none)
        )
        return draw >> nu.ForEachParAsync(entries, acts)

    # Any item of the kind, at any scope: its three subtrees.
    name = kind_name(kind)
    changed = nu.OnAny(
        nuspace.State.content_cells[name].on_change(),
        nuspace.State.content_planes[name].on_change(),
        nuspace.State.content_space[name].on_change(),
    )
    return nu.ReactLatest(changed, nu.let(nuspace.atomic(kind.find()), listed), initial=True)


def _shown(held: nu.Nu) -> nu.Nu:
    """The candidates of the kind a target names, or why there are none."""
    built = nu.Eval(ForKind(kind_of(held), View.candidates, build=_candidates))

    def failed(err: nu.Nu) -> nu.Nu:
        return View.note.set(nu.Str("Cannot list this kind: ") + nu.str(err))

    return View.candidates.erase() >> View.note.erase() >> nu.TryCatch(built, catch=failed)


def _picked() -> nu.Nu:
    """The item picked, drawn as a hit, or a line saying none is."""
    address = nuspace.atomic(LINK.fallback({}))
    gone = View.picked.hit.erase() >> View.none.set("The picked item cannot be drawn.")

    def show(at: nu.Nu) -> nu.Nu:
        held = nu.Dict(at).len() > 0
        drawn = View.none.erase() >> _drawn(at, View.picked.hit, catch=gone)
        return View.picked.hit.erase() >> nu.IfDo(held, drawn, View.none.set("Nothing picked."))

    return nu.let(address, show)


def out() -> nu.Nu:
    """The picked item, the candidates and the Config, for as long as the cell runs."""
    which = View.config.which
    show, reactions = where(which, ("kind",), shown={"kind": DEFAULT_KIND})
    kinds = which.kind.input.set_options(kind_options())
    held = nuspace.atomic(TARGET.fallback({}))
    return nuspace.bracketed(
        kinds
        >> show
        >> nu.ParallelAsync(
            nu.ReactLatest(TARGET.on_change(), nu.let(held, _shown), initial=True),
            nu.ReactLatest(LINK.on_change(), _picked(), initial=True),
            nu.ReactEvery(View.picked.unpick.on_click(), LINK.erase()),
            *reactions,
        )
    )


CELL = CellSpec(
    "item_picker",
    "Item picker",
    source(__name__),
    description="Picks an item of any kind and keeps its address, linking this cell to it.",
    group="Content",
    icon="link",
)
