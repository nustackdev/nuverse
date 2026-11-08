"""The ops pages' cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the page it runs on comes in, and
:func:`.kit.on_ops` brackets it step by step over :data:`~.state.OPS`, the
root's state, found by its key. Pages of one kind run the same cells, told apart by their meta: eight
job pages, one program each.

- The root (:data:`ROOT`): welcome (and the first open), pulse, live, feed.
- :data:`FOLDERS`: Jobs, Traffic, Logs, Machine, Deploys, Incidents,
  Runbooks, Rules, Status, each with its cells.
- A job page (:data:`JOB`), an incident page (:data:`INCIDENT_CELLS`).
"""

from __future__ import annotations


__all__ = ["FOLDERS", "INCIDENT_CELLS", "JOB", "ROOT"]


# --- the root ------------------------------------------------------------------------------------


WELCOME = '''\
import nu
import nuspace
import nuspace.devices.web as web
import nustd.ui
from nudemos.ops import kit
from nudemos.ops.state import OPS

TEXT = """\\
Halcyon sells camping gear online. This is the space its two-person platform team runs it from.

Everything here is running: the storefront API is a real HTTP server in its own process, shoppers hit it,
backups archive real orders, a crawler checks the help center, and alert rules written as a few lines of Nu
watch the live numbers. Every block on every page is a small program: open its code, change it, run it again.
"""


class Ways(nustd.ui.Line):
    lead = nustd.ui.TextRef.slot()
    jobs = nustd.ui.LinkRef.slot()
    a = nustd.ui.TextRef.slot()
    deploys = nustd.ui.LinkRef.slot()
    b = nustd.ui.TextRef.slot()
    incidents = nustd.ui.LinkRef.slot()
    c = nustd.ui.TextRef.slot()
    status = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    ways = Ways.slot()


def out(plane):
    def draw(root):
        # Each folder by the id the first open minted for it, one read of the root's state.
        w, to = View.ways, lambda key: web.href(nuspace.atomic(nu.Str(OPS.made.folders[key])))
        return (
            View.about.set(TEXT)
            >> w.lead.set("Start at ") >> w.jobs.set(href=to("jobs"), label="the jobs")
            >> w.a.set(",  ship a release from ") >> w.deploys.set(href=to("deploys"), label="deploys")
            >> w.b.set(",  follow ") >> w.incidents.set(href=to("incidents"), label="incidents")
            >> w.c.set(",  or see what customers see on ") >> w.status.set(href=to("status"), label="the status page")
        )

    # The first open brings up the pages, the jobs and their schedules, once.
    return kit.on_root(plane, lambda root: kit.seed(root) >> draw(root) >> nu.ForeverDo(nu.Delay(3600.0)))
'''


PULSE = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

KEYS = ("release", "rps", "err", "p95", "orders", "incidents", "jobs")


class Tiles(nustd.ui.Grid):
    release = nustd.ui.StatRef.slot(label="Release")
    rps = nustd.ui.StatRef.slot(label="Requests/s")
    err = nustd.ui.StatRef.slot(label="Failing")
    p95 = nustd.ui.StatRef.slot(label="p95")
    orders = nustd.ui.StatRef.slot(label="Orders/min")
    incidents = nustd.ui.StatRef.slot(label="Incidents")
    jobs = nustd.ui.StatRef.slot(label="Jobs up")


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=7, min_width=105, gap=3)


def draw(t):
    def one(k):
        tile, v = getattr(View.tiles, k), nu.Dict(t[k])
        return tile.set_value(v["value"]) >> tile.set_delta(v["delta"]) >> tile.set_trend(v["trend"])

    return nu.Sequential(*(one(k) for k in KEYS))


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
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

WINDOW = 600


class Both(nustd.ui.Row):
    traffic = nustd.ui.AreaChart.slot(("requests a second",), title="Requests a second, last 10 minutes", x_type="time", x_format="{HH}:{mm}", height=220)
    errors = nustd.ui.LineChart.slot(("failing %",), title="Failing requests, %", x_type="time", x_format="{HH}:{mm}", y_min=0, height=220, colors=["#e5484d"])


class View(nustd.ui.Column):
    both = Both.slot(gap=4, wrap=True, min_width=380, align="start")


