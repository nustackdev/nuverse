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
import nuspace
from nudemos.mnist.interactions import (
    Checkpoint, Digits, Evaluate, Histograms, Info, Predict, Restore, TrainChunk, Weights,
)
from nudemos.mnist.state import Run
from nudemos.mnist.trainer import Trainer

#: This run's state: the job's own cell's.
RUN = nuspace.here(Run)

#: This run's hyperparameters, baked in at launch.
HP = {}

#: Steps per chunk, and chunks between a look, an eval and a save.
CHUNK, LOOK, EVAL, SAVE = 25, 2, 8, 8

#: Test images scored on every eval. The last eval scores them all.
SCORED = 2000

#: Chunks at the start of a run that each save, untrained to trained in a few steps.
EARLY = 4

#: The two models the run keeps: the latest checkpoint, and the weights at the best test score.
LATEST, BEST = RUN.models["latest"], RUN.models["best"]


def higher(a, b):
    return nu.Float(nu.If(a > b, a, b))


def logged(m):
    # One commit per chunk: the series, the step, the pace.
    def write(step, now):
        pace = nu.float(m["steps"]) / higher(nu.Float(now) - RUN.beat.fallback(0.0), 1e-3)
        return (
            RUN.loss.set_item(step, m["loss"]) >> RUN.acc.set_item(step, m["acc"])
            >> RUN.lrs.set_item(step, m["lr"]) >> RUN.now.set(m) >> RUN.step.set(step)
            >> RUN.speed.set(nu.If(RUN.speed.fallback(0.0) > 0.0, RUN.speed * 0.7 + pace * 0.3, pace))
            >> RUN.beat.set(nu.Float(now))
        )

    return nu.let(RUN.step.fallback(0) + nu.int(m["steps"]), lambda s: nu.let(nustd.time.time(), lambda t: write(s, t)))


def look(step):
    def keep(h, p):
        return nuspace.atomic(RUN.hists.set_item(step, h) >> RUN.preds.set(p) >> RUN.looked.set(step))

    return nu.let(Histograms(), lambda h: nu.let(Predict(), lambda p: keep(h, p)))


def kept(model, blob, step, acc):
    return model.blob.set(blob) >> model.step.set(step) >> model.acc.set(acc)


def bested(step, acc):
    # The weights, when this score beats the best one kept.
    better = nuspace.atomic(nu.Float(acc) > BEST.acc.fallback(-1.0))
    stored = nu.let(Weights(step), lambda w: nuspace.atomic(kept(BEST, w, step, acc)))
    return nu.IfDo(better, stored)


def scored(step, limit):
    def keep(e):
        best = higher(RUN.best.fallback(0.0), nu.Float(e["acc"]))
        return (
            RUN.test_loss.set_item(step, e["loss"]) >> RUN.test_acc.set_item(step, e["acc"])
            >> RUN.tested.set(e["acc"]) >> RUN.best.set(best)
        )

    return nu.let(Evaluate(limit), lambda e: nuspace.atomic(keep(e)) >> bested(step, e["acc"]))


def saved(step):
    # The whole checkpoint, with the latest test score it had.
    return nu.let(Checkpoint(step), lambda b: nuspace.atomic(kept(LATEST, b, step, RUN.tested.fallback(-1.0))))


def every(step, chunks):
    return step % (CHUNK * chunks) == 0


def turn():
    # The last chunk stops at the run's end. The lr is read now: the slider may have moved it.
    n = nuspace.atomic(nu.Int(nu.If(RUN.total - RUN.step < CHUNK, RUN.total - RUN.step, CHUNK)))
    chunk = nu.let(TrainChunk(n, nuspace.atomic(RUN.lr.fallback(HP["lr"]))), lambda m: nuspace.atomic(logged(m)))

    def after(s):
        step = nu.Int(s)
        return (
            nu.IfDo(every(step, LOOK), look(step))
            >> nu.IfDo(every(step, EVAL), scored(step, SCORED))
            >> nu.IfDo(every(step, SAVE).or_(step <= CHUNK * EARLY), saved(step))
        )

    return chunk >> nu.let(nuspace.atomic(RUN.step), after)


def started(info, step, digits):
    # Where it left off, or from the top: hparams, the trainer's facts, step 0.
    return nuspace.atomic(
        RUN.hp.set(HP) >> RUN.info.set(info) >> RUN.lr.set(RUN.lr.fallback(HP["lr"]))
        >> RUN.total.set(info["per_epoch"] * HP["epochs"]) >> RUN.step.set(step)
        >> RUN.started.set(RUN.started.fallback(nustd.time.time())) >> RUN.digits.set(digits)
        >> RUN.beat.set(nustd.time.time()) >> RUN.status.set("training")
    )


def finish():
    step = nuspace.atomic(RUN.step)
    stopped = nuspace.atomic(RUN.status.set("stopped"))

    def ended(e):
        acc = nu.Float(e["acc"])
        scores = nuspace.atomic(RUN.final.set(acc) >> RUN.tested.set(acc) >> LATEST.acc.set(acc))
        return scores >> bested(step, acc) >> nuspace.atomic(RUN.status.set("done"))

    return saved(step) >> nu.IfDo(nuspace.atomic(RUN.stop.fallback(False)), stopped, nu.let(Evaluate(0), ended))


def train():
    restored = Restore(nuspace.atomic(LATEST.blob.fallback(b"")))
    begin = nu.let(Info(), lambda i: nu.let(restored, lambda s: nu.let(Digits(), lambda d: started(i, s, d))))
    going = nuspace.atomic(RUN.stop.fallback(False).not_().and_(RUN.step.fallback(0) < RUN.total.fallback(1)))
    # A first look before the first step, and a fresh run's untrained model saved: the digits start out read wrong.
    first = look(nuspace.atomic(RUN.step)) >> nu.IfDo(nuspace.atomic(RUN.step == 0), saved(0))
    return nu.Provide(Trainer, HP, begin >> first >> nu.WhileDo(going, turn()) >> finish())


def out(cell):
    said = RUN.status.fallback("")
    resting = nuspace.atomic((said == "done").or_(said == "stopped"))
    fresh = nuspace.atomic(RUN.status.set("starting"))
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
