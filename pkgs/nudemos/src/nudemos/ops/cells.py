"""The ops pages' cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the page it runs on comes in, and
:func:`.kit.on_ops` brackets it step by step over :data:`~.state.OPS`, the
root's state, found by its key. Pages of one kind run the same cells, told apart by their meta: eight
job pages, one program each.

- The root (:data:`ROOT`): welcome (and the first open), pulse, live, feed.
- :data:`FOLDERS`: Jobs, Traffic, Logs, Machine, Deploys, Incidents,
  Runbooks, Rules, Status, each with its cells.
- A job page (:data:`JOB`), an incident page (:data:`INCIDENT_CELLS`).

A cell with one part declares it as the one slot of a ``nu.Shape`` and
reaches what is inside by descent (``View.board[0].to(ui.DataTableRef...)``);
tables take rows from :mod:`.views`, a page column turned into a link by
:func:`nudemos.pages.linked`.
"""

from __future__ import annotations


__all__ = ["FOLDERS", "INCIDENT_CELLS", "JOB", "ROOT"]


# --- the root ------------------------------------------------------------------------------------


WELCOME = '''\
import nu
import nuspace
import nuspace.web as web
from nustd import ui
from nudemos.ops import kit
from nudemos.ops.state import folder_of

TEXT = """\\
Halcyon sells camping gear online. This is the space its two-person platform team runs it from.

Everything here is running: the storefront API is a real HTTP server in its own process, shoppers hit it,
backups archive real orders, a crawler checks the help center, and alert rules written as a few lines of Nu
watch the live numbers. Every block on every page is a small program: open its code, change it, run it again.

Start at the jobs, ship a release from deploys, follow incidents, or see what customers see on the status page.
"""

#: The folders the welcome points at, and a line on each.
WAYS = {
    "jobs": "Every job, its runs, its log and its controls",
    "deploys": "Ship a release, or roll one back",
    "incidents": "What the rules opened, and who was paged",
    "status": "What customers see right now",
}


class View(ui.Column):
    about = ui.MarkdownRef.slot()
    ways = ui.GridRef.slot(max_columns=4, min_cell_width=200, gap=3)


def way(key):
    tile = View.ways[key].to(ui.PageLinkRef.slot(variant="tile"))
    # Each folder by the id the first open minted for it, one read of the root's state.
    return nuspace.atomic(web.link(tile, folder_of(key), description=WAYS[key]))


def out(plane):
    def draw(root):
        return View.about.set(TEXT) >> nu.Sequential(*(way(key) for key in WAYS))

    # The first open brings up the pages, the jobs and their schedules, once.
    return kit.on_root(plane, lambda root: kit.seed(root) >> draw(root) >> nu.ForeverDo(nu.Delay(3600.0)))
'''


PULSE = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

TILES = {"release": "Release", "rps": "Requests/s", "err": "Failing", "p95": "p95", "orders": "Orders/min", "incidents": "Incidents", "jobs": "Jobs up"}


class View(nu.Shape):
    tiles = ui.GridRef.slot(max_columns=7, min_cell_width=140, gap=3)


def draw(t):
    def one(k):
        v = nu.Dict(t[k])
        stat = View.tiles[k].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=TILES[k]))
        return stat.set(v["value"], delta=v["delta"], trend=v["trend"])

    return nu.Sequential(*(one(k) for k in TILES))


def out(plane):
    def build(root):
        read = views.pulse(OPS.gw.fallback({}), OPS.release.fallback({}), nu.Dict(OPS.jobs.extract()).fallback({}),
                           nu.Dict(OPS.incidents.extract()).fallback({}), OPS.load.fallback({}))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change(), OPS.incidents.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return kit.on_ops(plane, build)
"""


LIVE = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

WINDOW = 600


class View(nu.Shape):
    both = ui.GridRef.slot(cols=2, stack_below=800, gap=4)


traffic = View.both[0, 0].to(ui.CardRef.slot(title="Requests a second", subtitle="last 10 minutes"))[0].to(
    ui.AreaChart.slot(("requests a second",), x_type="time", x_format="{HH}:{mm}", height=220))
errors = View.both[0, 1].to(ui.CardRef.slot(title="Failing requests", subtitle="share of requests, %"))[0].to(
    ui.LineChart.slot(("failing %",), x_type="time", x_format="{HH}:{mm}", y_min=0, height=220, colors=["var(--status-danger)"]))


def out(plane):
    def build(root):
        since = nu.Int(nu.ToInt(nustd.time.time())) - WINDOW
        read = nu.Dict.of(
            rps=views.named("requests a second", OPS.rps.range(since, since + WINDOW + 5)),
            err=views.named("failing %", OPS.err.range(since, since + WINDOW + 5), 100.0),
        )
        draw = lambda v: traffic.set(v["rps"]) >> errors.set(v["err"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return kit.on_ops(plane, build)
"""


FEED = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "when", "label": "When", "width": 110, "cell": ui.RelativeTimeRef},
    {"key": "kind", "label": "What", "width": 110, "cell": ui.BadgeRef.slot(size="sm")},
    {"key": "text", "label": "Said"},
]


class View(nu.Shape):
    feed = ui.CardRef.slot(title="What happened", subtitle="newest first")


table = View.feed[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Feed"))


def out(plane):
    def build(root):
        read = views.feed_rows(OPS.events.fallback([]), 14)
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.events.on_change()])), nu.let(nuspace.atomic(read), table.set_rows))

    return kit.on_ops(plane, build)
