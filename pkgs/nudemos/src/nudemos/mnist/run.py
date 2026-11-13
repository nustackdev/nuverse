"""The run page: one training run, live, steered from here.

Launch makes one per run, and the run's job right under it. Every cell
finds the job by the id the page keeps (:func:`~.views.with_job`) and reads
the job's state from there: the page holds nothing else.

- ``status``: the run's name, status, hyperparameters, progress and tiles.
- ``steer``: the learning rate, live, and stop or resume.
- ``curves``: loss, accuracy and learning rate by step, from kh57 samples.
- ``digits``: twelve test digits and what the model reads in each.
- ``dists``: each layer's weights and gradients over training, as heatmaps.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["CURVES", "DIGITS", "DISTS", "PAGE", "STATUS", "STEER"]


_IMPORTS = """\
import nu
import nustd.ui
import nuspace
import nuspace.system.supervisor
from nudemos.mnist import views
from nudemos.mnist.state import run_at
from nudemos.mnist.views import with_job
"""


def _cell(body: str) -> str:
    return _IMPORTS + "\n\n" + body


STATUS = _cell("""\
KEYS = {
    "step": "Step",
    "epoch": "Epoch",
    "loss": "Train loss",
    "acc": "Train accuracy",
    "test": "Best test accuracy",
    "speed": "Steps a second",
}


class View(nu.Shape):
    run = nustd.ui.PageSectionRef.slot(title="The run", description="how it was set up, how far it is, how it does")


pill = View.run.actions["pill"].to(nustd.ui.StatusPillRef)
facts = View.run["facts"].to(nustd.ui.TextRef.slot(tone="muted"))
progress = View.run["progress"].to(nustd.ui.ProgressRef)
tiles = View.run["tiles"].to(nustd.ui.GridRef.slot(max_columns=6, min_cell_width=140, gap=3))


def tile(k):
    return tiles[k].to(nustd.ui.CardRef.slot(size="sm"))[0].to(nustd.ui.StatRef.slot(label=KEYS[k]))


def draw(s):
    return (
        pill.set(s["status"], tone=s["tone"]) >> facts.set(s["facts"])
        >> progress.set(s["progress"], caption=s["caption"])
        >> tile("step").set_value(s["step"]) >> tile("epoch").set_value(s["epoch"]) >> tile("loss").set_value(s["loss"])
        >> tile("acc").set_value(s["acc"]) >> tile("test").set(s["test"], label=s["test_label"]) >> tile("speed").set_value(s["speed"])
    )


def follow(job):
    moves = [run_at(job).step.on_change(), run_at(job).status.on_change()]
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*moves)), nu.let(nuspace.atomic(views.summary(views.run_view(job))), draw), every=3.0)


def out(plane):
    return with_job(plane, follow)
""")


STEER = _cell("""\
import math


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Steer", subtitle="the job reads the learning rate on its next chunk")


row = View.card["steer"].to(nustd.ui.RowRef.slot(gap=4, align="center", grow={"lr": 1}))
lr_slider = row["lr"].to(nustd.ui.SliderRef.slot(min=-4.5, max=-1.0, step=0.05, label="Learning rate, live", show_value=False))
lr_badge = row["shown"].to(nustd.ui.BadgeRef.slot(variant="info"))
stop = View.card.actions["stop"].to(nustd.ui.ButtonRef.slot(label="Stop", variant="secondary", icon="square"))


@nu.host
def log10(x):
    return math.log10(x) if x > 0 else -3.0


@nu.host
def lr_of(v):
    return round(10 ** float(v), 7)


def button(status):
    resume = stop.set("Resume", variant="primary", icon="play", disabled=False)
    halt = stop.set("Stop", variant="secondary", icon="square", disabled=False)
    done = stop.set("Done", variant="ghost", icon="check", disabled=True)
    return nu.SwitchDo(status, {"stopped": resume, "done": done}, default=halt)


def press(job):
    # Stop asks the loop to save and end. Resume clears it and brings the job up again.
    run = run_at(job)
    status = nuspace.atomic(run.status.fallback(""))
    halt = nuspace.atomic(run.stop.set(True) >> run.status.set("stopping"))
    up = nuspace.system.supervisor.supervise(job, policy=nuspace.system.supervisor.ON_FAILURE, exists_ok=True)
    resume = nuspace.atomic(run.stop.set(False) >> run.status.set("resuming")) >> nuspace.atomic(up)
    return nu.let(status, lambda s: nu.IfDo(nu.Str(s) == "stopped", resume, nu.IfDo(nu.Str(s) == "training", halt)))


def show(lr):
    return lr_slider.set(log10(lr)) >> lr_badge.set(nu.Str("lr ") + nu.Str(views.lr_label(lr)))


def follow(job):
    # The slider writes the run's lr; the job reads it on its next chunk. Every tab follows.
    lr = run_at(job).lr
    steer = nu.let(lr_of(lr_slider), lambda v: nuspace.atomic(lr.set(nu.Float(v))))
    status = run_at(job).status
    return stop.init() >> nu.ParallelAsync(
        nu.Reconcile(nuspace.atomic(lr.on_change()), nu.let(nuspace.atomic(lr.fallback(0.0)), show)),
        nu.Reconcile(nuspace.atomic(status.on_change()), nu.let(nuspace.atomic(status.fallback("")), button)),
        nu.ReactEvery(lr_slider.on_change(), steer),
        nu.ReactEvery(stop.on_click(), press(job)),
    )


