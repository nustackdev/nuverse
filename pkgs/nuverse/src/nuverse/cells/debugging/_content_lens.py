"""What the content lenses share: one scope's items, browsed as kind, then item id, then the item.

A content lens (:mod:`.space_content_lens`, :mod:`.plane_content_lens`,
:mod:`.cell_content_lens`) shows the items of one scope as cascading
columns. The first column is every kind holding items in the scope, found
by walking the kinds present in ``States.contents`` and keeping those whose
``Kind.items(scope)`` is not empty. The second is the picked kind's item
ids. From the third on, the picked item raw, its stored fields browsed as
any lens browses storage. Below the columns, the same item drawn with its
kind's ``render``.

Read only. It repaints on any write to the contents, so what is shown is
what is stored.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nustd.kv
import nustd.ui
import nustd.ui.lens
from nu.lang import Cardinality
from nuspace import States, ops
from nuspace.content import Drawing
from nuspace.ext import content_spec
from nustd.ui.lens.columns import LensFailed


if TYPE_CHECKING:
    from collections.abc import Sequence

    from nuspace.content import Content
    from nuspace.ext import ContentSpec


__all__ = ["ContentColumns", "Item", "View", "browse", "content_columns", "option", "picked"]


#: Where a lens arm parks the cursor the browser sent. One lens per cell.
NAV = "_content_lens_nav"

#: How long a burst of writes is waited out before the lens repaints once.
REPAINT_DELAY = 0.25

#: How many rows one column ships.
MAX_ROWS = nustd.ui.lens.DEFAULT_MAX_ROWS


class Item(nustd.ui.Column):
    """The item at the cursor, drawn with its kind's ``render``."""

    heading = nustd.ui.HeadingRef.slot(level=4)
    drawn = nustd.ui.Column.slot()
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    """A content lens: the scope picked, its items as columns, the item at the cursor drawn."""

    pick = nustd.ui.SelectRef.slot(searchable=True)
    lens = nustd.ui.lens.LensRef.slot(max_rows=MAX_ROWS)
    item = Item.slot(gap=2)


def _specs(names: Sequence[object]) -> dict[str, ContentSpec]:
    """The installed specs of the kinds named in the store, by name, sorted. One not installed is left out."""
    found = {}
    for name in sorted(str(n) for n in names):
        try:
            found[name] = content_spec(name)
        except LookupError:
            continue
    return found


def _column(kind: str, rows: nu.Nu, max_rows: int) -> nu.Nu:
    """One column of ``rows``, capped at ``max_rows``, its total beside them."""
    return nu.let(
        rows,
        lambda held: nu.Dict.of(
            kind=nu.Str(kind),
            entries=nu.GetItem(held, nu.Slice(None, max_rows, None)),
            total=nu.Len(held),
        ),
    )


def _door(key: nu.Nu, kind: str, preview: str = "") -> nu.Nu:
    """A row that is a way in: a kind, or an item."""
    return nu.Dict.of(key=key, kind=kind, preview=preview, navigable=True, vtype="")


def _kinds_column(specs: dict[str, ContentSpec], scope: tuple[str, str], max_rows: int) -> nu.Nu:
    """The kinds holding items in ``scope``, one row each, its spec's label as preview."""

    def held(name: str, spec: ContentSpec) -> nu.Nu:
        count = nu.Len(nu.list(spec.kind.items(scope).keys()))
        return nu.List.of(count, _door(nu.Str(name), "mapping", spec.label))

    pairs = nu.List.of(*(held(name, spec) for name, spec in specs.items()))
    rows = (
        pairs.iter()
        .filter(lambda pair: nu.Int(nu.GetItem(pair, nu.Int(0))) > 0)
        .map(lambda pair: nu.GetItem(pair, nu.Int(1)))
        .to_list()
    )
    return _column("mapping", rows, max_rows)


def _ids_column(kind: type[Content[Any]], scope: tuple[str, str], max_rows: int) -> nu.Nu:
    """The ids of ``kind``'s items in ``scope``, one row each."""
    ids = nu.list(kind.items(scope).keys())
    return _column(
        "mapping", ids.iter().map(lambda at: _door(nu.ToStr(at), "shape")).to_list(), max_rows
    )


