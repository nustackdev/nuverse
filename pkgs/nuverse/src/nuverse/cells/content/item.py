"""An item cell: any one item, of any kind, drawn in full by its kind's ``render``.

Its Config says which: the kind, by name, from the installed kinds, the
scope (by id or key) and the item's content key (:mod:`._editing`). Left
as it is, it shows its own cell's ``value`` text item. It only shows: an
editor of the same item edits it, and every change of the item draws it
again.

What it draws is built for the kind when it runs (:class:`._editing.ForKind`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.ui
from nuspace.shapes.content import entries
from nuspace.specs import CellSpec

from .. import source
from ._editing import (
    DEFAULT_KIND,
    ITEM,
    TARGET,
    ForKind,
    KindField,
    LevelField,
    Scope,
    kind_of,
    kind_options,
    pointed,
    where,
)


if TYPE_CHECKING:
    from nuspace.shapes.content import Content


__all__ = ["CELL", "out"]


#: What the Config asks: the kind, then where the item is, the scope by id or key.
FIELDS = ("kind", "level", "scope", "by", "key")


class Which(nustd.ui.Column):
    """Config: which item it shows."""

    kind = KindField.slot(label="Kind")
    level = LevelField.slot(label="Scope")
    scope = Scope.slot(gap=3, align="end")
    key = nustd.ui.InputRef.slot(label="Item key", placeholder=ITEM)


class Config(nustd.ui.Accordion):
    which = Which.slot(gap=3)


class View(nustd.ui.Column):
    item = nustd.ui.Column.slot()
    note = nustd.ui.TextRef.slot()
    config = Config.slot(sections=[{"id": "which", "label": "Config"}])


def _drawn(kind: type[Content[Any]], level: str, scope_id: str, key: str) -> nu.Nu:
    """One item drawn by its kind's ``render``, and again whenever it changes, for as long as it is shown."""
    item = entries(kind, level, scope_id)[key]
    drawn = kind.render(item)
    # The item's own subtree: a write to any of its fields draws it again.
    return drawn >> nu.ReactEvery(item.on_change(), drawn)


def _shown(held: nu.Nu) -> nu.Nu:
    """The item a target names, drawn, or why it cannot be."""
    kind = kind_of(held)

    def draw(level: str, scope_id: nu.Str, key: nu.Str) -> nu.Nu:
        built = nu.Eval(ForKind(kind, View.item, level, scope_id, key, build=_drawn))

        def failed(err: nu.Nu) -> nu.Nu:
            return View.note.set(nu.Str("Cannot draw this item: ") + nu.str(err))

        return View.item.erase() >> View.note.erase() >> nu.TryCatch(built, catch=failed)

    def missing(why: nu.Str) -> nu.Nu:
        return View.item.erase() >> View.note.set(why)

    return pointed(held, draw, missing=missing)


def out() -> nu.Nu:
    """The item and its Config, for as long as the cell runs."""
    which = View.config.which
    show, reactions = where(which, FIELDS, shown={"kind": DEFAULT_KIND})
    kinds = which.kind.input.set_options(kind_options())
    held = nuspace.atomic(TARGET.fallback({}))
    shown = nu.ReactLatest(TARGET.on_change(), nu.let(held, _shown), initial=True)
    return nuspace.bracketed(kinds >> show >> nu.ParallelAsync(shown, *reactions))


CELL = CellSpec(
    "item",
    "Item",
    source(__name__),
    description="Any one item of any kind, drawn in full, picked under Config.",
    group="Content",
    icon="file-text",
)
