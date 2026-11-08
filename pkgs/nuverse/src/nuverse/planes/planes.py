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

A count reads at most :data:`PAGE` ids and says ``100+`` past that.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["BY_SPEC", "PAGE", "PLANE", "TABLE"]


#: The most ids one read takes: rows in a table, ids behind a count.
PAGE = 100


BY_SPEC = """\
import nu
import nustd.ui
import nuspace
from nuverse.planes.planes import PAGE
from nuverse.planes.runs import ids

SPECS = nuspace.Space.indexes.spec_planes


def row(at):
    spec = nu.Str(at)
    # Newest first, one page: the planes still in the space, removed ones skipped.
    newest = nu.List(SPECS[spec].ids.reversed_keys(limit=PAGE + 1))
    there = newest.iter().filter(lambda p: nuspace.plane.exists(nu.Str(p))).to_list()
    count = nu.If(newest.len() > PAGE, nu.str(PAGE) + "+", nu.str(there.len()))
    last = nu.If(there.len() > 0, nuspace.plane.title(nu.Str(there[0])), "-")
    return nu.List.of(spec, count, last)


def rows():
    return ids(SPECS).iter().map(row).to_list()


def table(shown):
    columns = ["Spec", "Planes", "Newest"]
    return nustd.ui.TableRef("by spec").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(nuspace.atomic(rows()), table)


# A plane made from a spec, or one removed.
changes = [
    SPECS.on_descendants_change("*", "ids", "*"),
    nuspace.Space.indexes.removed.on_children_change(),
]
out = nu.Reconcile(nuspace.atomic(nu.OnAny(*changes)), draw())
"""


TABLE = """\
import nu
import nustd.ui
import nuspace
from nuspace.shapes import ROOT
from nuverse.planes.planes import PAGE

COLUMNS = ["Name", "Spec", "System", "Cells", "Planes", "ID"]
PLANES = nustd.ui.TableRef("planes")


def counted(held):
    # How many ids a plane's list holds, one page read at most.
    page = nu.List(held.keys(limit=PAGE + 1))
    return nu.If(page.len() > PAGE, nu.str(PAGE) + "+", nu.str(page.len()))


def row(p):
    plane = nuspace.Space.planes[p]
    spec = nu.Str(plane.spec.fallback(""))
    return nu.List.of(
        nuspace.plane.title(p),
        nu.If(spec == "", "-", spec),
        nu.If(plane.system.fallback(False), "yes", "no"),
        counted(plane.cells),
        counted(plane.children),
        p,
    )


def top():
    # What the table shows: the planes right under root, the first PAGE.
    return nu.list(nuspace.Space.planes[ROOT].children.keys(limit=PAGE))


def rows():
    return top().iter().map(lambda at: row(nu.Str(at))).to_list()


def draw():
    shown = lambda r: PLANES.set(nu.Dict.of(columns=COLUMNS, rows=r, row_key="ID"))
    return nu.let(nuspace.atomic(rows()), shown)


def follow(at):
    # One shown plane's row again, in place, when its own row changes: one watch per shown plane.
    p = nu.Str(at)
    again = nu.let(nuspace.atomic(row(p)), lambda r: PLANES.set_row(p, r))
    return nu.ReactEvery(nuspace.atomic(nuspace.plane.on_change(p)), lambda _: again)


# Which planes show: root's children made, moved or removed. Nothing else wakes the whole table.
listed = nuspace.atomic(nuspace.plane.on_children_change(ROOT))
out = nu.ParallelAsync(
    nu.Reconcile(listed, draw()),
    nu.ReconcileLatestEach(nuspace.atomic(top()), listed, follow),
)
"""


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
