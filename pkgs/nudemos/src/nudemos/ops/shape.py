"""What the pages show, shaped from the store: plain Python, wrapped as terms in :mod:`.views`.

Each function takes records as the store holds them and gives back what a
widget takes: table rows, chart series, tiles, markdown. Times are shown as
clock times and ages; nothing here names a host, a user or a path.
"""

from __future__ import annotations

import time
from typing import Any

from .gateway import RELEASES
from .model import JOBS, STABLE, ago, duration


__all__ = [
    "TONES",
    "components",
    "deploy_rows",
    "feed_rows",
    "incident_head",
    "incident_rows",
    "job_head",
    "job_rows",
    "job_runs",
    "joined",
    "log_rows",
    "machine_tiles",
    "named",
    "proc_rows",
    "pulse",
    "release_notes",
    "route_rows",
    "rule_rows",
    "run_rows",
    "series",
    "timeline",
]


#: A job's or an incident's status, as a pill's tone.
TONES = {
    "running": "ok",
    "ok": "ok",
    "starting": "info",
    "restarting": "info",
    "paused": "neutral",
    "failed": "danger",
    "crashed": "danger",
    "down": "danger",
    "open": "danger",
    "acked": "warn",
    "monitoring": "info",
    "resolved": "ok",
}


def clock(at: float) -> str:
    """``at`` as ``20:41:07``, the space's own clock."""
    return time.strftime("%H:%M:%S", time.localtime(at)) if at else ""


def series(pairs: list | None, scale: float = 1.0) -> list[list[float]]:
    """kh57 ``(second, value)`` pairs as ``[[ms, value], ...]`` for a time axis."""
    return [[int(k) * 1000, round(float(v) * scale, 2)] for k, v in sorted(pairs or [])]


def named(name: str, pairs: list | None, scale: float = 1.0) -> dict[str, list]:
    """One chart series by name: ``{name: [[ms, value], ...]}``."""
    return {name: series(pairs, scale)}


def joined(*parts: dict) -> dict:
    """Several :func:`named` series as one chart's data."""
    out: dict = {}
    for p in parts:
        out.update(p or {})
    return out


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def pulse(
    gw: dict, release: dict, jobs: dict, incidents: dict, load: dict
) -> dict[str, dict[str, str]]:
    """The overview's tiles: ``{key: {value, delta, trend}}``."""
    gw, jobs, incidents = gw or {}, jobs or {}, incidents or {}
    # Monitoring is fixed and watched: not open, but said.
    open_ = [i for i in incidents.values() if i.get("status") not in ("resolved", "monitoring")]
    watched = sum(1 for i in incidents.values() if i.get("status") == "monitoring")
    worst = min((i.get("sev", 9) for i in open_), default=0)
    healthy = sum(1 for j in jobs.values() if j.get("status") in ("running", "ok"))
    up = time.time() - (gw.get("started") or time.time())
    err = gw.get("err", 0.0)
    return {
        "release": {
            "value": release.get("version", "-"),
            "delta": f"up {duration(up)}" if gw else "starting",
            "trend": "flat",
        },
        "rps": {
            "value": f"{gw.get('rps', 0):.1f}",
            "delta": f"{(load or {}).get('active', 0)} shoppers",
            "trend": "flat",
        },
        "err": {
            "value": _pct(err),
            "delta": "last 15s, over 5%" if err > 0.05 else "last 15s",
            "trend": "down" if err > 0.05 else "flat",
        },
        "p95": {
            "value": f"{gw.get('p95', 0):.0f} ms",
            "delta": f"p50 {gw.get('p50', 0):.0f} ms",
            "trend": "flat",
        },
        "orders": {
            "value": str(gw.get("orders_min", 0)),
            "delta": f"{gw.get('orders', 0):,} this run",
            "trend": "flat",
        },
        "incidents": {
            "value": str(len(open_)),
            "delta": f"worst sev {worst}"
            if open_
            else (f"{watched} monitoring" if watched else "all clear"),
            "trend": "down" if open_ else "flat",
        },
        "jobs": {
            "value": f"{healthy} of {len(jobs)}",
            "delta": "healthy",
            "trend": "flat" if healthy == len(jobs) else "down",
        },
    }