"""


ROOT = (("welcome", WELCOME), ("pulse", PULSE), ("live", LIVE), ("feed", FEED))


# --- jobs ----------------------------------------------------------------------------------------


BOARD = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos import pages
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "job", "label": "Job", "width": 130, "cell": ui.PageLinkRef.slot(variant="inline")},
    {"key": "what", "label": "What it is", "wrap": "truncate", "hide_below": 900},
    {"key": "schedule", "label": "Schedule", "width": 120},
    {"key": "status", "label": "Status", "width": 110, "cell": ui.StatusPillRef},
    {"key": "last", "label": "Last", "width": 100, "cell": ui.RelativeTimeRef},
    {"key": "said", "label": "It said", "wrap": "truncate"},
    {"key": "next", "label": "Next", "width": 100},
    {"key": "runs", "label": "Runs", "width": 150, "hide_below": 1100},
]


class View(nu.Shape):
    board = ui.CardRef.slot(title="Every job", subtitle="each a headless plane in its own process, kept up or scheduled by the supervisor")


table = View.board[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Jobs"))


def out(plane):
    def build(root):
        rows = views.job_rows(nu.Dict(OPS.jobs.extract()).fallback({}), nu.Dict(OPS.made.views.extract()).fallback({}), nustd.time.time())
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.jobs.on_change()])), nu.let(nuspace.atomic(pages.linked(rows, "job")), table.set_rows), every=5.0)

    return kit.on_ops(plane, build)
"""


RECENT = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit
from nudemos.ops.state import OPS

SCHEDULED = ["backup", "offsite", "linkcheck", "digest"]


class View(nu.Shape):
    took = ui.CardRef.slot(title="Scheduled runs", subtitle="how long the last 12 of each took, seconds")


bars_of = View.took[0].to(ui.BarChart.slot(SCHEDULED, height=240, legend=True))


@nu.host
def bars(runs):
    # The last 12 runs of each scheduled job, oldest first, their run number on the x axis.
    out = {}
    for name in SCHEDULED:
        rs = list(reversed((runs or {}).get(name) or []))[-12:]
        out[name] = [[f"#{i + 1}", round((r.get("ms") or 0) / 1000, 2)] for i, r in enumerate(rs)]
    return out


def out(plane):
    def build(root):
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.runs.on_change()])), nu.let(nuspace.atomic(bars(nu.Dict(OPS.runs.extract()).fallback({}))), bars_of.set), every=10.0)

    return kit.on_ops(plane, build)
"""


JOBS = (("board", BOARD), ("took", RECENT))


JOB_HEAD = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS


class View(nu.Shape):
    head = ui.PageSectionRef.slot()


run = View.head.actions[0].to(ui.ButtonRef.slot(label="Run now", icon="play", size="sm"))
pause = View.head.actions[1].to(ui.ButtonRef.slot(label="Pause", variant="secondary", icon="pause", size="sm"))
restart = View.head.actions[2].to(ui.ButtonRef.slot(label="Restart", variant="secondary", icon="refresh-cw", size="sm"))
top = View.head[0].to(ui.LineRef)
status = top[0].to(ui.StatusPillRef)
line = top[1].to(ui.TextRef.slot(tone="muted"))


def draw(h):
    paused = nu.Bool(h["paused"])
    return (
        View.head.set_description(h["desc"]) >> status.set(h["status"], tone=h["tone"]) >> line.set(h["line"])
        >> pause.set(nu.Str(nu.If(paused, "Resume", "Pause")), icon=nu.Str(nu.If(paused, "play", "pause")))
        >> run.set_disabled(nu.Bool(h["service"])) >> restart.set_disabled(nu.Bool(h["service"]).not_())
    )


def out(plane):
    def build(root, name):
        head = views.job_head(OPS.jobs[name].fallback({}), name, nustd.time.time())
        flip = nu.IfDo(kit.paused(name), kit.resume(root, name), kit.pause(root, name))
        return View.head.set_title(name) >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.jobs.on_change()])), nu.let(nuspace.atomic(head), draw), every=1.0),
            nu.ReactEvery(run.on_click(), kit.run_now(root, name)),
            nu.ReactEvery(pause.on_click(), flip),
            nu.ReactEvery(restart.on_click(), kit.restart(root, name)),
        )

    return kit.on_subject(plane, "job", build)
"""


JOB_RUNS = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "started", "label": "Started", "width": 110, "cell": ui.RelativeTimeRef},
    {"key": "result", "label": "Result", "width": 110, "cell": ui.StatusPillRef},
    {"key": "took", "label": "Took", "width": 90, "align": "end"},
    {"key": "summary", "label": "Summary", "wrap": "truncate"},
    {"key": "process", "label": "Process", "width": 100, "align": "end", "hide_below": 900},
]


class View(nu.Shape):
    runs = ui.CardRef.slot(title="Runs", subtitle="newest first")


table = View.runs[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Runs"))


def out(plane):
    def build(root, name):
        rows = views.job_runs(OPS.runs[name].fallback([]), OPS.jobs[name].fallback({}), nustd.time.time())
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.runs[name].on_change(), OPS.jobs[name].on_change()])), nu.let(nuspace.atomic(rows), table.set_rows), every=5.0)

    return kit.on_subject(plane, "job", build)
"""


JOB_LOG = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "time", "label": "Time", "width": 120, "cell": ui.TextRef.slot(mono=True, size="sm")},
    {"key": "level", "label": "Level", "width": 100, "cell": ui.BadgeRef.slot(size="sm")},
    {"key": "message", "label": "Message"},
    {"key": "detail", "label": "Detail", "width": 260, "wrap": "truncate", "hide_below": 900},
]


class View(nu.Shape):
    log = ui.CardRef.slot(title="Its log", subtitle="the newest 25 lines, live")


table = View.log[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Log"))


def out(plane):
    def build(root, name):
        # Its own stream, newest 25 lines: a read the size of what is shown, however long the stream.
        rows = views.log_rows(kit.tail(name, 25), "debug", "", 25)
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.counts.on_change()])), nu.let(nuspace.atomic(rows), table.set_rows), every=3.0)

    return kit.on_subject(plane, "job", build)
"""


JOB = (("head", JOB_HEAD), ("runs", JOB_RUNS), ("log", JOB_LOG))


# --- traffic -------------------------------------------------------------------------------------


KNOB = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit
from nudemos.ops.state import OPS

STATS = {"sent": "Requests sent", "failed": "Failed", "orders": "Orders placed"}


class View(nu.Shape):
    knob = ui.CardRef.slot(title="Shoppers", subtitle="as many as you set hit the storefront, over real connections")


