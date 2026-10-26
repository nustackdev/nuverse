"""What the cells read and draw: a run's state as terms, and plain Python that shapes it.

The terms reach a run's state from any plane (:func:`at`), wait for a run
page's job (:func:`with_job`), gather what a view shows in one read
(:func:`run_view`, :func:`board`). The ``@nu.host`` functions turn what
was read into what a widget takes: tile strings, chart series, heatmap
cells, prose. They are plain Python, so cells stay short and the shaping
is testable on its own.
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING, Any

import nu
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import snap

from .ink import sample, strokes_of, strokes_to_image
from .reader import image_png
from .state import Run, job_cell, job_of, runs_of, status_of
from .trainer import LAYERS


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "TONES",
    "answer",
    "at",
    "board",
    "cards",
    "choices",
    "curves",
    "drawn",
    "heatmaps",
    "ink",
    "leader",
    "lr_label",
    "lr_text",
    "overlay",
    "picture",
    "plan",
    "rows",
    "run_view",
    "series",
    "shelf",
    "summary",
    "with_job",
]


#: The pill tone for each status.
TONES = {
    "starting": "info",
    "resuming": "info",
    "training": "ok",
    "stopping": "warn",
    "stopped": "neutral",
    "done": "ok",
    "down": "danger",
}

#: Points sampled per curve, and histogram snapshots per heatmap.
POINTS, SNAPSHOTS = 300, 40


# --- terms -------------------------------------------------------------------------------------


def at(job: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`~.state.Run`, landed on ``job``'s cell. Bare."""
    return ops.cell_state(job_cell(job), term)


