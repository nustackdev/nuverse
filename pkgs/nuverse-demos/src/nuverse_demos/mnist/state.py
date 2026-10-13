"""The state a run keeps, and where the cells that show it find it.

A run is a headless job plane with one cell, ``<job>_main``. :class:`Run`
is that cell's state: what it trains with, how far it got, and its metrics.
The job writes it bare (its own state), every other cell reads and steers it
under the job's cell with ``ops.cell_state``. One class, imported by every
cell, so the slots are declared once.

The metric series are kh57 maps keyed by step: they grow with the run, and a
chart samples a few hundred points out of them at the same cost however long
it trained.

The models are here too, as bytes, under :attr:`Run.models`: ``latest``,
the whole checkpoint the run resumes from and pages read live, and ``best``,
the weights at its best test accuracy. Each with the step it was taken at and
the test accuracy it had (:class:`Model`). Nothing that draws reads ``blob``:
the bytes go from the job to the store to a reader, never to a browser.

The planes hang as the Launch plane makes them::

    MNIST                 the root, made from :data:`nuverse_demos.mnist.PLANE`
      Launch, Compare, Read
      <run>               a run page (ui), made_by ``mnist_run``
        train             the job (headless, mp), made_by ``mnist_job``
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space


__all__ = [
    "JOB",
    "PAGE",
    "SLOTS",
    "Model",
    "Pick",
    "Run",
    "job_cell",
    "job_of",
    "runs_of",
    "status_of",
]


#: ``made_by`` of a run page, and of the job under it.
PAGE, JOB = "mnist_run", "mnist_job"


#: The models a run keeps, by slot.
SLOTS = ("latest", "best")


class Model(nu.Shape):
    """A stored model: its bytes, the step they were taken at, and the test accuracy then (-1 for none yet)."""

    blob = nustd.kv.BytesRef.slot()
    step = nustd.kv.IntRef.slot()
    acc = nustd.kv.FloatRef.slot()


class Run(nuspace.CellState):
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


class Pick(nuspace.PlaneState):
    """The Compare plane's: the runs ticked in its table, by run page id."""

    pages = nustd.kv.ListRef.slot(str)


def _made_by(plane: nu.Nu) -> nu.Str:
    return Space.planes[nu.Str(plane)].props.made_by.fallback("")


def job_of(page: nu.StrArg) -> nu.Str:
    """The job under a run page, ``""`` while it has none. Bare read."""
    jobs = ops.children(page).iter().filter(lambda p: _made_by(p) == JOB)
    return nu.str(nu.First(jobs)).fallback("")


def job_cell(job: nu.StrArg) -> nu.Str:
    """A job's one cell: its id with ``_main`` after it."""
    return nu.Str(job) + "_main"


def runs_of(root: nu.StrArg) -> nu.List:
    """``[[page, job, name], ...]``, every run under the MNIST plane, oldest first. Bare read."""
    pages = ops.children(root).iter().filter(lambda p: _made_by(p) == PAGE)

    def row(p: nu.Nu) -> nu.Nu:
        page = nu.Str(p)
        return nu.List.of(page, job_of(page), ops.plane_title(page))

    return pages.map(row).to_list()


def status_of(job: nu.StrArg) -> nu.Str:
    """A run's status, ``down`` for one that says it trains but has no live run. Bare read."""
    said = ops.cell_state(job_cell(job), Run.status.fallback("starting"))
    live = Space.kernel.planes_running.contains(job)
    resting = (said == "done").or_(said == "stopped")
    return nu.Str(nu.If(resting.or_(live), said, "down"))