grid = View.knob[0].to(ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=4, align="center"))
users = grid["users"].to(ui.SliderRef.slot(label="Shoppers on the site", min=0, max=60, step=1))


@nu.host
def shown(load):
    t = (load or {}).get("totals") or {}
    return {"sent": f"{t.get('sent', 0):,}", "failed": f"{t.get('failed', 0) + t.get('refused', 0):,}", "orders": f"{t.get('orders', 0):,}"}


def draw(v):
    return nu.Sequential(*(grid[k].to(ui.StatRef.slot(label=label)).set(v[k]) for k, label in STATS.items()))


def out(plane):
    def build(root):
        moved = OPS.load.set(kit.merged(OPS.load.fallback({}), nu.Dict.of(users=nu.ToInt(users))))
        return users.set_value(nu.Float(OPS.load.fallback({})["users"])) >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.load.on_change()])), nu.let(nuspace.atomic(shown(OPS.load.fallback({}))), draw), every=2.0),
            nu.ReactEvery(users.on_change(), nuspace.atomic(moved)),
        )

    return kit.on_ops(plane, build)
"""


TRAFFIC_CHARTS = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

WINDOW = 300
TIME = {"x_type": "time", "x_format": "{HH}:{mm}", "height": 230}


class View(nu.Shape):
    charts = ui.GridRef.slot(max_columns=3, min_cell_width=320, gap=4)


def chart(key, title, kind):
    return View.charts[key].to(ui.CardRef.slot(title=title, subtitle="last 5 minutes"))[0].to(kind)


load = chart("load", "Load", ui.AreaChart.slot(("requests a second", "orders a minute"), **TIME))
latency = chart("latency", "Latency, ms", ui.LineChart.slot(("p50", "p95"), y_min=0, **TIME))
memory = chart("memory", "Gateway memory, MB", ui.AreaChart.slot(("gateway MB",), y_min=0, colors=["var(--chart-3)"], **TIME))


def out(plane):
    def build(root):
        since = nu.Int(nu.ToInt(nustd.time.time())) - WINDOW
        end = since + WINDOW + 5
        read = nu.Dict.of(
            load=views.joined(views.named("requests a second", OPS.rps.range(since, end)), views.named("orders a minute", OPS.orders.range(since, end))),
            latency=views.joined(views.named("p50", OPS.p50.range(since, end)), views.named("p95", OPS.p95.range(since, end))),
            rss=views.named("gateway MB", OPS.gw_rss.range(since, end)),
        )
        draw = lambda v: load.set(v["load"]) >> latency.set(v["latency"]) >> memory.set(v["rss"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return kit.on_ops(plane, build)
"""


ROUTES = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "route", "label": "Route"},
    {"key": "rpm", "label": "Last minute", "kind": "number", "width": 120, "align": "end"},
    {"key": "err", "label": "Failing", "width": 100, "align": "end"},
    {"key": "p50", "label": "p50 ms", "kind": "number", "width": 90, "align": "end"},
    {"key": "p95", "label": "p95 ms", "kind": "number", "width": 90, "align": "end"},
]


class View(nu.Shape):
    both = ui.GridRef.slot(cols="2fr 1fr", stack_below=800, gap=4)


