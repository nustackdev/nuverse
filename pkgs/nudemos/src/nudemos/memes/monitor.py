"""The Monitor plane: the sync watched as a system, not the market it reads.

- ``bar``: the sync's state, as everywhere.
- ``health``: blocks and trades a second, transactions read, lag behind the
  tip, RPC latency, errors.
- ``charts``: the same over time, each a kh57 series sampled at a fixed
  cost however long the sync has run: the whole run, or the last half hour.
- ``errors``: the newest errors the sync met, and what it did about them.
"""

from __future__ import annotations

from nuspace import Plane

from .cells import BAR, cell


__all__ = ["CHARTS", "ERRORS", "HEALTH", "PLANE"]


HEALTH = cell("""\
class Tiles(nustd.ui.Grid):
    blocks = nustd.ui.StatRef.slot(label="Blocks a second")
    trades = nustd.ui.StatRef.slot(label="Trades a second")
    txs = nustd.ui.StatRef.slot(label="Transactions read")
    lag = nustd.ui.StatRef.slot(label="Behind the tip")
    latency = nustd.ui.StatRef.slot(label="RPC latency")
    errors = nustd.ui.StatRef.slot(label="Errors")
    calls = nustd.ui.StatRef.slot(label="RPC calls")
    uptime = nustd.ui.StatRef.slot(label="Up")


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=8, min_width=120, gap=3)


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


def draw(v):
    t = View.tiles
    keys = ("blocks", "trades", "txs", "lag", "latency", "errors", "calls", "uptime")
    return nu.Sequential(*(getattr(t, k).set(v[k][0], delta=v[k][1]) for k in keys))


def out(plane):
    def follow(root):
        read = shaped(at_root(root, Memes.stats.fallback({})), nustd.time.time())
        return redraws([at_root(root, Memes.beat.on_change())], read, draw, every=2.0)

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
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


class Charts(nustd.ui.Grid):
    throughput = nustd.ui.LineChart.slot(["blocks/s", "trades/s"], title="Throughput", x_type="time", height=220, option=TWO)
    flow = nustd.ui.LineChart.slot(["launches/min", "SOL/min"], title="Launches and volume", x_type="time", height=220, option=TWO)
    lag = nustd.ui.AreaChart.slot(title="Slots behind the tip", x_type="time", height=220, option=TIME)
    latency = nustd.ui.LineChart.slot(title="RPC latency, ms", x_type="time", height=220, option=TIME)
    errors = nustd.ui.BarChart.slot(title="Errors", x_type="time", height=220, option=TIME)


class Head(nustd.ui.Row):
    title = nustd.ui.HeadingRef.slot(level=4)
    window = nustd.ui.SelectRef.slot(options=WINDOWS, selected="1800")


class View(nustd.ui.Column):
    head = Head.slot(gap=3, align="center", justify="between")
    charts = Charts.slot(columns=3, min_width=300, gap=3)


class Pick(nu.Shape):
    # This tab's window, in seconds.
    window = nu.IntRef.slot()


def paint(root):
    begin = nu.If(Pick.window > 0, nu.ToInt(nustd.time.time()) - Pick.window, 0)

    def sample(series):
        return at_root(root, series.sample(POINTS, begin=begin))

    m = Memes
    read = views.health(*(sample(s) for s in (m.blocks_s, m.trades_s, m.launches_m, m.volume_m, m.lag, m.latency, m.errors_n)))
    c = View.charts

    def draw(d):
        return (
            c.throughput.set(d["throughput"]) >> c.flow.set(d["flow"]) >> c.lag.set(d["lag"])
            >> c.latency.set(d["latency"]) >> c.errors.set(d["errors"])
        )

    return nu.let(snap(read), draw)


def out(plane):
    def follow(root):
        # One pass at a time, at most every few seconds: a point lands every five.
        beat = snap(at_root(root, Memes.beat.on_change()))
        painted = nu.ReconcileReactive(beat, paint(root) >> nu.Delay(EVERY), every=10.0)
        picked = nu.ReactForever(View.head.window.on_change(), Pick.window.set(nu.ToInt(View.head.window)) >> paint(root))
        head = View.head.title.set("Over time") >> View.head.window.set_options(WINDOWS) >> View.head.window.set("1800")
        return head >> nu.Frame(Pick, nu.ParallelAsync(painted, picked), window=1800)

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


ERRORS = cell("""\
COLUMNS = [
    {"key": "when", "label": "When", "width": 170, "sortable": False},
    {"key": "call", "label": "Call", "width": 80, "sortable": False},
    {"key": "slot", "label": "Slot", "kind": "number", "width": 120, "sortable": False},
    {"key": "message", "label": "What happened", "sortable": False},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    note = nustd.ui.TextRef.slot()
    errors = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Errors")


def out(plane):
    def follow(root):
        read = views.error_rows(at_root(root, Memes.errors.fallback([])), nustd.time.time())
        return redraws([at_root(root, Memes.beat.on_change())], read, View.errors.set_rows, every=5.0)

    note = "Every failed call backs the sync off: 1s, doubling to 30s, back to none on the next block read. Rate limits, timeouts and refused connections all land here."
    return View.head.set("Errors, newest first") >> View.note.set(note) >> nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


PLANE = Plane(
    "memes_monitor",
    "Monitor",
    icon="activity",
    description="The memes sync, watched: throughput, lag, latency, errors.",
    meta={"editable": True, "full_width": True},
    cells=(("sync", BAR), ("health", HEALTH), ("charts", CHARTS), ("errors", ERRORS)),
    backend="async",
)
