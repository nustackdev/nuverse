"""An items cell: every item of one kind in one scope, listed, opened, edited, added and removed.

Its Config says which: the kind, by name, from the kinds the space
registered, and the scope (:mod:`._editing`). Left as it is, it lists its
own cell's text items. Each item is a line drawn with its kind's
``render_hit``, with Open and Remove. Add makes one with ``Content.new`` and
opens it. The item open is drawn in full with ``render``, and below it a
field per plain field of the kind's Shape (text, number, on or off, date)
edits it. Which item is open is the cell's own state; the items are
everyone's.

What it draws is built for the kind when it runs (:class:`._editing.ForKind`),
so it uses the kind's own API: ``items``, ``at``, ``new``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.datetime.kv
import nustd.kv
import nustd.ui
from nuspace import Snippet, ops
from nustd.ui.core import SectionRef

from .. import source
from ._editing import (
    DEFAULT_KIND,
    ForKind,
    KindField,
    LevelField,
    Target,
    kind_of,
    kind_options,
    landed,
    pointed,
    where,
)


if TYPE_CHECKING:
    from nuspace.content import Content


__all__ = ["SNIPPET", "Open", "out"]


#: What the Config asks: the kind, then the scope.
FIELDS = ("kind", "level", "scope")


class Open(nuspace.CellState):
    """Which item the cell has open, by id. ``""`` or missing: none."""

    opened = nustd.kv.StrRef.slot()


class Which(nustd.ui.Column):
    """Config: whose items it lists."""

    kind = KindField.slot(label="Kind")
    level = LevelField.slot(label="Scope")
    scope = nustd.ui.InputRef.slot(label="Scope id", placeholder="This cell or plane")


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
    """The item open: drawn in full, then its fields."""

    title = nustd.ui.HeadingRef.slot(level=4)
    view = nustd.ui.Column.slot()
    form = nustd.ui.Column.slot(gap=2)


class Listing(nustd.ui.Column):
    head = Head.slot(gap=2)
    empty = nustd.ui.EmptyStateRef.slot()
    lines = nustd.ui.Column.slot(gap=1)
    opened = Opened.slot(gap=3)


class TextField(nustd.ui.Column):
    label = nustd.ui.TextRef.slot()
    input = nustd.ui.InputRef.slot()


class NumberField(nustd.ui.Column):
    label = nustd.ui.TextRef.slot()
    input = nustd.ui.NumberInputRef.slot()


class FlagField(nustd.ui.Column):
    label = nustd.ui.TextRef.slot()
    input = nustd.ui.SwitchRef.slot()


class DateField(nustd.ui.Column):
    label = nustd.ui.TextRef.slot()
    input = nustd.ui.DatePickerRef.slot()


def _field(name: str, ref: nu.Nu, under: nu.Nu) -> tuple[nu.Nu, list[nu.Nu]] | None:
    """One plain field of an item as an input under ``under``, both ways. None for any other field."""

    def section(cls: type[nustd.ui.Column]) -> nu.Nu:
        return SectionRef(name, section_cls=cls, parent_ref=under)

    if isinstance(ref, nustd.kv.BoolRef):
        box = section(FlagField)
        show, typed = box.input.set(ref.fallback(False)), ref.set(nu.ToBool(box.input))
        echo = box.input.set(ref)
    elif isinstance(ref, (nustd.kv.FloatRef, nustd.kv.IntRef)):
        box = section(NumberField)
        cast = nu.ToInt if isinstance(ref, nustd.kv.IntRef) else nu.ToFloat
        show, typed = box.input.set_value(ref.fallback(0)), ref.set(cast(box.input))
        echo = box.input.set_value(ref)
    elif isinstance(ref, nustd.kv.StrRef):
        box = section(TextField)
        show, typed = box.input.set(ref.fallback("")), ref.set(nu.ToStr(box.input))
        echo = box.input.set(nu.str(ref))
    elif isinstance(ref, nustd.datetime.kv.DateRef):
        box = section(DateField)
        day = nu.Str(box.input)
        iso = nu.Str(nu.If(ref.exists(), nu.ToStr(ref), ""))
        show, typed = box.input.set(iso), nu.IfDo(day == "", ref.erase(), ref.set(day))
        echo = box.input.set(iso)
    else:
        return None
    reactions = [
        nu.ReactForever(box.input.on_change(), typed),
        nu.ReactForever(ref.on_change(), echo),
    ]
    return box.label.set(name.replace("_", " ").capitalize()) >> show, reactions


def _form(kind: type[Content[Any]], item: nu.Shape, under: nu.Nu) -> nu.Nu:
    """An input per plain field of the kind's Shape, editing ``item``, for as long as it is open."""
    fields = [_field(name, getattr(item, name), under) for name in kind.schema()._slots]
    held = [f for f in fields if f is not None]
    if not held:
        return nu.Noop()
    shows = nu.Sequential(*(show for show, _ in held))
    return shows >> nu.ParallelAsync(*(r for _, reactions in held for r in reactions))


