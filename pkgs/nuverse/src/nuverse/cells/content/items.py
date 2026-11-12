"""An items cell: every item of one kind in one scope, listed, opened, added and removed.

Its Config says which: the kind, by name, from the installed kinds, and
the scope, by id or key (:mod:`._editing`). Left as it is, it lists its
own cell's text items, in an Items card. Each item is a line drawn with its
kind's ``render_hit``, with Open and Remove, keyed by its content key. Add
makes one under a fresh, time ordered content key
(``nuspace.utils.MintId``) and opens it. The item open is drawn in full
with ``render``, in a card of its own. Editing is an editor cell's, pointed
at the item by its address. Which item is open is the cell's own state;
the items are everyone's.

What it draws is built for the kind when it runs (:class:`._editing.ForKind`),
so it reads the kind's items as a place holds them
(:func:`~nuspace.shapes.content.entries`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.shapes.content import entries
from nuspace.specs import CellSpec
from nuspace.utils import MintId

from .. import source
from ._editing import (
    DEFAULT_KIND,
    KIND,
    TARGET,
    ForKind,
    Scope,
    kind_of,
    kind_options,
    landed,
    pointed,
    scoped,
    where,
)


if TYPE_CHECKING:
    from nuspace.shapes.content import Content


__all__ = ["CELL", "OPENED", "Open", "out"]


class Open(nu.Shape):
    """Which item the cell has open, by content key. ``""`` or missing: none."""

    opened = nustd.kv.StrRef.slot()


#: The running cell's open item (:class:`Open`).
OPENED = nuspace.here(Open).opened


class Which(nustd.ui.Column):
    """Config: whose items it lists, the kind, then the scope by id or key."""

    kind = nustd.ui.FieldRef.slot(label="Kind")
    level = nustd.ui.FieldRef.slot(label="Scope")
    scope = Scope.slot(gap=3, align="end", grow={"value": 1})


class Body(nustd.ui.Column):
    # The Items card: the listing built for the kind lands in it.
    listing = nustd.ui.CardRef.slot(title="Items")
    note = nustd.ui.TextRef.slot()
    config = nustd.ui.AccordionRef.slot(sections=[{"id": "which", "label": "Config"}])


class View(nu.Shape):
    """The cell's root: its :class:`Body`, the parts spaced apart."""

    body = Body.slot(gap=3)


#: The running cell's surface.
BODY = View.body


#: The body's parts in the order they draw, whichever is written first.
ORDER = nu.Sequential(*(BODY.insert(part) for part in ("listing", "note", "config")))

#: The Config's one section.
WHICH = BODY.config["which"].to(Which.slot(gap=3))

#: The kind select, in the Config.
KINDS = WHICH.kind.control.to(KIND)


class Line(nustd.ui.Row):
    """One item: its hit, then what can be done with it."""

    # Where the item's hit lands.
    hit = nustd.ui.ColumnRef.slot()
    open = nustd.ui.ButtonRef.slot(label="Open", variant="ghost", size="sm")
    delete = nustd.ui.ButtonRef.slot(label="Remove", icon="trash-2", variant="ghost", size="sm")


class Listing(nu.Shape):
    """What the listing draws in the Items card: Add on its header, then the lines and the item open."""

    actions = nustd.ui.ButtonRef.slot(label="Add", icon="plus", variant="secondary", size="sm")
    empty = nustd.ui.EmptyStateRef.slot()
    # One line per item, keyed by its content key.
    lines = nustd.ui.ColumnRef.slot(Line.slot(gap=2, align="center", grow={"hit": 1}), gap=1)
    opened = nustd.ui.CardRef.slot(variant="outline")