routes = View.both[0, 0].to(ui.CardRef.slot(title="Routes", subtitle="last minute, busiest first"))[0].to(
    ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Routes"))
codes = View.both[0, 1].to(ui.CardRef.slot(title="Status codes", subtitle="last minute"))[0].to(ui.PieChart.slot(height=240, donut=True))


def out(plane):
    def build(root):
        gw = OPS.gw.fallback({})
        read = nu.Dict.of(rows=views.route_rows(gw), codes=nu.Dict(gw).get_item("codes", {}))
        draw = lambda v: routes.set_rows(v["rows"]) >> codes.set(v["codes"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return kit.on_ops(plane, build)
"""


ACCESS = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "time", "label": "Time", "width": 120, "cell": ui.TextRef.slot(mono=True, size="sm")},
    {"key": "level", "label": "Level", "width": 100, "cell": ui.BadgeRef.slot(size="sm")},
    {"key": "message", "label": "Request"},
    {"key": "detail", "label": "Detail", "wrap": "truncate", "hide_below": 900},
]


class View(nu.Shape):
    access = ui.CardRef.slot(title="Access log", subtitle="the gateway's log, as it is written")


table = View.access[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Access log"))


def out(plane):
    def build(root):
        rows = views.log_rows(kit.tail("gateway", 12), "debug", "", 12)
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(rows), table.set_rows), every=2.0)

    return kit.on_ops(plane, build)
"""


TRAFFIC = (("knob", KNOB), ("charts", TRAFFIC_CHARTS), ("routes", ROUTES), ("access", ACCESS))


# --- logs ----------------------------------------------------------------------------------------


EXPLORER = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.model import JOBS
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "time", "label": "Time", "width": 120, "cell": ui.TextRef.slot(mono=True, size="sm")},
    {"key": "level", "label": "Level", "width": 100, "cell": ui.BadgeRef.slot(size="sm")},
    {"key": "message", "label": "Message"},
    {"key": "detail", "label": "Detail", "wrap": "truncate", "hide_below": 900},
]
LEVELS = ["debug", "info", "warning", "error"]


class View(nu.Shape):
    explorer = ui.PageSectionRef.slot(title="Explorer", description="Every job's stream, newest first. Pick one, a level, or search it.")


pick = View.explorer[0].to(ui.RowRef.slot(gap=3, wrap=True, grow={"find": 1}))
stream = pick["stream"].to(ui.SelectRef.slot(options=list(JOBS)))
level = pick["level"].to(ui.SelectRef.slot(options=LEVELS))
find = pick["find"].to(ui.InputRef.slot(placeholder="Find in the newest 4,000 lines, eg ranking or 503"))
live = pick["live"].to(ui.SwitchRef.slot(label="Follow", default=True))
said = View.explorer[1].to(ui.TextRef.slot(tone="muted", size="sm"))
lines = View.explorer[2].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Log lines"))


@nu.host
def told(name, counts, shown, took, needle):
    total = (counts or {}).get(name, 0)
    what = f"matching '{needle}' in the newest 4,000" if needle else "newest"
    return f"{total:,} lines in {name}. Showing {len(shown)} {what}, read in {took * 1000:.0f} ms."


def out(plane):
    def build(root):
        name, floor, needle = nu.Str(stream), nu.Str(level), nu.Str(find).strip()
        # A search scans the newest 4,000 lines, a plain look reads 80: either way the read stays the size of what is asked.
        n = nu.Int(nu.If(needle == "", 80, 4000))

        def show(t0):
            def drew(rows):
                line = told(name, OPS.counts.fallback({}), rows, nustd.time.time() - nu.Float(t0), needle)
                return lines.set_rows(rows) >> said.set(line)
            return nu.let(views.log_rows(kit.tail(name, n), floor, needle, 80), drew)

        once = nu.let(nustd.time.time(), show)
        follow = nu.Reconcile(nuspace.atomic(OPS.counts.on_change()), nu.IfDo(nu.Bool(live), once) >> nu.Delay(1.0), every=5.0)
        picked = [nu.ReactEvery(ev, once) for ev in (stream.on_change(), level.on_change(), find.on_change())]
        return stream.set("gateway") >> level.set("info") >> find.set("") >> live.set(True) >> said.set("Reading the stream") >> once >> nu.ParallelAsync(follow, *picked)

    return kit.on_ops(plane, build)
"""


VOLUME = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit
from nudemos.ops.state import OPS


class View(nu.Shape):
    volume = ui.CardRef.slot(title="Lines kept per stream")


bars_of = View.volume[0].to(ui.BarChart.slot(horizontal=True, height=260))


@nu.host
def bars(counts):
    return [[k, v] for k, v in sorted((counts or {}).items(), key=lambda kv: kv[1])]


def out(plane):
    return kit.on_ops(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.counts.on_change()])), nu.let(nuspace.atomic(bars(OPS.counts.fallback({}))), bars_of.set), every=5.0))
"""


LOGS = (("explorer", EXPLORER), ("volume", VOLUME))


# --- machine -------------------------------------------------------------------------------------


GAUGES = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

GAUGES = {"cpu": "CPU", "mem": "Memory", "disk": "Disk"}
TILES = {"cores": "Cores", "memory": "Memory in use", "disk": "Disk", "net": "Network", "uptime": "Up"}


class View(ui.Column):
    note = ui.TextRef.slot(tone="muted")
    gauges = ui.GridRef.slot(max_columns=3, min_cell_width=200, gap=4)
    tiles = ui.GridRef.slot(max_columns=5, min_cell_width=160, gap=3)


def gauge(k):
    card = View.gauges[k].to(ui.CardRef.slot(title=GAUGES[k], size="sm"))
    return card[0].to(ui.GaugeChart.slot(name=GAUGES[k], value_format="{value}%", height=170))


def tile(k):
    return View.tiles[k].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=TILES[k]))


def draw(v):
    m, t = v["m"], v["t"]
    return (
        nu.Sequential(*(gauge(k).set(m[k]) for k in GAUGES))
        >> nu.Sequential(*(tile(k).set(nu.Dict(t[k])["value"], delta=nu.Dict(t[k])["delta"]) for k in TILES))
    )


def out(plane):
    def build(root):
        m = OPS.machine.fallback({})
        read = nu.Dict.of(m=m, t=views.machine_tiles(m))
        note = View.note.set("The machine this space runs on, read from the kernel every 2 seconds by the telemetry job.")
        # Nothing to show before the telemetry job's first reading.
        shown = nu.IfDo(nuspace.atomic(OPS.machine.exists()), nu.let(nuspace.atomic(read), draw))
        return note >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.tick.on_change()])), shown, every=4.0)

    return kit.on_ops(plane, build)
"""


MACHINE_CHARTS = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

WINDOW = 900
TIME = {"x_type": "time", "x_format": "{HH}:{mm}", "y_min": 0, "height": 230}


class View(nu.Shape):
    both = ui.GridRef.slot(cols=2, stack_below=800, gap=4)


use = View.both[0, 0].to(ui.CardRef.slot(title="CPU and memory, %", subtitle="last 15 minutes"))[0].to(
    ui.LineChart.slot(("CPU %", "memory %"), y_max=100, **TIME))
load = View.both[0, 1].to(ui.CardRef.slot(title="Load", subtitle="1 minute average, last 15 minutes"))[0].to(
    ui.AreaChart.slot(("load",), colors=["var(--chart-6)"], **TIME))


def out(plane):
    def build(root):
        since = nu.Int(nu.ToInt(nustd.time.time())) - WINDOW
        end = since + WINDOW + 5
        read = nu.Dict.of(
            use=views.joined(views.named("CPU %", OPS.cpu.range(since, end)), views.named("memory %", OPS.mem.range(since, end))),
            load=views.named("load", OPS.load1.range(since, end)),
        )
        draw = lambda v: use.set(v["use"]) >> load.set(v["load"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.tick.on_change()])), nu.let(nuspace.atomic(read), draw), every=4.0)

    return kit.on_ops(plane, build)
"""


PROCS = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "job", "label": "Job", "width": 120},
    {"key": "process", "label": "Process", "width": 110, "align": "end"},
    {"key": "state", "label": "State", "width": 140},
    {"key": "cpu", "label": "CPU", "width": 100, "align": "end"},
    {"key": "memory", "label": "Memory", "width": 110, "align": "end"},
    {"key": "up", "label": "Up for", "align": "end"},
]


class View(nu.Shape):
    procs = ui.CardRef.slot(title="Every job's process", subtitle="read from the kernel with the rest")


table = View.procs[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Processes"))


def out(plane):
    def build(root):
        rows = views.proc_rows(OPS.machine.fallback({}), nu.Dict(OPS.jobs.extract()).fallback({}))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.tick.on_change()])), nu.let(nuspace.atomic(rows), table.set_rows), every=4.0)

    return kit.on_ops(plane, build)
