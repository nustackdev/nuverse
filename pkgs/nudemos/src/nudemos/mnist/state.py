"""The state a run keeps, and where the cells that show it find it.

A run is a headless job plane with one cell. :class:`Run` is that cell's
state: what it trains with, how far it got, and its metrics. The job writes
it as its own (``nuspace.here(Run)``), every other cell reads and steers it
at the job's cell (:func:`run_at`). One class, imported by every cell, so the
slots are declared once.

The MNIST plane keeps its runs' planes in its own state (:class:`Runs`), and
a run page its job's id (:class:`Made`), so nothing looks a run up by
scanning.

The metric series are kh57 maps keyed by step: they grow with the run, and a
chart samples a few hundred points out of them at the same cost however long
it trained.

The models are here too, as bytes, under :attr:`Run.models`: ``latest``,
the whole checkpoint the run resumes from and pages read live, and ``best``,
the weights at its best test accuracy. Each with the step it was taken at and
the test accuracy it had (:class:`Model`). Nothing that draws reads ``blob``:
the bytes go from the job to the store to a reader, never to a browser.

The planes hang as the Launch plane makes them::

    MNIST                 the root, made from :data:`nudemos.mnist.PLANE`
      Launch, Compare, Read
      <run>               a run page (on the web), spec ``mnist_run``
        train             the job (headless, mp), spec ``mnist_job``
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv


__all__ = [
    "JOB",
    "PAGE",
    "SLOTS",
    "Made",
    "Model",
    "Pick",
    "Run",
    "Runs",
    "job_cell",
    "job_of",
    "run_at",
    "runs_change",
    "runs_of",
    "status_of",
]


#: The spec names of a run page, and of the job under it.
PAGE, JOB = "mnist_run", "mnist_job"


#: The models a run keeps, by slot.
SLOTS = ("latest", "best")


class Model(nu.Shape):
    """A stored model: its bytes, the step they were taken at, and the test accuracy then (-1 for none yet)."""

    blob = nustd.kv.BytesRef.slot()
    step = nustd.kv.IntRef.slot()
    acc = nustd.kv.FloatRef.slot()


class Run(nu.Shape):
    """A run's state, on its job's one cell."""

    # What it trains with, as launched, and the learning rate it trains at now.
    hp = nustd.kv.ObjectRef.slot()
    lr = nustd.kv.FloatRef.slot()
    # starting, training, stopping, stopped, done.
    status = nustd.kv.StrRef.slot()
    stop = nustd.kv.BoolRef.slot()
    # Device, parameter count, steps per epoch, as the trainer reports them.
    info = nustd.kv.ObjectRef.slot()
    step = nustd.kv.IntRef.slot()
    total = nustd.kv.IntRef.slot()
    started = nustd.kv.FloatRef.slot()
    beat = nustd.kv.FloatRef.slot()
    speed = nustd.kv.FloatRef.slot()
    # The latest chunk's train metrics, the latest, best and final test accuracy.
    now = nustd.kv.ObjectRef.slot()
    tested = nustd.kv.FloatRef.slot()
    best = nustd.kv.FloatRef.slot()
    final = nustd.kv.FloatRef.slot()
    # The models by slot (:data:`SLOTS`): ``latest`` a whole checkpoint, ``best`` the weights alone.
    models = nustd.kv.DictRef.slot(Model)
    # Series by step.
    loss = nustd.kv.Kh57Ref.slot(float)
    acc = nustd.kv.Kh57Ref.slot(float)
    test_loss = nustd.kv.Kh57Ref.slot(float)
    test_acc = nustd.kv.Kh57Ref.slot(float)
    lrs = nustd.kv.Kh57Ref.slot(float)
    # Histograms by step, a JSON string each (see ``Trainer.histograms``).
    hists = nustd.kv.Kh57Ref.slot(str)
    # The sample digits, once, and what the model says about them, latest. ``looked`` is the
    # step of the latest look: a scalar to follow, an ObjectRef rewritten in place does not say.
    digits = nustd.kv.ObjectRef.slot()
    preds = nustd.kv.ObjectRef.slot()
    looked = nustd.kv.IntRef.slot()


class Pick(nu.Shape):
    """The Compare plane's, in its plane's state: the runs ticked in its table, by run plane id."""

    planes = nustd.kv.ListRef.slot(str)


class Runs(nu.Shape):
    """The MNIST plane's, in its plane's state: its run planes, oldest first."""

    planes = nustd.kv.LogDictRef.slot(bool)


class Made(nu.Shape):
    """A run page's, in its plane's state: its job, once made."""

    job = nustd.kv.StrRef.slot()


def job_of(page: nu.StrArg) -> nu.Str:
    """The job under a run page, ``""`` while it has none. Bare read."""
    return nu.Str(nuspace.at.plane(id=page).state(Made).job.fallback(""))


def job_cell(job: nu.StrArg) -> nu.Str:
    """A job's one cell, NULL for a job with none. Bare read: one seek."""
    return nu.Str(nuspace.Space.planes[job].cells.first())


def run_at(job: nu.StrArg) -> Run:
    """A run's state, at its job's cell, typed as :class:`Run`."""
    return nuspace.at.cell(id=job_cell(job)).state(Run)


def runs_of(root: nu.StrArg) -> nu.List:
    """``[[page, job, name], ...]``, every run under the MNIST plane, oldest first. Bare read.

    The pages the plane keeps (:class:`Runs`) that are still in the space.
    """
    pages = nuspace.at.plane(id=root).state(Runs).planes
    kept = nu.list(nu.If(pages.exists(), nu.list(pages.keys()), []))
    shown = kept.iter().filter(lambda p: nuspace.plane.exists(nu.Str(p)))

    def row(p: nu.Nu) -> nu.Nu:
        page = nu.Str(p)
        return nu.List.of(page, job_of(page), nuspace.plane.title(page))

    return shown.map(row).to_list()


def runs_change(root: nu.StrArg) -> nu.Nu:
    """A watch on the MNIST plane's runs: one launched (its list), one removed (its children)."""
    pages = nuspace.at.plane(id=root).state(Runs).planes
    return nu.OnAny(nuspace.Space.planes[root].children.on_change(), pages.on_change())


def status_of(job: nu.StrArg) -> nu.Str:
    """A run's status, ``down`` for one that says it trains but has no live run. Bare read."""
    said = run_at(job).status.fallback("starting")
    live = nu.If(nuspace.plane.exists(job), nuspace.plane_run.any_live(job), False)
    resting = (said == "done").or_(said == "stopped")
    return nu.Str(nu.If(resting.or_(live), said, "down"))
