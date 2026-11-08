"""nudemos mnist: the trainer on synthetic images, and the job loop on a real store.

No dataset download here: every trainer runs on ``data="synthetic"``, a few
hundred random images, on the cpu.
"""

from __future__ import annotations

import asyncio
import json

import pytest

import nu
import nuspace
import nuspace.places
from nudemos.mnist.interactions import Evaluate, Histograms, Predict, TrainChunk
from nudemos.mnist.job import job_source
from nudemos.mnist.state import Run
from nudemos.mnist.trainer import LAYERS, Trainer, load
from nuspace import Space


SYNTHETIC = {"data": "synthetic", "device": "cpu", "batch_size": 16}


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("NUVERSE_MNIST_DATA", str(tmp_path / "data"))


def _trainer(**hp) -> Trainer:
    trainer = Trainer(**{**SYNTHETIC, **hp})
    trainer.setup()
    return trainer


# --- the trainer -------------------------------------------------------------------------------


def test_a_chunk_returns_sane_metrics():
    m = _trainer().train(5, 1e-3)
    assert set(m) == {"loss", "acc", "steps", "seconds", "lr"}
    assert 0.0 < m["loss"] < 10.0
    assert 0.0 <= m["acc"] <= 1.0
    assert m["lr"] == 1e-3


def test_a_chunk_takes_the_lr_it_is_given():
    trainer = _trainer()
    assert trainer.train(1, 0.05)["lr"] == 0.05
    assert trainer.opt.param_groups[0]["lr"] == 0.05


def test_eval_predict_and_histograms():
    trainer = _trainer(samples=4)
    trainer.train(2, 1e-3)
    e = trainer.evaluate()
    assert 0.0 <= e["acc"] <= 1.0
    preds = trainer.predict()
    assert len(preds) == 4
    assert all(0 <= p < 10 and 0.0 <= c <= 1.0 and len(probs) == 10 for p, c, probs in preds)
    hists = json.loads(trainer.histograms())
    assert list(hists) == list(LAYERS)
    assert all(sum(h["w"]) == getattr(trainer.model, k).weight.numel() for k, h in hists.items())
    digits = trainer.digits()
    assert all(d["src"].startswith("data:image/png;base64,") for d in digits)


def test_a_checkpoint_round_trips_as_bytes():
    one = _trainer()
    one.train(3, 1e-3)
    blob = one.checkpoint(3)
    assert isinstance(blob, bytes)
    two = _trainer()
    assert two.restore(blob) == 3
    assert two.evaluate() == one.evaluate()
    assert two.gen.get_state().equal(one.gen.get_state())
    assert _trainer().restore(b"") == 0


def test_weights_are_the_model_alone_and_smaller():
    trainer = _trainer()
    trainer.train(1, 1e-3)
    weights, whole = trainer.weights(1), trainer.checkpoint(1)
    assert len(weights) < len(whole) / 2
    assert set(load(weights)) == {"model", "arch", "step"}
    assert load(whole)["arch"] == {"channels": 16, "dropout": 0.25}


async def test_the_interactions_call_the_provided_trainer():
    body = nu.let(
        TrainChunk(2, 1e-3),
        lambda m: nu.let(
            Evaluate(10),
            lambda e: nu.let(
                Predict(), lambda p: nu.let(Histograms(), lambda h: nu.List.of(m, e, p, h))
            ),
        ),
    )
    (m, e, p, h), _ = await nu.arun(nu.Provide(Trainer, SYNTHETIC, body))
    assert m["loss"] > 0
    assert 0.0 <= e["acc"] <= 1.0
    assert len(p) == 12
    assert set(json.loads(h)) == set(LAYERS)


# --- the job loop ------------------------------------------------------------------------------


async def _job(store, hp: dict, **every: int) -> str:
    """A headless job plane with its one cell, as Launch makes it. The cell id."""
    pace = {"chunk": 4, "look": 1, "eval": 2, "save": 2, **every}
    source = job_source({**SYNTHETIC, **hp}, **pace)
    add = nuspace.plane.add("job", backend="mp", spec="mnist_job") >> nuspace.cell.add(
        "job", source, id="job_main", name="train", fabrics=[]
    )
    await store.do(add)
    return "job_main"