def feed_rows(events: list | None, base: str, n: int = 14) -> list[dict[str, Any]]:
    """The feed, newest first: ``{key, when, kind, text}``."""
    return [
        {
            "key": f"{e.get('at')}-{i}",
            "when": clock(e.get("at", 0)),
            "kind": e.get("kind", ""),
            "text": e.get("text", ""),
        }
        for i, e in enumerate((events or [])[:n])
    ]


def _schedule(j: dict) -> str:
    if j.get("kind") == "service":
        return "always on"
    every = j.get("every") or 0
    return f"every {every // 60} min" if every % 60 == 0 else f"every {every}s"


def job_rows(jobs: dict | None, now: float) -> list[dict[str, Any]]:
    """The Jobs table: one row per job, in :data:`JOBS` order."""
    rows = []
    for name in JOBS:
        j = (jobs or {}).get(name, {})
        last = j.get("last") or {}
        if j.get("kind") == "service":
            seen = (
                f"up {duration(now - j['started'])}"
                if j.get("status") == "running" and j.get("started")
                else j.get("reason", "")[:60]
            )
        else:
            seen = (
                f"{ago(last.get('ended', 0), now)}, {last.get('summary', '')}"
                if last
                else "not run yet"
            )
        nxt = ""
        if j.get("paused"):
            nxt = "paused"
        elif j.get("kind") == "scheduled" and j.get("next"):
            nxt = "now" if j["next"] <= now else f"in {duration(j['next'] - now)}"
        rows.append(
            {
                "key": name,
                "job": name,
                "what": JOBS[name]["title"],
                "schedule": _schedule({**JOBS[name], **j}),
                "status": j.get("status", "starting"),
                "last": seen,
                "next": nxt,
                "runs": f"{j.get('runs_ok', 0)} ok, {j.get('runs_failed', 0)} failed"
                if j.get("kind") == "scheduled"
                else f"{max(0, len(j.get('starts', [])) - 1)} restarts",
            }
        )
    return rows


def job_head(j: dict | None, name: str, now: float) -> dict[str, Any]:
    """A job page's head: ``{status, tone, line, paused, service}``."""
    j = {**JOBS[name], **(j or {})}
    status = j.get("status", "starting")
    bits = [_schedule(j)]
    if j.get("pid"):
        bits.append(f"process {j['pid']}")
    if j.get("kind") == "service" and j.get("started") and status == "running":
        bits.append(f"up {duration(now - j['started'])}")
    if j.get("kind") == "scheduled":
        last = j.get("last") or {}
        if last:
            bits.append(
                f"last run {ago(last.get('ended', 0), now)} took {duration(last.get('ms', 0) / 1000)}"
            )
        if j.get("next") and not j.get("paused"):
            bits.append(
                "next " + ("now" if j["next"] <= now else f"in {duration(j['next'] - now)}")
            )
    if status in ("crashed", "down") and j.get("reason"):
        bits.append(j["reason"])
    return {
        "status": status,
        "tone": TONES.get(status, "neutral"),
        "line": "  ·  ".join(bits),
        "paused": bool(j.get("paused")),
        "service": j.get("kind") == "service",
        "desc": j.get("desc", ""),
    }


def run_rows(runs: list | None, now: float) -> list[dict[str, Any]]:
    """A job's runs, newest first."""
    return [
        {
            "key": str(r.get("at")),
            "started": clock(r.get("at", 0)),
            "result": "ok" if r.get("ok") else "failed",
            "took": duration((r.get("ms") or 0) / 1000),
            "summary": r.get("summary", ""),
            "process": str(r.get("pid", "")),
        }
        for r in (runs or [])
    ]


def job_runs(runs: list | None, rec: dict | None, now: float) -> list[dict[str, Any]]:
    """A job page's runs: a scheduled job's runs, or a service's processes, newest first."""
    rec = rec or {}
    if rec.get("kind") != "service":
        return run_rows(runs, now)
    rows = []
    for life in reversed(rec.get("lives", [])):
        live = not life.get("end")
        status = rec.get("status", "") if live else ""
        rows.append(
            {
                "key": str(life.get("at")),
                "started": clock(life.get("at", 0)),
                "result": status or ("crashed" if "memory" in life.get("why", "") else "ended"),
                "took": duration((life.get("end") or now) - life.get("at", now)),
                "summary": ("serving now" if status == "running" else rec.get("reason", status))
                if live
                else life.get("why", ""),
                "process": str(life.get("pid", "")),
            }
        )
    return rows


