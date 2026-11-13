"""The Metrics plane: one series over a window, charted from a sample, live.

- ``bar``: the store's state, as on every Log plane.
- ``metrics`` (:func:`out`): a series and a window picked over a chart
  card titled by the series it draws; a line chart of up to
  :data:`~nulog.planes.consts.SAMPLE_LIMIT` points sampled from the window;
  tiles beside it: the latest point drawn, the low, the high, the mean.

The chart is a kh57 range sample: about twice the points drawn in reads,
the same at a thousand points in the window or a billion. It is sampled
again every few seconds (the ``every`` setting) and on every change of a
picker. The series list follows the store, as the stream list does.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.time
import nustd.ui as ui
from nuspace.specs import PlaneSpec, WebOptions

from . import consts, fmt, reads
from .cells import BAR, METRICS
from .state import following, root_of, with_store


__all__ = ["PLANE", "View", "out"]


#: Seconds between looks at the series list.
NAMES_EVERY = 2.0

#: The tiles beside the chart, in order.
TILES = (
    ("latest", "Latest"),
    ("low", "Low"),
    ("high", "High"),
    ("mean", "Mean"),
    ("drawn", "Points drawn"),
)


# ---- the view ---------------------------------------------------------------
#
#   [ series.......... ][ window ]
#   [ <series>                     ][ latest ]
#   [ the chart                    ][ low    ]
#   [                              ][ ...    ]   tiles under the chart when narrow


class View(nu.Shape):
    """The ``metrics`` cell's root."""

    metrics = ui.ColumnRef.slot(gap=4)


tools = View.metrics[0].to(
    ui.RowRef.slot(gap=3, align="end", stack_below=560, grow={0: 2, 1: 1}, max_width=560)
)
series = (
    tools[0]
    .to(ui.FieldRef.slot(label="Series"))
    .control.to(ui.SelectRef.slot(placeholder="No series yet", searchable=True))
)
window = (
    tools[1]
    .to(ui.FieldRef.slot(label="Window"))
    .control.to(ui.SelectRef.slot(options=list(consts.WINDOW_OPTIONS), value=consts.DEFAULT_WINDOW))
)

empty = View.metrics[1].to(ui.EmptyStateRef)
main = View.metrics[2].to(ui.GridRef.slot(cols="3fr 1fr", gap=4, stack_below=900))

card = main[0, 0].to(
    ui.CardRef.slot(
        title="No series yet",
        subtitle=f"Up to {consts.SAMPLE_LIMIT} points sampled from the window",
    )
)
chart = card[0].to(
    ui.LineChart.slot(
        x_type="time", height=360, area=True, legend=False, max_points=consts.SAMPLE_LIMIT
    )
)

side = main[0, 1].to(ui.ColumnRef.slot(gap=3))
stats = [
    side[i].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=label))
    for i, (_, label) in enumerate(TILES)
]


class Pick(nu.Shape):
    # This tab's: what the pickers say, and the points and tiles last drawn.
    series = nu.StrRef.slot()
    window = nu.StrRef.slot()
    points = nu.ObjectRef.slot()
    tiles = nu.ObjectRef.slot()


# ---- the program ------------------------------------------------------------


def draw(v: nu.Dict) -> nu.Nu:
    shown = nu.Dict(v["tiles"])
    tiles = nu.Sequential(
        *(
            stats[i].set(shown[k]["value"], delta=shown[k]["delta"], trend=shown[k]["trend"])
            for i, (k, _) in enumerate(TILES)
        )
    )
    drawn = card.set_caption(v["empty"]) >> chart.set(v["points"])
    return nu.IfDo(Pick.tiles != v["tiles"], tiles >> Pick.tiles.set(v["tiles"])) >> nu.IfDo(
        Pick.points != v["points"], drawn >> Pick.points.set(v["points"])
    )


def paint() -> nu.Nu:
    # One sample of the window, shaped once, drawn where it changed.
    got = nu.If(Pick.series == "", nu.List.of(), reads.points(Pick.series, nu.int(Pick.window)))
    return nu.let(fmt.chart(got, nustd.time.time()), lambda v: draw(nu.Dict(v)))


def titled() -> nu.Nu:
    return card.set_title(nu.If(Pick.series == "", "No series yet", Pick.series))


def names() -> nu.Nu:
    # New series show up; a tab whose series went away moves to the first one there is.
    def show(got: nu.Nu) -> nu.Nu:
        def moved(k: nu.Nu) -> nu.Nu:
            to = nu.Str(k)
            return nu.IfDo(
                to != Pick.series, Pick.series.set(to) >> series.set(to) >> titled() >> paint()
            )

        return series.set_options(fmt.options(got)) >> nu.let(fmt.pick(got, Pick.series), moved)

    return nu.let(reads.series(), show)


def picked() -> list[nu.Nu]:
    return [
        nu.ReactEvery(series.on_change(), Pick.series.set(nu.Str(series)) >> titled() >> paint()),
        nu.ReactEvery(window.on_change(), Pick.window.set(nu.Str(window)) >> paint()),
    ]


def off(seen: nu.Dict) -> nu.Nu:
    return main.erase() >> empty.set(seen["title"], seen["note"])


def live(s: nu.Dict) -> nu.Nu:
    # Drawn afresh: the main view was erased while the store was away.
    fresh = empty.erase() >> Pick.points.set(None) >> Pick.tiles.set(None) >> titled()
    loops = [
        nu.ForeverDo(names() >> nu.Delay(NAMES_EVERY)),
        nu.ForeverDo(paint() >> nu.Delay(s["every"])),
    ]
    return fresh >> nu.ParallelAsync(*loops, *picked())


def out(plane: nu.StrArg) -> nu.Nu:
    """The ``metrics`` cell on ``plane``: the chart card and its tiles, live."""

    def view(s: nu.Dict) -> nu.Nu:
        shown = series.init() >> window.set(Pick.window)
        return Pick.window.set(nu.Str(s["window"])) >> shown >> with_store(s, lambda: live(s), off)

    def follow(root: nu.Str) -> nu.Nu:
        return nu.Frame(
            Pick,
            following(root, view),
            series="",
            window=consts.DEFAULT_WINDOW,
            points=None,
            tiles=None,
        )

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))


PLANE = PlaneSpec(
    "nulog_metrics",
    "Metrics",
    icon="chart-line",
    description="One metric series over a window, charted from a sample, live.",
    web=WebOptions(editable=True, width="board"),
    cells=(("bar", BAR), ("metrics", METRICS)),
    backend="async",
)
