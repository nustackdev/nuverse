"""The Launch plane: a form that starts runs, and the runs it started.

- ``form``: the hyperparameters, a name, and two buttons. Launch writes a run
  page (:data:`~nudemos.mnist.run.PAGE`) under the MNIST plane and a headless
  job under the page, its one cell :func:`~nudemos.mnist.job.job_source` with
  the form's values baked in, then puts the job under the supervisor, which
  starts it, and opens the page. Sweep does the same for three learning rates
  around the one picked.
  Without torch it shows how to install it instead.
- ``runs``: every run so far, newest first, with its status and best score, each name a link to its page.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["FORM", "PLANE", "RUNS"]


FORM = """\
import importlib.util

import nu
import nuspace
import nuspace.web
import nuspace.specs
import nuspace.system.supervisor
import nustd.ui
from nudemos.mnist import views
from nudemos.mnist.job import launch_source
from nudemos.mnist.run import PAGE
from nudemos.mnist.state import JOB, Made, Runs, runs_of

OPTIMIZERS = ["adam", "adamw", "sgd"]
RATES = ["0.0001", "0.0003", "0.001", "0.003", "0.01", "0.03"]
BATCHES = ["32", "64", "128", "256"]
CHANNELS = ["8", "16", "32"]


#: Whether torch is here to train with. It comes with the ``mnist`` extra.
READY = importlib.util.find_spec("torch") is not None

MISSING = '**Training needs torch.** Install it with `pip install "nudemos[mnist]"`, then restart the space.'


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    run = nustd.ui.CardRef.slot(title="New run", subtitle="pick the knobs, then launch one run or a sweep")


knobs = View.run["knobs"].to(nustd.ui.GridRef.slot(cols=3, stack_below=640, gap=4))
notice = View.run.footer["notice"].to(nustd.ui.MarkdownRef)


def pick(r, c, label, options, value):
    # A labelled select at a place of the knobs grid, starting on ``value``.
    return knobs[r, c].to(nustd.ui.Field.slot(label=label)).control.to(nustd.ui.SelectRef.slot(options=options, value=value))


optimizer = pick(0, 0, "Optimizer", OPTIMIZERS, "adam")
lr = pick(0, 1, "Learning rate", RATES, "0.001")
batch = pick(0, 2, "Batch size", BATCHES, "64")
channels = pick(1, 0, "Conv channels", CHANNELS, "16")
epochs = knobs[1, 1].to(nustd.ui.NumberInputRef.slot(label="Epochs", min=1, max=20, step=1, value=3.0))
dropout = knobs[1, 2].to(nustd.ui.SliderRef.slot(label="Dropout", min=0.0, max=0.6, step=0.05, value=0.25))
name = View.run["name"].to(nustd.ui.InputRef.slot(placeholder="Name it, or leave it to us"))
go = View.run.actions["launch"].to(nustd.ui.ButtonRef.slot(label="Launch run", icon="play"))
sweep = View.run.actions["sweep"].to(
    nustd.ui.ButtonRef.slot(label="Sweep 3 learning rates", variant="secondary", icon="sliders-horizontal")
)


def asked():
    # What the form says now, read from the browser once per click.
    return nu.Dict.of(
        optimizer=nu.Str(optimizer), lr=nu.ToFloat(lr), batch_size=nu.ToInt(batch), channels=nu.ToInt(channels),
        epochs=nu.int(epochs), dropout=nu.float(dropout),
    )


def launch(root, hp, name):
    # A run page under the MNIST plane, the headless job under the page, supervised: it starts now.
    # Three commits: the page, then the job and its cell (it draws nothing), then its id kept, the run listed and the job supervised.
    def made(page, job):
        p, j = nu.Str(page), nu.Str(job)
        add = nuspace.plane.add(parent=p, name="train", backend="mp", spec=JOB, into=job) >> nuspace.cell.add(
            j, launch_source(hp), name="train", fabrics=[]
        )
        ids = nuspace.at.plane(id=p).state(Made)
        kept = ids.job.set(j)
        listed = nuspace.at.plane(id=root).state(Runs).planes.set_item(p, True)
        policy = nuspace.system.supervisor.ON_FAILURE
        up = nuspace.system.supervisor.supervise(j, policy=policy, exists_ok=True)
        return (
            nuspace.specs.add_plane(PAGE, parent=root, name=name, into=page)
            >> nuspace.atomic(add)
            >> nuspace.atomic(kept >> listed >> up)
        )

    return nu.let("", lambda page: nu.let("", lambda job: made(page, job)))


def runs(root, how):
    # One run, or three for a sweep, named and counted on from the runs there are.
    def start(plan):
        each = nu.ForEachDo(nu.List(plan), lambda p: launch(root, nu.List(p)[0], nu.List(p)[1]))
        newest = nuspace.atomic(nu.List(runs_of(root))[-1][0])
        opened = View.history.push(nuspace.web.href(newest))
        return each >> name.reset() >> nu.IfDo(nu.Str(how) == "one", opened)

    typed = nu.Str(name).strip()
    plan = views.plan(asked(), nuspace.atomic(runs_of(root).len()), typed, how)
    return nu.let(plan, start)


def defaults():
    # Every knob as its slot declares it.
    return nu.Sequential(*(k.init() for k in (optimizer, lr, batch, channels, epochs, dropout, name)))


def out(plane):
    def clicks(root):
        return go.init() >> sweep.init() >> nu.ParallelAsync(
            nu.ReactEvery(go.on_click(), runs(nu.Str(root), "one")),
            nu.ReactEvery(sweep.on_click(), runs(nu.Str(root), "sweep")),
        )

    if not READY:
        return defaults() >> notice.set(MISSING) >> nu.ForeverDo(nu.Delay(3600.0))
    return defaults() >> nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), clicks)
"""


RUNS = """\
import nu
import nuspace
import nustd.ui
from nudemos import pages
from nudemos.mnist import views
from nudemos.mnist.state import runs_change

COLUMNS = [
    {"key": "run", "label": "Run", "cell": nustd.ui.PageLinkRef.slot(variant="inline")},
    {"key": "status", "label": "Status", "cell": nustd.ui.StatusPillRef, "width": 130},
    {"key": "lr", "label": "LR", "align": "end", "width": 80},
    {"key": "progress", "label": "Progress", "cell": nustd.ui.ProgressRef, "width": 140, "hide_below": 640},
    {"key": "best", "label": "Best test", "align": "end", "width": 100},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Runs", subtitle="newest first")


runs = View.card["runs"].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="page", density="compact", label="Runs"))


def out(plane):
    def follow(root):
        read = pages.linked(views.rows(views.board(nu.Str(root))), "run")
        return nu.Reconcile(nuspace.atomic(runs_change(nu.Str(root))), nu.let(nuspace.atomic(read), runs.set_rows), every=2.0)

    return nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), follow)
"""


PLANE = PlaneSpec(
    "mnist_launch",
    "Launch",
    icon="rocket",
    description="Start MNIST training runs from a form.",
    web=WebOptions(editable=True, width="board"),
    cells=(("form", FORM), ("runs", RUNS)),
    backend="async",
)
