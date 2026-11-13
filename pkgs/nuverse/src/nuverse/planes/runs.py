"""The ``runs`` Plane: what the kernel is running now, live.

Three cells, each drawn again when what is live changes, and only when what
it shows did: the counts, the live plane runs, and their live cell runs.
Everything is read off ``Space.exec.indexes.live`` and the run records it
names, so it costs what is running, never history. Times are drawn by the
browser from when each run started, so nothing redraws as the clock moves.

The cells are shims (:func:`~nuverse.planes.shim`): :func:`counts`,
:func:`live` and :func:`cells` here are their code.
"""

from __future__ import annotations

import nu
import nuspace
import nuspace.web as web
import nustd.ui
from nuspace.specs import PlaneSpec, WebOptions
from nuverse.planes import shim


__all__ = [
    "BACKEND_COLUMN",
    "CELLS",
    "CELLS_TABLE",
    "COUNTS",
    "LIVE",
    "LIVE_INDEX",
    "PLANE",
    "PLANE_COLUMN",
    "RUNS_TABLE",
    "STARTED_COLUMN",
    "Cells",
    "Counts",
    "Live",
    "cells",
    "count_column",
    "counts",
    "draw_cells",
    "draw_counts",
    "draw_live",
    "id_column",
    "ids",
    "live",
    "lives",
    "ms",
    "tile",
]


def ids(held: nu.Nu) -> nu.List:
    """The keys of a live set, ``[]`` when it is not there. A read.

    A plane run's live sets are made when it is added and dropped once it
    is over, so a read racing its end finds none.
    """
    return nu.List(nu.If(held.exists(), nu.list(held.keys()), []))


def lives() -> list[nu.Nu]:
    """What says what is live moved: a plane run, a cell run, either starting, a worker.

    Fresh subscriptions on every call.
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


def ms(t: nu.Nu) -> nu.Nu:
    """Epoch seconds ``t`` as the epoch ms a ``RelativeTime`` cell draws, blank while ``t`` reads NULL."""
    return nu.If(nu.IsNull(t), "", nu.int(nu.Float(t) * 1000))


def tile(grid: nustd.ui.GridRef, name: str, label: str, value: nu.Nu) -> nu.Nu:
    """One count in a tile grid: a small Card holding a Stat, at ``grid[name]``."""
    card = grid[name].to(nustd.ui.CardRef.slot(size="sm"))
    return card[0].to(nustd.ui.StatRef).set(nu.str(value), label=label)


def _column(key: str, label: str, cell: object = None, **more: object) -> dict:
    # Nothing sorts: the rows keep the order they are read in.
    column: dict = {"key": key, "label": label, "sortable": False, **more}
    if cell is not None:
        column["cell"] = cell
    return column


#: Columns the system tables share.
PLANE_COLUMN = _column("plane", "Plane", nustd.ui.PageLinkRef.slot(variant="inline"), wrap="nowrap")
BACKEND_COLUMN = _column("backend", "Backend", nustd.ui.BadgeRef.slot(size="sm"))
STARTED_COLUMN = _column("started", "Started", nustd.ui.RelativeTimeRef, wrap="nowrap")


def id_column(key: str, label: str) -> dict:
    """An id column: cut short, and left out on a narrow pane."""
    return _column(key, label, wrap="truncate", max_width=160, hide_below=720)


def count_column(key: str, label: str) -> dict:
    """A count column, set to the end."""
    return _column(key, label, align="end")


LIVE_INDEX = nuspace.Space.exec.indexes.live


# --- counts ------------------------------------------------------------------------------


class Counts(nu.Shape):
    """The ``counts`` cell's root: a grid of count tiles."""

    tiles = nustd.ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=3)


def _counts() -> nu.List:
    runs = ids(LIVE_INDEX.plane_runs)
    held = runs.iter().map(lambda r: ids(LIVE_INDEX.plane_run_to_cell_runs[nu.Str(r)].ids).len())
    return nu.List.of(runs.len(), nu.Sum(held), ids(LIVE_INDEX.workers).len())


def draw_counts() -> nu.Nu:
    """Read the counts once and draw the tiles."""

    def tiles(n: nu.ObjectRef) -> nu.Nu:
        got = nu.List(n)
        return (
            tile(Counts.tiles, "runs", "Live runs", got[0])
            >> tile(Counts.tiles, "cells", "Live cells", got[1])
            >> tile(Counts.tiles, "workers", "Workers up", got[2])
        )

    return nu.let(nuspace.atomic(_counts()), tiles)


