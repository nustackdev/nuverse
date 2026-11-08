"""The Compare plane: every run side by side, and the best one in a sentence.

- ``leader``: live prose, the best run and how it was trained.
- ``table``: every run's hyperparameters, progress and scores. Tick a run's
  Plot box to overlay it, click its row to open it.
- ``overlay``: test accuracy and train loss of the ticked runs (all of them
  when none is ticked), one line per run.

The ticks are this plane's state (:class:`~nudemos.mnist.state.Pick`), so
every tab overlays the same runs.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["LEADER", "OVERLAY", "PLANE", "TABLE"]


_IMPORTS = """\
import nu
import nuspace
import nuspace.devices.web
import nustd.ui
from nudemos.mnist import views
from nudemos.mnist.state import Pick, runs_change

#: The runs ticked, in this plane's state.
PICK = nuspace.at.plane.state(Pick)
"""


def _cell(body: str) -> str:
    return _IMPORTS + "\n\n" + body


LEADER = _cell("""\
class Board(nustd.ui.Column):
    line = nustd.ui.MarkdownRef.slot()
    best = nustd.ui.LinkRef.slot()


def draw(d):
    return Board.line.set(d["text"]) >> nu.IfDo(nu.Str(d["href"]) != "", Board.best.set(href=d["href"], label=d["label"]))


def out(plane):
    # On the MNIST plane, or on Compare under it: the runs hang from the root either way.
    def follow(root):
        runs = runs_change(nu.Str(root))
        return nu.Reconcile(nuspace.atomic(runs), nu.let(nuspace.atomic(views.leader(views.board(nu.Str(root)))), draw), every=2.0)

    row = nuspace.Space.planes[plane]
    root = nuspace.atomic(nu.If(row.spec.fallback("") == "mnist_compare", row.parent, plane))
    return nu.let(root, follow)
""")


TABLE = _cell("""\
def column(key, label=None, **more):
    return {"key": key, "label": label or key.capitalize(), "editable": False, **more}


COLUMNS = [
    {"key": "plot", "label": "Plot", "kind": "bool", "width": 60},
    column("run"), column("status"), column("optimizer"), column("lr", "LR"), column("batch"),
    column("channels"), column("dropout"), column("epochs"), column("progress"),
    column("loss", "Train loss"), column("best", "Best test"), column("final", "Final test"),
]


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="page", clickable_rows=True, editable=True, dense=True)


def plot(ev):
    # Tick or untick a run's Plot box: the overlay below follows every tab's ticks.
    page = nu.Str(ev["key"])
    picked = nu.list(PICK.planes.fallback([]))
    kept = picked.iter().filter(lambda p: nu.Str(p) != page).to_list()
    return nuspace.atomic(PICK.planes.set(nu.If(nu.Bool(ev["value"]), kept + nu.List.of(page), kept)))


def out(plane):
    t = View.table

    def follow(root):
        runs = [runs_change(nu.Str(root)), PICK.planes.on_change()]
        read = views.rows(views.board(nu.Str(root)), nu.list(PICK.planes.fallback([])))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*runs)), nu.let(nuspace.atomic(read), t.set_rows), every=2.0),
            nu.ReactEvery(t.on_edit(), plot),
            nu.ReactEvery(t.on_row_click(), lambda ev: View.history.push(nuspace.devices.web.href(ev["key"]))),
        )

    return nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), follow)
""")


OVERLAY = _cell("""\
#: The legend under the lines, wrapping, so every run's name shows whole.
UNDER = {"legend": {"type": "plain", "top": "auto", "bottom": 0}, "grid": {"top": 42, "bottom": 84}}


class Charts(nustd.ui.Grid):
    acc = nustd.ui.LineChart.slot(title="Test accuracy", y_format="{value}%", legend=True, height=340, option=UNDER)
    loss = nustd.ui.LineChart.slot(title="Train loss", legend=True, height=340, option=UNDER)


class View(nustd.ui.Column):
    charts = Charts.slot(columns=2, min_width=320, gap=3)


def draw(d):
    c = View.charts
    return c.acc.set(d["acc"]) >> c.loss.set(d["loss"]) >> c.acc.merge(d["legend"]) >> c.loss.merge(d["legend"])


def out(plane):
    def follow(root):
        read = views.overlay(views.series(nu.Str(root)), nu.list(PICK.planes.fallback([])))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[PICK.planes.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), follow)
""")


PLANE = PlaneSpec(
    "mnist_compare",
    "Compare",
    icon="trophy",
    description="Every MNIST run side by side: a table, overlaid curves, the best one.",
    web=WebOptions(editable=True, full_width=True),
    cells=(("leader", LEADER), ("table", TABLE), ("overlay", OVERLAY)),
    backend="async",
)