async def _load(store, cell: str) -> nu.Nu:
    load = Space.cells[cell].prog.load(scope={"plane": "job", "cell": cell})
    return await store.run(nuspace.atomic(load))


async def _start(store, cell: str) -> asyncio.Task:
    term = nuspace.places.inside(await _load(store, cell), plane="job", cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx))


#: The run's state, where the job keeps it: its own cell's.
RUN = nuspace.at.cell(id="job_main").state(Run)


async def _until(check, timeout: float = 30.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not await check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.05)


async def test_the_job_trains_to_the_end_and_logs_into_kh57(store):
    cell = await _job(store, {"epochs": 1})
    await asyncio.wait_for(await _start(store, cell), 60)
    assert await store.read(RUN.status) == "done"
    total = await store.read(RUN.total)
    assert total == 12  # 192 images, 16 a batch, one epoch
    assert await store.read(RUN.step) == total
    losses = await store.read(nu.sorted(RUN.loss.sample(100)))
    assert [k for k, _ in losses] == [4, 8, 12]
    assert all(v > 0 for _, v in losses)
    assert [k for k, _ in await store.read(nu.sorted(RUN.test_acc.sample(100)))] == [8]
    assert [k for k, _ in await store.read(nu.sorted(RUN.hists.sample(100)))] == [
        0,
        4,
        8,
        12,
    ]
    assert len(await store.read(RUN.preds)) == 12
    final = await store.read(RUN.final)
    assert 0.0 <= final <= 1.0
    latest = await store.read(RUN.models["latest"].step)
    assert latest == 12
    assert await store.read(RUN.models["latest"].acc) == final
    blob = await store.read(RUN.models["latest"].blob)
    assert load(blob)["step"] == 12
    # The best weights are the ones at the best score seen, the final one among them.
    best = await store.read(RUN.models["best"].acc)
    assert best == max(final, await store.read(RUN.best))
    assert set(load(await store.read(RUN.models["best"].blob))) == {"model", "arch", "step"}
    assert (await store.read(RUN.hp))["batch_size"] == 16


async def test_the_last_chunk_stops_at_the_end(store):
    cell = await _job(store, {"epochs": 1}, chunk=5, look=10, eval=10, save=10)
    await asyncio.wait_for(await _start(store, cell), 60)
    assert [k for k, _ in await store.read(nu.sorted(RUN.loss.sample(100)))] == [5, 10, 12]
    assert await store.read(RUN.step) == 12


async def test_the_job_honors_stop_and_resumes_from_its_checkpoint(store):
    cell = await _job(store, {"epochs": 50})
    task = await _start(store, cell)

    async def stepped():
        return (await store.read(RUN.step.fallback(0))) >= 8

    await _until(stepped)
    await store.run(nuspace.atomic(RUN.stop.set(True)))
    await asyncio.wait_for(task, 30)
    assert await store.read(RUN.status) == "stopped"
    step = await store.read(RUN.step)
    assert 8 <= step < await store.read(RUN.total)
    assert await store.read(RUN.models["latest"].step) == step

    # A stopped run ends at once when it is started again.
    await asyncio.wait_for(await _start(store, cell), 10)
    assert await store.read(RUN.step) == step

    # Resumed: it loads the checkpoint and carries on from the step it saved.
    resume = RUN.stop.set(False) >> RUN.status.set("resuming") >> RUN.lr.set(0.01)
    await store.run(nuspace.atomic(resume))
    task = await _start(store, cell)

    async def moved():
        return (await store.read(RUN.step)) > step

    await _until(moved)
    await store.run(nuspace.atomic(RUN.stop.set(True)))
    await asyncio.wait_for(task, 30)
    lrs = await store.read(nu.sorted(RUN.lrs.sample(1000)))
    assert dict(lrs)[step + 4] == 0.01


def test_a_look_before_the_first_step_fixes_no_grad_range():
    trainer = _trainer()
    first = json.loads(trainer.histograms())
    assert all(sum(h["g"]) == 0 for h in first.values())
    trainer.train(2, 1e-3)
    later = json.loads(trainer.histograms())
    assert all(sum(h["g"]) == getattr(trainer.model, k).weight.numel() for k, h in later.items())
    assert all(h["gr"] != 1e-3 for h in later.values())