"""


MACHINE = (("gauges", GAUGES), ("charts", MACHINE_CHARTS), ("procs", PROCS))


# --- deploys -------------------------------------------------------------------------------------


SHIP = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit
from nudemos.ops.gateway import RELEASES
from nudemos.ops.model import STABLE
from nudemos.ops.state import OPS


class View(nu.Shape):
    ship = ui.CardRef.slot(title="Release", subtitle="deploy one and the gateway restarts on it")


version = View.ship.actions[0].to(ui.SelectRef.slot(options=list(RELEASES)))
deploy = View.ship.actions[1].to(ui.ButtonRef.slot(label="Deploy", icon="upload", size="sm"))
rollback = View.ship.actions[2].to(ui.ButtonRef.slot(label=f"Roll back to {STABLE[-1]}", variant="secondary", icon="undo-2", size="sm"))
now = View.ship[0].to(ui.LineRef)
live = now[0].to(ui.StatusPillRef)
line = now[1].to(ui.TextRef.slot(tone="muted"))


@nu.host
def serving(release, gw, jobs):
    status = (jobs or {}).get("gateway", {}).get("status", "")
    version = (gw or {}).get("release")
    if status == "running" and version == release.get("version"):
        return {"label": f"{version} serving", "tone": "ok", "line": f"Deployed by {release.get('by', '')}. The gateway restarts on the new release when you deploy."}
    return {"label": f"{release.get('version', '')} {status or 'starting'}", "tone": "warn" if status in ("restarting", "starting") else "danger",
            "line": "The gateway is coming up on the release." if status in ("restarting", "starting", "running") else "The gateway is down. The supervisor keeps bringing it back."}


def out(plane):
    def build(root):
        shipping = kit.deploy(root, nu.Str(version), "you", "")
        back = kit.deploy(root, STABLE[-1], "you", "rollback")
        draw = lambda v: live.set(v["label"], tone=v["tone"]) >> line.set(v["line"])
        return version.set("1.9.0") >> deploy.init() >> rollback.init() >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.gw.on_change(), OPS.jobs.on_change()])), nu.let(nuspace.atomic(serving(OPS.release.fallback({}), OPS.gw.fallback({}), nu.Dict(OPS.jobs.extract()).fallback({}))), draw), every=2.0),
            nu.ReactEvery(deploy.on_click(), shipping),
            nu.ReactEvery(rollback.on_click(), back),
        )

    return kit.on_ops(plane, build)
"""


HISTORY = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "when", "label": "When", "width": 110, "cell": ui.RelativeTimeRef},
    {"key": "version", "label": "Release", "width": 100, "cell": ui.BadgeRef.slot(size="sm")},
    {"key": "from", "label": "From", "width": 90, "hide_below": 900},
    {"key": "by", "label": "By", "width": 140},
    {"key": "why", "label": "Note", "wrap": "truncate"},
]


class View(nu.Shape):
    both = ui.GridRef.slot(cols="2fr 1fr", stack_below=800, gap=4)


history = View.both[0, 0].to(ui.CardRef.slot(title="Deploys", subtitle="newest first, the live one marked"))[0].to(
    ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Deploys"))
notes = View.both[0, 1].to(ui.CardRef.slot(title="Releases"))[0].to(ui.MarkdownRef)


def out(plane):
    def build(root):
        read = nu.Dict.of(rows=views.deploy_rows(OPS.deploys.fallback([])), notes=views.release_notes(nu.Str(OPS.release.fallback({})["version"])))
        draw = lambda v: history.set_rows(v["rows"]) >> notes.set(v["notes"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.deploys.on_change()])), nu.let(nuspace.atomic(read), draw), every=30.0)

    return kit.on_ops(plane, build)
"""


DEPLOYS = (("ship", SHIP), ("history", HISTORY))


# --- incidents -----------------------------------------------------------------------------------


INCIDENT_BOARD = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos import pages
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "incident", "label": "Incident", "width": 120, "cell": ui.PageLinkRef.slot(variant="inline")},
    {"key": "sev", "label": "Sev", "width": 80, "cell": ui.BadgeRef.slot(size="sm")},
    {"key": "title", "label": "What", "wrap": "truncate"},
    {"key": "status", "label": "Status", "width": 120, "cell": ui.StatusPillRef},
    {"key": "opened", "label": "Opened", "width": 110, "cell": ui.RelativeTimeRef},
    {"key": "lasted", "label": "Lasted", "width": 100, "align": "end"},
    {"key": "release", "label": "Release", "width": 90, "hide_below": 900},
]


class View(nu.Shape):
    board = ui.CardRef.slot(title="Incidents", subtitle="open first, newest first")


table = View.board[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Incidents"))


@nu.host
def said(rows):
    return "No incidents yet. The alert rules open them on their own when the numbers turn." if not rows else f"{sum(1 for r in rows if r['status']['label'] != 'resolved')} open of {len(rows)}. Open one for its timeline."


def out(plane):
    def build(root):
        rows = views.incident_rows(nu.Dict(OPS.incidents.extract()).fallback({}), nu.Dict(OPS.made.incidents.extract()).fallback({}), nustd.time.time())
        draw = lambda r: table.set_rows(pages.linked(r, "incident")) >> View.board.set_caption(said(r))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.incidents.on_change()])), nu.let(nuspace.atomic(rows), draw), every=10.0)

    return kit.on_ops(plane, build)
"""


PAGER = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

PAGES = [
    {"key": "when", "label": "Sent", "width": 110, "cell": ui.RelativeTimeRef},
    {"key": "to", "label": "To", "width": 170},
    {"key": "text", "label": "Page", "wrap": "truncate"},
]
ROTA = [{"key": "name", "label": "On call"}, {"key": "role", "label": "As", "width": 150}, {"key": "team", "label": "Team", "width": 110}]


class View(nu.Shape):
    both = ui.GridRef.slot(cols=2, stack_below=800, gap=4)