def _listing(kind: type[Content[Any]], level: str, scope_id: str) -> nu.Nu:
    """One scope's items of ``kind``: the lines, Add, and the item open, for as long as it is shown."""
    items = entries(kind, level, scope_id)
    # A scope no item landed in yet has no mapping: it lists none.
    keys = nuspace.atomic(nu.list(nu.If(items.exists(), nu.list(items.keys()), [])))
    lines, opened = Listing.lines, Listing.opened

    def hit(found: nu.Nu) -> nu.Nu:
        key = nu.Str(found)
        line = lines[key]
        drawn = landed(kind.render_hit(items[key]), line.hit)
        return drawn >> line.open.init() >> line.delete.init()

    def hits(got: nu.Nu) -> nu.Nu:
        return nu.ForEachDo(nu.List(got), hit)

    def drawn(got: nu.Nu) -> nu.Nu:
        none = Listing.empty.set(label="No items yet", description="Add one.")
        # Lines of items gone dropped, new ones drawn, all in the order the keys sort.
        return (
            Listing.actions.init()
            >> lines.keep(got)
            >> hits(got)
            >> lines.set_order(got)
            >> nu.IfDo(nu.List(got).len() == 0, none, Listing.empty.erase())
        )

    def acts(found: nu.Nu) -> nu.Nu:
        key = nu.Str(found)
        line = lines[key]
        shut = nu.IfDo(OPENED.fallback("") == key, OPENED.set(""))
        return nu.ParallelAsync(
            nu.ReactEvery(line.open.on_click(), OPENED.set(key)),
            nu.ReactEvery(line.delete.on_click(), nuspace.atomic(items[key].erase() >> shut)),
        )

    def listed(got: nu.Nu) -> nu.Nu:
        return drawn(got) >> nu.ForEachParAsync(nu.List(got), acts)

    def detail(at: nu.Nu) -> nu.Nu:
        key = nu.Str(at)
        item = items[key]
        view = landed(kind.render(item), opened)
        there = nuspace.atomic(items.contains(key))
        shown = opened.set_title(key) >> view >> nu.ReactEvery(item.on_change(), view)
        return opened.erase() >> nu.IfDo((key != "").and_(there), shown)

    def add(minted: nu.Nu) -> nu.Nu:
        # Written empty, the item is there at once: listed before any of it is set.
        key = nu.Str(minted)
        return nuspace.atomic(items[key].set({}) >> OPENED.set(key))

    return nu.ParallelAsync(
        # Items made or removed: the lines kept in step, each with its buttons.
        nu.ReactLatest(items.on_children_change(), nu.let(keys, listed), initial=True),
        # An item edited: the hits again, the lines kept.
        nu.ReactEvery(items.on_change(), nu.let(keys, hits)),
        # A time ordered key: a scope's keys sort the way its items were added.
        nu.ReactEvery(Listing.actions.on_click(), nu.let(MintId("i"), add)),
        nu.ReactLatest(
            OPENED.on_change(), nu.let(nuspace.atomic(OPENED.fallback("")), detail), initial=True
        ),
    )


def _shown(held: nu.Nu) -> nu.Nu:
    """The listing for the kind and scope a target names, or why there is none."""
    kind = kind_of(held)

    def listed(level: str, scope_id: nu.Str, _: nu.Str) -> nu.Nu:
        built = nu.Eval(ForKind(kind, BODY.listing, level, scope_id, build=_listing))

        def failed(err: nu.Nu) -> nu.Nu:
            return BODY.note.set(nu.Str("Cannot list these items: ") + nu.str(err))

        return BODY.listing.erase() >> BODY.note.erase() >> nu.TryCatch(built, catch=failed)

    def missing(why: nu.Str) -> nu.Nu:
        return BODY.listing.erase() >> BODY.note.set(why)

    return pointed(held, listed, missing=missing)


def out() -> nu.Nu:
    """The items and their Config, for as long as the cell runs."""
    show, reactions = where(
        {"kind": KINDS, **scoped(WHICH.level, WHICH.scope)}, shown={"kind": DEFAULT_KIND}
    )
    kinds = KINDS.set_options(kind_options())
    held = nuspace.atomic(TARGET.fallback({}))
    shown = nu.ReactLatest(TARGET.on_change(), nu.let(held, _shown), initial=True)
    return nuspace.bracketed(ORDER >> kinds >> show >> nu.ParallelAsync(shown, *reactions))


CELL = CellSpec(
    "items",
    "Items",
    source(__name__),
    description="Every item of one kind in one scope: open, add and remove them.",
    group="Content",
    icon="list-checks",
)
