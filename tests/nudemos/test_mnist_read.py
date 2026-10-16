"""nudemos mnist: models kept in the store, read back by a reader, and the Read page's shaping.

Offline: synthetic images, tiny runs, the cpu.
"""

from __future__ import annotations

import asyncio

import pytest

import nu
from nudemos.mnist import views
from nudemos.mnist.ink import blank
from nudemos.mnist.interactions import Classify, Holds, MnistDigit, Use
from nudemos.mnist.job import job_source
from nudemos.mnist.reader import KEEP, Reader, image_png
from nudemos.mnist.state import Run
from nudemos.mnist.trainer import Trainer
from nuspace import ops


SYNTHETIC = {"data": "synthetic", "device": "cpu", "batch_size": 16}

#: Runs on both store backends: the model bytes must round-trip through sqlite too.
STORES = ["memory", "sqlite"]


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("NUVERSE_MNIST_DATA", str(tmp_path / "data"))


def _trainer() -> Trainer:
    trainer = Trainer(**SYNTHETIC)
    trainer.setup()
    trainer.train(2, 1e-3)
    return trainer


def _digit() -> list:
    return Reader(data="synthetic").test_digit(0)["pixels"]


# --- the reader --------------------------------------------------------------------------------


def test_the_reader_reads_with_the_weights_it_was_given():
    trainer = _trainer()
    reader = Reader(data="synthetic")
    assert reader.classify(_digit()) == {}
    assert reader.use("a/latest/2", trainer.checkpoint(2)) == "a/latest/2"
    said = reader.classify(_digit())
    assert set(said) == {"digit", "probs", "model"}
    assert len(said["probs"]) == 10
    assert abs(sum(said["probs"]) - 1.0) < 1e-3
    assert said["digit"] == max(range(10), key=lambda k: said["probs"][k])
    # Weights alone read the same as the whole checkpoint.
    reader.use("a/best/2", trainer.weights(2))
    assert reader.classify(_digit())["probs"] == said["probs"]


def test_the_reader_loads_a_key_once_and_keeps_a_few():
    blob = _trainer().weights(2)
    reader = Reader(data="synthetic")
    reader.use("a/latest/2", blob)
    reader.use("a/latest/2", blob)
    assert reader.loads == 1
    assert reader.holds("a/latest/2")
    assert not reader.holds("a/latest/4")
    for i in range(KEEP + 1):
        reader.use(f"b/latest/{i}", blob)
    assert len(reader.models) == KEEP
    assert not reader.holds("a/latest/2")


def test_no_bytes_and_a_blank_field_read_as_nothing():
    reader = Reader(data="synthetic")
    reader.use("a/latest/2", _trainer().weights(2))
    assert reader.classify(blank()) == {}
    assert reader.classify([]) == {}
    assert reader.use("a/latest/-1", b"") == ""
    assert reader.classify(_digit()) == {}


def test_a_test_digit_is_a_field_and_a_label():
    d = Reader(data="synthetic").test_digit(3)
    assert len(d["pixels"]) == 28 and all(len(r) == 28 for r in d["pixels"])
    assert 0 <= d["label"] < 10
    assert image_png(d["pixels"]).startswith("data:image/png;base64,")


# --- from the store ----------------------------------------------------------------------------


async def _trained(store, parent: str = "") -> None:
    """A tiny run, trained to the end in plane ``job``, cell ``job_main``, under ``parent`` when given."""
    from nuspace.shapes import Reroot, Space
    from nustd.kv import Snapshot

    pace = {"chunk": 4, "look": 3, "eval": 2, "save": 2}
    await store.run(
        ops.add_plane("job", backend="mp", ui=False, made_by="mnist_job", parent=parent)
        >> ops.add_cell("job", job_source({**SYNTHETIC, "epochs": 1}, **pace), cell_id="job_main")
    )
    load = Space.cells["job_main"].prog.load(
        scope={"plane": "job", "cell": "job_main"}, rewrite=Reroot("job", "job_main")
    )
    term = nu.Frame(
        ops.Here, await store.run(Snapshot(load, scope=Space)), plane="job", cell="job_main"
    )
    await asyncio.wait_for(nu.arun(term, store.ctx), 60)


