"""The ``workers`` Plane: the workers the backends hold, live.

Two cells, each drawn again when what is live changes, and only when what it
shows did: the counts per backend, and every live worker with the plane run
it serves. Read off ``Space.exec.indexes.live.workers`` and the records it
names, so it costs what is up, never history. Times are drawn by the browser
from when each worker started, so nothing redraws as the clock moves.

The cells are shims (:func:`~nuverse.planes.shim`): :func:`counts` and
:func:`listing` here are their code.
"""

from __future__ import annotations

import nu
import nuspace
import nuspace.kernel
import nuspace.web as web
import nustd.ui
from nuspace.specs import PlaneSpec, WebOptions
from nuverse.planes import shim
from nuverse.planes.runs import (
    BACKEND_COLUMN,
    LIVE_INDEX,
    PLANE_COLUMN,
    STARTED_COLUMN,
    count_column,
    id_column,
    ids,
    lives,
    ms,
    tile,
)


__all__ = [
    "COUNTS",
    "PAGE",
    "PLANE",
    "TABLE",
    "TABLE_REF",
    "Counts",
    "Listing",
    "counts",
    "draw_counts",
    "draw_listing",
    "listing",
]


#: The most workers the table lists.
PAGE = 100


# --- counts ------------------------------------------------------------------------------


class Counts(nu.Shape):
    """The ``counts`` cell's root: a grid of count tiles, all up then one per backend."""

    tiles = nustd.ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=3)


def _backends() -> nu.List:
    # Each live worker's backend.
    def of(w: nu.ObjectRef) -> nu.Nu:
        return nuspace.Space.exec.workers[nu.Str(w)].backend.fallback("")

    return ids(LIVE_INDEX.workers).iter().map(of).to_list()


def _count(held: nu.List, backend: str) -> nu.Nu:
    return nu.Count(held.iter().filter(lambda b: b == backend))


def draw_counts() -> nu.Nu:
    """Read the live workers' backends once and draw the tiles."""

    def tiles(got: nu.ObjectRef) -> nu.Nu:
        held = nu.List(got)
        each = [
            tile(Counts.tiles, backend, backend, _count(held, backend))
            for backend in nuspace.kernel.BACKENDS
        ]
        return tile(Counts.tiles, "up", "Up", held.len()) >> nu.Sequential(*each)

    return nu.let(nuspace.atomic(_backends()), tiles)


def counts(plane: nu.StrArg) -> nu.Nu:
    """The ``counts`` cell: workers up, and per backend, drawn again when a worker comes or goes."""
    return nu.Reconcile(
        nuspace.atomic(nu.OnAny(LIVE_INDEX.workers.on_children_change())), draw_counts()
    )


# --- the table ---------------------------------------------------------------------------


class Listing(nu.Shape):
    """The ``workers`` cell's root: a titled Card holding the table."""

    workers = nustd.ui.CardRef.slot(title="Workers", subtitle=f"Newest first, {PAGE} at most")


TABLE_REF = Listing.workers[0].to(
    nustd.ui.DataTableRef.slot(
        columns=[
            PLANE_COLUMN,
            BACKEND_COLUMN,
            count_column("cells", "Cells"),
            STARTED_COLUMN,
            id_column("run", "Run"),
            id_column("id", "ID"),
        ],
        row_key="id",
        label="Workers",
    )
)


def _cells_on(w: nu.Str, plane_run: nu.Str) -> nu.Nu:
    # The plane run's live cell runs placed on this worker: a walk of what is live.
    live = ids(LIVE_INDEX.plane_run_to_cell_runs[plane_run].ids).iter()
    return nu.Count(live.filter(lambda c: nuspace.Space.exec.cell_runs[nu.Str(c)].worker == w))


def _rows() -> nu.List:
    def row(at: nu.ObjectRef) -> nu.Dict:
        w = nu.Str(at)
        worker = nuspace.Space.exec.workers[w]
        plane_run = nu.Str(worker.plane_run)
        return nu.Dict.of(
            plane=web.page(nu.Str(nuspace.Space.exec.plane_runs[plane_run].plane)),
            backend=worker.backend.fallback(""),
            cells=_cells_on(w, plane_run),
            started=ms(worker.started_at),
            run=plane_run,
            id=w,
        )

    # Ids sort by when they were minted: newest first, one page.
    newest = nu.List(LIVE_INDEX.workers.reversed_keys(limit=PAGE))
    return newest.iter().map(row).to_list()


def draw_listing() -> nu.Nu:
    """Read the live workers once and draw the table."""
    return nu.let(nuspace.atomic(_rows()), TABLE_REF.set_rows)


def listing(plane: nu.StrArg) -> nu.Nu:
    """The ``workers`` cell: every live worker, newest first, drawn again when what is live moves."""
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw_listing())


COUNTS = shim("workers", "counts")
TABLE = shim("workers", "listing")


PLANE = PlaneSpec(
    "workers",
    "Workers",
    icon="cpu",
    description="The workers the backends hold, kept live.",
    cells=(("counts", COUNTS), ("workers", TABLE)),
    group="System",
    web=WebOptions(editable=True, full_width=False),
    backend="async",
)