sent = View.both[0, 0].to(ui.CardRef.slot(title="Who was paged", subtitle="newest first"))[0].to(
    ui.DataTableRef.slot(columns=PAGES, row_key="key", density="compact", label="Pages"))
rota = View.both[0, 1].to(ui.CardRef.slot(title="On call"))[0].to(
    ui.DataTableRef.slot(columns=ROTA, row_key="name", density="compact", label="Rota"))


def out(plane):
    def build(root):
        return rota.set_rows(OPS.oncall.fallback([])) >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.pager.on_change()])), nu.let(nuspace.atomic(views.page_rows(OPS.pager.fallback([]))), sent.set_rows))

    return kit.on_ops(plane, build)
"""


INCIDENTS = (("board", INCIDENT_BOARD), ("pager", PAGER))


INC_HEAD = """\
import nu
import nuspace
import nuspace.web as web
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS, folder_of

TIMELINE = [
    {"key": "time", "label": "Time", "width": 100, "cell": ui.TextRef.slot(mono=True, size="sm")},
    {"key": "what", "label": "What"},
    {"key": "who", "label": "Who", "width": 120, "hide_below": 640},
]


class View(nu.Shape):
    head = ui.PageSectionRef.slot()


ack = View.head.actions[0].to(ui.ButtonRef.slot(label="Acknowledge", variant="secondary", icon="check", size="sm"))
resolve = View.head.actions[1].to(ui.ButtonRef.slot(label="Resolve", icon="check", size="sm"))
runbook = View.head.actions[2].to(ui.LinkRef.slot(icon="book-open"))
top = View.head[0].to(ui.LineRef)
status = top[0].to(ui.StatusPillRef)
line = top[1].to(ui.TextRef.slot(tone="muted"))
card = View.head[1].to(ui.CardRef.slot(title="Timeline", subtitle="oldest first"))
timeline = card[0].to(ui.DataTableRef.slot(columns=TIMELINE, row_key="key", density="compact", label="Timeline"))
say = card[1].to(ui.RowRef.slot(gap=2, grow={"text": 1}))
text = say["text"].to(ui.InputRef.slot(placeholder="Add a note to the timeline"))
add = say["add"].to(ui.ButtonRef.slot(label="Add note", variant="secondary", icon="send"))


def draw(v):
    h = v["head"]
    return View.head.set_title(h["title"]) >> status.set(h["status"], tone=h["tone"]) >> line.set(h["line"]) >> timeline.set_rows(v["timeline"])


def out(plane):
    def build(root, iid):
        inc = OPS.incidents[iid].fallback({})
        read = nu.Dict.of(head=views.incident_head(inc, nustd.time.time()), timeline=views.timeline(inc))
        typed = nu.Str(text).strip()
        note = nu.IfDo(typed != "", kit.remark(root, iid, typed) >> text.set(""))
        first = ack.init() >> resolve.init() >> text.set("") >> add.init()
        linked = nuspace.atomic(web.link(runbook, folder_of("runbooks"), label="Open the runbook"))
        return first >> linked >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.incidents[iid].on_change()])), nu.let(nuspace.atomic(read), draw), every=5.0),
            nu.ReactEvery(ack.on_click(), kit.settle_incident(root, iid, "acked")),
            nu.ReactEvery(resolve.on_click(), kit.settle_incident(root, iid, "resolved")),
            nu.ReactEvery(add.on_click(), note),
        )

    return kit.on_subject(plane, "incident", build)
"""


INC_AROUND = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

TIME = {"x_type": "time", "x_format": "{HH}:{mm}", "y_min": 0, "height": 220}


class View(nu.Shape):
    both = ui.GridRef.slot(cols=2, stack_below=800, gap=4)


err = View.both[0, 0].to(ui.CardRef.slot(title="Failing requests, %", subtitle="around the incident"))[0].to(
    ui.LineChart.slot(("failing %",), colors=["var(--status-danger)"], **TIME))
rss = View.both[0, 1].to(ui.CardRef.slot(title="Gateway memory, MB", subtitle="around the incident"))[0].to(
    ui.AreaChart.slot(("gateway MB",), colors=["var(--chart-3)"], **TIME))


@nu.host
def window(inc, now):
    start = int((inc or {}).get("opened", now)) - 180
    end = int((inc or {}).get("resolved") or now) + 60
    return [start, min(end, int(now) + 1)]


def out(plane):
    def build(root, iid):
        w = nu.List(window(OPS.incidents[iid].fallback({}), nustd.time.time()))
        read = nu.Dict.of(err=views.named("failing %", OPS.err.sample(400, nu.Int(w[0]), nu.Int(w[1])), 100.0), rss=views.named("gateway MB", OPS.gw_rss.sample(400, nu.Int(w[0]), nu.Int(w[1]))))
        draw = lambda v: err.set(v["err"]) >> rss.set(v["rss"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(read), draw), every=3.0)

    return kit.on_subject(plane, "incident", build)
"""


INCIDENT_CELLS = (("incident", INC_HEAD), ("around", INC_AROUND))


# --- runbooks ------------------------------------------------------------------------------------