def out(plane):
    def build(root):
        since = nu.Int(nu.ToInt(nustd.time.time())) - WINDOW
        read = nu.Dict.of(
            rps=views.named("requests a second", OPS.rps.range(since, since + WINDOW + 5)),
            err=views.named("failing %", OPS.err.range(since, since + WINDOW + 5), 100.0),
        )
        draw = lambda v: View.both.traffic.set(v["rps"]) >> View.both.errors.set(v["err"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return kit.on_ops(plane, build)
"""


FEED = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [{"key": "when", "label": "When", "width": 100}, {"key": "kind", "label": "What", "width": 100}, {"key": "text", "label": "", "editable": False}]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    feed = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Feed")


def out(plane):
    def build(root):
        read = views.feed_rows(OPS.events.fallback([]), root, 14)
        return View.head.set("What happened, newest first") >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.events.on_change()])), nu.let(nuspace.atomic(read), View.feed.set_rows))

    return kit.on_ops(plane, build)
"""


ROOT = (("welcome", WELCOME), ("pulse", PULSE), ("live", LIVE), ("feed", FEED))


# --- jobs ----------------------------------------------------------------------------------------


BOARD = """\
import nu
import nuspace
import nustd.time
import nuspace.devices.web as web
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS, job_view

COLUMNS = [
    {"key": "job", "label": "Job", "width": 110},
    {"key": "what", "label": "What it is"},
    {"key": "schedule", "label": "Schedule", "width": 120},
    {"key": "status", "label": "Status", "width": 100},
    {"key": "last", "label": "Last"},
    {"key": "next", "label": "Next", "width": 100},
    {"key": "runs", "label": "Runs", "width": 150},
]


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    intro = nustd.ui.TextRef.slot()
    jobs = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, dense=True, label="Jobs")


def out(plane):
    def build(root):
        rows = views.job_rows(nu.Dict(OPS.jobs.extract()).fallback({}), nustd.time.time())
        opened = nu.ReactEvery(View.jobs.on_row_click(), lambda ev: View.history.push(web.href(nuspace.atomic(job_view(nu.Str(ev["key"]))))))
        intro = View.intro.set("Every job runs as a headless plane in its own process, kept up or scheduled by the supervisor. Click one for its runs, its log and its controls.")
        return intro >> nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.jobs.on_change()])), nu.let(nuspace.atomic(rows), View.jobs.set_rows), every=5.0), opened)

    return kit.on_ops(plane, build)
"""


RECENT = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit
from nudemos.ops.state import OPS

SCHEDULED = ["backup", "offsite", "linkcheck", "digest"]


class View(nustd.ui.Column):
    took = nustd.ui.BarChart.slot(SCHEDULED, title="How long the scheduled runs took, seconds", height=240, legend=True)


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
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.runs.on_change()])), nu.let(nuspace.atomic(bars(nu.Dict(OPS.runs.extract()).fallback({}))), View.took.set), every=10.0)

    return kit.on_ops(plane, build)
"""


JOBS = (("board", BOARD), ("took", RECENT))


JOB_HEAD = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS


class Top(nustd.ui.Row):
    status = nustd.ui.StatusPillRef.slot()
    line = nustd.ui.TextRef.slot()


class Controls(nustd.ui.Row):
    run = nustd.ui.ButtonRef.slot(label="Run now", icon="play")
    pause = nustd.ui.ButtonRef.slot(label="Pause", variant="secondary", icon="pause")
    restart = nustd.ui.ButtonRef.slot(label="Restart", variant="secondary", icon="refresh-cw")


class View(nustd.ui.Column):
    desc = nustd.ui.TextRef.slot()
    top = Top.slot(gap=3)
    controls = Controls.slot(gap=2)


def draw(h):
    c = View.controls
    paused = nu.Bool(h["paused"])
    return (
        View.desc.set(h["desc"]) >> View.top.status.set(h["status"], tone=h["tone"]) >> View.top.line.set(h["line"])
        >> c.pause.set(nu.Str(nu.If(paused, "Resume", "Pause")), icon=nu.Str(nu.If(paused, "play", "pause")))
        >> c.run.set_disabled(nu.Bool(h["service"])) >> c.restart.set_disabled(nu.Bool(h["service"]).not_())
    )


def out(plane):
    def build(root, name):
        head = views.job_head(OPS.jobs[name].fallback({}), name, nustd.time.time())
        flip = nu.IfDo(kit.paused(name), kit.resume(root, name), kit.pause(root, name))
        first = View.desc.set("") >> View.top.status.set("starting", tone="info") >> View.top.line.set("") >> View.controls.run.set("Run now", icon="play") >> View.controls.pause.set("Pause", variant="secondary", icon="pause") >> View.controls.restart.set("Restart", variant="secondary", icon="refresh-cw")
        return first >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.jobs.on_change()])), nu.let(nuspace.atomic(head), draw), every=1.0),
            nu.ReactEvery(View.controls.run.on_click(), kit.run_now(root, name)),
            nu.ReactEvery(View.controls.pause.on_click(), flip),
            nu.ReactEvery(View.controls.restart.on_click(), kit.restart(root, name)),
        )

    return kit.on_subject(plane, "job", build)
"""


JOB_RUNS = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "started", "label": "Started", "width": 100},
    {"key": "result", "label": "Result", "width": 90},
    {"key": "took", "label": "Took", "width": 90},
    {"key": "summary", "label": "Summary"},
    {"key": "process", "label": "Process", "width": 100},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    runs = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Runs")


def out(plane):
    def build(root, name):
        rows = views.job_runs(OPS.runs[name].fallback([]), OPS.jobs[name].fallback({}), nustd.time.time())
        return View.head.set("Runs, newest first") >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.runs[name].on_change(), OPS.jobs[name].on_change()])), nu.let(nuspace.atomic(rows), View.runs.set_rows), every=5.0)

    return kit.on_subject(plane, "job", build)
"""


JOB_LOG = """\
import nu
import nuspace
import nustd.ui
from nulog.messages.ops import tail
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [{"key": "time", "label": "Time", "width": 120}, {"key": "level", "label": "Level", "width": 90}, {"key": "message", "label": "Message"}, {"key": "detail", "label": "", "width": 260}]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    lines = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Log")


def out(plane):
    def build(root, name):
        # Its own stream, newest 25 lines: a read the size of what is shown, however long the stream.
        rows = views.log_rows(kit.tail(name, 25), "debug", "", 25)
        return View.head.set("Its log, live") >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.counts.on_change()])), nu.let(nuspace.atomic(rows), View.lines.set_rows), every=3.0)

    return kit.on_subject(plane, "job", build)
