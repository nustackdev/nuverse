"""The ``runs`` Plane: what the kernel is running now, live.

Three cells, each drawn again when what is live changes, and only when what
it shows did: the counts, the live plane runs, and their live cell runs.
Everything is read off ``Space.exec.indexes.live`` and the run records it
names, so it costs what is running, never history. Ages move with the
clock, so the tables are read again every minute too.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["CELLS", "COUNTS", "LIVE", "PLANE", "age", "ids", "lives"]


def age(now: nu.Nu, t: nu.Nu, unknown: str = "") -> nu.Nu:
    """How long since ``t`` in minutes, eg ``12m``, ``unknown`` while ``t`` reads NULL. For cell sources to import."""
    m = nu.int(nu.Float(now) - t) // 60
    spelled = nu.If(
        m < 1, "<1m", nu.If(m < 60, nu.str(m) + "m", nu.str(m // 60) + "h " + nu.str(m % 60) + "m")
    )
    return nu.If(nu.IsNull(t), unknown, spelled)


def ids(held: nu.Nu) -> nu.List:
    """The keys of a live set, ``[]`` when it is not there. A read. For cell sources to import.

    A plane run's live sets are made when it is added and dropped once it
    is over, so a read racing its end finds none.
    """
    return nu.List(nu.If(held.exists(), nu.list(held.keys()), []))


def lives() -> list[nu.Nu]:
    """What says what is live moved: a plane run, a cell run, either starting, a worker.

    Fresh subscriptions on every call. For cell sources to import.
    """
    live = nuspace.Space.exec.indexes.live
    runs = nuspace.Space.exec
    return [
        live.plane_runs.on_children_change(),
        live.plane_run_to_cell_runs.on_descendants_change("*", "ids", "*"),
        runs.plane_runs.on_descendants_change("*", "started_at"),
        runs.cell_runs.on_descendants_change("*", "started_at"),
        live.workers.on_children_change(),
    ]


COUNTS = """\
import nu
import nustd.ui
import nuspace
from nuverse.planes.runs import ids, lives

LIVE = nuspace.Space.exec.indexes.live


def tile(name, label, value):
    return nustd.ui.StatRef(name).set(nu.str(value), label=label)


def counts():
    runs = ids(LIVE.plane_runs)
    cells = nu.Sum(runs.iter().map(lambda r: ids(LIVE.plane_run_to_cell_runs[nu.Str(r)].ids).len()))
    return nu.List.of(runs.len(), cells, ids(LIVE.workers).len())


def tiles(n):
    return (
        tile("runs", "Live runs", n[0])
        >> tile("cells", "Live cells", n[1])
        >> tile("workers", "Workers up", n[2])
    )


def draw():
    return nu.let(nuspace.atomic(counts()), tiles)


out = nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw())
"""


LIVE = """\
import nu
import nustd.time
import nustd.ui
import nuspace
from nuverse.planes.runs import age, ids, lives

LIVE = nuspace.Space.exec.indexes.live


def rows():
    now = nustd.time.time()

    def row(at):
        r = nu.Str(at)
        run = nuspace.Space.exec.plane_runs[r]
        return nu.List.of(
            nuspace.plane.title(run.plane),
            run.backend.fallback(""),
            run.by.fallback(""),
            ids(LIVE.plane_run_to_cell_runs[r].ids).len(),
            ids(LIVE.plane_run_to_workers[r].ids).len(),
            age(now, run.started_at),
        )

    return ids(LIVE.plane_runs).iter().map(row).to_list()


def table(shown):
    columns = ["Plane", "Backend", "By", "Cells", "Workers", "Age"]
    return nustd.ui.TableRef("live runs").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(nuspace.atomic(rows()), table)


out = nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw(), every=60.0)
"""


CELLS = """\
import nu
import nustd.time
import nustd.ui
import nuspace
from nuverse.planes.runs import age, ids, lives

LIVE = nuspace.Space.exec.indexes.live


def rows():
    now = nustd.time.time()

    def row(plane, at):
        run = nuspace.Space.exec.cell_runs[nu.Str(at)]
        return nu.List.of(
            nuspace.plane.title(plane),
            nuspace.cell.title(run.cell),
            run.by.fallback(""),
            run.version.fallback(0),
            run.worker.fallback(""),
            age(now, run.started_at, "starting"),
        )

    def cells(at):
        r = nu.Str(at)
        plane = nu.Str(nuspace.Space.exec.plane_runs[r].plane)
        live = ids(LIVE.plane_run_to_cell_runs[r].ids).iter()
        return live.map(lambda c: row(plane, c)).to_list()

    return nu.List(nu.Collect(nu.Flatten(ids(LIVE.plane_runs).iter().map(cells))))


def table(shown):
    columns = ["Plane", "Cell", "By", "Version", "Worker", "Age"]
    return nustd.ui.TableRef("live cells").set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(nuspace.atomic(rows()), table)


out = nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw(), every=60.0)
"""


PLANE = PlaneSpec(
    "runs",
    "Runs",
    icon="activity",
    description="Live plane runs and their cells, kept live.",
    cells=(("counts", COUNTS), ("live", LIVE), ("cells", CELLS)),
    group="System",
    web=WebOptions(editable=True, full_width=False),
    backend="async",
)