def with_job(plane: nu.StrArg, body: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``body(job)`` once the run page ``plane`` has its job: Launch makes it right after the page."""
    found = snap(job_of(plane) != "")
    wait = nu.WaitReactive(snap(Space.planes[plane].children.on_change()), found, every=2.0)
    return wait >> nu.let(snap(job_of(plane)), lambda job: body(nu.Str(job)))


def run_view(job: nu.StrArg) -> nu.Nu:
    """Everything a run's tiles and steering show, in one dict. Bare."""
    r = Run
    return nu.Dict.of(
        status=status_of(job),
        hp=at(job, r.hp.fallback({})),
        info=at(job, r.info.fallback({})),
        lr=at(job, r.lr.fallback(0.0)),
        step=at(job, r.step.fallback(0)),
        total=at(job, r.total.fallback(0)),
        now=at(job, r.now.fallback({})),
        best=at(job, r.best.fallback(0.0)),
        final=at(job, r.final.fallback(-1.0)),
        speed=at(job, r.speed.fallback(0.0)),
        started=at(job, r.started.fallback(0.0)),
        beat=at(job, r.beat.fallback(0.0)),
    )


def board(root: nu.StrArg) -> nu.Nu:
    """Every run under the MNIST plane as ``[page, name, view]``, oldest first. Bare."""

    def row(r: nu.Nu) -> nu.Nu:
        run = nu.List(r)
        return nu.List.of(run[0], run[2], run_view(nu.Str(run[1])))

    return runs_of(root).iter().map(row).to_list()


# --- shaping -----------------------------------------------------------------------------------


def lr_text(lr: float) -> str:
    """A learning rate the way people write one: ``3e-4``, ``1e-3``, ``0.01``."""
    if not lr:
        return "-"
    if lr >= 0.01:
        return f"{lr:g}"
    mant, exp = f"{lr:.1e}".split("e")
    mant = mant.rstrip("0").rstrip(".")
    return f"{mant}e{int(exp)}"


#: :func:`lr_text` as a term, for a cell drawing a learning rate it read.
lr_label = nu.host(lr_text, name="LrLabel")


def _pct(x: float | None) -> str:
    return "-" if x is None or x < 0 else f"{100 * x:.1f}%"


def _hp_line(hp: dict, info: dict) -> str:
    if not hp:
        return ""
    parts = [
        hp.get("optimizer", ""),
        f"batch {hp.get('batch_size')}",
        f"{hp.get('epochs')} epochs",
        f"{hp.get('channels')} channels",
        f"dropout {hp.get('dropout')}",
    ]
    if info:
        parts += [f"{info.get('params', 0) / 1000:.0f}k params", info.get("device", "")]
    return " · ".join(p for p in parts if p)


@nu.host
def summary(v: dict) -> dict:
    """A :func:`run_view` as the strings the run page's header and tiles show."""
    hp, info, now = v["hp"] or {}, v["info"] or {}, v["now"] or {}
    step, total = v["step"], v["total"]
    per = info.get("per_epoch") or 0
    epoch = f"{step / per:.2f}" if per else "-"
    epochs = hp.get("epochs", "-")
    status = v["status"]
    return {
        "status": status,
        "tone": TONES.get(status, "neutral"),
        "facts": _hp_line(hp, info),
        "progress": (step / total) if total else 0.0,
        "caption": f"step {step:,} of {total:,}" if total else "starting",
        "step": f"{step:,}",
        "epoch": f"{epoch} / {epochs}",
        "loss": f"{now['loss']:.4f}" if "loss" in now else "-",
        "acc": _pct(now.get("acc")),
        "test": _pct(v["final"]) if v["final"] >= 0 else _pct(v["best"] or None),
        "test_label": "Test accuracy" if v["final"] >= 0 else "Best test accuracy",
        "speed": f"{v['speed']:.0f}" if v["speed"] and status == "training" else "-",
        "lr": v["lr"],
        "lr_text": lr_text(v["lr"]),
    }


def _points(pairs: list | None, scale: float = 1.0) -> list:
    return [[k, round(v * scale, 5)] for k, v in sorted(pairs or [])]


@nu.host
def curves(loss: list, test_loss: list, acc: list, test_acc: list, lrs: list) -> dict:
    """The run page's chart data: loss, accuracy in percent, and the learning rate, by step."""
    return {
        "loss": {"train": _points(loss), "test": _points(test_loss)},
        "acc": {"train": _points(acc, 100.0), "test": _points(test_acc, 100.0)},
        "lr": _points(lrs),
    }


def _bins(r: float, n: int) -> list[str]:
    step = 2 * r / n
    return [f"{-r + step * (i + 0.5):.2g}" for i in range(n)]


@nu.host
def heatmaps(snapshots: list | None) -> dict:
    """Per layer, its weights and grads over steps, as a heatmap's option patch: ``{w: {layer: patch}, g: ...}``.

    Steps run along x, bins along y, each cell ``log1p(count)`` so the tails show.
    """
    shots = [(k, json.loads(v)) for k, v in sorted(snapshots or [])][-SNAPSHOTS:]
    out: dict[str, dict[str, Any]] = {"w": {}, "g": {}}
    for kind, span in (("w", "wr"), ("g", "gr")):
        for layer in LAYERS:
            cells = [
                [i, j, round(math.log1p(c), 3)]
                for i, (_, h) in enumerate(shots)
                for j, c in enumerate(h[layer][kind])
            ]
            last = shots[-1][1][layer] if shots else None
            out[kind][layer] = {
                "xAxis": {"data": [str(step) for step, _ in shots]},
                "yAxis": {"data": _bins(last[span], len(last[kind])) if last else []},
                "visualMap": {"min": 0, "max": max((c[2] for c in cells), default=1) or 1},
                "series": [{"data": cells}],
            }
    return out


def _bar(digit: int, prob: float, said: int, ok: bool) -> dict:
    """One probability bar, the one the model went for in green or red."""
    color = (
        ("var(--status-ok)" if ok else "var(--status-danger)")
        if digit == said
        else "var(--text-muted)"
    )
    return {"value": [str(digit), round(prob * 100, 1)], "itemStyle": {"color": color}}


@nu.host
def cards(digits: list | None, preds: list | None) -> dict:
    """The sample digits with what the model says: per card its image, verdict and probabilities."""
    digits, preds = digits or [], preds or []
    shown, right = [], 0
    for i, d in enumerate(digits):
        p = preds[i] if i < len(preds) else None
        ok = p is not None and p[0] == d["label"]
        right += ok
        verdict = "not yet" if p is None else f"reads {p[0]} · {100 * p[1]:.0f}%"
        probs = [_bar(k, v, p[0], ok) for k, v in enumerate(p[2])] if p else []
        shown.append(
            {
                "src": d["src"],
                "title": f"label {d['label']}",
                "verdict": verdict,
                "variant": "neutral" if p is None else ("ok" if ok else "danger"),
                "probs": probs,
            }
        )
    head = f"{right} of {len(digits)} read right" if preds else "Waiting for the first look"
    return {"head": head, "cards": shown}


#: The learning rates a sweep picks from: half a decade apart.
LADDER = (1e-5, 3e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1)


def _around(lr: float) -> list[float]:
    """The ladder's rung nearest ``lr``, and one either side of it."""
    i = min(range(len(LADDER)), key=lambda k: abs(math.log10(LADDER[k] / lr)))
    i = min(max(i, 1), len(LADDER) - 2)
    return [LADDER[i - 1], LADDER[i], LADDER[i + 1]]


@nu.host
def plan(hp: dict, count: int, name: str, how: str) -> list:
    """The runs a click starts, ``[[hp, name], ...]``: one, or three learning rates around ``hp``'s.

    Named as typed, or after their number and what sets them apart.
    """
    rates = [hp["lr"]] if how == "one" else _around(hp["lr"])
    out = []
    for i, lr in enumerate(rates):
        n = count + i + 1
        auto = f"Run {n} · {hp['optimizer']} {lr_text(lr)}"
        named = auto if not name else (name if how == "one" else f"{name} · {lr_text(lr)}")
        out.append([{**hp, "lr": float(f"{lr:.3g}")}, named])
    return out


@nu.host
def rows(runs: list, picked: list | None = None) -> list:
    """One dict per run for a table, keyed by its page, newest first. ``plot`` says if it is picked."""
    out = []
    for page, name, v in reversed(runs):
        hp, now = v["hp"] or {}, v["now"] or {}
        total = v["total"] or 0
        out.append(
            {
                "page": page,
                "plot": page in (picked or []),
                "run": name,
                "status": v["status"],
                "optimizer": hp.get("optimizer", ""),
                "lr": lr_text(v["lr"] or hp.get("lr", 0)),
                "batch": hp.get("batch_size", ""),
                "channels": hp.get("channels", ""),
                "dropout": hp.get("dropout", ""),
                "epochs": hp.get("epochs", ""),
                "progress": f"{100 * v['step'] / total:.0f}%" if total else "-",
                "loss": f"{now['loss']:.4f}" if "loss" in now else "-",
                "best": _pct(v["best"] or None),
                "final": _pct(v["final"]),
            }
        )
    return out


def _score(v: dict) -> float:
    return v["final"] if v["final"] >= 0 else (v["best"] or 0.0)


@nu.host
def leader(runs: list) -> dict:
    """The leaderboard, live prose: the best run, how it was trained, and the rest. And a link to it.

    ``{text, href, label}``, ``href`` empty while no run has a test score.
    """
    none = {"href": "", "label": ""}
    if not runs:
        return {"text": "No runs yet. Launch one: a minute or two on a laptop CPU.", **none}
    ranked = sorted(runs, key=lambda r: -_score(r[2]))
    page, name, v = ranked[0]
    hp = v["hp"] or {}
    live = sum(1 for _, _, w in runs if w["status"] in ("training", "starting", "resuming"))
    best = _score(v)
    if not best:
        return {"text": f"**{len(runs)} runs**, {live} training. No test score yet.", **none}
    line = (
        f"Best run: **{name}** at **{100 * best:.2f}%** test accuracy "
        f"({hp.get('optimizer', '')}, lr {lr_text(hp.get('lr', 0))}, batch {hp.get('batch_size')}, "
        f"{hp.get('channels')} channels, {hp.get('epochs')} epochs)."
    )
    rest = f" {len(runs)} runs, {live} training now." if len(runs) > 1 else ""
    if len(ranked) > 1 and _score(ranked[1][2]):
        gap = 100 * (best - _score(ranked[1][2]))
        ahead = f"{gap:.2f} points ahead of" if gap >= 0.005 else "level with"
        rest += f" {ahead} {ranked[1][1]}."
    return {"text": line + rest, "href": f"/{page}", "label": f"Open {name}"}


def series(root: nu.StrArg) -> nu.Nu:
    """Every run as ``[page, name, test accuracy, train loss]``, each a sample by step. Bare."""

    def row(r: nu.Nu) -> nu.Nu:
        run = nu.List(r)
        job = nu.Str(run[1])
        return nu.List.of(
            run[0], run[2], at(job, Run.test_acc.sample(POINTS)), at(job, Run.loss.sample(POINTS))
        )

    return runs_of(root).iter().map(row).to_list()


@nu.host
def overlay(runs: list, picked: list | None) -> dict:
    """Every run's curves, one series per run name, and a legend patch showing the picked ones, or all."""
    picked = [r[0] for r in runs if r[0] in (picked or [])]
    return {
        "acc": {name: _points(acc, 100.0) for _, name, acc, _ in runs},
        "loss": {name: _points(loss) for _, name, _, loss in runs},
        # Named series only, so the chart's own default one stays out of the legend.
        "legend": {
            "legend": {
                "data": [name for _, name, _, _ in runs],
                "selected": {name: not picked or page in picked for page, name, _, _ in runs},
            }
        },
    }


# --- reading -----------------------------------------------------------------------------------


def shelf(root: nu.StrArg) -> nu.Nu:
    """Every run as ``[job, name, view, models]``, models ``{slot: {step, acc}}`` (no bytes), oldest first. Bare."""

    def model(job: nu.Str, slot: str) -> nu.Nu:
        m = Run.models[slot]
        return nu.Dict.of(step=at(job, m.step.fallback(-1)), acc=at(job, m.acc.fallback(-1.0)))

    def row(r: nu.Nu) -> nu.Nu:
        run = nu.List(r)
        job = nu.Str(run[1])
        models = nu.Dict.of(latest=model(job, "latest"), best=model(job, "best"))
        return nu.List.of(job, run[2], run_view(job), models)

    return runs_of(root).iter().map(row).to_list()


def _choice(job: str, name: str, v: dict, models: dict) -> dict:
    status = v["status"]
    score = _pct(v["final"]) if v["final"] >= 0 else _pct(v["best"] or None)
    saved = models["latest"]["step"] >= 0
    tail = score if saved else "no checkpoint yet"
    return {"value": job, "label": f"{name} · {status} · {tail}"}


@nu.host
def choices(runs: list) -> dict:
    """The run picker: ``{options, first, newest}``, newest first.

    ``first`` is the newest run with a model, ``newest`` the newest run of all.
    """
    options = [_choice(job, name, v, models) for job, name, v, models in reversed(runs)]
    stored = [job for job, _, _, models in reversed(runs) if models["latest"]["step"] >= 0]
    newest = options[0]["value"] if options else ""
    return {"options": options, "first": stored[0] if stored else newest, "newest": newest}


def _ink(value: object) -> list:
    return strokes_to_image(strokes_of(value))


#: :func:`~.ink.strokes_to_image` as a term over a pad's value: what the drawing looks like to the model.
ink = nu.host(_ink, name="Ink")


#: :func:`~.reader.image_png` as a term: a 28x28 field as the run page draws its digits.
picture = nu.host(image_png, name="Picture")


@nu.host
def drawn(n: int) -> list:
    """``[digit, strokes]``, a sample digit drawn by hand, a different one for each ``n``."""
    return sample(None, None)


def _model_line(slot: str, model: dict | None) -> str:
    if not model or model.get("step", -1) < 0:
        return "No checkpoint stored yet: a run saves one every few hundred steps."
    acc = model.get("acc", -1.0)
    scored = f", {100 * acc:.1f}% on the test set" if acc is not None and acc >= 0 else ""
    return f"The {slot} checkpoint, step {model['step']:,}{scored}."


@nu.host
def answer(said: dict | None, label: int, slot: str, model: dict | None) -> dict:
    """What a read shows: the digit, how sure, a bar per digit, and a line on the model that read it.

    ``label`` is the true digit for an MNIST test digit, -1 for one drawn here.
    """
    said = said or {}
    line = _model_line(slot, model)
    if not said:
        blank = model and model.get("step", -1) >= 0
        return {
            "digit": "-",
            "sure": "draw a digit" if blank else "nothing to read with",
            "bars": [_bar(k, 0.0, -1, True) for k in range(10)],
            "line": line,
        }
    digit, probs = said["digit"], said["probs"]
    ok = label < 0 or digit == label
    known = "" if label < 0 else (f" · label {label}, right" if ok else f" · label {label}, wrong")
    return {
        "digit": str(digit),
        "sure": f"{100 * probs[digit]:.0f}% sure{known}",
        "bars": [_bar(k, p, digit, ok) for k, p in enumerate(probs)],
        "line": line,
    }