def content_columns(
    names: Sequence[object],
    level: str,
    scope_id: str,
    cursor: Sequence[object] | None,
    max_rows: int = MAX_ROWS,
) -> nu.Nu:
    """Every column for ``cursor``: kinds, then item ids, then the item raw, root first.

    Built in python once the cursor and the kinds are known, so a kind can
    be reached by its own API (``items``, ``at``, ``schema``). The item's
    columns are a lens's own (:func:`nustd.ui.lens.column_terms`), its
    fields read where the item lives.

    Args:
        names: The kind names present in ``States.contents``.
        level: The scope's level.
        scope_id: The scope's id, ``""`` for the space.
        cursor: The browser's cursor: a kind name, an item id, then a path in the item.
        max_rows: How many rows one column ships.
    """
    scope = (level, str(scope_id))
    specs = _specs(names)
    steps = tuple(str(s) for s in (cursor or ()))
    cols = [_kinds_column(specs, scope, max_rows)]
    if steps:
        spec = specs.get(steps[0])
        if spec is None:
            cols.append(LensFailed(f"{steps[0]}: no content kind of that name"))
        else:
            cols.append(_ids_column(spec.kind, scope, max_rows))
    head = nu.List.of(*cols)
    if len(steps) < 2 or steps[0] not in specs:
        return head
    kind = specs[steps[0]].kind
    item = nustd.ui.lens.column_terms(
        kind.schema(), steps[2:], prefix=kind.at(scope, steps[1]), max_rows=max_rows
    )
    return nu.List.of(head, item).iter().flatten().to_list()


#: :func:`content_columns` as an atom, so the kinds, the scope and the cursor can be run time values.
ContentColumns = nu.host(content_columns, name="ContentColumns")


def browse(level: str, scope_id: nu.StrArg) -> nu.Nu:
    """One scope's items as columns, and the item at the cursor drawn, for as long as it is shown.

    Never finishes: it repaints on every move of the cursor and, a burst
    waited out, on every write to the contents.

    Args:
        level: The scope's level, one of ``nuspace.content.LEVELS``.
        scope_id: The scope's id, ``""`` for the space.
    """
    lens, item = View.lens, View.item

    def columns(steps: nu.Nu) -> nu.Nu:
        built = ContentColumns(nu.list(States.contents.keys()), level, scope_id, steps)
        return nu.TryCatch(
            nu.Eval(built, promise={"cardinality": Cardinality.SCALAR}),
            catch=lambda error: nu.List.of(LensFailed(nu.ToStr(error))),
        )

    def drawn(steps: nu.Nu) -> nu.Nu:
        kind, item_id = nu.Str(nu.GetItem(steps, nu.Int(0))), nu.Str(nu.GetItem(steps, nu.Int(1)))
        drawing = nu.Eval(Drawing(kind, level, scope_id, item_id, item.drawn))

        def failed(error: nu.Nu) -> nu.Nu:
            return item.note.set(nu.Str("Cannot draw this item: ") + nu.str(error))

        return item.heading.set(nu.Str("Rendered ") + item_id) >> nu.TryCatch(drawing, catch=failed)

    def paint(cursor: nu.Nu) -> nu.Nu:
        steps = nu.list(cursor)
        shown = lens.set_columns(steps, columns(steps))
        return ops.snapshot(shown >> item.erase() >> nu.IfDo(steps.len() >= 2, drawn(steps)))

    def live(cursor: nu.Nu, pending: nu.Nu) -> nu.Nu:
        moved = nu.ReactForever(
            lens.on_nav(), cursor.set(nu.Attr(NAV)) >> paint(cursor), changed_key=NAV
        )
        written = nu.ReactForever(
            nustd.kv.Snapshot(States.contents.on_change(), scope=States),
            nu.Debounce(REPAINT_DELAY, paint(cursor), pending=pending),
        )
        return paint(cursor) >> nu.ParallelAsync(moved, written)

    return nu.let(nu.List.of(), lambda cursor: nu.let(None, lambda pending: live(cursor, pending)))


def picked(
    level: str,
    options: nu.Nu,
    first: nu.StrArg,
    moved: nu.Nu,
) -> nu.Nu:
    """A dropdown of scopes at ``level`` and :func:`browse` on the one picked, for as long as it runs.

    Picking one restarts the lens on it, its cursor at the root.

    Args:
        level: The scopes' level.
        options: The scopes as select options, ``{value: id, label}``. A bare read.
        first: The scope picked first.
        moved: An event: scopes added or removed, so they are listed again. A bare subscription.
    """
    pick = View.pick
    listed = pick.set_options(ops.snapshot(options))
    lens_on_pick = nu.ReactLatest(
        pick.on_change(), nu.let(nu.Str(pick), lambda at: browse(level, nu.Str(at))), initial=True
    )
    relisted = nu.ReactForever(ops.snapshot(moved), listed)
    return listed >> pick.set(first) >> nu.ParallelAsync(lens_on_pick, relisted)


def option(row: nu.Nu) -> nu.Nu:
    """A cell or plane row (``ops.cell_rows``, ``ops.plane_rows``) as a select option, labelled by name or id."""
    label = nu.If(row["name"] != "", row["name"], row["id"])
    return nu.Dict.of(value=row["id"], label=label)
