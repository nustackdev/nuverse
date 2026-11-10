"""An items cell: every item of one kind in one scope, listed, opened, added and removed.

Its Config says which: the kind, by name, from the installed kinds, and
the scope, by id or key (:mod:`._editing`). Left as it is, it lists its own cell's text
items. Each item is a line drawn with its kind's ``render_hit``, with Open
and Remove. Add makes one under a fresh, time ordered content key
(``nuspace.utils.MintId``) and opens it. The item open is drawn in full with ``render``. Editing is an
editor cell's, pointed at the item by its address. Which item is open is
the cell's own state; the items are everyone's.

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
from nustd.ui.core import SectionRef

from .. import source
from ._editing import (
    DEFAULT_KIND,
    TARGET,
    ForKind,
    KindField,
    LevelField,
    Scope,
    kind_of,
    kind_options,
    landed,
    pointed,
    where,
)


if TYPE_CHECKING:
    from nuspace.shapes.content import Content


__all__ = ["CELL", "OPENED", "Open", "out"]


#: What the Config asks: the kind, then the scope, by id or key.
FIELDS = ("kind", "level", "scope", "by")


class Open(nu.Shape):
    """Which item the cell has open, by content key. ``""`` or missing: none."""

    opened = nustd.kv.StrRef.slot()


#: The running cell's open item (:class:`Open`).
OPENED = nuspace.here(Open).opened


class Which(nustd.ui.Column):
    """Config: whose items it lists."""

    kind = KindField.slot(label="Kind")
    level = LevelField.slot(label="Scope")
    scope = Scope.slot(gap=3, align="end")


class Config(nustd.ui.Accordion):
    which = Which.slot(gap=3)


class View(nustd.ui.Column):
    # Where the listing built for the kind lands.
    listing = nustd.ui.Column.slot(gap=3)
    note = nustd.ui.TextRef.slot()
    config = Config.slot(sections=[{"id": "which", "label": "Config"}])


class Head(nustd.ui.Row):
    add = nustd.ui.ButtonRef.slot(label="Add", icon="plus", variant="secondary")


class Line(nustd.ui.Row):
    """One item: its hit, then what can be done with it."""

    hit = nustd.ui.Column.slot()
    open = nustd.ui.ButtonRef.slot(label="Open", variant="ghost")
    remove = nustd.ui.ButtonRef.slot(label="Remove", icon="trash-2", variant="ghost")


class Opened(nustd.ui.Column):
    """The item open, drawn in full."""

    title = nustd.ui.HeadingRef.slot(level=4)
    view = nustd.ui.Column.slot()


class Listing(nustd.ui.Column):
    head = Head.slot(gap=2)
    empty = nustd.ui.EmptyStateRef.slot()
    lines = nustd.ui.Column.slot(gap=1)
    opened = Opened.slot(gap=3)


def _listing(kind: type[Content[Any]], level: str, scope_id: str) -> nu.Nu:
    """One scope's items of ``kind``: the lines, Add, and the item open, for as long as it is shown."""
    items = entries(kind, level, scope_id)
    # A scope no item landed in yet has no mapping: it lists none.
    keys = nuspace.atomic(nu.list(nu.If(items.exists(), nu.list(items.keys()), [])))
    opened = Listing.opened

    def line(found: nu.Nu) -> nu.Nu:
        return SectionRef(nu.Str("i_") + nu.str(found), section_cls=Line, parent_ref=Listing.lines)

    def hit(found: nu.Nu) -> nu.Nu:
        row = line(found)
        return row.hit.erase() >> landed(kind.render_hit(items[nu.Str(found)]), row.hit)

    def hits(got: nu.Nu) -> nu.Nu:
        return nu.ForEachDo(nu.List(got), hit)

    def drawn(got: nu.Nu) -> nu.Nu:
        none = Listing.empty.set(label="No items yet", description="Add one.")
        return (
            Listing.lines.erase()
            >> Listing.empty.erase()
            >> hits(got)
            >> nu.IfDo(nu.List(got).len() == 0, none)
        )

    def acts(found: nu.Nu) -> nu.Nu:
        row, key = line(found), nu.Str(found)
        shut = nu.IfDo(OPENED.fallback("") == key, OPENED.set(""))
        return nu.ParallelAsync(
            nu.ReactEvery(row.open.on_click(), OPENED.set(key)),
            nu.ReactEvery(row.remove.on_click(), nuspace.atomic(items[key].erase() >> shut)),
        )

    def listed(got: nu.Nu) -> nu.Nu:
        return drawn(got) >> nu.ForEachParAsync(nu.List(got), acts)

    def detail(at: nu.Nu) -> nu.Nu:
        key = nu.Str(at)
        item = items[key]
        view = opened.view.erase() >> landed(kind.render(item), opened.view)
        there = nuspace.atomic(items.contains(key))
        shown = opened.title.set(key) >> view >> nu.ReactEvery(item.on_change(), view)
        return opened.erase() >> nu.IfDo((key != "").and_(there), shown)

    def add(minted: nu.Nu) -> nu.Nu:
        # Written empty, the item is there at once: listed before any field is set.
        key = nu.Str(minted)
        return nuspace.atomic(items[key].set({}) >> OPENED.set(key))

    return nu.ParallelAsync(
        # Items made or removed: the lines again, each with its buttons.
        nu.ReactLatest(items.on_children_change(), nu.let(keys, listed), initial=True),
        # An item edited: its hit again, the lines kept.
        nu.ReactEvery(items.on_change(), nu.let(keys, hits)),
        # A time ordered key: a scope's keys sort the way its items were added.
        nu.ReactEvery(Listing.head.add.on_click(), nu.let(MintId("i"), add)),
        nu.ReactLatest(
            OPENED.on_change(), nu.let(nuspace.atomic(OPENED.fallback("")), detail), initial=True
        ),
    )


def _shown(held: nu.Nu) -> nu.Nu:
    """The listing for the kind and scope a target names, or why there is none."""
    kind = kind_of(held)

    def listed(level: str, scope_id: nu.Str, _: nu.Str) -> nu.Nu:
        built = nu.Eval(ForKind(kind, View.listing, level, scope_id, build=_listing))

        def failed(err: nu.Nu) -> nu.Nu:
            return View.note.set(nu.Str("Cannot list these items: ") + nu.str(err))

        return View.listing.erase() >> View.note.erase() >> nu.TryCatch(built, catch=failed)

    def missing(why: nu.Str) -> nu.Nu:
        return View.listing.erase() >> View.note.set(why)

    return pointed(held, listed, missing=missing)


def out() -> nu.Nu:
    """The items and their Config, for as long as the cell runs."""
    which = View.config.which
    show, reactions = where(which, FIELDS, shown={"kind": DEFAULT_KIND})
    kinds = which.kind.input.set_options(kind_options())
    held = nuspace.atomic(TARGET.fallback({}))
    shown = nu.ReactLatest(TARGET.on_change(), nu.let(held, _shown), initial=True)
    return nuspace.bracketed(kinds >> show >> nu.ParallelAsync(shown, *reactions))


CELL = CellSpec(
    "items",
    "Items",
    source(__name__),
    description="Every item of one kind in one scope: open, add and remove them.",
    group="Content",
    icon="list-checks",
)
