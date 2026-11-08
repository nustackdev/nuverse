"""The ``workers`` Plane: the workers the backends hold, live.

Two cells, each drawn again when what is live changes, and only when what it
shows did: the counts per backend, and every live worker with the plane run
it serves. Read off ``Space.exec.indexes.live.workers`` and the records it
names, so it costs what is up, never history. Ages move with the clock, so
the table is read again every minute too.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["COUNTS", "PLANE", "TABLE"]


COUNTS = """\
import nu
import nustd.ui
import nuspace
import nuspace.kernel
from nuverse.planes.runs import ids

LIVE = nuspace.Space.exec.indexes.live


def backends():
    # Each live worker's backend.
    def of(w):
        return nuspace.Space.exec.workers[nu.Str(w)].backend.fallback("")

    return ids(LIVE.workers).iter().map(of).to_list()


def count(held, backend):
    return nu.Count(nu.List(held).iter().filter(lambda b: b == backend))


def tiles(held):
    up = nustd.ui.StatRef("up").set(nu.str(nu.List(held).len()), label="Up")
    return up >> nu.Sequential(
        *[
            nustd.ui.StatRef(backend).set(nu.str(count(held, backend)), label=backend)
            for backend in nuspace.kernel.BACKENDS
        ]
    )


def draw():
    return nu.let(nuspace.atomic(backends()), tiles)


out = nu.Reconcile(nuspace.atomic(nu.OnAny(LIVE.workers.on_children_change())), draw())
"""


TABLE = """\
import nu
import nustd.time
import nustd.ui
import nuspace
from nuverse.planes.runs import age, ids, lives

LIVE = nuspace.Space.exec.indexes.live

#: The most workers the table lists.
PAGE = 100


def cells_on(w, plane_run):
    # The plane run's live cell runs placed on this worker: a walk of what is live.
    live = ids(LIVE.plane_run_to_cell_runs[plane_run].ids).iter()
    return nu.Count(live.filter(lambda c: nuspace.Space.exec.cell_runs[nu.Str(c)].worker == w))


def rows():
    now = nustd.time.time()

    def row(at):
        w = nu.Str(at)
        worker = nuspace.Space.exec.workers[w]
        plane_run = nu.Str(worker.plane_run)
        plane = nuspace.Space.exec.plane_runs[plane_run].plane
        return nu.List.of(
            w,
            worker.backend.fallback(""),
            nuspace.plane.title(plane),
            plane_run,
            cells_on(w, plane_run),
            age(now, worker.started_at),
        )

    # Ids sort by when they were minted: newest first, one page.
    newest = nu.List(LIVE.workers.reversed_keys(limit=PAGE))
    return newest.iter().map(row).to_list()


def table(shown):
    columns = ["ID", "Backend", "Plane", "Run", "Cells", "Age"]
    return nustd.ui.TableRef("workers").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(nuspace.atomic(rows()), table)


out = nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw(), every=60.0)
"""


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
