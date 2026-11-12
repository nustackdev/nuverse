"""The Compare plane: every run side by side, and the best one in a sentence.

- ``leader``: live prose, the best run and how it was trained.
- ``table``: every run's hyperparameters, progress and scores. Tick a run's
  Plot box to overlay it, click its name to open it.
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
import nuspace.web
import nustd.ui
from nudemos.mnist import views
from nudemos.mnist.state import Pick, runs_change

#: The runs ticked, in this plane's state.
PICK = nuspace.at.plane.state(Pick)
"""


def _cell(body: str) -> str:
    return _IMPORTS + "\n\n" + body


LEADER = _cell("""\
class View(nustd.ui.Column):
    line = nustd.ui.MarkdownRef.slot()
    best = nustd.ui.LinkRef.slot(arrow=True)


def draw(d):
    page = nu.Str(d["page"])
    return View.line.set(d["text"]) >> nu.IfDo(page != "", View.best.set(href=nuspace.web.href(page), label=d["label"]))


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
from nudemos import pages


def column(key, label=None, **more):
    return {"key": key, "label": label or key.capitalize(), "editable": False, **more}


COLUMNS = [
    {"key": "plot", "label": "Plot", "kind": "bool", "width": 60},
    column("run", cell=nustd.ui.PageLinkRef.slot(variant="inline")),
    column("status", cell=nustd.ui.StatusPillRef),
    column("optimizer", hide_below=900), column("lr", "LR", align="end"), column("batch", align="end", hide_below=900),
    column("channels", align="end", hide_below=1100), column("dropout", align="end", hide_below=1100),
    column("epochs", align="end", hide_below=1100), column("progress", cell=nustd.ui.ProgressRef, width=120),
    column("loss", "Train loss", align="end"), column("best", "Best test", align="end"), column("final", "Final test", align="end"),
]


class View(nu.Shape):
    table = nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="page", editable=True, density="compact", label="Runs")


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
        read = pages.linked(views.rows(views.board(nu.Str(root)), nu.list(PICK.planes.fallback([]))), "run")
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*runs)), nu.let(nuspace.atomic(read), t.set_rows), every=2.0),
            nu.ReactEvery(t.on_edit(), plot),
        )

    return nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), follow)
""")


OVERLAY = _cell("""\
#: The legend under the lines, wrapping, so every run's name shows whole.
UNDER = {"legend": {"type": "plain", "top": "auto", "bottom": 0}, "grid": {"top": 24, "bottom": 84}}


class View(nu.Shape):
    charts = nustd.ui.GridRef.slot(cols=2, stack_below=800, gap=4)


acc = View.charts[0, 0].to(nustd.ui.CardRef.slot(title="Test accuracy"))["acc"].to(
    nustd.ui.LineChart.slot(y_format="{value}%", legend=True, height=340, option=UNDER)
)
loss = View.charts[0, 1].to(nustd.ui.CardRef.slot(title="Train loss"))["loss"].to(
    nustd.ui.LineChart.slot(legend=True, height=340, option=UNDER)
)


def draw(d):
    return acc.set(d["acc"]) >> loss.set(d["loss"]) >> acc.merge(d["legend"]) >> loss.merge(d["legend"])


def out(plane):
    def follow(root):
        read = views.overlay(views.series(nu.Str(root)), nu.list(PICK.planes.fallback([])))
        return nu.Reconcile(nuspace.atomic(PICK.planes.on_change()), nu.let(nuspace.atomic(read), draw), every=2.0)

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