"""


JOB = (("head", JOB_HEAD), ("runs", JOB_RUNS), ("log", JOB_LOG))


# --- traffic -------------------------------------------------------------------------------------


KNOB = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit
from nudemos.ops.state import OPS


class Knob(nustd.ui.Row):
    users = nustd.ui.SliderRef.slot(label="Shoppers on the site", min=0, max=60, step=1)
    sent = nustd.ui.StatRef.slot(label="Requests sent")
    failed = nustd.ui.StatRef.slot(label="Failed")
    orders = nustd.ui.StatRef.slot(label="Orders placed")


class View(nustd.ui.Column):
    knob = Knob.slot(gap=6, wrap=True, min_width=180)


@nu.host
def shown(load):
    t = (load or {}).get("totals") or {}
    return {"sent": f"{t.get('sent', 0):,}", "failed": f"{t.get('failed', 0) + t.get('refused', 0):,}", "orders": f"{t.get('orders', 0):,}"}


def out(plane):
    def build(root):
        k = View.knob
        draw = lambda v: k.sent.set_value(v["sent"]) >> k.failed.set_value(v["failed"]) >> k.orders.set_value(v["orders"])
        moved = OPS.load.set(kit.merged(OPS.load.fallback({}), nu.Dict.of(users=nu.ToInt(k.users))))
        return k.users.set_value(nu.Float(OPS.load.fallback({})["users"])) >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.load.on_change()])), nu.let(nuspace.atomic(shown(OPS.load.fallback({}))), draw), every=2.0),
            nu.ReactEvery(k.users.on_change(), nuspace.atomic(moved)),
        )

    return kit.on_ops(plane, build)
"""


TRAFFIC_CHARTS = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

WINDOW = 300


class Charts(nustd.ui.Row):
    rps = nustd.ui.AreaChart.slot(("requests a second", "orders a minute"), title="Load", x_type="time", x_format="{HH}:{mm}", height=230)
    latency = nustd.ui.LineChart.slot(("p50", "p95"), title="Latency, ms", x_type="time", x_format="{HH}:{mm}", y_min=0, height=230)
    memory = nustd.ui.AreaChart.slot(("gateway MB",), title="Gateway memory, MB", x_type="time", x_format="{HH}:{mm}", y_min=0, height=230, colors=["#8e4ec6"])


class View(nustd.ui.Column):
    charts = Charts.slot(gap=4, wrap=True, min_width=320, align="start")


def out(plane):
    def build(root):
        since = nu.Int(nu.ToInt(nustd.time.time())) - WINDOW
        end = since + WINDOW + 5
        read = nu.Dict.of(
            load=views.joined(views.named("requests a second", OPS.rps.range(since, end)), views.named("orders a minute", OPS.orders.range(since, end))),
            latency=views.joined(views.named("p50", OPS.p50.range(since, end)), views.named("p95", OPS.p95.range(since, end))),
            rss=views.named("gateway MB", OPS.gw_rss.range(since, end)),
        )
        c = View.charts
        draw = lambda v: c.rps.set(v["load"]) >> c.latency.set(v["latency"]) >> c.memory.set(v["rss"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return kit.on_ops(plane, build)
"""


ROUTES = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "route", "label": "Route"},
    {"key": "rpm", "label": "Last minute", "kind": "number", "width": 120},
    {"key": "err", "label": "Failing", "width": 100},
    {"key": "p50", "label": "p50 ms", "kind": "number", "width": 90},
    {"key": "p95", "label": "p95 ms", "kind": "number", "width": 90},
]


class Both(nustd.ui.Row):
    routes = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Routes")
    codes = nustd.ui.PieChart.slot(title="Status codes, last minute", height=240, donut=True)


class View(nustd.ui.Column):
    both = Both.slot(gap=6, wrap=True, min_width=360, align="start")


def out(plane):
    def build(root):
        gw = OPS.gw.fallback({})
        read = nu.Dict.of(rows=views.route_rows(gw), codes=nu.Dict(gw).get_item("codes", {}))
        draw = lambda v: View.both.routes.set_rows(v["rows"]) >> View.both.codes.set(v["codes"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(read), draw), every=2.0)

    return kit.on_ops(plane, build)
"""


ACCESS = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [{"key": "time", "label": "Time", "width": 120}, {"key": "level", "label": "Level", "width": 90}, {"key": "message", "label": "Request"}, {"key": "detail", "label": ""}]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    lines = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Access log")


def out(plane):
    def build(root):
        rows = views.log_rows(kit.tail("gateway", 12), "debug", "", 12)
        return View.head.set("The gateway's log, as it is written") >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(rows), View.lines.set_rows), every=2.0)

    return kit.on_ops(plane, build)