def route_rows(gw: dict | None) -> list[dict[str, Any]]:
    """The routes the gateway served in the last minute, busiest first."""
    return [
        {**r, "key": r["route"], "err": f"{r['err']:.1f}%"} for r in (gw or {}).get("routes", [])
    ]


def log_rows(rows: list | None, level: str, text: str, n: int = 80) -> list[dict[str, Any]]:
    """Log lines newest first, kept when they match ``level`` (or worse) and ``text``, at most ``n``."""
    order = {"debug": 0, "info": 1, "warning": 2, "error": 3, "critical": 4}
    floor = order.get(level, 0)
    needle = (text or "").lower().strip()
    out = []
    for r in rows or []:
        if order.get(r.get("level", "info"), 1) < floor:
            continue
        msg = r.get("msg", "")
        fields = r.get("fields") or {}
        if needle and needle not in msg.lower() and needle not in str(fields).lower():
            continue
        extra = (
            fields.get("error")
            or ", ".join(
                f"{k}={v}"
                for k, v in fields.items()
                if k not in ("method", "path", "status", "ms", "bytes", "agent")
            )[:90]
        )
        out.append(
            {
                "key": f"{r.get('ts_us')}-{len(out)}",
                "time": time.strftime("%H:%M:%S", time.localtime(r.get("ts_us", 0) / 1e6))
                + f".{r.get('ts_us', 0) // 1000 % 1000:03d}",
                "level": r.get("level", ""),
                "message": msg,
                "detail": extra,
            }
        )
        if len(out) >= n:
            break
    return out


def machine_tiles(m: dict | None) -> dict[str, dict[str, str]]:
    """The Machine page's tiles."""
    m = m or {}
    load = m.get("load") or [0, 0, 0]
    return {
        "cores": {
            "value": str(m.get("cores", "-")),
            "delta": f"load {load[0]:.2f} / {load[1]:.2f} / {load[2]:.2f}",
        },
        "memory": {
            "value": f"{m.get('mem_used_gb', 0):.1f} GB",
            "delta": f"of {m.get('mem_total_gb', 0):.0f} GB",
        },
        "disk": {
            "value": f"{m.get('disk_free_gb', 0):,} GB free",
            "delta": f"of {m.get('disk_total_gb', 0):,} GB",
        },
        "net": {
            "value": f"{m.get('net_in', 0):,.0f} KB/s in",
            "delta": f"{m.get('net_out', 0):,.0f} KB/s out",
        },
        "uptime": {"value": duration(m.get("uptime", 0)), "delta": "since boot"},
    }


def proc_rows(m: dict | None, jobs: dict | None) -> list[dict[str, Any]]:
    """Every job's process: up or not, cpu, memory, age."""
    by = {p["job"]: p for p in (m or {}).get("procs", [])}
    rows = []
    for name in JOBS:
        p, j = by.get(name), (jobs or {}).get(name, {})
        if p is None:
            continue
        scheduled = JOBS[name]["kind"] == "scheduled"
        rows.append(
            {
                "key": name,
                "job": name,
                "process": str(p.get("pid", "")) if p.get("up") else "",
                "state": "running"
                if p.get("up")
                else ("between runs" if scheduled else j.get("status", "down")),
                "cpu": f"{p.get('cpu', 0):.1f}%" if p.get("up") else "",
                "memory": f"{p.get('rss', 0):.0f} MB" if p.get("up") else "",
                "up": duration(p.get("age", 0)) if p.get("up") else "",
            }
        )
    return rows


def deploy_rows(deploys: list | None, now: float) -> list[dict[str, Any]]:
    """Every deploy, newest first."""
    return [
        {
            "key": f"{d.get('at')}",
            "when": ago(d.get("at", 0), now),
            "version": d.get("version", ""),
            "from": d.get("from", ""),
            "by": d.get("by", ""),
            "why": d.get("why", "")
            or (
                "rollback"
                if d.get("version") in STABLE and d.get("from", "") > d.get("version", "")
                else ""
            ),
        }
        for d in (deploys or [])
    ]


def release_notes(live: str) -> str:
    """Every release, newest first, the live one marked."""
    out = []
    for version, r in reversed(list(RELEASES.items())):
        mark = "  **live**" if version == live else ""
        out.append(f"**{version}**{mark}  ·  {r['date']}\n\n{r['notes']}")
    return "\n\n".join(out)