RUNBOOK = '''\
import nu
import nuspace
import nustd.http
import nustd.time
from nustd import ui
from nudemos.ops import kit
from nudemos.ops.model import STABLE
from nudemos.ops.state import OPS

TEXT = """\\
### Storefront API failing after a deploy

When the error rate jumps right after a release, roll back first and investigate after.
Each button runs its step for real, and what it found lands in the log below.
"""

#: The steps in order: label, variant, icon.
STEPS = {
    "health": ("1. Check health", "secondary", "search"),
    "errors": ("2. Read the errors", "secondary", "file-text"),
    "rollback": (f"3. Roll back to {STABLE[-1]}", "primary", "undo-2"),
    "verify": ("4. Verify", "secondary", "check"),
    "resolve": ("5. Resolve the incident", "secondary", "check"),
}


class Health(nu.Service):
    get = nustd.http.GETRef.method("{url}")


class View(ui.Column):
    text = ui.MarkdownRef.slot()
    steps = ui.GridRef.slot(max_columns=5, min_cell_width=180, gap=2)


def button(key):
    label, variant, icon = STEPS[key]
    return View.steps[key].to(ui.ButtonRef.slot(label=label, variant=variant, icon=icon))


@nu.host
def errors_said(rows):
    errs = [r for r in rows if r.get("level") in ("error", "critical")]
    if not errs:
        return [True, f"No errors in the newest {len(rows)} lines."]
    top = {}
    for r in errs:
        key = (r.get("fields") or {}).get("error") or r.get("msg", "")
        top[key.split("(")[0].strip()] = top.get(key.split("(")[0].strip(), 0) + 1
    worst = max(top.items(), key=lambda kv: kv[1])
    return [False, f"{len(errs)} errors in the newest {len(rows)} lines, most of them: {worst[0]} ({worst[1]}x)."]


@nu.host
def verified(gw):
    err, rel = gw.get("err", 1.0), gw.get("release", "?")
    return [err < 0.01, f"{err * 100:.1f}% of requests failing on {rel}, p95 {gw.get('p95', 0):.0f} ms."]


@nu.host
def healthy(reply):
    return [True, f"Health answers: release {reply.get('release')}, up {reply.get('up_s')}s, holding {reply.get('rss_mb')} MB."]


def out(plane):
    def build(root):
        def step(name, said):
            return nuspace.atomic(kit.ran(name, said))

        url = nu.Str("http://127.0.0.1:") + nu.str(OPS.settings.fallback({})["port"]) + "/health"
        probe = nu.TryCatch(nu.let(Health.get(url=url), lambda r: step("Check health", healthy(r))),
                            catch=lambda e: step("Check health", nu.List.of(False, "The gateway does not answer: connection refused.")))
        moves = {
            "health": nu.With(nustd.http.bind(Health, timeout=2.0), body=probe),
            "errors": nu.let(kit.tail("gateway", 600), lambda rows: step("Read the errors", errors_said(rows))),
            "rollback": kit.deploy(root, STABLE[-1], "you", "rollback from the runbook") >> step("Roll back", nu.List.of(True, f"Deployed {STABLE[-1]}, the gateway is restarting on it.")),
            "verify": step("Verify", verified(OPS.gw.fallback({}))),
            "resolve": kit.resolve_open(root, "gateway") >> step("Resolve the incident", nu.List.of(True, "Resolved the open storefront incident.")),
        }
        shown = View.text.set(TEXT) >> nu.Sequential(*(button(key).init() for key in STEPS))
        return shown >> nu.ParallelAsync(*(nu.ReactEvery(button(key).on_click(), move) for key, move in moves.items()))

    return kit.on_ops(plane, build)
'''


CHORES = '''\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit

TEXT = """\\
### Chores

Run a scheduled job now, beside its schedule. Each runs in its own process, like on schedule.
"""

#: Each chore by its job: button label, icon, what the steps log calls it.
CHORES = {
    "backup": ("Back up orders now", "save", "Back up orders"),
    "offsite": ("Send offsite now", "upload", "Send offsite"),
    "linkcheck": ("Check help links now", "link", "Check help links"),
    "digest": ("Write the digest now", "file-text", "Write the digest"),
}


class View(ui.Column):
    text = ui.MarkdownRef.slot()
    chores = ui.GridRef.slot(max_columns=4, min_cell_width=180, gap=2)


def button(name):
    label, icon, _ = CHORES[name]
    return View.chores[name].to(ui.ButtonRef.slot(label=label, variant="secondary", icon=icon))


def out(plane):
    def build(root):
        def run(name):
            what = CHORES[name][2]
            return kit.run_now(root, name) >> nuspace.atomic(kit.ran(what, nu.List.of(True, f"Started {name} in a fresh process.")))

        shown = View.text.set(TEXT) >> nu.Sequential(*(button(name).init() for name in CHORES))
        return shown >> nu.ParallelAsync(*(nu.ReactEvery(button(name).on_click(), run(name)) for name in CHORES))

    return kit.on_ops(plane, build)
'''


STEPS = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "when", "label": "When", "width": 110, "cell": ui.RelativeTimeRef},
    {"key": "step", "label": "Step", "width": 200},
    {"key": "result", "label": "Result", "width": 90, "cell": ui.BadgeRef.slot(size="sm")},
    {"key": "said", "label": "What it found", "wrap": "truncate"},
]


class View(nu.Shape):
    steps = ui.CardRef.slot(title="Steps run", subtitle="newest first")


table = View.steps[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Steps run"))


def out(plane):
    return kit.on_ops(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.steps.on_change()])), nu.let(nuspace.atomic(views.step_rows(OPS.steps.fallback([]))), table.set_rows)))
"""


RUNBOOKS = (("gateway", RUNBOOK), ("chores", CHORES), ("steps", STEPS))


# --- rules ---------------------------------------------------------------------------------------


RULE_BOARD = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "rule", "label": "Rule", "width": 150, "editable": False},
    {"key": "when", "label": "When", "editable": False},
    {"key": "then", "label": "Then", "editable": False, "hide_below": 900},
    {"key": "state", "label": "Now", "width": 100, "editable": False, "cell": ui.StatusPillRef},
    {"key": "fired", "label": "Fired", "width": 80, "kind": "number", "align": "end", "editable": False},
    {"key": "last", "label": "Last", "width": 100, "editable": False, "cell": ui.RelativeTimeRef},
    {"key": "on", "label": "On", "kind": "bool", "width": 70},
]
INTRO = "Each rule is a cell on the watchdog job, checked every 2 seconds against the live numbers. Turn one off here; read its code below."


class View(nu.Shape):
    rules = ui.CardRef.slot(title="Alert rules", subtitle=INTRO)


table = View.rules[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", editable=True, density="compact", label="Rules"))


def out(plane):
    def build(root):
        def flip(ev):
            rule = OPS.rules[nu.Str(ev["key"])]
            return nuspace.atomic(rule.set(kit.merged(rule.fallback({}), nu.Dict.of(on=nu.ToBool(ev["value"])))))

        read = views.rule_rows(nu.Dict(OPS.rules.extract()).fallback({}))
        return nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.rules.on_change()])), nu.let(nuspace.atomic(read), table.set_rows), every=5.0), nu.ReactEvery(table.on_edit(), flip))

    return kit.on_ops(plane, build)
"""