"""


TRAFFIC = (("knob", KNOB), ("charts", TRAFFIC_CHARTS), ("routes", ROUTES), ("access", ACCESS))


# --- logs ----------------------------------------------------------------------------------------


EXPLORER = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.model import JOBS
from nudemos.ops.state import OPS

COLUMNS = [{"key": "time", "label": "Time", "width": 120}, {"key": "level", "label": "Level", "width": 90}, {"key": "message", "label": "Message"}, {"key": "detail", "label": ""}]
LEVELS = ["debug", "info", "warning", "error"]


class Pick(nustd.ui.Row):
    stream = nustd.ui.SelectRef.slot(options=list(JOBS))
    level = nustd.ui.SelectRef.slot(options=LEVELS)
    find = nustd.ui.InputRef.slot(placeholder="Find in the newest 4,000 lines, eg ranking or 503")
    live = nustd.ui.SwitchRef.slot(label="Follow", default=True)


class View(nustd.ui.Column):
    pick = Pick.slot(gap=3)
    said = nustd.ui.TextRef.slot()
    lines = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Log lines")


@nu.host
def told(name, counts, shown, took, needle):
    total = (counts or {}).get(name, 0)
    what = f"matching '{needle}' in the newest 4,000" if needle else "newest"
    return f"{total:,} lines in {name}. Showing {len(shown)} {what}, read in {took * 1000:.0f} ms."


def out(plane):
    p = View.pick

    def build(root):
        stream, level, needle = nu.Str(p.stream), nu.Str(p.level), nu.Str(p.find).strip()
        # A search scans the newest 4,000 lines, a plain look reads 80: either way the read stays the size of what is asked.
        n = nu.Int(nu.If(needle == "", 80, 4000))

        def show(t0):
            def drew(rows):
                said = told(stream, OPS.counts.fallback({}), rows, nustd.time.time() - nu.Float(t0), needle)
                return View.lines.set_rows(rows) >> View.said.set(said)
            return nu.let(views.log_rows(kit.tail(stream, n), level, needle, 80), drew)

        once = nu.let(nustd.time.time(), show)
        follow = nu.Reconcile(nuspace.atomic(OPS.counts.on_change()), nu.IfDo(nu.Bool(p.live), once) >> nu.Delay(1.0), every=5.0)
        picked = [nu.ReactEvery(ev, once) for ev in (p.stream.on_change(), p.level.on_change(), p.find.on_change())]
        return p.stream.set("gateway") >> p.level.set("info") >> p.find.set("") >> p.live.set(True) >> View.said.set("Reading the stream") >> once >> nu.ParallelAsync(follow, *picked)

    return kit.on_ops(plane, build)
"""


VOLUME = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit
from nudemos.ops.state import OPS


class View(nustd.ui.Column):
    volume = nustd.ui.BarChart.slot(title="Lines kept per stream", horizontal=True, height=260)


@nu.host
def bars(counts):
    return [[k, v] for k, v in sorted((counts or {}).items(), key=lambda kv: kv[1])]


def out(plane):
    return kit.on_ops(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.counts.on_change()])), nu.let(nuspace.atomic(bars(OPS.counts.fallback({}))), View.volume.set), every=5.0))
"""


LOGS = (("explorer", EXPLORER), ("volume", VOLUME))


# --- machine -------------------------------------------------------------------------------------


GAUGES = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

KEYS = ("cores", "memory", "disk", "net", "uptime")


class Gauges(nustd.ui.Row):
    cpu = nustd.ui.GaugeChart.slot(name="CPU", value_format="{value}%", height=170)
    mem = nustd.ui.GaugeChart.slot(name="memory", value_format="{value}%", height=170)
    disk = nustd.ui.GaugeChart.slot(name="disk", value_format="{value}%", height=170)


class Tiles(nustd.ui.Grid):
    cores = nustd.ui.StatRef.slot(label="Cores")
    memory = nustd.ui.StatRef.slot(label="Memory in use")
    disk = nustd.ui.StatRef.slot(label="Disk")
    net = nustd.ui.StatRef.slot(label="Network")
    uptime = nustd.ui.StatRef.slot(label="Up")


class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot()
    gauges = Gauges.slot(gap=4, wrap=True, min_width=200)
    tiles = Tiles.slot(columns=5, min_width=150, gap=3)


def draw(v):
    m, t, g = v["m"], v["t"], View.gauges
    return (
        g.cpu.set(m["cpu"]) >> g.mem.set(m["mem"]) >> g.disk.set(m["disk"])
        >> nu.Sequential(*(getattr(View.tiles, k).set_value(nu.Dict(t[k])["value"]) >> getattr(View.tiles, k).set_delta(nu.Dict(t[k])["delta"]) for k in KEYS))
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
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

WINDOW = 900


class Charts(nustd.ui.Row):
    use = nustd.ui.LineChart.slot(("CPU %", "memory %"), title="CPU and memory, last 15 minutes", x_type="time", x_format="{HH}:{mm}", y_min=0, y_max=100, height=230)
    load = nustd.ui.AreaChart.slot(("load",), title="Load, 1 minute", x_type="time", x_format="{HH}:{mm}", y_min=0, height=230, colors=["#12a594"])


class View(nustd.ui.Column):
    charts = Charts.slot(gap=4, wrap=True, min_width=380, align="start")


def out(plane):
    def build(root):
        since = nu.Int(nu.ToInt(nustd.time.time())) - WINDOW
        end = since + WINDOW + 5
        read = nu.Dict.of(
            use=views.joined(views.named("CPU %", OPS.cpu.range(since, end)), views.named("memory %", OPS.mem.range(since, end))),
            load=views.named("load", OPS.load1.range(since, end)),
        )
        draw = lambda v: View.charts.use.set(v["use"]) >> View.charts.load.set(v["load"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.tick.on_change()])), nu.let(nuspace.atomic(read), draw), every=4.0)

    return kit.on_ops(plane, build)
"""


