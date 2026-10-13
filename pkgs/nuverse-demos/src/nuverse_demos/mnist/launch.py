"""The Launch plane: a form that starts runs, and the runs it started.

- ``form``: the hyperparameters, a name, and two buttons. Launch writes a run
  page (:data:`~nuverse_demos.mnist.run.PAGE`) under the MNIST plane and a headless
  job under the page, its one cell :func:`~nuverse_demos.mnist.job.job_source` with
  the form's values baked in, then puts the job under the supervisor, which
  starts it, and opens the page. Sweep does the same for three learning rates
  around the one picked.
  Without torch it shows how to install it instead.
- ``runs``: every run so far, newest first, with its status and best score. A click opens it.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["FORM", "PLANE", "RUNS"]


FORM = """\
import importlib.util

import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import snap
from nuverse_demos.mnist import views
from nuverse_demos.mnist.job import launch_source
from nuverse_demos.mnist.run import PAGE
from nuverse_demos.mnist.state import JOB, job_cell, runs_of

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

MISSING = '**Training needs torch.** Install it with `pip install "nuverse-demos[mnist]"`, then restart the space.'


class View(nustd.ui.Column):
    notice = nustd.ui.MarkdownRef.slot()
    nav = nustd.ui.NavRef.slot()
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
    def made(page, job):
        return (
            ops.create_plane(PAGE, parent=root, name=name, into=page)
            >> ops.add_plane(backend="mp", name="train", parent=nu.Str(page), ui=False, made_by=JOB, into=job)
            >> ops.add_cell(nu.Str(job), launch_source(hp), cell_id=job_cell(job), name="train")
            >> nuspace.supervise(nu.Str(job))
        )

    return nu.let("", lambda page: nu.let("", lambda job: made(page, job)))


def runs(root, how):
    # One run, or three for a sweep, named and counted on from the runs there are.
    def start(plan):
        each = nu.ForEachDo(nu.List(plan), lambda p: launch(root, nu.List(p)[0], nu.List(p)[1]))
        newest = snap(nu.List(runs_of(root))[-1][0])
        opened = views.go(View.nav, nu.Str("/") + nu.Str(newest))
        return each >> View.go.name.set("") >> nu.IfDo(nu.Str(how) == "one", opened)

    typed = nu.Str(View.go.name).strip()
    plan = views.plan(asked(), snap(runs_of(root).len()), typed, how)
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
            nu.ReactForever(View.go.launch.on_click(), runs(nu.Str(root), "one")),
            nu.ReactForever(View.go.sweep.on_click(), runs(nu.Str(root), "sweep")),
        )

    if not READY:
        return View.notice.set(MISSING) >> nu.ForeverDo(nu.Delay(3600.0))
    return defaults() >> nu.let(snap(ops.parent(plane)), clicks)
"""


RUNS = """\
import nu
import nustd.ui
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import redraws, snap
from nuverse_demos.mnist import views

COLUMNS = [{"key": "run", "label": "Run"}, "status", "lr", "progress", {"key": "best", "label": "Best test"}]


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    head = nustd.ui.HeadingRef.slot(level=4)
    runs = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="page", clickable_rows=True, dense=True)


def out(plane):
    def follow(root):
        runs = Space.planes[nu.Str(root)].children.on_change()
        opened = nu.ReactForever(View.runs.on_row_click(), lambda ev: views.go(View.nav, nu.Str("/") + nu.Str(ev["key"])))
        return nu.ParallelAsync(redraws([runs], views.rows(views.board(nu.Str(root))), View.runs.set_rows, every=2.0), opened)

    return View.head.set("Runs, newest first") >> nu.let(snap(ops.parent(plane)), follow)
"""


PLANE = Plane(
    "mnist_launch",
    "Launch",
    icon="rocket",
    description="Start MNIST training runs from a form.",
    meta={"editable": True, "full_width": True},
    cells=(("form", FORM), ("runs", RUNS)),
    backend="async",
)
