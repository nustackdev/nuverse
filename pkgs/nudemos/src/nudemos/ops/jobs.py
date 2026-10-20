"""The jobs' cells, as sources: each job is a headless plane, its cells these short Nu programs.

Nu owns the loops, the commits and the schedule; the resources in
:mod:`.gateway`, :mod:`.work` and :mod:`.machine` own the sockets, the files
and ``/proc``. Every job writes its side into the root's :class:`~.state.Ops`
in short commits, and the pages follow those writes.

- ``gateway``: serves the storefront API, flushes its log and numbers once a second.
- ``traffic``: a second of shoppers per turn, as many as the Traffic page says.
- ``telemetry``: the machine and every job's process, every 2 seconds.
- ``watchdog``: one cell per alert rule (:data:`RULES`).
- ``backup``, ``offsite``, ``linkcheck``, ``digest``: one run each time the
  supervisor starts them, their schedule a fixed delay (:func:`scheduled`).

:data:`SOURCES` is every job's cells by name, what :func:`.kit.seed` writes.
"""

from __future__ import annotations

from .model import JOBS


__all__ = ["GATEWAY", "RULES", "SOURCES", "TELEMETRY", "TRAFFIC", "scheduled"]


GATEWAY = """\
import nu
import nustd.time
from nudemos.ops import kit
from nudemos.ops.calls import Drain, Open
from nudemos.ops.gateway import Gateway
from nudemos.ops.state import Ops

SERIES = {"rps": Ops.rps, "err": Ops.err, "p50": Ops.p50, "p95": Ops.p95, "gw_rss": Ops.gw_rss, "orders": Ops.orders}


@nu.host
def crashed(rec, gw, now):
    # The flush that finds it out of memory says so before the next one raises.
    return {**rec, "status": "crashed", "crashed": now, "reason": gw["dying"], "crashes": rec.get("crashes", 0) + 1}


def flush(root, d):
    d, t = nu.Dict(d), nu.Int(nu.Dict(d)["point"]["t"])
    me = Ops.jobs["gateway"]
    dying = nu.Str(nu.Dict(d["gw"])["dying"]) != ""
    return kit.landed(root,
        kit.logged("gateway", d["lines"]) >> Ops.gw.set(d["gw"])
        >> nu.Sequential(*(ref.set_item(t, nu.Float(d["point"][k])) for k, ref in SERIES.items()))
        >> nu.IfDo(dying, me.set(crashed(me.fallback({}), d["gw"], nustd.time.time())))
        >> Ops.beat.set(Ops.beat.fallback(0) + 1)
    )


def out(plane):
    def serve(root):
        cfg = nu.Dict(kit.snap(kit.at_root(root, nu.Dict.of(settings=Ops.settings.fallback({}), release=Ops.release.fallback({})))))
        opened = Open(cfg["settings"]["port"], cfg["release"]["version"], cfg["settings"]["data"])
        up = kit.landed(root, kit.job_started("gateway"))
        # Once a second, what it served: lines, numbers, a point per series. Out of memory, Drain raises.
        loop = nu.ForeverDo(nu.Delay(1.0) >> nu.let(Drain(), lambda d: flush(root, d)))
        return up >> nu.Provide(Gateway, {}, nu.let(opened, lambda d: flush(root, d)) >> loop)

    return kit.on_root(plane, serve)
"""


TRAFFIC = """\
import nu
from nudemos.ops import kit
from nudemos.ops.calls import Shop
from nudemos.ops.state import Ops
from nudemos.ops.work import Shoppers


@nu.host
def tallied(load, shop):
    # The knob stays the page's: only what the shoppers saw is written over it.
    return {**(load or {}), **{k: v for k, v in shop.items() if k not in ("lines", "users")}, "active": shop["users"]}


def turn(root):
    knobs = kit.snap(kit.at_root(root, nu.Dict.of(users=Ops.load.fallback({})["users"], port=Ops.settings.fallback({})["port"])))
    shop = nu.let(knobs, lambda k: Shop(nu.Dict(k)["port"], nu.Dict(k)["users"]))
    write = lambda s: kit.landed(root, Ops.load.set(tallied(Ops.load.fallback({}), s)) >> kit.logged("traffic", nu.Dict(s)["lines"]))
    return nu.let(shop, write)


def out(plane):
    def shoppers(root):
        up = kit.landed(root, kit.job_started("traffic") >> kit.said("traffic", "info", "shoppers starting"))
        return up >> nu.Provide(Shoppers, {}, nu.ForeverDo(turn(root)))

    return kit.on_root(plane, shoppers)
"""