PROCS = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "job", "label": "Job", "width": 120},
    {"key": "process", "label": "Process", "width": 110},
    {"key": "state", "label": "State", "width": 140},
    {"key": "cpu", "label": "CPU", "width": 100},
    {"key": "memory", "label": "Memory", "width": 110},
    {"key": "up", "label": "Up for"},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    procs = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Processes")


def out(plane):
    def build(root):
        rows = views.proc_rows(OPS.machine.fallback({}), nu.Dict(OPS.jobs.extract()).fallback({}))
        return View.head.set("Every job's process") >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.tick.on_change()])), nu.let(nuspace.atomic(rows), View.procs.set_rows), every=4.0)

    return kit.on_ops(plane, build)
"""


MACHINE = (("gauges", GAUGES), ("charts", MACHINE_CHARTS), ("procs", PROCS))


# --- deploys -------------------------------------------------------------------------------------


SHIP = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit
from nudemos.ops.gateway import RELEASES
from nudemos.ops.model import STABLE
from nudemos.ops.state import OPS


class Ship(nustd.ui.Row):
    version = nustd.ui.SelectRef.slot(options=list(RELEASES))
    deploy = nustd.ui.ButtonRef.slot(label="Deploy", icon="upload")
    rollback = nustd.ui.ButtonRef.slot(label="Roll back to 1.8.3", variant="secondary", icon="undo-2")


class Live(nustd.ui.Row):
    live = nustd.ui.StatusPillRef.slot()
    line = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    live = Live.slot(gap=3)
    ship = Ship.slot(gap=2)


@nu.host
def live(release, gw, jobs):
    status = (jobs or {}).get("gateway", {}).get("status", "")
    serving = (gw or {}).get("release")
    if status == "running" and serving == release.get("version"):
        return {"label": f"{serving} serving", "tone": "ok", "line": f"Deployed by {release.get('by', '')}. The gateway restarts on the new release when you deploy."}
    return {"label": f"{release.get('version', '')} {status or 'starting'}", "tone": "warn" if status in ("restarting", "starting") else "danger",
            "line": "The gateway is coming up on the release." if status in ("restarting", "starting", "running") else "The gateway is down. The supervisor keeps bringing it back."}


def out(plane):
    s = View.ship

    def build(root):
        picked = nu.Str(s.version)
        shipping = kit.deploy(root, picked, "you", "")
        back = kit.deploy(root, STABLE[-1], "you", "rollback")
        draw = lambda v: View.live.live.set(v["label"], tone=v["tone"]) >> View.live.line.set(v["line"])
        buttons = s.deploy.set("Deploy", icon="upload") >> s.rollback.set(f"Roll back to {STABLE[-1]}", variant="secondary", icon="undo-2")
        return s.version.set("1.9.0") >> buttons >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.gw.on_change(), OPS.jobs.on_change()])), nu.let(nuspace.atomic(live(OPS.release.fallback({}), OPS.gw.fallback({}), nu.Dict(OPS.jobs.extract()).fallback({}))), draw), every=2.0),
            nu.ReactEvery(s.deploy.on_click(), shipping),
            nu.ReactEvery(s.rollback.on_click(), back),
        )

    return kit.on_ops(plane, build)
"""


HISTORY = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [{"key": "when", "label": "When", "width": 110}, {"key": "version", "label": "Release", "width": 100}, {"key": "from", "label": "From", "width": 100}, {"key": "by", "label": "By", "width": 160}, {"key": "why", "label": "Note"}]


class Both(nustd.ui.Row):
    history = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Deploys")
    notes = nustd.ui.MarkdownRef.slot()


class View(nustd.ui.Column):
    both = Both.slot(gap=6, wrap=True, min_width=360, align="start")


def out(plane):
    def build(root):
        read = nu.Dict.of(rows=views.deploy_rows(OPS.deploys.fallback([]), nustd.time.time()), notes=views.release_notes(nu.Str(OPS.release.fallback({})["version"])))
        draw = lambda v: View.both.history.set_rows(v["rows"]) >> View.both.notes.set(nu.Str("### Releases\\n\\n") + nu.Str(v["notes"]))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.deploys.on_change()])), nu.let(nuspace.atomic(read), draw), every=30.0)

    return kit.on_ops(plane, build)
"""


DEPLOYS = (("ship", SHIP), ("history", HISTORY))


# --- incidents -----------------------------------------------------------------------------------


INCIDENT_BOARD = """\
import nu
import nuspace
import nustd.time
import nuspace.devices.web as web
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS, incident_view

COLUMNS = [
    {"key": "id", "label": "Incident", "width": 110},
    {"key": "sev", "label": "Sev", "width": 70},
    {"key": "title", "label": "What"},
    {"key": "status", "label": "Status", "width": 110},
    {"key": "opened", "label": "Opened", "width": 100},
    {"key": "lasted", "label": "Lasted", "width": 100},
    {"key": "release", "label": "Release", "width": 90},
]


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    empty = nustd.ui.TextRef.slot()
    incidents = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, dense=True, label="Incidents")


@nu.host
def said(rows):
    return "No incidents yet. The alert rules open them on their own when the numbers turn." if not rows else f"{sum(1 for r in rows if r['status'] != 'resolved')} open of {len(rows)}. Click one for its timeline."


