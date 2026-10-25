"""The Metrics plane: one series over a window, charted from a sample, live.

- ``bar``: the store's state, as on every Log plane.
- ``metrics``: pick a series and a window; a line chart of up to
  :data:`~nulog.planes.consts.SAMPLE_LIMIT` points sampled from the window,
  and tiles over them: the latest point drawn, the low, the high, the mean.

The chart is a kh57 range sample: about twice the points drawn in reads,
the same at a thousand points in the window or a billion. It is sampled
again every few seconds (the ``every`` setting) and on every change of a
picker. The series list follows the store, as the stream list does.
"""

from __future__ import annotations

from nuspace import PlaneSpec

from .cells import BAR, cell


__all__ = ["METRICS", "PLANE"]


METRICS = cell("""\
#: Seconds between looks at the series list.
NAMES_EVERY = 2.0


class SeriesField(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(placeholder="No series yet", searchable=True)


class WindowField(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=list(consts.WINDOW_OPTIONS), selected=consts.DEFAULT_WINDOW)


class Pickers(nustd.ui.Grid):
    series = SeriesField.slot(label="Series")
    window = WindowField.slot(label="Window")


class Tiles(nustd.ui.Grid):
    latest = nustd.ui.StatRef.slot(label="Latest")
    low = nustd.ui.StatRef.slot(label="Low")
    high = nustd.ui.StatRef.slot(label="High")
    mean = nustd.ui.StatRef.slot(label="Mean")
    drawn = nustd.ui.StatRef.slot(label="Points drawn")


class Main(nustd.ui.Column):
    tiles = Tiles.slot(columns=5, min_width=130, gap=3)
    note = nustd.ui.TextRef.slot()
    chart = nustd.ui.LineChart.slot(x_type="time", height=360, area=True, legend=False, max_points=consts.SAMPLE_LIMIT)


class View(nustd.ui.Column):
    pickers = Pickers.slot(columns=2, min_width=200, gap=3)
    empty = nustd.ui.EmptyStateRef.slot()
    main = Main.slot(gap=3)


class Pick(nu.Shape):
    # This tab's: what the pickers say, and the points and tiles last drawn.
    series = nu.StrRef.slot()
    window = nu.StrRef.slot()
    points = nu.ObjectRef.slot()
    tiles = nu.ObjectRef.slot()


P, M = View.pickers, View.main
KEYS = ("latest", "low", "high", "mean", "drawn")


def draw(v):
    shown = nu.Dict(v["tiles"])
    tiles = nu.Sequential(*(getattr(M.tiles, k).set(shown[k]["value"], delta=shown[k]["delta"], trend=shown[k]["trend"]) for k in KEYS))
    chart = M.note.set(v["empty"]) >> M.chart.set(v["points"])
    return nu.IfDo(Pick.tiles != v["tiles"], tiles >> Pick.tiles.set(v["tiles"])) >> nu.IfDo(Pick.points != v["points"], chart >> Pick.points.set(v["points"]))


def paint():
    # One sample of the window, shaped once, drawn where it changed.
    got = nu.If(Pick.series == "", nu.List.of(), reads.points(Pick.series, nu.int(Pick.window)))
    return nu.let(fmt.chart(got, nustd.time.time()), lambda v: draw(nu.Dict(v)))


def names():
    # New series show up; a tab whose series went away moves to the first one there is.
    def show(got):
        kept = fmt.pick(got, Pick.series)
        moved = lambda k: nu.IfDo(nu.Str(k) != Pick.series, Pick.series.set(nu.Str(k)) >> P.series.choice.set(nu.Str(k)) >> paint())
        return P.series.choice.set_options(fmt.options(got)) >> nu.let(kept, moved)

    return redraw(reads.series(), show)


def picked():
    def on(field, keep):
        return nu.ReactForever(field.choice.on_change(), keep >> paint())

    return [
        on(P.series, Pick.series.set(nu.Str(P.series.choice))),
        on(P.window, Pick.window.set(nu.Str(P.window.choice))),
    ]


def off(said):
    seen = nu.Dict(said)
    return View.main.erase() >> View.empty.set(seen["title"], seen["note"])


def live(s):
    # Drawn afresh: the main view was erased while the store was away.
    fresh = View.empty.erase() >> Pick.points.set(None) >> Pick.tiles.set(None)
    loops = [
        drawing(nu.ForeverDo(names() >> nu.Delay(NAMES_EVERY))),
        nu.ForeverDo(paint() >> nu.Delay(s["every"])),
    ]
    return fresh >> nu.ParallelAsync(*loops, *picked())


def out(plane):
    def view(s):
        window = Pick.window.set(nu.Str(s["window"])) >> P.window.choice.set(nu.Str(s["window"]))
        return P.series.choice.set_options([]) >> window >> with_store(s, lambda: live(s), off)

    def follow(root):
        return nu.Frame(Pick, following(root, view), series="", window=consts.DEFAULT_WINDOW, points=None, tiles=None)

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


PLANE = PlaneSpec(
    "nulog_metrics",
    "Metrics",
    icon="chart-line",
    description="One metric series over a window, charted from a sample, live.",
    meta={"editable": True, "full_width": True},
    cells=(("bar", BAR), ("metrics", METRICS)),
    backend="async",
)
