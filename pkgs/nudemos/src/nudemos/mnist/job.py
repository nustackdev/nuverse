"""The job: one run's training loop, a Nu program over the trainer.

Nu owns the loop, torch owns the step. :data:`TRAIN` provides a
:class:`~nudemos.mnist.trainer.Trainer` and loops in Nu: a chunk of steps
at the learning rate the run's state holds now, its metrics written into
kh57 series in one short commit, then every few chunks the weights and grads
binned, the sample digits predicted, the test set scored and a checkpoint
saved. It stops when the run's ``stop`` flag is set or its steps are done.

Checkpoints go into the run's state as bytes (:attr:`~.state.Run.models`):
``latest``, everything to resume from, on every save; ``best``, the weights
alone, whenever a test score beats the best one kept. A fresh run also saves
before its first step and after each of its first few chunks, so a page
reading ``latest`` sees the model go from guessing to reading.

Restarted (a crash, the space reopened), it restores ``latest`` and carries
on from the step it was saved at. A run that is done or stopped ends at once.

:func:`job_source` is the cell the Launch plane writes for a run, its
hyperparameters baked in as :data:`HP`.
"""

from __future__ import annotations

from typing import Any

import nu


__all__ = ["DEFAULTS", "EVERY", "TRAIN", "job_source"]


#: What a run trains with when the form leaves something out.
DEFAULTS: dict[str, Any] = {
    "lr": 1e-3,
    "batch_size": 64,
    "epochs": 3,
    "channels": 16,
    "dropout": 0.25,
    "optimizer": "adam",
    "seed": 0,
}

#: Steps per chunk, and chunks between a look (histograms, predictions), an eval and a save.
EVERY: dict[str, int] = {"chunk": 25, "look": 2, "eval": 8, "save": 8}


