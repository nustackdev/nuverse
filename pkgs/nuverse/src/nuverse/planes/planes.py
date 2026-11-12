"""The ``planes`` Plane: the space's planes by spec, and the planes at its top, live.

Two cells, each drawn again when what it shows changed. Neither lists the
whole space: a space may hold any number of planes, so each reads an index
or one level of the tree, a page at a time.

- ``by_spec``: one row per spec planes were made from, off
  ``Space.indexes.spec_planes``: how many, and the newest.
- ``planes``: the planes right under root, the first :data:`PAGE`, with
  their spec, whether they are system planes, and how many cells and planes
  each holds. Drawn whole when root's children change; a shown plane's row
  alone when that plane's own row changes, so its wakes follow what it
  shows, not the whole space.

A count reads at most :data:`PAGE` ids and says ``100+`` past that. The
cells are shims (:func:`~nuverse.planes.shim`): :func:`by_spec` and
:func:`listing` here are their code.
"""

from __future__ import annotations

import nu
import nuspace
import nuspace.web as web
import nustd.ui
from nuspace.shapes import ROOT
from nuspace.specs import PlaneSpec, WebOptions
from nuverse.planes import shim
from nuverse.planes.runs import count_column, id_column, ids


__all__ = [
    "BY_SPEC",
    "PAGE",
    "PLANE",
    "SPEC_TABLE",
    "TABLE",
    "TABLE_REF",
    "BySpec",
    "Listing",
    "by_spec",
    "draw_by_spec",
    "draw_listing",
    "listing",
    "row",
]


#: The most ids one read takes: rows in a table, ids behind a count.
PAGE = 100

SPECS = nuspace.Space.indexes.spec_planes

LINK = nustd.ui.PageLinkRef.slot(variant="inline")


# --- by spec -----------------------------------------------------------------------------


class BySpec(nu.Shape):
    """The ``by_spec`` cell's root: a titled Card holding the table."""

    specs = nustd.ui.CardRef.slot(title="By spec", subtitle="How many planes each spec made")


SPEC_TABLE = BySpec.specs[0].to(
    nustd.ui.DataTableRef.slot(
        columns=[
            {"key": "spec", "label": "Spec", "sortable": False},
            count_column("planes", "Planes"),
            {"key": "newest", "label": "Newest", "cell": LINK, "sortable": False},
        ],
        row_key="spec",
        label="Planes by spec",
    )
)


def _spec_row(at: nu.ObjectRef) -> nu.Dict:
    spec = nu.Str(at)
    # Newest first, one page: the planes still in the space, removed ones skipped.
    newest = nu.List(SPECS[spec].ids.reversed_keys(limit=PAGE + 1))
    there = newest.iter().filter(lambda p: nuspace.plane.exists(nu.Str(p))).to_list()
    # A capped count is a label, not a number.
    count = nu.If(newest.len() > PAGE, nu.str(PAGE) + "+", nu.str(there.len()))
    last = nu.If(there.len() > 0, web.page(nu.Str(there[0])), "")
    return nu.Dict.of(spec=spec, planes=count, newest=last)


def draw_by_spec() -> nu.Nu:
    """Read the specs once and draw the table."""
    rows = ids(SPECS).iter().map(_spec_row).to_list()
    return nu.let(nuspace.atomic(rows), SPEC_TABLE.set_rows)


def by_spec(plane: nu.StrArg) -> nu.Nu:
    """The ``by_spec`` cell: drawn again when a plane is made from a spec, or one is removed."""
    changes = [
        SPECS.on_descendants_change("*", "ids", "*"),
        nuspace.Space.indexes.removed.on_children_change(),
    ]
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*changes)), draw_by_spec())


# --- the top planes ----------------------------------------------------------------------


class Listing(nu.Shape):
    """The ``planes`` cell's root: a titled Card holding the table."""

    planes = nustd.ui.CardRef.slot(
        title="Top planes", subtitle=f"Right under the root, {PAGE} at most"
    )


TABLE_REF = Listing.planes[0].to(
    nustd.ui.DataTableRef.slot(
        columns=[
            {"key": "name", "label": "Name", "cell": LINK, "wrap": "nowrap", "sortable": False},
            {"key": "spec", "label": "Spec", "sortable": False},
            {
                "key": "system",
                "label": "System",
                "cell": nustd.ui.BadgeRef.slot(variant="secondary", size="sm"),
                "sortable": False,
            },
            count_column("cells", "Cells"),
            count_column("planes", "Planes"),
            id_column("id", "ID"),
        ],
        row_key="id",
        label="Top planes",
    )
)


def _counted(held: nu.Nu) -> nu.Nu:
    # How many ids a plane's list holds, one page read at most.
    page = nu.List(held.keys(limit=PAGE + 1))
    return nu.If(page.len() > PAGE, nu.str(PAGE) + "+", nu.str(page.len()))


def row(p: nu.Str) -> nu.Dict:
    """Plane ``p``'s row in the top planes table. A read."""
    plane = nuspace.Space.planes[p]
    return nu.Dict.of(
        name=web.page(p),
        spec=plane.spec.fallback(""),
        system=nu.If(plane.system.fallback(False), "system", ""),
        cells=_counted(plane.cells),
        planes=_counted(plane.children),
        id=p,
    )


def _top() -> nu.Nu:
    # What the table shows: the planes right under root, the first PAGE.
    return nu.list(nuspace.Space.planes[ROOT].children.keys(limit=PAGE))


def draw_listing() -> nu.Nu:
    """Read the top planes once and draw the table."""
    rows = nu.List(_top()).iter().map(lambda at: row(nu.Str(at))).to_list()
    return nu.let(nuspace.atomic(rows), TABLE_REF.set_rows)


def _follow(at: nu.ObjectRef) -> nu.Nu:
    # One shown plane's row again, in place, when its own row changes: one watch per shown plane.
    p = nu.Str(at)
    again = nu.let(nuspace.atomic(row(p)), lambda r: TABLE_REF.set_row(p, r))
    return nu.ReactEvery(nuspace.atomic(nuspace.plane.on_change(p)), lambda _: again)


def listing(plane: nu.StrArg) -> nu.Nu:
    """The ``planes`` cell: the top planes, whole when root's children move, a row when its plane does."""
    listed = nuspace.atomic(nuspace.plane.on_children_change(ROOT))
    return nu.ParallelAsync(
        nu.Reconcile(listed, draw_listing()),
        nu.ReconcileLatestEach(nuspace.atomic(_top()), listed, _follow),
    )


BY_SPEC = shim("planes", "by_spec")
TABLE = shim("planes", "listing")


PLANE = PlaneSpec(
    "planes",
    "Planes",
    icon="layers",
    description="The planes by spec, and the planes at the top, kept live.",
    cells=(("by_spec", BY_SPEC), ("planes", TABLE)),
    group="System",
    web=WebOptions(editable=True, full_width=False),
    backend="async",
)
