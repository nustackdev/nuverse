"""The ``sampled`` Plane: a series that grows forever, charted from a reservoir sample.

Three cells, meeting in the plane's shared state (``Series``):

- ``feed``: appends to a kh57-backed series, 25 points per commit every half
  second, 50 a second. A sqlite state store takes that easily, where one
  commit per point would not. Its tile shows how many points there are.
- ``chart``: repaints a line chart from a 200 point sample of the whole
  series when it moves, at most once a second. The sample costs the same at
  a thousand points or a billion.
- ``about``: says how it works.

Every open tab runs the plane, so every tab runs the feed: the last write's
time holds them to one batch per half second between them.
"""

from __future__ import annotations

from nuspace import PlaneSpec


__all__ = ["ABOUT", "CHART", "FEED", "PLANE"]


FEED = """\
import nu
import nustd.kv
import nustd.math
import nustd.random
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import snap

#: Points per commit, and seconds between commits: 50 points a second.
BATCH = 25
EVERY = 0.5


class Series(nuspace.PlaneState):
    nums = nustd.kv.Kh57Ref.slot(float)
    cursor = nustd.kv.IntRef.slot()
    at = nustd.kv.FloatRef.slot()


tile = nustd.ui.StatRef("points")


def point(i):
    # A slow wave with some noise on it.
    return nustd.math.sin(nu.float(i) / 200.0) * 10.0 + nustd.random.uniform(-1.0, 1.0)


def append(start):
    n = nu.Int(start)
    points = nu.ForRangeDo(n, n + BATCH, lambda i: Series.nums.set_item(i, point(i)))
    return points >> Series.cursor.set(n + BATCH)


def feed(now):
    # Due only when no tab fed in the last interval, so two tabs still feed one.
    due = nu.Float(now) - Series.at.fallback(0.0) >= EVERY * 0.9
    step = nu.let(Series.cursor.fallback(0), append) >> Series.at.set(nu.Float(now))
    return nu.IfDo(due, step)


def show():
    return nu.let(snap(Series.cursor.fallback(0)), lambda n: tile.set_value(nu.str(n)))


step = ops.atomic_state(nu.let(nustd.time.time(), feed)) >> show()
out = tile.set_label("Points in the series") >> nu.ForeverDo(nu.DelayedDo(EVERY, step))
"""


CHART = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace.system.utils import snap

#: Points drawn, whatever the series holds, and the least seconds between repaints.
SAMPLE = 200
EVERY = 1.0


class Series(nuspace.PlaneState):
    nums = nustd.kv.Kh57Ref.slot(float)
    cursor = nustd.kv.IntRef.slot()
    at = nustd.kv.FloatRef.slot()


class View(nustd.ui.Column):
    chart = nustd.ui.LineChart.slot(height=320)


def paint():
    sample = snap(nu.sorted(Series.nums.sample(SAMPLE)))
    return nu.let(sample, lambda points: View.chart.set(points))


# One pass at a time: writes landing while one paints and waits merge into one more.
out = nu.ReconcileReactive(snap(Series.cursor.on_change()), paint() >> nu.Delay(EVERY), every=5.0)
"""


ABOUT = '''\
import nu
import nustd.ui

TEXT = """\\
### How it works

- Feed writes 50 numbers a second into a **kh57-backed** series in the plane's state, 25 per commit. It grows without limit.
- Chart repaints from a 200 point reservoir sample. The same cost at a thousand points or a billion.
- Chart follows the series through `on_change`, at most once a second.
- Every open tab runs the plane. The last write's time holds the feeds to one between them.
- One Ref system for storage, sampling and the chart, one set of Interactions for the feed and the redraw.
"""

out = nustd.ui.MarkdownRef("about").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = PlaneSpec(
    "sampled",
    "Sampled",
    icon="chart-line",
    description="A series that grows forever, charted from a reservoir sample.",
    meta={"editable": True, "full_width": True},
    cells=(("feed", FEED), ("chart", CHART), ("about", ABOUT)),
    group="Demos",
    backend="async",
)