def _listing(kind: type[Content[Any]], level: str, scope_id: str) -> nu.Nu:
    """One scope's items of ``kind``: the lines, Add, and the item open, for as long as it is shown."""
    scope = (level, scope_id)
    items = kind.items(scope)
    ids = ops.snapshot(nu.list(items.keys()))
    opened = Listing.opened

    def line(found: nu.Nu) -> nu.Nu:
        return SectionRef(nu.Str("i_") + nu.str(found), section_cls=Line, parent_ref=Listing.lines)

    def hit(found: nu.Nu) -> nu.Nu:
        row = line(found)
        return row.hit.erase() >> landed(kind.render_hit(kind.at(scope, nu.Str(found))), row.hit)

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
        row, item_id = line(found), nu.Str(found)
        shut = nu.IfDo(Open.opened.fallback("") == item_id, Open.opened.set(""))
        return nu.ParallelAsync(
            nu.ReactForever(row.open.on_click(), Open.opened.set(item_id)),
            nu.ReactForever(row.remove.on_click(), items[item_id].erase() >> shut),
        )

    def listed(got: nu.Nu) -> nu.Nu:
        return drawn(got) >> nu.ForEachParAsync(nu.List(got), acts)

    def detail(at: nu.Nu) -> nu.Nu:
        item_id = nu.Str(at)
        item = kind.at(scope, item_id)
        view = opened.view.erase() >> landed(kind.render(item), opened.view)
        there = ops.snapshot(items.contains(item_id))
        shown = (
            opened.title.set(item_id)
            >> view
            >> nu.ParallelAsync(
                _form(kind, item, opened.form), nu.ReactForever(items.on_change(), view)
            )
        )
        return opened.erase() >> nu.IfDo((item_id != "").and_(there), shown)

    return nu.ParallelAsync(
        # Items made or removed: the lines again, each with its buttons.
        nu.ReactLatest(items.on_children_change(), nu.let(ids, listed), initial=True),
        # An item edited: its hit again, the lines kept.
        nu.ReactForever(items.on_change(), nu.let(ids, hits)),
        nu.ReactForever(Listing.head.add.on_click(), kind.new(scope, into=Open.opened)),
        nu.ReactLatest(
            Open.opened.on_change(),
            nu.let(ops.snapshot(Open.opened.fallback("")), detail),
            initial=True,
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

    return pointed(held, listed)


def out() -> nu.Nu:
    """The items and their Config, for as long as the cell runs."""
    which = View.config.which
    show, reactions = where(which, FIELDS, shown={"kind": DEFAULT_KIND})
    kinds = which.kind.input.set_options(ops.snapshot(kind_options()))
    held = ops.snapshot(Target.target.fallback({}))
    shown = nu.ReactLatest(Target.target.on_change(), nu.let(held, _shown), initial=True)
    return ops.bracketed(kinds >> show >> nu.ParallelAsync(shown, *reactions))


SNIPPET = Snippet(
    "items",
    "Items",
    source(__name__),
    description="Every item of one kind in one scope: open, edit, add and remove them.",
    group="Content",
    icon="list-checks",
)