def counts(plane: nu.StrArg) -> nu.Nu:
    """The ``counts`` cell: live runs, live cells, workers up, drawn again when one moves."""
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw_counts())


# --- live plane runs ---------------------------------------------------------------------


class Live(nu.Shape):
    """The ``live`` cell's root: a titled Card holding the table."""

    runs = nustd.ui.CardRef.slot(title="Live runs", subtitle="Plane runs going now")


RUNS_TABLE = Live.runs[0].to(
    nustd.ui.DataTableRef.slot(
        columns=[
            PLANE_COLUMN,
            BACKEND_COLUMN,
            _column("by", "By"),
            count_column("cells", "Cells"),
            count_column("workers", "Workers"),
            STARTED_COLUMN,
            id_column("run", "Run"),
        ],
        row_key="run",
        label="Live runs",
    )
)


def _live_rows() -> nu.List:
    def row(at: nu.ObjectRef) -> nu.Dict:
        r = nu.Str(at)
        run = nuspace.Space.exec.plane_runs[r]
        return nu.Dict.of(
            plane=web.page(nu.Str(run.plane)),
            backend=run.backend.fallback(""),
            by=run.by.fallback(""),
            cells=ids(LIVE_INDEX.plane_run_to_cell_runs[r].ids).len(),
            workers=ids(LIVE_INDEX.plane_run_to_workers[r].ids).len(),
            started=ms(run.started_at),
            run=r,
        )

    return ids(LIVE_INDEX.plane_runs).iter().map(row).to_list()


def draw_live() -> nu.Nu:
    """Read the live plane runs once and draw their table."""
    return nu.let(nuspace.atomic(_live_rows()), RUNS_TABLE.set_rows)


def live(plane: nu.StrArg) -> nu.Nu:
    """The ``live`` cell: every live plane run, drawn again when what is live moves."""
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw_live())


# --- live cell runs ----------------------------------------------------------------------


class Cells(nu.Shape):
    """The ``cells`` cell's root: a titled Card holding the table."""

    cells = nustd.ui.CardRef.slot(title="Live cells", subtitle="The cell runs of those plane runs")


CELLS_TABLE = Cells.cells[0].to(
    nustd.ui.DataTableRef.slot(
        columns=[
            PLANE_COLUMN,
            _column("cell", "Cell", wrap="truncate", max_width=180),
            _column("state", "State", nustd.ui.StatusPillRef),
            _column("by", "By", hide_below=640),
            count_column("version", "Version"),
            STARTED_COLUMN,
            id_column("worker", "Worker"),
            id_column("id", "ID"),
        ],
        row_key="id",
        label="Live cells",
    )
)


def _cell_rows() -> nu.List:
    def row(plane: nu.Str, at: nu.ObjectRef) -> nu.Dict:
        c = nu.Str(at)
        run = nuspace.Space.exec.cell_runs[c]
        starting = nu.IsNull(run.started_at)
        return nu.Dict.of(
            plane=web.page(plane),
            cell=nuspace.cell.title(run.cell),
            state=nu.Dict.of(
                label=nu.If(starting, "starting", "running"),
                tone=nu.If(starting, "neutral", "ok"),
            ),
            by=run.by.fallback(""),
            version=run.version.fallback(0),
            started=ms(run.started_at),
            worker=run.worker.fallback(""),
            id=c,
        )

    def of_run(at: nu.ObjectRef) -> nu.List:
        r = nu.Str(at)
        plane = nu.Str(nuspace.Space.exec.plane_runs[r].plane)
        held = ids(LIVE_INDEX.plane_run_to_cell_runs[r].ids).iter()
        return held.map(lambda c: row(plane, c)).to_list()

    return nu.List(nu.Collect(nu.Flatten(ids(LIVE_INDEX.plane_runs).iter().map(of_run))))


def draw_cells() -> nu.Nu:
    """Read the live cell runs once and draw their table."""
    return nu.let(nuspace.atomic(_cell_rows()), CELLS_TABLE.set_rows)


def cells(plane: nu.StrArg) -> nu.Nu:
    """The ``cells`` cell: every live cell run, drawn again when what is live moves."""
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*lives())), draw_cells())


COUNTS = shim("runs", "counts")
LIVE = shim("runs", "live")
CELLS = shim("runs", "cells")


PLANE = PlaneSpec(
    "runs",
    "Runs",
    icon="activity",
    description="Live plane runs and their cells, kept live.",
    cells=(("counts", COUNTS), ("live", LIVE), ("cells", CELLS)),
    group="System",
    web=WebOptions(editable=True),
    backend="async",
)