async def test_a_reader_reads_the_models_a_run_stored(store):
    await _trained(store)
    job, image = nu.Str("job"), _digit()

    def read(slot: str) -> nu.Nu:
        step = ops.snapshot(views.at(job, Run.models[slot].step))
        blob = ops.snapshot(views.at(job, Run.models[slot].blob))

        def classify(key: nu.Nu) -> nu.Nu:
            used = nu.let(
                Use(key, blob), lambda k: nu.let(Classify(image), lambda r: nu.List.of(k, r))
            )
            # Asked again for a key it holds, it answers without the bytes.
            return nu.let(used, lambda u: nu.let(Holds(key), lambda h: nu.List.of(u[0], u[1], h)))

        return nu.let(job + "/" + slot + "/" + nu.str(step), classify)

    body = nu.let(read("latest"), lambda a: nu.let(read("best"), lambda b: nu.List.of(a, b)))
    (latest, best), _ = await nu.arun(nu.Provide(Reader, {"data": "synthetic"}, body), store.ctx)
    assert latest[0] == "job/latest/12"
    assert len(latest[1]["probs"]) == 10
    assert latest[2] is True
    assert best[0].startswith("job/best/")
    assert len(best[1]["probs"]) == 10


async def test_a_test_digit_through_the_interaction():
    d, _ = await nu.arun(nu.Provide(Reader, {"data": "synthetic"}, MnistDigit()))
    assert 0 <= d["label"] < 10


async def test_the_shelf_lists_runs_with_their_models_and_no_bytes(store):
    from nudemos.mnist import PLANE
    from nudemos.mnist.run import PAGE

    await store.run(
        ops.create_plane(PLANE, plane_id="m")
        >> ops.create_plane(PAGE, parent="m", name="Run 1", plane_id="r")
    )
    await _trained(store, parent="r")
    ((job, name, view, models),) = await store.read(views.shelf("m"))
    assert (job, name, view["status"]) == ("job", "Run 1", "done")
    assert models["latest"]["step"] == 12
    assert models["best"]["step"] >= 0
    assert set(models["latest"]) == {"step", "acc"}
    c, _ = nu.run(views.choices([[job, name, view, models]]))
    assert c["first"] == "job"


# --- shaping -----------------------------------------------------------------------------------


def _view(status="training", best=0.9, final=-1.0) -> dict:
    return {"status": status, "best": best, "final": final}


def test_choices_lists_runs_newest_first_and_picks_one_with_a_model():
    none, some = {"latest": {"step": -1}}, {"latest": {"step": 200}}
    runs = [
        ["j1", "Run 1", _view("done", 0.97, 0.98), some],
        ["j2", "Run 2", _view("starting", 0.0), none],
    ]
    c, _ = nu.run(views.choices(runs))
    assert [o["value"] for o in c["options"]] == ["j2", "j1"]
    assert c["options"][0]["label"] == "Run 2 · starting · no checkpoint yet"
    assert c["options"][1]["label"] == "Run 1 · done · 98.0%"
    assert c["first"] == "j1"
    assert c["newest"] == "j2"


def test_answer_shapes_a_read():
    said = {"digit": 7, "probs": [0.01] * 7 + [0.91] + [0.01] * 2, "model": "j/latest/200"}
    a, _ = nu.run(views.answer(said, -1, "latest", {"step": 200, "acc": 0.95}))
    assert a["digit"] == "7"
    assert a["sure"] == "91% sure"
    assert len(a["bars"]) == 10
    assert a["line"] == "The latest checkpoint, step 200, 95.0% on the test set."
    a, _ = nu.run(views.answer(said, 3, "best", {"step": 200, "acc": -1.0}))
    assert a["sure"] == "91% sure · label 3, wrong"
    a, _ = nu.run(views.answer({}, -1, "latest", {"step": -1, "acc": -1.0}))
    assert a["digit"] == "-"
    assert a["line"].startswith("No checkpoint stored yet")
