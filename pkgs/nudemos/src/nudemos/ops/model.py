"""The ops space's records, as plain Python: what a job, a run, a deploy, an incident and a rule hold.

No Nu here. Each function takes the record as it is in the store and gives
back the record to write, so the cells and jobs (:mod:`.kit`) call them as
host functions inside one commit, and the tests call them directly.

- :data:`JOBS`: every job the space runs, what it does and how it is scheduled.
- :data:`ONCALL`, :data:`RULES`, :data:`HISTORY`: who is paged, the alert
  rules, and the deploys before this space opened.
- :func:`job_up`, :func:`job_done`, :func:`job_crashed`: a job's record over its runs.
- :func:`open_incident`, :func:`note`, :func:`settle`: incidents and their timelines.
- :func:`decide`: one rule's turn: whether it fires, holds or clears.
"""

from __future__ import annotations

import time
from typing import Any


__all__ = [
    "HISTORY",
    "JOBS",
    "ONCALL",
    "RULES",
    "STABLE",
    "ago",
    "decide",
    "duration",
    "job_crashed",
    "job_done",
    "job_up",
    "note",
    "open_incident",
    "push",
    "settle",
]


#: Every job, in the order the Jobs page lists them. ``every`` is seconds between runs, 0 for a service.
JOBS: dict[str, dict[str, Any]] = {
    "gateway": {
        "title": "Storefront API",
        "kind": "service",
        "every": 0,
        "backend": "mp",
        "desc": "Halcyon's HTTP API: catalog, search, cart, orders, the help center. Restarted on failure.",
    },
    "traffic": {
        "title": "Shoppers",
        "kind": "service",
        "every": 0,
        "backend": "mp",
        "desc": "Synthetic shoppers browsing, searching and ordering over real HTTP.",
    },
    "telemetry": {
        "title": "Machine telemetry",
        "kind": "service",
        "every": 0,
        "backend": "mp",
        "desc": "Reads cpu, memory, disk, load and every job's process from the kernel, every 2 seconds.",
    },
    "watchdog": {
        "title": "Alert rules",
        "kind": "service",
        "every": 0,
        "backend": "async",
        "desc": "The alert rules, each a cell, checked every 2 seconds against the live numbers.",
    },
    "backup": {
        "title": "Orders backup",
        "kind": "scheduled",
        "every": 120,
        "backend": "mp",
        "desc": "Archives the orders store as a tar.gz and keeps the newest 8.",
    },
    "offsite": {
        "title": "Offsite copy",
        "kind": "scheduled",
        "every": 180,
        "backend": "mp",
        "desc": "Copies the newest archive offsite and checks its sha256.",
    },
    "linkcheck": {
        "title": "Help center links",
        "kind": "scheduled",
        "every": 90,
        "backend": "mp",
        "desc": "Crawls the help center over HTTP and fails on any link that answers 404.",
    },
    "digest": {
        "title": "Ops digest",
        "kind": "scheduled",
        "every": 300,
        "backend": "mp",
        "desc": "Writes a short markdown digest of the space for the team channel.",
    },
}

#: Who gets paged, in order.
ONCALL = [
    {"name": "Priya Nandakumar", "role": "primary", "team": "platform"},
    {"name": "Tomás Ferreira", "role": "secondary", "team": "platform"},
    {"name": "Mara Quint", "role": "release manager", "team": "storefront"},
]

#: The releases known good: what a rollback goes back to, newest last.
STABLE = ["1.8.2", "1.8.3"]

#: Deploys before this space opened, oldest first: ``(version, hours ago, by)``.
HISTORY = [("1.8.2", 21 * 24 + 5, "Mara Quint"), ("1.8.3", 12 * 24 + 3, "Tomás Ferreira")]

#: The alert rules the watchdog runs, by cell name: what each says, and what it does when it fires.
RULES: dict[str, dict[str, Any]] = {
    "error_rate": {
        "title": "Errors over 5%",
        "says": "More than 5% of gateway requests fail for 6 seconds",
        "does": "opens a sev 2 incident and pages the primary",
    },
    "crash_loop": {
        "title": "Crash loop",
        "says": "The gateway crashes twice in 5 minutes",
        "does": "raises the incident to sev 1 and pages the secondary",
    },
    "broken_links": {
        "title": "Broken help links",
        "says": "The link check fails",
        "does": "opens a sev 3 incident for the docs owner",
    },
    "memory": {
        "title": "Gateway memory",
        "says": "The gateway holds more than 220 MB",
        "does": "notes it in the feed, once per climb",
    },
    "stale_backup": {
        "title": "Backup stale",
        "says": "No good backup in 10 minutes",
        "does": "pauses the offsite copy and pages the primary",
    },
}


def push(items: list | None, item: object, keep: int = 200) -> list:
    """``item`` first, then ``items``, at most ``keep`` long."""
    return [item, *(items or [])][:keep]


def ago(at: float, now: float | None = None) -> str:
    """``at`` as ``12s ago``, ``4m ago``, ``3h ago``, ``2d ago``."""
    s = max(0.0, (now or time.time()) - (at or 0))
    if not at:
        return "never"
    if s < 60:
        return f"{s:.0f}s ago"
    if s < 3600:
        return f"{s / 60:.0f}m ago"
    if s < 86400:
        return f"{s / 3600:.0f}h ago"
    return f"{s / 86400:.0f}d ago"


def duration(s: float) -> str:
    """Seconds as ``850 ms``, ``4.2 s``, ``3m 10s``, ``2h 05m``."""
    if s < 1:
        return f"{s * 1000:.0f} ms"
    if s < 60:
        return f"{s:.1f} s"
    if s < 3600:
        return f"{int(s // 60)}m {int(s % 60):02d}s"
    return f"{int(s // 3600)}h {int(s % 3600 // 60):02d}m"