TRAIN = """\
import nu
import nustd.time
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.mnist.interactions import (
    Checkpoint, Digits, Evaluate, Histograms, Info, Predict, Restore, TrainChunk, Weights,
)
from nudemos.mnist.state import Run
from nudemos.mnist.trainer import Trainer

#: This run's hyperparameters, baked in at launch.
HP = {}

#: Steps per chunk, and chunks between a look, an eval and a save.
CHUNK, LOOK, EVAL, SAVE = 25, 2, 8, 8

#: Test images scored on every eval. The last eval scores them all.
SCORED = 2000

#: Chunks at the start of a run that each save, untrained to trained in a few steps.
EARLY = 4

#: The two models the run keeps: the latest checkpoint, and the weights at the best test score.
LATEST, BEST = Run.models["latest"], Run.models["best"]


def higher(a, b):
    return nu.Float(nu.If(a > b, a, b))


def logged(m):
    # One commit per chunk: the series, the step, the pace.
    def write(step, now):
        pace = nu.float(m["steps"]) / higher(nu.Float(now) - Run.beat.fallback(0.0), 1e-3)
        return (
            Run.loss.set_item(step, m["loss"]) >> Run.acc.set_item(step, m["acc"])
            >> Run.lrs.set_item(step, m["lr"]) >> Run.now.set(m) >> Run.step.set(step)
            >> Run.speed.set(nu.If(Run.speed.fallback(0.0) > 0.0, Run.speed * 0.7 + pace * 0.3, pace))
            >> Run.beat.set(nu.Float(now))
        )

    return nu.let(Run.step.fallback(0) + nu.int(m["steps"]), lambda s: nu.let(nustd.time.time(), lambda t: write(s, t)))


def look(step):
    def keep(h, p):
        return ops.atomic_state(Run.hists.set_item(step, h) >> Run.preds.set(p) >> Run.looked.set(step))

    return nu.let(Histograms(), lambda h: nu.let(Predict(), lambda p: keep(h, p)))


def kept(model, blob, step, acc):
    return model.blob.set(blob) >> model.step.set(step) >> model.acc.set(acc)


def bested(step, acc):
    # The weights, when this score beats the best one kept.
    better = snap(nu.Float(acc) > BEST.acc.fallback(-1.0))
    stored = nu.let(Weights(step), lambda w: ops.atomic_state(kept(BEST, w, step, acc)))
    return nu.IfDo(better, stored)


def scored(step, limit):
    def keep(e):
        best = higher(Run.best.fallback(0.0), nu.Float(e["acc"]))
        return (
            Run.test_loss.set_item(step, e["loss"]) >> Run.test_acc.set_item(step, e["acc"])
            >> Run.tested.set(e["acc"]) >> Run.best.set(best)
        )

    return nu.let(Evaluate(limit), lambda e: ops.atomic_state(keep(e)) >> bested(step, e["acc"]))


def saved(step):
    # The whole checkpoint, with the latest test score it had.
    return nu.let(Checkpoint(step), lambda b: ops.atomic_state(kept(LATEST, b, step, Run.tested.fallback(-1.0))))


def every(step, chunks):
    return step % (CHUNK * chunks) == 0


def turn():
    # The last chunk stops at the run's end. The lr is read now: the slider may have moved it.
    n = snap(nu.Int(nu.If(Run.total - Run.step < CHUNK, Run.total - Run.step, CHUNK)))
    chunk = nu.let(TrainChunk(n, snap(Run.lr.fallback(HP["lr"]))), lambda m: ops.atomic_state(logged(m)))

    def after(s):
        step = nu.Int(s)
        return (
            nu.IfDo(every(step, LOOK), look(step))
            >> nu.IfDo(every(step, EVAL), scored(step, SCORED))
            >> nu.IfDo(every(step, SAVE).or_(step <= CHUNK * EARLY), saved(step))
        )

    return chunk >> nu.let(snap(Run.step), after)


def started(info, step, digits):
    # Where it left off, or from the top: hparams, the trainer's facts, step 0.
    return ops.atomic_state(
        Run.hp.set(HP) >> Run.info.set(info) >> Run.lr.set(Run.lr.fallback(HP["lr"]))
        >> Run.total.set(info["per_epoch"] * HP["epochs"]) >> Run.step.set(step)
        >> Run.started.set(Run.started.fallback(nustd.time.time())) >> Run.digits.set(digits)
        >> Run.beat.set(nustd.time.time()) >> Run.status.set("training")
    )


def finish():
    step = snap(Run.step)
    stopped = ops.atomic_state(Run.status.set("stopped"))

    def ended(e):
        acc = nu.Float(e["acc"])
        scores = ops.atomic_state(Run.final.set(acc) >> Run.tested.set(acc) >> LATEST.acc.set(acc))
        return scores >> bested(step, acc) >> ops.atomic_state(Run.status.set("done"))

    return saved(step) >> nu.IfDo(snap(Run.stop.fallback(False)), stopped, nu.let(Evaluate(0), ended))


def train():
    restored = Restore(snap(LATEST.blob.fallback(b"")))
    begin = nu.let(Info(), lambda i: nu.let(restored, lambda s: nu.let(Digits(), lambda d: started(i, s, d))))
    going = snap(Run.stop.fallback(False).not_().and_(Run.step.fallback(0) < Run.total.fallback(1)))
    # A first look before the first step, and a fresh run's untrained model saved: the digits start out read wrong.
    first = look(snap(Run.step)) >> nu.IfDo(snap(Run.step == 0), saved(0))
    return nu.Provide(Trainer, HP, begin >> first >> nu.WhileDo(going, turn()) >> finish())


def out(cell):
    said = Run.status.fallback("")
    resting = snap((said == "done").or_(said == "stopped"))
    fresh = ops.atomic_state(Run.status.set("starting"))
    return nu.IfDo(resting, nu.Noop(), fresh >> train())
"""


def job_source(hp: dict[str, Any], **every: int) -> str:
    """:data:`TRAIN` with ``hp`` over :data:`DEFAULTS` baked in, and ``every`` over :data:`EVERY`."""
    baked = {**DEFAULTS, **{k: v for k, v in hp.items() if v is not None}}
    pace = {**EVERY, **every}
    lines = "".join(f"    {k!r}: {v!r},\n" for k, v in baked.items())
    return TRAIN.replace("HP = {}", "HP = {\n" + lines + "}").replace(
        "CHUNK, LOOK, EVAL, SAVE = 25, 2, 8, 8",
        f"CHUNK, LOOK, EVAL, SAVE = {pace['chunk']}, {pace['look']}, {pace['eval']}, {pace['save']}",
    )


#: ``job_source`` as a term, for a cell that launches runs from what a form says.
launch_source = nu.host(job_source, name="JobSource")
