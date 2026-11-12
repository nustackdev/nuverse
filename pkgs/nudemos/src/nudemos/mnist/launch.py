"""The Launch plane: a form that starts runs, and the runs it started.

- ``form``: the hyperparameters, a name, and two buttons. Launch writes a run
  page (:data:`~nudemos.mnist.run.PAGE`) under the MNIST plane and a headless
  job under the page, its one cell :func:`~nudemos.mnist.job.job_source` with
  the form's values baked in, then puts the job under the supervisor, which
  starts it, and opens the page. Sweep does the same for three learning rates
  around the one picked.
  Without torch it shows how to install it instead.
- ``runs``: every run so far, newest first, with its status and best score. A click opens it.
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


def pick(options):
    return type("Pick", (nustd.ui.Field,), {"choice": nustd.ui.SelectRef.slot(options=options)})


class Knobs(nustd.ui.Grid):
    optimizer = pick(OPTIMIZERS).slot(label="Optimizer")
    lr = pick(RATES).slot(label="Learning rate")
    batch = pick(BATCHES).slot(label="Batch size")
    channels = pick(CHANNELS).slot(label="Conv channels")
    epochs = nustd.ui.NumberInputRef.slot(label="Epochs", min=1, max=20, step=1)
    dropout = nustd.ui.SliderRef.slot(label="Dropout", min=0.0, max=0.6, step=0.05)


class Go(nustd.ui.Row):
    name = nustd.ui.InputRef.slot(placeholder="Name it, or leave it to us")
    launch = nustd.ui.ButtonRef.slot(label="Launch run", icon="play")
    sweep = nustd.ui.ButtonRef.slot(label="Sweep 3 learning rates", variant="secondary", icon="sliders-horizontal")


#: Whether torch is here to train with. It comes with the ``mnist`` extra.
READY = importlib.util.find_spec("torch") is not None

MISSING = '**Training needs torch.** Install it with `pip install "nudemos[mnist]"`, then restart the space.'


class View(nustd.ui.Column):
    notice = nustd.ui.MarkdownRef.slot()
    history = nustd.ui.HistoryRef.slot()
    knobs = Knobs.slot(columns=3, min_width=200, gap=3)
    go = Go.slot(gap=2, align="end")


K = View.knobs


def asked():
    # What the form says now, read from the browser once per click.
    return nu.Dict.of(
        optimizer=nu.Str(K.optimizer.choice), lr=nu.ToFloat(K.lr.choice),
        batch_size=nu.ToInt(K.batch.choice), channels=nu.ToInt(K.channels.choice),
        epochs=nu.int(K.epochs), dropout=nu.float(K.dropout),
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
        return each >> View.go.name.set("") >> nu.IfDo(nu.Str(how) == "one", opened)

    typed = nu.Str(View.go.name).strip()
    plan = views.plan(asked(), nuspace.atomic(runs_of(root).len()), typed, how)
    return nu.let(plan, start)


def defaults():
    return (
        K.optimizer.choice.set("adam") >> K.lr.choice.set("0.001") >> K.batch.choice.set("64")
        >> K.channels.choice.set("16") >> K.epochs.set_value(3.0) >> K.dropout.set(0.25)
        >> View.go.name.set("") >> View.go.launch.set("Launch run", icon="play")
        >> View.go.sweep.set("Sweep 3 learning rates", variant="secondary", icon="sliders-horizontal")
    )


def out(plane):
    def clicks(root):
        return nu.ParallelAsync(
            nu.ReactEvery(View.go.launch.on_click(), runs(nu.Str(root), "one")),
            nu.ReactEvery(View.go.sweep.on_click(), runs(nu.Str(root), "sweep")),
        )

    if not READY:
        return View.notice.set(MISSING) >> nu.ForeverDo(nu.Delay(3600.0))
    return defaults() >> nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), clicks)
"""


RUNS = """\
import nu
import nuspace.web
import nuspace
import nustd.ui
from nudemos.mnist import views
from nudemos.mnist.state import runs_change

COLUMNS = [{"key": "run", "label": "Run"}, "status", "lr", "progress", {"key": "best", "label": "Best test"}]


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    head = nustd.ui.HeadingRef.slot(level=4)
    runs = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="page", clickable_rows=True, dense=True)


def out(plane):
    def follow(root):
        runs = runs_change(nu.Str(root))
        opened = nu.ReactEvery(View.runs.on_row_click(), lambda ev: View.history.push(nuspace.web.href(ev["key"])))
        return nu.ParallelAsync(nu.Reconcile(nuspace.atomic(runs), nu.let(nuspace.atomic(views.rows(views.board(nu.Str(root)))), View.runs.set_rows), every=2.0), opened)

    return View.head.set("Runs, newest first") >> nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), follow)
"""


PLANE = PlaneSpec(
    "mnist_launch",
    "Launch",
    icon="rocket",
    description="Start MNIST training runs from a form.",
    web=WebOptions(editable=True, full_width=True),
    cells=(("form", FORM), ("runs", RUNS)),
    backend="async",
)