# --- jobs --------------------------------------------------------------------------------------


def job_up(rec: dict | None, name: str, pid: int, now: float) -> dict:
    """A job's record as one of its runs starts in process ``pid``."""
    rec = {**(rec or {}), **JOBS[name], "name": name}
    starts = [t for t in rec.get("starts", []) if t > now - 3600][-20:]
    # A start after a crash is a fall; a deploy or a Restart asked for is not.
    falls = [t for t in rec.get("falls", []) if t > now - 3600][-20:]
    if rec.get("status") == "crashed":
        falls.append(now)
    lives = list(rec.get("lives", []))[-19:]
    if lives and not lives[-1].get("end"):
        # How the last process ended, as its record said when this one started.
        why = {
            "crashed": rec.get("reason", "crashed"),
            "restarting": "restarted",
            "paused": "stopped",
        }.get(rec.get("status", ""), "exited")
        lives[-1] = {**lives[-1], "end": now, "why": why}
    lives.append({"at": now, "pid": pid})
    return {
        **rec,
        "status": "running",
        "pid": pid,
        "started": now,
        "starts": [*starts, now],
        "falls": falls,
        "lives": lives,
    }


def job_done(rec: dict | None, name: str, result: dict, now: float) -> tuple[dict, dict]:
    """A scheduled job's record after a run, and the run's own row.

    Returns:
        ``(record, run)``: the record with its last run, counts and streak;
        the run as the Jobs page lists it.
    """
    rec = dict(rec or {})
    ok = bool(result.get("ok"))
    started = rec.get("started") or now - result.get("ms", 0) / 1000
    run = {
        "at": started,
        "ended": now,
        "ok": ok,
        "ms": result.get("ms", 0),
        "summary": result.get("summary", ""),
        "pid": rec.get("pid", 0),
        "lines": len(result.get("lines") or []),
    }
    rec.update(
        status="ok" if ok else "failed",
        last=run,
        runs_ok=rec.get("runs_ok", 0) + ok,
        runs_failed=rec.get("runs_failed", 0) + (not ok),
        streak=0 if ok else rec.get("streak", 0) + 1,
        next=now + (rec.get("every") or JOBS[name]["every"]),
        paused=rec.get("paused", False),
    )
    return rec, run


def job_crashed(rec: dict | None, reason: str, now: float) -> dict:
    """A service's record as its process dies."""
    return {
        **(rec or {}),
        "status": "crashed",
        "crashed": now,
        "reason": reason,
        "crashes": (rec or {}).get("crashes", 0) + 1,
    }


# --- incidents ---------------------------------------------------------------------------------


def open_incident(
    incidents: dict | None, key: str, title: str, sev: int, detail: str, release: str, now: float
) -> tuple[dict, str, bool]:
    """Open an incident for ``key``, or note ``detail`` on the one still open for it.

    A higher severity raises an open incident's, never lowers it.

    Returns:
        ``(incident, id, new)``: the incident to write under ``id``, and
        whether it is a new one.
    """
    incidents = incidents or {}
    for iid, inc in incidents.items():
        if inc.get("key") == key and inc.get("status") != "resolved":
            raised = sev < inc.get("sev", 9)
            text = f"Raised to sev {sev}: {detail}" if raised else detail
            # Worse, or back after it was calm: open again.
            again = raised or inc.get("status") == "monitoring"
            inc = {
                **inc,
                "sev": min(sev, inc.get("sev", 9)),
                "status": "open" if again else inc["status"],
            }
            return note(inc, text, now, "rule"), iid, False
    iid = f"INC-{2040 + len(incidents) + 1}"
    inc = {
        "id": iid,
        "key": key,
        "title": title,
        "sev": sev,
        "status": "open",
        "opened": now,
        "release": release,
        "timeline": [],
    }
    return (
        note(inc, f"Opened by the {key.replace('_', ' ')} rule: {detail}", now, "rule"),
        iid,
        True,
    )


def note(inc: dict, text: str, now: float, who: str = "") -> dict:
    """``text`` on an incident's timeline, newest last."""
    return {
        **inc,
        "timeline": [*inc.get("timeline", []), {"at": now, "text": text, "who": who}][-60:],
    }


def settle(inc: dict, status: str, who: str, now: float) -> dict:
    """An incident moved to ``status`` (``acked``, ``monitoring``, ``resolved``) by ``who``."""
    words = {
        "acked": "Acknowledged",
        "monitoring": "Monitoring",
        "resolved": "Resolved",
        "open": "Reopened",
    }
    out = {**inc, "status": status, status: now}
    return note(out, f"{words.get(status, status)} by {who}", now, who)


# --- rules -------------------------------------------------------------------------------------


def decide(rec: dict | None, reason: str, hold: int, now: float) -> tuple[dict, str]:
    """One rule's turn: what to do, given whether its condition holds now (``reason`` non-empty).

    It fires once the condition has held for ``hold`` turns in a row, and
    clears once it stops holding. Off, it only keeps count of nothing.

    Returns:
        ``(record, verdict)``: the rule's record to write, and ``fire``,
        ``clear`` or ``""``.
    """
    rec = dict(rec or {})
    if not rec.get("on", True):
        return {**rec, "seen": 0, "firing": False}, ""
    seen = rec.get("seen", 0) + 1 if reason else 0
    rec.update(seen=seen, checked=now, checks=rec.get("checks", 0) + 1)
    if reason and seen >= hold and not rec.get("firing"):
        rec.update(firing=True, fired=rec.get("fired", 0) + 1, last=now, reason=reason)
        return rec, "fire"
    if not reason and rec.get("firing"):
        rec.update(firing=False, cleared=now)
        return rec, "clear"
    return rec, ""