TELEMETRY = """\
import nu
import nustd.time
from nudemos.ops import kit
from nudemos.ops.calls import Read
from nudemos.ops.machine import Machine
from nudemos.ops.state import Ops

EVERY = 2.0
SERIES = {"cpu": Ops.cpu, "mem": Ops.mem, "disk": Ops.disk, "load1": Ops.load1}


@nu.host
def pids(jobs):
    return {name: j.get("pid", 0) for name, j in (jobs or {}).items() if j.get("pid")}


@nu.host
def point(m):
    return {"t": int(m["at"]), "cpu": m["cpu"], "mem": m["mem"], "disk": m["disk"], "load1": m["load"][0]}


@nu.host
def lost(jobs, m):
    # A service whose process is gone and that has not said why: down, until it starts again.
    up = {p["job"]: p["up"] for p in m["procs"]}
    return {
        name: {**j, "status": "down"}
        for name, j in (jobs or {}).items()
        if j.get("kind") == "service" and j.get("status") == "running" and up.get(name) is False
    }


def write(root, m):
    p = nu.Dict(point(m))
    t = nu.Int(p["t"])
    downs = lost(nu.Dict(Ops.jobs.extract()), m)
    return kit.landed(root,
        Ops.machine.set(m)
        >> nu.Sequential(*(ref.set_item(t, nu.Float(p[k])) for k, ref in SERIES.items()))
        >> nu.ForEachDo(nu.Dict(downs).items(), lambda kv: Ops.jobs[nu.Str(kv[0])].set(kv[1]))
        >> Ops.tick.set(Ops.tick.fallback(0) + 1)
    )


def out(plane):
    def watch(root):
        asked = kit.snap(kit.at_root(root, nu.Dict.of(pids=pids(nu.Dict(Ops.jobs.extract())), disk=Ops.settings.fallback({})["data"])))
        read = nu.let(asked, lambda a: nu.let(Read(nu.Dict(a)["pids"], nu.Dict(a)["disk"]), lambda m: write(root, m)))
        up = kit.landed(root, kit.job_started("telemetry"))
        return up >> nu.Provide(Machine, {}, nu.ForeverDo(read >> nu.Delay(EVERY)))

    return kit.on_root(plane, watch)
"""