RULE_CODE = """\
import nu
import nuspace
from nustd import ui
from nudemos import headless
from nudemos.ops import kit
from nudemos.ops.jobs import RULES
from nudemos.ops.model import RULES as SAID
from nudemos.ops.state import worker_of

#: A section per rule, in the watchdog's order, titled by what it watches.
SECTIONS = [{"id": name, "label": SAID[name]["title"] + ": " + SAID[name]["says"].lower()} for name in RULES]


class View(nu.Shape):
    code = ui.CardRef.slot(title="How each rule reads", subtitle="the watchdog's cells, as they run now")


rules = View.code[0].to(ui.AccordionRef.slot(sections=SECTIONS))


def out(plane):
    def build(root):
        # The rules as they run now: read off the watchdog's cells, by name, so an edit there shows here.
        def one(name):
            cell = headless.cell_of(worker_of("watchdog"), name)
            return rules[name].to(ui.CodeRef.slot(language="python", wrap=True)).set(nu.str(nuspace.atomic(nuspace.Space.cells[cell].prog)))
        return nu.Sequential(*(one(name) for name in RULES)) >> nu.ForeverDo(nu.Delay(3600.0))

    return kit.on_root(plane, build)
"""


RULES = (("rules", RULE_BOARD), ("code", RULE_CODE))


# --- status --------------------------------------------------------------------------------------


STATUS_NOW = """\
import nu
import nuspace
from nustd import ui
from nudemos.ops import kit, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "name", "label": "Component"},
    {"key": "status", "label": "Status", "width": 150, "cell": ui.StatusPillRef},
    {"key": "note", "label": "Note", "wrap": "truncate", "hide_below": 640},
]


class View(ui.Column):
    banner = ui.AlertRef.slot()
    parts = ui.CardRef.slot(title="Components")


table = View.parts[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", label="Components"))


@nu.host
def banner(parts):
    bad = [p for p in parts if p["status"]["tone"] != "ok"]
    if not bad:
        return {"title": "All systems operational", "body": "Halcyon's storefront, search, checkout and help center are working normally.", "variant": "ok"}
    worst = "danger" if any(p["status"]["tone"] == "danger" for p in bad) else "warn"
    return {"title": "We are investigating an issue" if worst == "danger" else "Some systems are degraded",
            "body": ", ".join(p["name"] for p in bad) + ": " + bad[0]["status"]["label"].lower() + ". Updates follow here as we learn more.", "variant": worst}


def draw(parts):
    shown = nu.let(banner(parts), lambda v: View.banner.set(v["title"], body=v["body"], variant=v["variant"]))
    return shown >> table.set_rows(parts)


def out(plane):
    def build(root):
        read = views.components(OPS.gw.fallback({}), nu.Dict(OPS.jobs.extract()).fallback({}), OPS.release.fallback({}))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change(), OPS.jobs.on_change()])), nu.let(nuspace.atomic(read), draw), every=3.0)

    return kit.on_ops(plane, build)
"""


UPTIME = """\
import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.ops import kit
from nudemos.ops.state import OPS

#: A bar a minute, coloured by how many requests it served: under 95% danger, under 99.5% warn.
BANDS = {"visualMap": {"show": False, "dimension": 1, "pieces": [
    {"lt": 95, "color": "var(--status-danger)"},
    {"gte": 95, "lt": 99.5, "color": "var(--status-warn)"},
    {"gte": 99.5, "color": "var(--status-ok)"},
]}}


class View(nu.Shape):
    uptime = ui.CardRef.slot(title="Requests served", subtitle="minute by minute, the last hour")


bars_of = View.uptime[0].to(ui.BarChart.slot(y_min=50, y_max=100, height=200, value_format="{value}%", colors=["var(--status-ok)"], option=BANDS))


@nu.host
def minutes(pairs, now):
    by = {}
    for t, err in pairs or []:
        by.setdefault(int(t) // 60, []).append(err)
    # The last hour, or since the space opened when that is sooner: a bar a minute, never an empty run before it.
    # A gap of more than 5 minutes is the space closed, not an outage: start after it.
    first = min(by, default=int(now) // 60)
    for a, b in zip(sorted(by), sorted(by)[1:]):
        if b - a > 5:
            first = b
    first = max(int(now) // 60 - 59, first)
    out = []
    for m in range(first, int(now) // 60 + 1):
        errs = by.get(m)
        label = nu_time(m * 60)
        out.append([label, round(100 - sum(errs) / len(errs) * 100, 2) if errs else 0])
    return out


def nu_time(t):
    import time
    return time.strftime("%H:%M", time.localtime(t))


def out(plane):
    def build(root):
        now = nustd.time.time()
        since = nu.Int(nu.ToInt(now)) - 3600
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(minutes(OPS.err.sample(2400, since, since + 3605), now)), bars_of.set), every=10.0)

    return kit.on_ops(plane, build)
"""


STATUS = (("now", STATUS_NOW), ("uptime", UPTIME))


#: The pages under the root: key (its id after the root's), label, icon, cells.
FOLDERS = (
    ("jobs", "Jobs", "lucide:cog", JOBS),
    ("traffic", "Traffic", "lucide:activity", TRAFFIC),
    ("logs", "Logs", "lucide:square-terminal", LOGS),
    ("machine", "Machine", "lucide:cpu", MACHINE),
    ("deploys", "Deploys", "lucide:rocket", DEPLOYS),
    ("incidents", "Incidents", "lucide:flame", INCIDENTS),
    ("runbooks", "Runbooks", "lucide:book-open", RUNBOOKS),
    ("rules", "Rules", "lucide:bell", RULES),
    ("status", "Status", "lucide:gauge", STATUS),
)
