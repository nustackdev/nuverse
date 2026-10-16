"""The run page: one training run, live, steered from here.

Launch makes one per run, and the run's job right under it. Every cell
finds the job as the page's child (:func:`~.views.with_job`) and reads the
job's state from there: the page holds no state of its own.

- ``status``: the run's name, status, hyperparameters, progress and tiles.
- ``steer``: the learning rate, live, and stop or resume.
- ``curves``: loss, accuracy and learning rate by step, from kh57 samples.
- ``digits``: twelve test digits and what the model reads in each.
- ``dists``: each layer's weights and gradients over training, as heatmaps.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["CURVES", "DIGITS", "DISTS", "PAGE", "STATUS", "STEER"]


_IMPORTS = """\
import nu
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws, snap
from nudemos.mnist import views
from nudemos.mnist.state import Run
from nudemos.mnist.views import at, with_job
"""


def _cell(body: str) -> str:
    return _IMPORTS + "\n\n" + body


STATUS = _cell("""\
class Head(nustd.ui.Row):
    pill = nustd.ui.StatusPillRef.slot()
    facts = nustd.ui.TextRef.slot()


class Tiles(nustd.ui.Grid):
    step = nustd.ui.StatRef.slot(label="Step")
    epoch = nustd.ui.StatRef.slot(label="Epoch")
    loss = nustd.ui.StatRef.slot(label="Train loss")
    acc = nustd.ui.StatRef.slot(label="Train accuracy")
    test = nustd.ui.StatRef.slot(label="Best test accuracy")
    speed = nustd.ui.StatRef.slot(label="Steps a second")


class View(nustd.ui.Column):
    head = Head.slot(gap=3, align="center")
    progress = nustd.ui.ProgressRef.slot()
    tiles = Tiles.slot(columns=6, min_width=130, gap=3)


def draw(s):
    t = View.tiles
    return (
        View.head.pill.set(s["status"], tone=s["tone"]) >> View.head.facts.set(s["facts"])
        >> View.progress.set(s["progress"], caption=s["caption"])
        >> t.step.set_value(s["step"]) >> t.epoch.set_value(s["epoch"]) >> t.loss.set_value(s["loss"])
        >> t.acc.set_value(s["acc"]) >> t.test.set(s["test"], label=s["test_label"]) >> t.speed.set_value(s["speed"])
    )


def follow(job):
    moves = [at(job, Run.step.on_change()), at(job, Run.status.on_change())]
    return redraws(moves, views.summary(views.run_view(job)), draw, every=3.0)


def out(plane):
    return with_job(plane, follow)
""")


STEER = _cell("""\
import math


class Steer(nustd.ui.Row):
    lr = nustd.ui.SliderRef.slot(min=-4.5, max=-1.0, step=0.05, label="Learning rate, live", show_value=False)
    shown = nustd.ui.BadgeRef.slot(variant="info")
    stop = nustd.ui.ButtonRef.slot(label="Stop", variant="secondary", icon="square")


class View(nustd.ui.Column):
    steer = Steer.slot(gap=4, align="center")


S = View.steer


@nu.host
def log10(x):
    return math.log10(x) if x > 0 else -3.0


@nu.host
def lr_of(v):
    return round(10 ** float(v), 7)


def button(status):
    resume = S.stop.set("Resume", variant="primary", icon="play", disabled=False)
    stop = S.stop.set("Stop", variant="secondary", icon="square", disabled=False)
    done = S.stop.set("Done", variant="ghost", icon="check", disabled=True)
    return nu.SwitchDo(status, {"stopped": resume, "done": done}, default=stop)


def press(job):
    # Stop asks the loop to save and end. Resume clears it and brings the job up again.
    status = snap(at(job, Run.status.fallback("")))
    stop = ops.atomic_state(at(job, Run.stop.set(True) >> Run.status.set("stopping")))
    resume = ops.atomic_state(at(job, Run.stop.set(False) >> Run.status.set("resuming"))) >> nuspace.supervise(job)
    return nu.let(status, lambda s: nu.IfDo(nu.Str(s) == "stopped", resume, nu.IfDo(nu.Str(s) == "training", stop)))


def show(lr):
    return S.lr.set(log10(lr)) >> S.shown.set(nu.Str("lr ") + nu.Str(views.lr_label(lr)))


def follow(job):
    # The slider writes the run's lr; the job reads it on its next chunk. Every tab follows.
    lr = at(job, Run.lr)
    steer = nu.let(lr_of(S.lr), lambda v: ops.atomic_state(lr.set(nu.Float(v))))
    status = at(job, Run.status)
    # Slots show in the order first written: slider, then its value, then the button.
    placed = S.lr.set(-3.0) >> S.shown.set("lr") >> S.stop.set("Stop")
    return placed >> nu.ParallelAsync(
        redraws([lr.on_change()], lr.fallback(0.0), show),
        redraws([status.on_change()], status.fallback(""), button),
        nu.ReactForever(S.lr.on_change(), steer),
        nu.ReactForever(S.stop.on_click(), press(job)),
    )


def out(plane):
    return with_job(plane, follow)