def out(plane):
    def build(root):
        rows = views.incident_rows(nu.Dict(OPS.incidents.extract()).fallback({}), nustd.time.time())
        draw = lambda r: View.incidents.set_rows(r) >> View.empty.set(said(r))
        opened = nu.ReactEvery(View.incidents.on_row_click(), lambda ev: View.history.push(web.href(nuspace.atomic(incident_view(nu.Str(ev["key"]))))))
        return nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.incidents.on_change()])), nu.let(nuspace.atomic(rows), draw), every=10.0), opened)

    return kit.on_ops(plane, build)
"""


PAGER = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [{"key": "when", "label": "Sent", "width": 100}, {"key": "to", "label": "To", "width": 170}, {"key": "text", "label": "Page"}]
ROTA = [{"key": "name", "label": "On call"}, {"key": "role", "label": "As", "width": 150}, {"key": "team", "label": "Team", "width": 110}]


class Both(nustd.ui.Row):
    pages = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Pages")
    rota = nustd.ui.TableRef.slot(columns=ROTA, row_key="name", dense=True, label="Rota")


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    both = Both.slot(gap=6, wrap=True, min_width=320, align="start")


@nu.host
def rows(pager):
    return [{"key": f"{p['at']}-{i}", "when": shape.clock(p["at"]), "to": f"{p['to']} ({p['role']})", "text": p["text"]} for i, p in enumerate(pager or [])][:20]


def out(plane):
    def build(root):
        return View.head.set("Who was paged") >> View.both.rota.set_rows(OPS.oncall.fallback([])) >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.pager.on_change()])), nu.let(nuspace.atomic(rows(OPS.pager.fallback([]))), View.both.pages.set_rows))

    return kit.on_ops(plane, build)
"""


INCIDENTS = (("board", INCIDENT_BOARD), ("pager", PAGER))


INC_HEAD = """\
import nu
import nuspace
import nuspace.devices.web as web
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS, folder_of


class Top(nustd.ui.Row):
    status = nustd.ui.StatusPillRef.slot()
    line = nustd.ui.TextRef.slot()


class Act(nustd.ui.Row):
    ack = nustd.ui.ButtonRef.slot(label="Acknowledge", variant="secondary", icon="check")
    resolve = nustd.ui.ButtonRef.slot(label="Resolve", icon="check")
    runbook = nustd.ui.LinkRef.slot()


class Say(nustd.ui.Row):
    text = nustd.ui.InputRef.slot(placeholder="Add a note to the timeline")
    add = nustd.ui.ButtonRef.slot(label="Add note", variant="secondary", icon="send")


class View(nustd.ui.Column):
    title = nustd.ui.HeadingRef.slot(level=2)
    top = Top.slot(gap=3)
    act = Act.slot(gap=2)
    timeline = nustd.ui.MarkdownRef.slot()
    say = Say.slot(gap=2)


def draw(v):
    h = v["head"]
    return View.title.set(h["title"]) >> View.top.status.set(h["status"], tone=h["tone"]) >> View.top.line.set(h["line"]) >> View.timeline.set(v["timeline"])


def out(plane):
    def build(root, iid):
        inc = OPS.incidents[iid].fallback({})
        read = nu.Dict.of(head=views.incident_head(inc, nustd.time.time()), timeline=views.timeline(inc))
        typed = nu.Str(View.say.text).strip()
        note = nu.IfDo(typed != "", kit.remark(root, iid, typed) >> View.say.text.set(""))
        labels = (
            View.title.set("") >> View.top.status.set("open", tone="danger") >> View.top.line.set("")
            >> View.act.ack.set("Acknowledge", variant="secondary", icon="check") >> View.act.resolve.set("Resolve", icon="check")
            >> View.say.text.set("") >> View.say.add.set("Add note", variant="secondary", icon="send")
        )
        runbook = web.href(nuspace.atomic(folder_of("runbooks")))
        return labels >> View.act.runbook.set(href=runbook, label="Open the runbook") >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.incidents[iid].on_change()])), nu.let(nuspace.atomic(read), draw), every=5.0),
            nu.ReactEvery(View.act.ack.on_click(), kit.settle_incident(root, iid, "acked")),
            nu.ReactEvery(View.act.resolve.on_click(), kit.settle_incident(root, iid, "resolved")),
            nu.ReactEvery(View.say.add.on_click(), note),
        )

    return kit.on_subject(plane, "incident", build)
"""


INC_AROUND = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS


class Charts(nustd.ui.Row):
    err = nustd.ui.LineChart.slot(("failing %",), title="Failing requests around it, %", x_type="time", x_format="{HH}:{mm}", y_min=0, height=220, colors=["#e5484d"])
    rss = nustd.ui.AreaChart.slot(("gateway MB",), title="Gateway memory around it, MB", x_type="time", x_format="{HH}:{mm}", y_min=0, height=220, colors=["#8e4ec6"])


class View(nustd.ui.Column):
    charts = Charts.slot(gap=4, wrap=True, min_width=360, align="start")


@nu.host
def window(inc, now):
    start = int((inc or {}).get("opened", now)) - 180
    end = int((inc or {}).get("resolved") or now) + 60
    return [start, min(end, int(now) + 1)]


def out(plane):
    def build(root, iid):
        w = nu.List(window(OPS.incidents[iid].fallback({}), nustd.time.time()))
        read = nu.Dict.of(err=views.named("failing %", OPS.err.sample(400, nu.Int(w[0]), nu.Int(w[1])), 100.0), rss=views.named("gateway MB", OPS.gw_rss.sample(400, nu.Int(w[0]), nu.Int(w[1]))))
        draw = lambda v: View.charts.err.set(v["err"]) >> View.charts.rss.set(v["rss"])
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
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.model import STABLE
from nudemos.ops.state import OPS