#: The alert rules, one cell each on the watchdog. Each is a check over the live numbers and what it does.
RULES = {
    "error_rate": """\
import nu
from nudemos.ops import kit


# More than 5% of gateway requests fail for 6 seconds, or it stops answering: open an incident, page the primary.
@nu.host
def check(v):
    gw, status = v["gw"], v["jobs"].get("gateway", {}).get("status")
    if status in ("crashed", "down"):
        return f"the gateway is not answering on {gw.get('release')}"
    return f"{gw['err']:.0%} of requests failing on {gw['release']}" if gw.get("rps", 0) > 1 and gw.get("err", 0) > 0.05 else ""


def act(root, why):
    return kit.incident(root, "gateway", "Storefront API failing", 2, why) >> kit.page(root, "primary", why)


def out(plane):
    calm = lambda root: kit.calm(root, "gateway", "Errors back under 5%")
    return kit.rule(plane, "error_rate", check, act, hold=3, clear=calm)
""",
    "crash_loop": """\
import nu
from nudemos.ops import kit


# The gateway crashes twice in 5 minutes (a deploy's restart is no crash): raise to sev 1, page the secondary.
@nu.host
def check(v):
    falls = [t for t in v["jobs"].get("gateway", {}).get("falls", []) if t > v["now"] - 300]
    return f"gateway crashed {len(falls)} times in 5 minutes" if len(falls) >= 2 else ""


def act(root, why):
    return kit.incident(root, "gateway", "Storefront API crash loop", 1, why) >> kit.page(root, "secondary", why)


def out(plane):
    return kit.rule(plane, "crash_loop", check, act)
""",
    "broken_links": """\
import nu
from nudemos.ops import kit


# The link check fails: open a sev 3 for whoever owns the help center.
@nu.host
def check(v):
    last = v["jobs"].get("linkcheck", {}).get("last") or {}
    return last.get("summary", "") if last and not last.get("ok") else ""


def act(root, why):
    return kit.incident(root, "help-center", "Help center has broken links", 3, why)


def out(plane):
    calm = lambda root: kit.calm(root, "help-center", "Every help link answers again")
    return kit.rule(plane, "broken_links", check, act, clear=calm)
""",
    "memory": """\
import nu
from nudemos.ops import kit
from nudemos.ops.state import Ops


# The gateway holds more than 220 MB: say so on the feed, once per climb.
@nu.host
def check(v):
    mb = v["gw"].get("rss_mb", 0)
    return f"gateway holds {mb:.0f} MB on {v['gw'].get('release')}" if mb > 220 else ""


def act(root, why):
    return kit.landed(root, kit.event("rule", why, "machine") >> kit.said("gateway", "warning", why))


def out(plane):
    return kit.rule(plane, "memory", check, act)
""",
    "stale_backup": """\
import nu
from nudemos.ops import kit


# No good backup in 10 minutes: pause the offsite copy, page the primary.
@nu.host
def check(v):
    last = v["jobs"].get("backup", {}).get("last") or {}
    late = v["now"] - (last.get("ended") or v["now"]) > 600 or (last and not last.get("ok"))
    return "no good orders backup in 10 minutes" if late else ""


def act(root, why):
    return kit.pause(root, "offsite", "until a good backup lands") >> kit.page(root, "primary", why)


def out(plane):
    return kit.rule(plane, "stale_backup", check, act, clear=lambda root: kit.resume(root, "offsite"))
""",
}


WATCHDOG = """\
import nu
from nudemos.ops import kit


def out(plane):
    # The rules beside this cell are the watchdog's work; this one says it is up.
    return kit.on_root(plane, lambda root: kit.landed(root, kit.job_started("watchdog")) >> nu.ForeverDo(nu.Delay(3600.0)))
"""


SCHEDULED = """\
import nu
from nudemos.ops import kit
from nudemos.ops.calls import Work
from nudemos.ops.state import Ops
from nudemos.ops.work import Worker

NAME = "backup"
WARMUP = 20.0


def out(plane):
    def once(root):
        # One run: say it started, do the work in this process, write what came of it.
        # The very first run waits for the gateway to take some orders: there is nothing to back up before.
        first = kit.snap(kit.at_root(root, nu.Dict(Ops.jobs[NAME].fallback({})).get_item("runs_ok", -1) < 0))
        up = nu.IfDo(first, nu.Delay(WARMUP)) >> kit.landed(root, kit.job_started(NAME))
        work = nu.let(kit.snap(kit.at_root(root, kit.ask())), lambda a: Work(NAME, a))
        return up >> nu.Provide(Worker, {}, nu.let(work, lambda r: kit.landed(root, kit.job_finished(NAME, r))))

    return kit.on_root(plane, once)
"""


def scheduled(name: str) -> str:
    """The cell of scheduled job ``name``: :data:`SCHEDULED` with its name in."""
    return SCHEDULED.replace('NAME = "backup"', f"NAME = {name!r}")


#: Every job's cells, ``(name, source)`` each, by job.
SOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "gateway": (("serve", GATEWAY),),
    "traffic": (("shop", TRAFFIC),),
    "telemetry": (("read", TELEMETRY),),
    "watchdog": (("up", WATCHDOG), *RULES.items()),
    **{
        name: (("run", scheduled(name)),)
        for name, spec in JOBS.items()
        if spec["kind"] == "scheduled"
    },
}