def out(plane):
    return with_job(plane, follow)
""")


CURVES = _cell("""\
#: Points sampled per series, however long the run, and the least seconds between repaints.
POINTS, EVERY = 300, 1.0


#: Each chart: its card's title, then the chart.
CHARTS = {
    "loss": ("Loss", nustd.ui.LineChart.slot(["train", "test"], height=240, symbols=False)),
    "acc": ("Accuracy", nustd.ui.LineChart.slot(["train", "test"], y_format="{value}%", height=240)),
    "lr": ("Learning rate", nustd.ui.LineChart.slot(step=True, height=240, option={"yAxis": {"type": "log"}})),
}


class View(nu.Shape):
    charts = nustd.ui.GridRef.slot(max_columns=3, min_cell_width=320, gap=4)


charts = {k: View.charts[k].to(nustd.ui.CardRef.slot(title=title, size="sm"))[k].to(chart) for k, (title, chart) in CHARTS.items()}


def paint(job):
    r = run_at(job)
    read = views.curves(*(s.sample(POINTS) for s in (r.loss, r.test_loss, r.acc, r.test_acc, r.lrs)))
    return nu.let(nuspace.atomic(read), lambda d: nu.Sequential(*(c.set(d[k]) for k, c in charts.items())))


def follow(job):
    # One pass at a time: steps landing while it paints merge into one more.
    return nu.Reconcile(nuspace.atomic(run_at(job).step.on_change()), paint(job) >> nu.Delay(EVERY), every=5.0)


def out(plane):
    return with_job(plane, follow)
""")


DIGITS = _cell("""\
PROBS = {
    "grid": {"left": 0, "right": 0, "top": 2, "bottom": 14},
    "yAxis": {"show": False, "max": 100}, "xAxis": {"axisLabel": {"fontSize": 9}}, "animation": False,
}


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Test digits", subtitle="Waiting for the first look")


digits = View.card["digits"].to(nustd.ui.GridRef.slot(max_columns=6, min_cell_width=120, gap=2))


def card(i, c):
    d = digits[i].to(nustd.ui.CardRef.slot(size="sm"))
    image = d["image"].to(nustd.ui.ImageRef.slot(width=84, height=84, fit="contain", radius="md"))
    verdict = d["verdict"].to(nustd.ui.BadgeRef.slot(size="sm"))
    probs = d["probs"].to(nustd.ui.BarChart.slot(height=64, tooltip=False, option=PROBS))
    shown = image.set(c["src"], alt=c["title"]) >> verdict.set(c["verdict"], variant=c["variant"])
    return d.set_title(c["title"]) >> shown >> probs.set(c["probs"])


def draw(v):
    cards = nu.List(v["cards"])
    each = nu.ForRangeDo(0, cards.len(), lambda i: card(i, nu.Dict(cards[i])))
    return View.card.set_subtitle(v["head"]) >> each >> digits.truncate(cards.len())


def follow(job):
    # Each look the job takes moves ``looked``: the digits and what it reads in them.
    read = views.cards(run_at(job).digits.fallback([]), run_at(job).preds.fallback([]))
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*[run_at(job).looked.on_change()])), nu.let(nuspace.atomic(read), draw))


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


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=4)


CARDS = {
    "w": View.page["w"].to(nustd.ui.CardRef.slot(title="Weights over training", subtitle="each layer binned every 50 steps, log counts")),
    "g": View.page["g"].to(nustd.ui.CardRef.slot(title="Gradients over training", subtitle="the last batch's, same bins")),
}


def heatmap(card, layer):
    maps = card["maps"].to(nustd.ui.GridRef.slot(max_columns=4, min_cell_width=200, gap=2))
    return maps[layer].to(nustd.ui.HeatmapChart.slot(title=layer, **SHAPE))


MAPS = {k: {l: heatmap(card, l) for l in LAYERS} for k, card in CARDS.items()}


def paint(job):
    def draw(h):
        return nu.Sequential(*(MAPS[k][l].merge(h[k][l]) for k in "wg" for l in LAYERS))

    return nu.let(nuspace.atomic(views.heatmaps(run_at(job).hists.sample(SNAPSHOTS))), draw)


def follow(job):
    # The job bins the layers on each look it takes.
    looked = nuspace.atomic(run_at(job).looked.on_change())
    return nu.Reconcile(looked, paint(job) >> nu.Delay(EVERY), every=10.0)


def out(plane):
    return with_job(plane, follow)
""")


PAGE = PlaneSpec(
    "mnist_run",
    "Run",
    icon="activity",
    description="One MNIST training run: live curves, digits and distributions, steered from here.",
    web=WebOptions(editable=True, width="board"),
    cells=(
        ("status", STATUS),
        ("steer", STEER),
        ("curves", CURVES),
        ("digits", DIGITS),
        ("dists", DISTS),
    ),
    backend="async",
)