def incident_rows(incidents: dict | None, now: float) -> list[dict[str, Any]]:
    """Every incident, open first, newest first."""
    items = sorted(
        (incidents or {}).values(),
        key=lambda i: (i.get("status") == "resolved", -i.get("opened", 0)),
    )
    return [
        {
            "key": i["id"],
            "id": i["id"],
            "sev": f"sev {i.get('sev')}",
            "title": i.get("title", ""),
            "status": i.get("status", ""),
            "opened": ago(i.get("opened", 0), now),
            "release": i.get("release", ""),
            "lasted": duration((i.get("resolved") or now) - i.get("opened", now)),
        }
        for i in items
    ]


def incident_head(inc: dict | None, now: float) -> dict[str, Any]:
    """An incident page's head."""
    inc = inc or {}
    status = inc.get("status", "open")
    line = (
        f"Sev {inc.get('sev', '?')}  ·  opened {clock(inc.get('opened', 0))}, {ago(inc.get('opened', 0), now)}"
        f"  ·  on release {inc.get('release', '?')}  ·  {duration((inc.get('resolved') or now) - inc.get('opened', now))} long"
    )
    return {
        "title": inc.get("title", ""),
        "status": status,
        "tone": TONES.get(status, "neutral"),
        "line": line,
    }


def timeline(inc: dict | None) -> str:
    """An incident's timeline as markdown, oldest first."""
    lines = [
        f"- **{clock(t.get('at', 0))}**  {t.get('text', '')}"
        + (f"  · _{t['who']}_" if t.get("who") not in ("", "rule", None) else "")
        for t in (inc or {}).get("timeline", [])
    ]
    return "\n".join(lines) or "Nothing yet."


def rule_rows(rules: dict | None, now: float) -> list[dict[str, Any]]:
    """Every alert rule: what it watches, what it does, how often it fired."""
    return [
        {
            "key": name,
            "rule": r.get("title", name),
            "when": r.get("says", ""),
            "then": r.get("does", ""),
            "state": "off" if not r.get("on", True) else ("firing" if r.get("firing") else "quiet"),
            "fired": f"{r.get('fired', 0)}x"
            + (f", last {ago(r['last'], now)}" if r.get("last") else ""),
        }
        for name, r in (rules or {}).items()
    ]


def components(gw: dict | None, jobs: dict | None, release: dict | None) -> list[dict[str, str]]:
    """The status page's components: ``{name, tone, label, note}`` each."""
    gw, jobs = gw or {}, jobs or {}
    routes = {r["route"]: r for r in gw.get("routes", [])}
    up = jobs.get("gateway", {}).get("status") == "running" and gw.get("rps", 0) > 0

    def route(names: list[str], label: str, note: str) -> dict[str, str]:
        rs = [routes[n] for n in names if n in routes]
        err = max((r["err"] for r in rs), default=0.0)
        if not up:
            return {
                "name": label,
                "tone": "danger",
                "label": "Major outage",
                "note": "not answering",
            }
        if err > 20:
            return {
                "name": label,
                "tone": "danger",
                "label": "Partial outage",
                "note": f"{err:.0f}% of requests failing",
            }
        if err > 2:
            return {
                "name": label,
                "tone": "warn",
                "label": "Degraded",
                "note": f"{err:.1f}% of requests failing",
            }
        p95 = max((r["p95"] for r in rs), default=0)
        return {"name": label, "tone": "ok", "label": "Operational", "note": note.format(p95=p95)}

    links = jobs.get("linkcheck", {})
    help_ok = (links.get("last") or {}).get("ok", True)
    backup = jobs.get("backup", {})
    return [
        route(["/api/catalog", "/api/cart"], "Storefront", "p95 {p95} ms"),
        route(["/api/search"], "Search", "p95 {p95} ms"),
        route(["/api/orders", "/api/orders/:id"], "Checkout and orders", "p95 {p95} ms"),
        {
            "name": "Help center",
            "tone": "ok" if help_ok else "warn",
            "label": "Operational" if help_ok else "Broken links",
            "note": (links.get("last") or {}).get("summary", ""),
        },
        {
            "name": "Order backups",
            "tone": "ok" if (backup.get("last") or {}).get("ok", True) else "danger",
            "label": "Operational" if (backup.get("last") or {}).get("ok", True) else "Failing",
            "note": f"last {ago((backup.get('last') or {}).get('ended', 0))}",
        },
    ]
