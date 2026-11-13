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

The pad is ``nustd.ui.SketchRef``.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["PLANE", "READ"]


READ = '''\
import nu
import nuspace
import nustd.ui
from nudemos.mnist import views
from nudemos.mnist.interactions import Classify, Holds, MnistDigit, Use
from nudemos.mnist.reader import Reader
from nudemos.mnist.state import run_at, runs_change

#: Seconds between looks at the picked run for a newer checkpoint.
EVERY = 0.5

TEXT = """\\
### Read a digit

Pick a run and one of its checkpoints, then draw a digit on the pad. It is read on every stroke.
On **Latest**, a run still training reads the same drawing again as each new checkpoint lands. Until you pick a run, this page follows the newest one: draw, launch a run, and watch it learn to read your digit.
"""

SLOTS = [{"value": "latest", "label": "Latest"}, {"value": "best", "label": "Best"}]

BARS = {"grid": {"left": 0, "right": 0, "top": 8, "bottom": 18}, "yAxis": {"show": False, "max": 100}, "animation": False}


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=4)


text = View.page["text"].to(nustd.ui.MarkdownRef)
pick = View.page["pick"].to(nustd.ui.GridRef.slot(cols=2, stack_below=640, gap=4))
work = View.page["work"].to(nustd.ui.GridRef.slot(cols="1fr 1fr", stack_below=800, gap=4))

run = pick[0, 0].to(nustd.ui.Field.slot(label="Run")).control.to(
    nustd.ui.SelectRef.slot(placeholder="No runs yet: launch one", searchable=True)
)
checkpoint = pick[0, 1].to(nustd.ui.Field.slot(label="Checkpoint")).control.to(
    nustd.ui.RadioGroupRef.slot(options=SLOTS, selected="latest", orientation="horizontal")
)

pad = work[0, 0].to(nustd.ui.CardRef.slot(title="Draw", subtitle="read on every stroke"))
sketch = pad["sketch"].to(nustd.ui.SketchRef.slot(
    width=280, tools=["pen"], controls=["clear"], defaults={"size": 0.07}, label="Draw a digit, 0 to 9",
))
sample = pad.actions["sample"].to(nustd.ui.ButtonRef.slot(label="Draw a sample", variant="secondary", size="sm", icon="pencil"))
test = pad.actions["test"].to(nustd.ui.ButtonRef.slot(label="Try a test digit", variant="secondary", size="sm", icon="refresh-cw"))

answer = work[0, 1].to(nustd.ui.CardRef.slot(title="Read"))
said = answer["said"].to(nustd.ui.StatRef.slot(label="It reads"))
probs = answer["probs"].to(nustd.ui.BarChart.slot(height=180, tooltip=False, option=BARS))
line = answer["line"].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))
seen_image = answer["seen"].to(nustd.ui.ImageRef.slot(width=112, height=112, radius="md"))
seen_caption = answer.footer["caption"].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))


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


CAPTION = "What the model is given: the ink cropped, scaled into 20x20 and centered by its mass in 28x28, as MNIST was made."
AS_IS = "What the model is given: an MNIST test digit, as it is."


def model(job, slot):
    # A model's step and test score, never its bytes.
    m = run_at(job).models[slot]
    return nu.Dict.of(step=m.step.fallback(-1), acc=m.acc.fallback(-1.0))


def draw(a):
    return said.set(a["digit"], label=nu.Str("It reads, ") + nu.Str(a["sure"])) >> probs.set(a["bars"]) >> line.set(a["line"])


def read(job, slot, m, look):
    # The weights leave the store only when the reader has not got this step of this model.
    key = job + "/" + slot + "/" + nu.str(m["step"])
    blob = nuspace.atomic(run_at(job).models[slot].blob.fallback(b""))
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
        return nu.let(nuspace.atomic(model(job, slot)), lambda m: go(job, slot, m))

    # No run picked yet (none launched): nothing to read with.
    chosen = nu.let(nu.Str(Shown.job), lambda j: nu.let(nu.Str(Shown.kind), lambda s: picked(nu.Str(j), nu.Str(s))))
    return nu.IfDo(Shown.job != "", chosen)


def took(image, label):
    return (
        Shown.image.set(image) >> Shown.label.set(label) >> Shown.n.set(Shown.n + 1)
        >> seen_image.set(views.picture(Shown.image))
        >> seen_caption.set(nu.If(Shown.label < 0, CAPTION, AS_IS)) >> settle()
    )


def drew():
    return nu.let(sketch, lambda s: took(views.ink(s), -1))


def sampled():
    def put(d):
        strokes = nu.List(d)[1]
        return sketch.set(strokes) >> took(views.ink(strokes), -1)

    return nu.let(views.drawn(Shown.n), put)


def tested():
    return nu.let(MnistDigit(), lambda d: sketch.set([]) >> took(d["pixels"], d["label"]))


def options(c):
    # New runs show up. A tab with none picked takes the newest run with a model, and one nobody
    # has picked a run on follows the newest run as it is launched.
    def go(job):
        return run.set(job) >> Shown.job.set(job) >> settle()

    newer = Shown.chosen.not_().and_(nu.Str(c["newest"]) != Shown.job).and_(Shown.job != "")
    return (
        run.set_options(c["options"])
        >> nu.IfDo(Shown.job == "", go(c["first"]))
        >> nu.IfDo(newer, go(c["newest"]))
    )


def chose():
    return Shown.chosen.set(True) >> Shown.job.set(nu.Str(run)) >> settle()


def body(root):
    runs = runs_change(nu.Str(root))
    start = (
        text.set(TEXT) >> run.init() >> checkpoint.set("latest") >> sketch.init() >> sample.init() >> test.init()
        >> said.set("-") >> probs.init() >> line.init()
    )
    return start >> took([], -1) >> nu.ParallelAsync(
        nu.Reconcile(nuspace.atomic(runs), nu.let(nuspace.atomic(views.choices(views.shelf(nu.Str(root)))), options), every=3.0),
        nu.ReactEvery(run.on_change(), chose()),
        nu.ReactEvery(checkpoint.on_change(), Shown.kind.set(nu.Str(checkpoint)) >> settle()),
        nu.ReactEvery(sample.on_click(), sampled()),
        nu.ReactEvery(test.on_click(), tested()),
        nu.ReactEvery(sketch.on_change(), drew()),
        nu.ForeverDo(nu.Delay(EVERY) >> settle()),
    )


def out(plane):
    def run(root):
        shown = nu.Frame(Shown, body(root), job="", chosen=False, kind="latest", image=[], label=-1, n=0, seen="")
        return nu.Provide(Reader, {}, shown)

    return nu.let(nuspace.atomic(nuspace.Space.planes[plane].parent), run)
'''


PLANE = PlaneSpec(
    "mnist_read",
    "Read",
    icon="pencil",
    description="Pick a trained MNIST model, draw a digit, and watch it read.",
    web=WebOptions(editable=True, width="board"),
    cells=(("read", READ),),
    backend="async",
)
