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

from .. import source
from ._editing import (
    DEFAULT_KIND,
    KIND,
    TARGET,
    ForKind,
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


class Picked(nustd.ui.Row):
    # Where the picked item's hit lands.
    hit = nustd.ui.ColumnRef.slot()
    unpick = nustd.ui.ButtonRef.slot(label="Clear", icon="x", variant="ghost", size="sm")


class Body(nustd.ui.Column):
    picked = Picked.slot(gap=2, align="center", grow={"hit": 1})
    none = nustd.ui.TextRef.slot(tone="muted")
    # Where the candidates built for the kind land.
    candidates = nustd.ui.ColumnRef.slot(gap=1)
    note = nustd.ui.TextRef.slot()
    config = nustd.ui.AccordionRef.slot(sections=[{"id": "which", "label": "Config"}])


class View(nu.Shape):
    """The cell's root: its :class:`Body`, the parts spaced apart."""

    body = Body.slot(gap=3)


#: The running cell's surface.
BODY = View.body


#: The body's parts in the order they draw, whichever is written first.
ORDER = nu.Sequential(
    *(BODY.insert(part) for part in ("picked", "none", "candidates", "note", "config"))
)

#: The kind select, in the Config's one section.
KINDS = BODY.config["which"].to(nustd.ui.FieldRef.slot(label="Kind")).control.to(KIND)


class About(nustd.ui.Column):
    """A candidate's item: its hit, and under it where it lives."""

    # Where the item's hit lands.
    hit = nustd.ui.ColumnRef.slot()
    # Its scope, then its content key.
    where = nustd.ui.LineRef.slot()


class Candidate(nustd.ui.Row):
    """One item that can be picked: the item, and Pick."""

    about = About.slot(gap=0)
    pick = nustd.ui.ButtonRef.slot(label="Pick", variant="ghost", size="sm")


class Candidates(nu.Shape):
    """What the candidates draw: every item of the kind, by position, or why there is none."""

    empty = nustd.ui.EmptyStateRef.slot()
    rows = nustd.ui.ColumnRef.slot(Candidate.slot(gap=2, align="center", grow={"about": 1}), gap=1)


def _drawn(address: nu.Nu, under: nu.Nu, *, catch: nu.Nu) -> nu.Nu:
    """The item at ``address`` drawn as a hit under ``under``; ``catch`` when it cannot be."""
    at = nu.Dict(address)
    scope = nu.List(at["scope"])
    drawn = drawing(at["kind"], scope[0], scope[1], at["key"], under, hit=True)
    return nu.TryCatch(drawn, catch=lambda _: catch)


def _candidates(kind: type[Content[Any]]) -> nu.Nu:
    """Every item of ``kind``, each with Pick, listed again whenever an item of the kind changes."""
    rows = Candidates.rows

    def drawn(entry: nu.Nu) -> nu.Nu:
        i, address = nu.List(entry)[0], nu.Dict(nu.List(nu.List(entry)[1])[0])
        row, scope = rows[nu.Int(i)], nu.List(address["scope"])
        about = row.about
        level = about.where[0].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))
        key = about.where[1].to(nustd.ui.TextRef.slot(mono=True, size="sm"))
        # The hit first: the row's parts draw in the order first written.
        return (
            _drawn(address, about.hit, catch=about.hit.erase())
            >> level.set(nu.str(scope[0]) + nu.Str(" ") + nu.str(scope[1]))
            >> key.set(nu.str(address["key"]))
            >> row.pick.init()
        )

    def acts(entry: nu.Nu) -> nu.Nu:
        i, address = nu.List(entry)[0], nu.List(nu.List(entry)[1])[0]
        return nu.ReactEvery(rows[nu.Int(i)].pick.on_click(), LINK.set(address))

    def listed(found: nu.Nu) -> nu.Nu:
        entries = nu.List(found).iter().enumerate().to_list()
        count = nu.List(found).len()
        none = Candidates.empty.set(
            label="Nothing to pick", description="No items of this kind yet."
        )
        # The rows rewritten in place, the ones past the last item dropped.
        draw = (
            nu.ForEachDo(entries, drawn)
            >> rows.truncate(count)
            >> nu.IfDo(count == 0, none, Candidates.empty.erase())
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
    built = nu.Eval(ForKind(kind_of(held), BODY.candidates, build=_candidates))

    def failed(err: nu.Nu) -> nu.Nu:
        return BODY.note.set(nu.Str("Cannot list this kind: ") + nu.str(err))

    return BODY.candidates.erase() >> BODY.note.erase() >> nu.TryCatch(built, catch=failed)


def _picked() -> nu.Nu:
    """The item picked, drawn as a hit, or a line saying none is."""
    address = nuspace.atomic(LINK.fallback({}))
    gone = BODY.picked.erase() >> BODY.none.set("The picked item cannot be drawn.")

    def show(at: nu.Nu) -> nu.Nu:
        held = nu.Dict(at).len() > 0
        drawn = (
            BODY.none.erase()
            >> _drawn(at, BODY.picked.hit, catch=gone)
            >> BODY.picked.unpick.init()
        )
        return BODY.picked.erase() >> nu.IfDo(held, drawn, BODY.none.set("Nothing picked."))

    return nu.let(address, show)


def out() -> nu.Nu:
    """The picked item, the candidates and the Config, for as long as the cell runs."""
    show, reactions = where({"kind": KINDS}, shown={"kind": DEFAULT_KIND})
    kinds = KINDS.set_options(kind_options())
    held = nuspace.atomic(TARGET.fallback({}))
    return nuspace.bracketed(
        ORDER
        >> kinds
        >> show
        >> nu.ParallelAsync(
            nu.ReactLatest(TARGET.on_change(), nu.let(held, _shown), initial=True),
            nu.ReactLatest(LINK.on_change(), _picked(), initial=True),
            nu.ReactEvery(BODY.picked.unpick.on_click(), LINK.erase()),
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
