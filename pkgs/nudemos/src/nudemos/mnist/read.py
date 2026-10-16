"""The Read plane: pick a run's model, draw a digit, and watch it read.

One cell, ``read``:

- a run picker (every run, newest first, with its status and score, the
  ones still training too) and a slot: the ``latest`` checkpoint or the
  ``best`` one;
- a sketch pad, read on every stroke end. Two more ways in: draw a sample
  (hand authored strokes, put on the pad from here) and try an MNIST test
  digit as is;
- the digit it reads, a bar per digit, and the 28x28 field the model was
  given, so the preprocessing shows.

The model comes out of the run's state into a :class:`~.reader.Reader`
provided around the cell, and is read again only when the run stores a new
one: a run still training on ``latest`` reads the same drawing anew with
every checkpoint it lands.

The pad is ``nustd.ui.SketchRef``. Where the installed nustd has none yet the
page goes without it, and the two buttons still feed it.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["PLANE", "READ"]


READ = '''\
import nu
import nustd.ui
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import redraws, snap
from nudemos.mnist import views
from nudemos.mnist.interactions import Classify, Holds, MnistDigit, Use
from nudemos.mnist.reader import Reader
from nudemos.mnist.state import Run
from nudemos.mnist.views import at

#: Seconds between looks at the picked run for a newer checkpoint.
EVERY = 0.5

TEXT = """\\
### Read a digit