TEXT = """\\
### Storefront API failing after a deploy

When the error rate jumps right after a release, roll back first and investigate after.
Each button runs its step for real, and what it found lands in the log below.
"""


class Health(nu.Service):
    get = nustd.http.GETRef.method("{url}")


class Steps(nustd.ui.Grid):
    health = nustd.ui.ButtonRef.slot(label="1. Check health", variant="secondary", icon="search")
    errors = nustd.ui.ButtonRef.slot(label="2. Read the errors", variant="secondary", icon="file-text")
    rollback = nustd.ui.ButtonRef.slot(label="3. Roll back", icon="undo-2")
    verify = nustd.ui.ButtonRef.slot(label="4. Verify", variant="secondary", icon="check")
    resolve = nustd.ui.ButtonRef.slot(label="5. Resolve the incident", variant="secondary", icon="check")


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    steps = Steps.slot(columns=5, min_width=170, gap=2)


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
    s = View.steps

    def build(root):
        def step(name, said):
            return nuspace.atomic(kit.ran(name, said))

        url = nu.Str("http://127.0.0.1:") + nu.str(OPS.settings.fallback({})["port"]) + "/health"
        probe = nu.TryCatch(nu.let(Health.get(url=url), lambda r: step("Check health", healthy(r))),
                            catch=lambda e: step("Check health", nu.List.of(False, "The gateway does not answer: connection refused.")))
        health = nu.With(nustd.http.bind(Health, timeout=2.0), body=probe)
        errs = nu.let(kit.tail("gateway", 600), lambda rows: step("Read the errors", errors_said(rows)))
        back = kit.deploy(root, STABLE[-1], "you", "rollback from the runbook") >> step("Roll back", nu.List.of(True, f"Deployed {STABLE[-1]}, the gateway is restarting on it."))
        verify = step("Verify", verified(OPS.gw.fallback({})))
        resolve = kit.resolve_open(root, "gateway") >> step("Resolve the incident", nu.List.of(True, "Resolved the open storefront incident."))
        labels = (
            s.health.set("1. Check health", variant="secondary", icon="search")
            >> s.errors.set("2. Read the errors", variant="secondary", icon="file-text")
            >> s.rollback.set(f"3. Roll back to {STABLE[-1]}", icon="undo-2")
            >> s.verify.set("4. Verify", variant="secondary", icon="check")
            >> s.resolve.set("5. Resolve the incident", variant="secondary", icon="check")
        )
        return View.text.set(TEXT) >> labels >> nu.ParallelAsync(
            nu.ReactEvery(s.health.on_click(), health),
            nu.ReactEvery(s.errors.on_click(), errs),
            nu.ReactEvery(s.rollback.on_click(), back),
            nu.ReactEvery(s.verify.on_click(), verify),
            nu.ReactEvery(s.resolve.on_click(), resolve),
        )

    return kit.on_ops(plane, build)
'''


CHORES = '''\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit

TEXT = """\\
### Chores

Run a scheduled job now, beside its schedule. Each runs in its own process, like on schedule.
"""


class Chores(nustd.ui.Row):
    backup = nustd.ui.ButtonRef.slot(label="Back up orders now", variant="secondary", icon="save")
    offsite = nustd.ui.ButtonRef.slot(label="Send offsite now", variant="secondary", icon="upload")
    links = nustd.ui.ButtonRef.slot(label="Check help links now", variant="secondary", icon="link")
    digest = nustd.ui.ButtonRef.slot(label="Write the digest now", variant="secondary", icon="file-text")


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    chores = Chores.slot(gap=2, wrap=True, min_width=160)


def out(plane):
    c = View.chores

    def build(root):
        def run(name, what):
            return kit.run_now(root, name) >> nuspace.atomic(kit.ran(what, nu.List.of(True, f"Started {name} in a fresh process.")))

        labels = (
            c.backup.set("Back up orders now", variant="secondary", icon="save")
            >> c.offsite.set("Send offsite now", variant="secondary", icon="upload")
            >> c.links.set("Check help links now", variant="secondary", icon="link")
            >> c.digest.set("Write the digest now", variant="secondary", icon="file-text")
        )
        return View.text.set(TEXT) >> labels >> nu.ParallelAsync(
            nu.ReactEvery(c.backup.on_click(), run("backup", "Back up orders")),
            nu.ReactEvery(c.offsite.on_click(), run("offsite", "Send offsite")),
            nu.ReactEvery(c.links.on_click(), run("linkcheck", "Check help links")),
            nu.ReactEvery(c.digest.on_click(), run("digest", "Write the digest")),
        )

    return kit.on_ops(plane, build)
