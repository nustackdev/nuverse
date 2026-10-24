"""An item cell: any one item, of any kind, drawn in full by its kind's ``render``.

Its Config says which: the kind, by name, from the kinds the space
registered, the scope and the item's id (:mod:`._editing`). Left as it is,
it shows its own cell's ``value`` text item. It only shows: an editor of the
same item edits it, and every change of the kind draws it again.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.ui
from nuspace import Cell, ops
from nuspace.content import Drawing

from .. import source
from ._editing import (
    DEFAULT_KIND,
    ITEM,
    KindField,
    LevelField,
    Target,
    kind_of,
    kind_options,
    pointed,
    where,
)


__all__ = ["CELL", "out"]


#: What the Config asks: the kind, then where the item is.
FIELDS = ("kind", "level", "scope", "id")


class Which(nustd.ui.Column):
    """Config: which item it shows."""

    kind = KindField.slot(label="Kind")
    level = LevelField.slot(label="Scope")
    scope = nustd.ui.InputRef.slot(label="Scope id", placeholder="This cell or plane")
    id = nustd.ui.InputRef.slot(label="Item id", placeholder=ITEM)


class Config(nustd.ui.Accordion):
    which = Which.slot(gap=3)


class View(nustd.ui.Column):
    item = nustd.ui.Column.slot()
    note = nustd.ui.TextRef.slot()
    config = Config.slot(sections=[{"id": "which", "label": "Config"}])


def _shown(held: nu.Nu) -> nu.Nu:
    """The item a target names, drawn, and drawn again whenever an item of its kind changes."""
    kind = kind_of(held)

    def draw(level: str, scope_id: nu.Str, item_id: nu.Str) -> nu.Nu:
        drawing = ops.snapshot(nu.Eval(Drawing(kind, level, scope_id, item_id, View.item)))

        def failed(err: nu.Nu) -> nu.Nu:
            return View.note.set(nu.Str("Cannot draw this item: ") + nu.str(err))

        once = View.item.erase() >> View.note.erase() >> nu.TryCatch(drawing, catch=failed)
        return once >> nu.ReactForever(nuspace.States.contents[kind].on_change(), once)

    return pointed(held, draw)


def out() -> nu.Nu:
    """The item and its Config, for as long as the cell runs."""
    which = View.config.which
    show, reactions = where(which, FIELDS, shown={"kind": DEFAULT_KIND})
    kinds = which.kind.input.set_options(ops.snapshot(kind_options()))
    held = ops.snapshot(Target.target.fallback({}))
    shown = nu.ReactLatest(Target.target.on_change(), nu.let(held, _shown), initial=True)
    return ops.bracketed(kinds >> show >> nu.ParallelAsync(shown, *reactions))


CELL = Cell(
    "item",
    "Item",
    source(__name__),
    description="Any one item of any kind, drawn in full, picked under Config.",
    group="Content",
    icon="file-text",
)