Pick a run and one of its checkpoints, then draw a digit on the pad. It is read on every stroke.
On **Latest**, a run still training reads the same drawing again as each new checkpoint lands. Until you pick a run, this page follows the newest one: draw, launch a run, and watch it learn to read your digit.
"""

SLOTS = [{"value": "latest", "label": "Latest"}, {"value": "best", "label": "Best"}]

#: The pad, where nustd has one.
SKETCH = getattr(nustd.ui, "SketchRef", None)


class RunField(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(placeholder="No runs yet: launch one", searchable=True)


class SlotField(nustd.ui.Field):
    choice = nustd.ui.RadioGroupRef.slot(options=SLOTS, selected="latest", orientation="horizontal")


class Pick(nustd.ui.Grid):
    run = RunField.slot(label="Run")
    model = SlotField.slot(label="Checkpoint")


class Tools(nustd.ui.Row):
    sample = nustd.ui.ButtonRef.slot(label="Draw a sample", variant="secondary", icon="pencil")
    test = nustd.ui.ButtonRef.slot(label="Try a test digit", variant="secondary", icon="refresh-cw")


PAD = {"sketch": SKETCH.slot(width=280, tools=["pen"], controls=["clear"], defaults={"size": 0.07}, label="Draw a digit, 0 to 9")} if SKETCH else {}
Pad = type("Pad", (nustd.ui.Card,), {**PAD, "tools": Tools.slot(gap=2, wrap=True)})


class Seen(nustd.ui.Row):
    image = nustd.ui.ImageRef.slot(width=112, height=112, rounded=True)
    caption = nustd.ui.TextRef.slot()


class Answer(nustd.ui.Card):
    said = nustd.ui.StatRef.slot(label="It reads")
    probs = nustd.ui.BarChart.slot(height=180, tooltip=False, option={
        "grid": {"left": 0, "right": 0, "top": 8, "bottom": 18},
        "yAxis": {"show": False, "max": 100}, "animation": False,
    })
    line = nustd.ui.TextRef.slot()
    seen = Seen.slot(gap=3, align="center")


class Work(nustd.ui.Grid):
    pad = Pad.slot(title="Draw")
    answer = Answer.slot(title="Read")


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    pick = Pick.slot(columns=2, min_width=240, gap=3)
    work = Work.slot(columns=2, min_width=300, gap=3)


class Shown(nu.Shape):
    # This tab's: the run and model kind (slot) picked, whether a person picked the run, the field to
    # read and its true label (-1 for one drawn), a count of inputs, and the key of the last read.
    job = nu.StrRef.slot()
    chosen = nu.BoolRef.slot()
    kind = nu.StrRef.slot()
    image = nu.ObjectRef.slot()
    label = nu.IntRef.slot()
    n = nu.IntRef.slot()
    seen = nu.StrRef.slot()


P, W = View.pick, View.work

CAPTION = "What the model is given: the ink cropped, scaled into 20x20 and centered by its mass in 28x28, as MNIST was made."
AS_IS = "What the model is given: an MNIST test digit, as it is."


def model(job, slot):
    # A model's step and test score, never its bytes.
    m = Run.models[slot]
    return nu.Dict.of(step=at(job, m.step.fallback(-1)), acc=at(job, m.acc.fallback(-1.0)))


def draw(a):
    A = W.answer
    return A.said.set(a["digit"], label=nu.Str("It reads, ") + nu.Str(a["sure"])) >> A.probs.set(a["bars"]) >> A.line.set(a["line"])


def read(job, slot, m, look):
    # The weights leave the store only when the reader has not got this step of this model.
    key = job + "/" + slot + "/" + nu.str(m["step"])
    blob = snap(at(job, Run.models[slot].blob.fallback(b"")))
    loaded = nu.IfDo(nu.Bool(Holds(key)), nu.Noop(), nu.let(Use(key, blob), lambda _: nu.Noop()))
    shown = views.answer(Classify(Shown.image), Shown.label, slot, m)
    # A read overtaken by a newer input or model draws nothing.
    return loaded >> nu.let(shown, lambda a: nu.IfDo(Shown.seen == look, draw(a)))


def settle():
    # Read again when the input, the run, the slot or the model's step moved since the last read.
    def go(job, slot, m):
        look = job + "/" + slot + "/" + nu.str(m["step"]) + "#" + nu.str(Shown.n)
        return nu.let(look, lambda k: nu.IfDo(nu.Str(k) != Shown.seen, Shown.seen.set(k) >> read(job, slot, m, k)))

    def picked(job, slot):
        return nu.let(snap(model(job, slot)), lambda m: go(job, slot, m))

    return nu.let(nu.Str(Shown.job), lambda j: nu.let(nu.Str(Shown.kind), lambda s: picked(nu.Str(j), nu.Str(s))))


def took(image, label):
    seen = W.answer.seen
    return (
        Shown.image.set(image) >> Shown.label.set(label) >> Shown.n.set(Shown.n + 1)
        >> seen.image.set(views.picture(Shown.image))
        >> seen.caption.set(nu.If(Shown.label < 0, CAPTION, AS_IS)) >> settle()
    )


def drew():
    return nu.let(W.pad.sketch, lambda s: took(views.ink(s), -1))


def sampled():
    def put(d):
        strokes = nu.List(d)[1]
        shown = W.pad.sketch.set(strokes) if SKETCH else nu.Noop()
        return shown >> took(views.ink(strokes), -1)

    return nu.let(views.drawn(Shown.n), put)


def tested():
    cleared = W.pad.sketch.set([]) if SKETCH else nu.Noop()
    return nu.let(MnistDigit(), lambda d: cleared >> took(d["pixels"], d["label"]))


def options(c):
    # New runs show up. A tab with none picked takes the newest run with a model, and one nobody
    # has picked a run on follows the newest run as it is launched.
    def go(job):
        return P.run.choice.set(job) >> Shown.job.set(job) >> settle()

    newer = Shown.chosen.not_().and_(nu.Str(c["newest"]) != Shown.job).and_(Shown.job != "")
    return (
        P.run.choice.set_options(c["options"])
        >> nu.IfDo(Shown.job == "", go(c["first"]))
        >> nu.IfDo(newer, go(c["newest"]))
    )


def chose():
    return Shown.chosen.set(True) >> Shown.job.set(nu.Str(P.run.choice)) >> settle()


def placed():
    # Slots show in the order first written: the text, the pickers, the pad, then the answer.
    A, T = W.answer, W.pad.tools
    pad = W.pad.sketch.set([]) if SKETCH else nu.Noop()
    return (
        View.text.set(TEXT) >> P.run.choice.set_options([]) >> P.model.choice.set("latest")
        >> pad >> T.sample.set_label("Draw a sample") >> T.test.set_label("Try a test digit")
        >> A.said.set("-") >> A.probs.set([]) >> A.line.set("") >> A.seen.caption.set(CAPTION)
    )


def body(root):
    runs = Space.planes[nu.Str(root)].children.on_change()
    pad = [nu.ReactForever(W.pad.sketch.on_change(), drew())] if SKETCH else []
    return placed() >> took([], -1) >> nu.ParallelAsync(
        redraws([runs], views.choices(views.shelf(nu.Str(root))), options, every=3.0),
        nu.ReactForever(P.run.choice.on_change(), chose()),
        nu.ReactForever(P.model.choice.on_change(), Shown.kind.set(nu.Str(P.model.choice)) >> settle()),
        nu.ReactForever(W.pad.tools.sample.on_click(), sampled()),
        nu.ReactForever(W.pad.tools.test.on_click(), tested()),
        nu.ForeverDo(nu.Delay(EVERY) >> settle()),
        *pad,
    )


def out(plane):
    def run(root):
        shown = nu.Frame(Shown, body(root), job="", chosen=False, kind="latest", image=[], label=-1, n=0, seen="")
        return nu.Provide(Reader, {}, shown)

    return nu.let(snap(ops.parent(plane)), run)
'''


PLANE = Plane(
    "mnist_read",
    "Read",
    icon="pencil",
    description="Pick a trained MNIST model, draw a digit, and watch it read.",
    meta={"editable": True, "full_width": True},
    cells=(("read", READ),),
    backend="async",
)
