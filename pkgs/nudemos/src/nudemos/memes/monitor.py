"""The Monitor plane: the sync watched as a system, not the market it reads.

- ``bar``: the sync's state, as everywhere.
- ``health``: blocks and trades a second, transactions read, lag behind the
  tip, RPC latency, errors.
- ``charts``: the same over time, each a kh57 series sampled at a fixed
  cost however long the sync has run: the whole run, or the last half hour.
- ``errors``: the newest errors the sync met, and what it did about them.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions

from .cells import BAR, cell


__all__ = ["CHARTS", "ERRORS", "HEALTH", "PLANE"]


HEALTH = cell("""\
KEYS = {
    "blocks": "Blocks a second",
    "trades": "Trades a second",
    "txs": "Transactions read",
    "lag": "Behind the tip",
    "latency": "RPC latency",
    "errors": "Errors",
    "calls": "RPC calls",
    "uptime": "Up",
}


class View(nu.Shape):
    tiles = nustd.ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=3)


@nu.host
def shaped(stats, now):
    s = stats or {}
    t, r = s.get("totals") or {}, s.get("rates") or {}
    return {
        "blocks": [f"{r.get('blocks', 0):.2f}", f"{t.get('blocks', 0):,.0f} in all"],
        "trades": [f"{r.get('trades', 0):.1f}", f"{t.get('trades', 0):,.0f} in all"],
        "txs": [f"{t.get('txs', 0):,.0f}", "every one, in every block"],
        "lag": [f"{s.get('lag', 0):,} slots", "every block, in order"],
        "latency": [f"{r.get('latency', 0):.0f} ms", "a call, on average"],
        "errors": [f"{t.get('errors', 0):,.0f}", f"{r.get('errors', 0):.0f} in the last few seconds"],
        "calls": [f"{t.get('calls', 0):,.0f}", s.get("rpc", "")],
        "uptime": [views.ago(s.get("started"), now) if s.get("started") else "-", "this run"],
    }


def tile(k, label):
    return View.tiles[k].to(nustd.ui.CardRef.slot(size="sm"))[0].to(nustd.ui.StatRef.slot(label=label))


def draw(v):
    return nu.Sequential(*(tile(k, label).set(v[k][0], delta=v[k][1]) for k, label in KEYS.items()))


def out(plane):
    def follow(root):
        read = shaped(memes_at(root).stats.fallback({}), nustd.time.time())
        return nu.Reconcile(nuspace.atomic(memes_at(root).beat.on_change()), nu.let(nuspace.atomic(read), draw), every=2.0)

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


CHARTS = cell("""\
#: Points sampled per series, and the least seconds between repaints.
POINTS, EVERY = 240, 5.0

#: The windows the picker offers, in seconds: 0 is the whole run.
WINDOWS = [{"value": "1800", "label": "Last 30 minutes"}, {"value": "7200", "label": "Last 2 hours"}, {"value": "0", "label": "Whole run"}]

TIME = {"xAxis": {"type": "time"}, "animation": False}

#: Two series a chart, on scales ten times apart: the second gets its own axis on the right.
TWO = {
    **TIME,
    "yAxis": [{"type": "value", "scale": True}, {"type": "value", "scale": True, "splitLine": {"show": False}}],
    "series": [{}, {"yAxisIndex": 1}],
}

#: Each chart: its card's title, then the chart.
CHARTS = {
    "throughput": ("Throughput", nustd.ui.LineChart.slot(["blocks/s", "trades/s"], x_type="time", height=220, option=TWO)),
    "flow": ("Launches and volume", nustd.ui.LineChart.slot(["launches/min", "SOL/min"], x_type="time", height=220, option=TWO)),
    "lag": ("Slots behind the tip", nustd.ui.AreaChart.slot(x_type="time", height=220, option=TIME)),
    "latency": ("RPC latency, ms", nustd.ui.LineChart.slot(x_type="time", height=220, option=TIME)),
    "errors": ("Errors", nustd.ui.BarChart.slot(x_type="time", height=220, option=TIME)),
}


class View(nu.Shape):
    over = nustd.ui.PageSectionRef.slot(title="Over time", description="each a series sampled at a fixed cost, however long the sync has run")


window = View.over.actions["window"].to(nustd.ui.SelectRef.slot(options=WINDOWS, selected="1800"))
grid = View.over["charts"].to(nustd.ui.GridRef.slot(max_columns=3, min_cell_width=320, gap=4))
charts = {k: grid[k].to(nustd.ui.CardRef.slot(title=title, size="sm"))[k].to(chart) for k, (title, chart) in CHARTS.items()}


class Pick(nu.Shape):
    # This tab's window, in seconds.
    window = nu.IntRef.slot()


def paint(root):
    begin = nu.If(Pick.window > 0, nu.ToInt(nustd.time.time()) - Pick.window, 0)

    def sample(series):
        return series.sample(POINTS, begin=begin)

    m = memes_at(root)
    read = views.health(*(sample(s) for s in (m.blocks_s, m.trades_s, m.launches_m, m.volume_m, m.lag, m.latency, m.errors_n)))
    drawn = nu.let(nuspace.atomic(read), lambda d: nu.Sequential(*(c.set(d[k]) for k, c in charts.items())))
    # The series exist once the sync has written: till then there is nothing to sample.
    return nu.IfDo(nu.Bool(nuspace.atomic(m.beat.exists())), drawn)


def out(plane):
    def follow(root):
        # One pass at a time, at most every few seconds: a point lands every five.
        beat = nuspace.atomic(memes_at(root).beat.on_change())
        painted = nu.Reconcile(beat, paint(root) >> nu.Delay(EVERY), every=10.0)
        picked = nu.ReactEvery(window.on_change(), Pick.window.set(nu.ToInt(window)) >> paint(root))
        return window.set("1800") >> nu.Frame(Pick, nu.ParallelAsync(painted, picked), window=1800)

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


ERRORS = cell("""\
COLUMNS = [
    {"key": "when", "label": "When", "width": 120, "sortable": False, "cell": nustd.ui.RelativeTimeRef},
    {"key": "call", "label": "Call", "width": 80, "sortable": False},
    {"key": "slot", "label": "Slot", "kind": "number", "align": "end", "width": 120, "sortable": False, "hide_below": 640},
    {"key": "message", "label": "What happened", "sortable": False, "wrap": "truncate"},
]

NOTE = "Every failed call backs the sync off: 1s, doubling to 30s, back to none on the next block read. Rate limits, timeouts and refused connections all land here."


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Errors", subtitle="newest first")


errors = View.card["errors"].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Errors"))
note = View.card.footer["note"].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))


def out(plane):
    def follow(root):
        read = views.error_rows(memes_at(root).errors.fallback([]))
        return nu.Reconcile(nuspace.atomic(memes_at(root).beat.on_change()), nu.let(nuspace.atomic(read), errors.set_rows), every=5.0)

    return note.set(NOTE) >> nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


PLANE = PlaneSpec(
    "memes_monitor",
    "Monitor",
    icon="activity",
    description="The memes sync, watched: throughput, lag, latency, errors.",
    web=WebOptions(editable=True, full_width=True),
    cells=(("sync", BAR), ("health", HEALTH), ("charts", CHARTS), ("errors", ERRORS)),
    backend="async",
)