""")


CURVES = _cell("""\
#: Points sampled per series, however long the run, and the least seconds between repaints.
POINTS, EVERY = 300, 1.0


class Charts(nustd.ui.Grid):
    loss = nustd.ui.LineChart.slot(["train", "test"], title="Loss", height=240, symbols=False)
    acc = nustd.ui.LineChart.slot(["train", "test"], title="Accuracy", y_format="{value}%", height=240)
    lr = nustd.ui.LineChart.slot(title="Learning rate", step=True, height=240, option={"yAxis": {"type": "log"}})


class View(nustd.ui.Column):
    charts = Charts.slot(columns=3, min_width=280, gap=3)


def paint(job):
    def sample(series):
        return at(job, series.sample(POINTS))

    read = views.curves(*(sample(s) for s in (Run.loss, Run.test_loss, Run.acc, Run.test_acc, Run.lrs)))
    c = View.charts
    return nu.let(snap(read), lambda d: c.loss.set(d["loss"]) >> c.acc.set(d["acc"]) >> c.lr.set(d["lr"]))


def follow(job):
    # One pass at a time: steps landing while it paints merge into one more.
    return nu.ReconcileReactive(snap(at(job, Run.step.on_change())), paint(job) >> nu.Delay(EVERY), every=5.0)


def out(plane):
    return with_job(plane, follow)
""")


DIGITS = _cell("""\
#: Sample digits shown, as the job picks them.
N = 12


class Digit(nustd.ui.Card):
    image = nustd.ui.ImageRef.slot(width=84, height=84, fit="contain", rounded=True)
    verdict = nustd.ui.BadgeRef.slot()
    probs = nustd.ui.BarChart.slot(height=64, tooltip=False, option={
        "grid": {"left": 0, "right": 0, "top": 2, "bottom": 14},
        "yAxis": {"show": False, "max": 100}, "xAxis": {"axisLabel": {"fontSize": 9}}, "animation": False,
    })


Digits = type("Digits", (nustd.ui.Grid,), {f"d{i}": Digit.slot() for i in range(N)})


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    digits = Digits.slot(columns=6, min_width=120, gap=2)


def card(i, c):
    d = getattr(View.digits, f"d{i}")
    shown = d.image.set(c["src"], alt=c["title"]) >> d.verdict.set(c["verdict"], variant=c["variant"])
    return d.set_title(c["title"]) >> shown >> d.probs.set(c["probs"])


def draw(v):
    cards = nu.List(v["cards"])
    each = [nu.IfDo(cards.len() > i, nu.let(cards[i], lambda c, i=i: card(i, c))) for i in range(N)]
    return View.head.set(v["head"]) >> nu.Sequential(*each)


def follow(job):
    # Each look the job takes moves ``looked``: the digits and what it reads in them.
    read = views.cards(at(job, Run.digits.fallback([])), at(job, Run.preds.fallback([])))
    return redraws([at(job, Run.looked.on_change())], read, draw)


def out(plane):
    return with_job(plane, follow)
""")


DISTS = _cell("""\
from nudemos.mnist.trainer import LAYERS

#: Histogram snapshots drawn, sampled over the whole run, and the least seconds between repaints.
SNAPSHOTS, EVERY = 48, 2.0


#: A heatmap per layer: steps along x, bins along y, no cell borders, every eighth bin labelled.
SHAPE = dict(legend=False, height=180, x_label="step", option={
    "xAxis": {"axisLabel": {"show": False}}, "yAxis": {"axisLabel": {"interval": 7}},
    "series": [{"itemStyle": {"borderWidth": 0}}],
})


def maps(kind):
    return type(kind, (nustd.ui.Grid,), {l: nustd.ui.HeatmapChart.slot(title=l, **SHAPE) for l in LAYERS})


class Weights(nustd.ui.Card):
    maps = maps("W").slot(columns=4, min_width=200, gap=2)


class Grads(nustd.ui.Card):
    maps = maps("G").slot(columns=4, min_width=200, gap=2)


class View(nustd.ui.Column):
    w = Weights.slot(title="Weights over training", subtitle="each layer binned every 50 steps, log counts")
    g = Grads.slot(title="Gradients over training", subtitle="the last batch's, same bins")


def paint(job):
    def draw(h):
        return nu.Sequential(*(getattr(getattr(View, k).maps, l).merge(h[k][l]) for k in "wg" for l in LAYERS))

    return nu.let(snap(views.heatmaps(at(job, Run.hists.sample(SNAPSHOTS)))), draw)


def follow(job):
    # The job bins the layers on each look it takes.
    looked = snap(at(job, Run.looked.on_change()))
    return nu.ReconcileReactive(looked, paint(job) >> nu.Delay(EVERY), every=10.0)


def out(plane):
    return with_job(plane, follow)
""")


PAGE = Plane(
    "mnist_run",
    "Run",
    icon="activity",
    description="One MNIST training run: live curves, digits and distributions, steered from here.",
    meta={"editable": True, "full_width": True},
    cells=(
        ("status", STATUS),
        ("steer", STEER),
        ("curves", CURVES),
        ("digits", DIGITS),
        ("dists", DISTS),
    ),
    backend="async",
)