'''


STEPS = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [{"key": "when", "label": "When", "width": 100}, {"key": "step", "label": "Step", "width": 200}, {"key": "result", "label": "", "width": 80}, {"key": "said", "label": "What it found"}]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    steps = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Steps run")


@nu.host
def rows(steps):
    return [{"key": f"{s['at']}-{i}", "when": shape.clock(s["at"]), "step": s["step"], "result": "ok" if s["ok"] else "not ok", "said": s["said"]} for i, s in enumerate(steps or [])][:16]


def out(plane):
    return kit.on_ops(plane, lambda root: View.head.set("Steps run, newest first") >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.steps.on_change()])), nu.let(nuspace.atomic(rows(OPS.steps.fallback([]))), View.steps.set_rows)))
"""


RUNBOOKS = (("gateway", RUNBOOK), ("chores", CHORES), ("steps", STEPS))


# --- rules ---------------------------------------------------------------------------------------


RULE_BOARD = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS

COLUMNS = [
    {"key": "rule", "label": "Rule", "width": 150},
    {"key": "when", "label": "When"},
    {"key": "then", "label": "Then"},
    {"key": "state", "label": "Now", "width": 90},
    {"key": "fired", "label": "Fired", "width": 130},
    {"key": "on", "label": "On", "kind": "bool", "width": 70},
]


class View(nustd.ui.Column):
    intro = nustd.ui.MarkdownRef.slot()
    rules = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, dense=True, label="Rules")


@nu.host
def rows(rules, now):
    return [{**r, "on": (rules or {}).get(r["key"], {}).get("on", True)} for r in shape.rule_rows(rules, now)]


INTRO = "Each rule is a cell on the watchdog job, checked every 2 seconds against the live numbers. Turn one off here; read its code below."


def out(plane):
    def build(root):
        def flip(ev):
            rule = OPS.rules[nu.Str(ev["key"])]
            return nuspace.atomic(rule.set(kit.merged(rule.fallback({}), nu.Dict.of(on=nu.ToBool(ev["value"])))))

        read = rows(nu.Dict(OPS.rules.extract()).fallback({}), nustd.time.time())
        return View.intro.set(INTRO) >> nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.rules.on_change()])), nu.let(nuspace.atomic(read), View.rules.set_rows), every=5.0), nu.ReactEvery(View.rules.on_edit(), flip))

    return kit.on_ops(plane, build)
"""


RULE_CODE = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit
from nudemos.ops.jobs import RULES
from nudemos.ops.model import RULES as SAID
from nudemos import headless
from nudemos.ops.state import worker_of


# A heading and the code of each rule, in order.
SLOTS = {}
for name in RULES:
    SLOTS["h_" + name] = nustd.ui.HeadingRef.slot(level=4)
    SLOTS["c_" + name] = nustd.ui.CodeRef.slot(language="python", wrap=True)
View = type("View", (nustd.ui.Column,), SLOTS)


def out(plane):
    def build(root):
        # The rules as they run now: read off the watchdog's cells, by name, so an edit there shows here.
        def one(name):
            cell = headless.cell_of(worker_of("watchdog"), name)
            code = getattr(View, "c_" + name).set(nu.str(nuspace.atomic(nuspace.Space.cells[cell].prog)))
            return getattr(View, "h_" + name).set(SAID[name]["title"] + ": " + SAID[name]["says"].lower()) >> code
        return nu.Sequential(*(one(name) for name in RULES)) >> nu.ForeverDo(nu.Delay(3600.0))

    return kit.on_root(plane, build)
"""


RULES = (("rules", RULE_BOARD), ("code", RULE_CODE))


# --- status --------------------------------------------------------------------------------------


STATUS_NOW = """\
import nu
import nuspace
import nustd.ui
from nudemos.ops import kit, shape, views
from nudemos.ops.state import OPS


class Component(nustd.ui.Row):
    name = nustd.ui.TextRef.slot()
    pill = nustd.ui.StatusPillRef.slot()
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    banner = nustd.ui.AlertRef.slot()
    parts = nustd.ui.GridRef.slot(Component, columns=1, gap=2)


@nu.host
def banner(parts):
    bad = [p for p in parts if p["tone"] != "ok"]
    if not bad:
        return {"title": "All systems operational", "body": "Halcyon's storefront, search, checkout and help center are working normally.", "variant": "ok"}
    worst = "danger" if any(p["tone"] == "danger" for p in bad) else "warn"
    return {"title": "We are investigating an issue" if worst == "danger" else "Some systems are degraded",
            "body": ", ".join(p["name"] for p in bad) + ": " + bad[0]["label"].lower() + ". Updates follow here as we learn more.", "variant": worst}


def draw(parts):
    b = banner(parts)
    one = lambda i: View.parts[nu.str(i)].name.set(nu.List(parts)[i]["name"]) >> View.parts[nu.str(i)].pill.set(nu.List(parts)[i]["label"], tone=nu.List(parts)[i]["tone"]) >> View.parts[nu.str(i)].note.set(nu.List(parts)[i]["note"])
    shown = nu.let(b, lambda v: View.banner.set(v["title"], body=v["body"], variant=v["variant"]))
    return shown >> nu.ForRangeDo(0, nu.List(parts).len(), one)


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
import nustd.ui
from nudemos.ops import kit
from nudemos.ops.state import OPS


class View(nustd.ui.Column):
    uptime = nustd.ui.BarChart.slot(
        title="Requests served, minute by minute", y_min=50, y_max=100, height=200, value_format="{value}%", colors=["#30a46c"],
        option={"visualMap": {"show": False, "dimension": 1, "pieces": [{"lt": 95, "color": "#e5484d"}, {"gte": 95, "lt": 99.5, "color": "#f5a524"}, {"gte": 99.5, "color": "#30a46c"}]}},
    )


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
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[OPS.beat.on_change()])), nu.let(nuspace.atomic(minutes(OPS.err.sample(2400, since, since + 3605), now)), View.uptime.set), every=10.0)

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
