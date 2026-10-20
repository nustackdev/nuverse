"""What every ops cell and job shares: the writes they make, the moves they make, the pages they make.

Bare terms (``logged``, ``job_started``, ``event``, ...) are writes over
:class:`~.state.Ops`: the caller lands them at the root and brackets them,
so one job's turn is one short commit. The moves (``deploy``,
``pause``, ``incident``, ``rule``, ...) bracket themselves: each is a few
commits and the supervisor calls it takes, safe from any cell or job.

- Logs: :func:`logged`, a job's lines into its stream, nulog's layout.
- Jobs: :func:`job_started`, :func:`job_finished`, :func:`ask`; and from a page
  :func:`run_now`, :func:`pause`, :func:`resume`, :func:`restart`.
- Releases: :func:`deploy`, a real restart of the gateway on another release.
- Incidents and people: :func:`incident`, :func:`calm`, :func:`settle_incident`, :func:`page`.
- Rules: :func:`rule`, a few lines of Nu over the live numbers that act when they hold.
- Pages: :func:`seed`, the first open: pages, jobs, the supervisor.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.itertools
import nustd.time
from nuspace import Plane, ops
from nuspace.shapes import Space
from nuspace.system.utils import snap

from . import model
from .state import (
    INCIDENT,
    JOB_PAGE,
    ROOT,
    WORKER,
    Ops,
    at_root,
    incident_page,
    job_page,
    job_plane,
    root_of,
)


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "GATEWAY_PORT",
    "ask",
    "at_root",
    "calm",
    "deploy",
    "event",
    "incident",
    "job_finished",
    "job_started",
    "logged",
    "on_root",
    "page",
    "pause",
    "restart",
    "resume",
    "rule",
    "run_now",
    "seed",
    "settle_incident",
    "snap",
    "view",
]


#: Where the gateway listens, on the loopback only.
GATEWAY_PORT = 8242

#: Who the space acts as when a person presses a button.
YOU = "you"

push = nu.host(model.push, name="Push")


@nu.host
def pid() -> int:
    """The process this term runs in: a job's own, or the space's for an async job."""
    return os.getpid()


def on_root(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root)``, the Ops root this plane belongs to read once, bare: ``build`` lands what it reads."""
    return nu.let(snap(root_of(plane)), lambda r: build(nu.Str(r)))


def landed(root: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`Ops`, at the root, in one commit."""
    return ops.atomic_state(at_root(root, term))


# --- logs and the feed ---------------------------------------------------------------------------


@nu.host
def _counted(counts: dict, name: str, n: int) -> dict:
    return {**(counts or {}), name: (counts or {}).get(name, 0) + n}


def logged(name: str | nu.Str, lines: nu.Nu) -> nu.Nu:
    """``lines`` (``{id, ts_us, level, msg, fields}`` each) into job ``name``'s stream. Bare."""
    stream = Ops.logs[name].entries

    def one(line: nu.Attr) -> nu.Nu:
        ln = nu.Dict(line)
        entry = nu.Dict.of(ts_us=ln["ts_us"], level=ln["level"], msg=ln["msg"], fields=ln["fields"])
        return stream.set_item(nu.Str(ln["id"]), entry)

    many = nu.List(lines)
    return nu.IfDo(
        many.len() > 0,
        nu.ForEachDo(many, one)
        >> Ops.counts.set(_counted(Ops.counts.fallback({}), name, many.len())),
    )


@nu.host
def _line(level: str, msg: str, fields: dict) -> list[dict[str, Any]]:
    import uuid

    return [
        {
            "id": uuid.uuid4().hex,
            "ts_us": int(time.time() * 1e6),
            "level": level,
            "msg": msg,
            "fields": fields or {},
        }
    ]


def said(
    name: str | nu.Str, level: nu.StrArg, msg: nu.StrArg, fields: nu.Nu | dict | None = None
) -> nu.Nu:
    """One line into job ``name``'s stream. Bare."""
    return logged(name, _line(level, msg, fields or {}))


def event(kind: nu.StrArg, text: nu.StrArg, link: nu.StrArg = "") -> nu.Nu:
    """One entry on the feed, newest first: ``kind`` is ``deploy``, ``incident``, ``page``, ``job``, ``rule``. Bare."""
    entry = nu.Dict.of(at=nustd.time.time(), kind=kind, text=text, link=link)
    return Ops.events.set(push(Ops.events.fallback([]), entry, 300))


# --- jobs ----------------------------------------------------------------------------------------


_up = nu.host(model.job_up, name="JobUp")
_done = nu.host(model.job_done, name="JobDone")


def job_started(name: str) -> nu.Nu:
    """Job ``name``'s record as a run starts in this process. Bare."""
    rec = Ops.jobs[name]
    return rec.set(_up(rec.fallback({}), name, pid(), nustd.time.time()))


def job_finished(name: str, result: nu.Nu) -> nu.Nu:
    """A scheduled job's run into its record, its runs, its stream and what it keeps. Bare.

    ``result`` is :meth:`.work.Worker.run`'s: ``{ok, summary, lines, result, ms}``.
    """
    res = nu.Dict(result)
    kept = nu.Dict(res["result"])

    def write(both: nu.ObjectRef) -> nu.Nu:
        pair = nu.List(both)
        runs = Ops.runs[name]
        return Ops.jobs[name].set(pair[0]) >> runs.set(push(runs.fallback([]), pair[1], 40))

    keep = {
        "backup": Ops.backups.set(kept["archives"]),
        "linkcheck": Ops.links.set(kept),
        "digest": Ops.digest.set(nu.Str(kept["text"])),
    }.get(name, nu.Noop())
    failed = event("job", nu.Str(f"{name} failed: ") + nu.Str(res["summary"]), f"jobs.{name}")
    return (
        nu.let(_done(Ops.jobs[name].fallback({}), name, res, nustd.time.time()), write)
        >> logged(name, res["lines"])
        >> nu.IfDo(nu.Bool(res["ok"]), keep, failed)
    )


@nu.host
def _ask(
    settings: dict, gw: dict, release: dict, jobs: dict, incidents: dict, machine: dict
) -> dict:
    return {
        "data": settings.get("data", ""),
        "port": settings.get("port", GATEWAY_PORT),
        "state": {
            "gw": gw,
            "release": release,
            "jobs": jobs,
            "incidents": incidents,
            "machine": machine,
        },
    }


def ask() -> nu.Nu:
    """What a scheduled job is told: ``{data, port, state}``. Bare read."""
    return _ask(
        Ops.settings.fallback({}),
        Ops.gw.fallback({}),
        Ops.release.fallback({}),
        nu.Dict(Ops.jobs.extract()).fallback({}),
        nu.Dict(Ops.incidents.extract()).fallback({}),
        Ops.machine.fallback({}),
    )


def view() -> nu.Nu:
    """What rules and pages look at: ``{gw, jobs, release, load, machine, now}``. Bare read."""
    return nu.Dict.of(
        gw=Ops.gw.fallback({}),
        jobs=nu.Dict(Ops.jobs.extract()).fallback({}),
        release=Ops.release.fallback({}),
        load=Ops.load.fallback({}),
        machine=Ops.machine.fallback({}),
        now=nustd.time.time(),
    )


@nu.host
def _merge(rec: dict | None, fields: dict) -> dict:
    return {**(rec or {}), **(fields or {})}


def _job_note(root: nu.StrArg, name: nu.StrArg, fields: dict, text: nu.StrArg) -> nu.Nu:
    rec = Ops.jobs[name]
    return landed(
        root,
        rec.set(_merge(rec.fallback({}), fields)) >> event("job", text, nu.Str("jobs.") + name),
    )


def run_now(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Run job ``name`` once now, beside its schedule."""
    jid = job_plane(root, name)
    return ops.plane_run(jid, by="ops") >> landed(
        root, event("job", nu.Str(name) + " run by hand", nu.Str("jobs.") + name)
    )


@nu.host
def _every(name: str) -> float:
    return float(model.JOBS[name]["every"])


def _supervise(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    jid = job_plane(root, name)
    if isinstance(name, str):
        every = float(model.JOBS[name]["every"])
        return (
            nuspace.supervise(jid, "always", every)
            if every
            else nuspace.supervise(jid, "on-failure")
        )
    every = nu.Float(_every(name))
    return nu.IfDo(
        every > 0.0, nuspace.supervise(jid, "always", every), nuspace.supervise(jid, "on-failure")
    )


def pause(root: nu.StrArg, name: nu.StrArg, why: nu.StrArg = "by hand") -> nu.Nu:
    """Take job ``name`` off its schedule: it runs no more until resumed."""
    note = _job_note(
        root, name, {"paused": True, "status": "paused"}, nu.Str(name) + " paused " + why
    )
    return nuspace.unsupervise(job_plane(root, name)) >> note


def resume(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Put job ``name`` back on its schedule: it runs now, then every interval."""
    note = _job_note(root, name, {"paused": False, "status": "starting"}, nu.Str(name) + " resumed")
    return _supervise(root, name) >> note


def restart(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Stop job ``name``'s run and start a fresh one: a new process for a service."""
    note = _job_note(root, name, {"status": "restarting"}, nu.Str(name) + " restarted")
    return note >> nuspace.unsupervise(job_plane(root, name)) >> _supervise(root, name)


# --- releases ------------------------------------------------------------------------------------


@nu.host
def _deployed(release: dict, deploys: list, version: str, who: str, why: str, now: float) -> list:
    was = (release or {}).get("version", "")
    rec = {"version": version, "at": now, "by": who, "why": why, "from": was}
    return [rec, model.push(deploys, rec, 50)]


def deploy(root: nu.StrArg, version: nu.StrArg, who: nu.StrArg = YOU, why: nu.StrArg = "") -> nu.Nu:
    """Ship ``version``: the release record, the deploy log, then a real restart of the gateway on it."""

    def write(both: nu.ObjectRef) -> nu.Nu:
        pair = nu.List(both)
        text = nu.Str("Deployed ") + nu.Str(version) + " by " + nu.Str(who)
        return (
            Ops.release.set(pair[0]) >> Ops.deploys.set(pair[1]) >> event("deploy", text, "deploys")
        )

    made = _deployed(
        Ops.release.fallback({}), Ops.deploys.fallback([]), version, who, why, nustd.time.time()
    )
    return landed(root, nu.let(made, write)) >> restart(root, "gateway")


# --- incidents and people ------------------------------------------------------------------------


_open = nu.host(model.open_incident, name="OpenIncident")
_note = nu.host(model.note, name="Note")
_settle = nu.host(model.settle, name="Settle")


@nu.host
def _who(oncall: list, role: str) -> str:
    return next(
        (p["name"] for p in oncall or model.ONCALL if p["role"] == role), model.ONCALL[0]["name"]
    )


def page(root: nu.StrArg, role: nu.StrArg, text: nu.StrArg, incident: nu.StrArg = "") -> nu.Nu:
    """Page whoever is on call as ``role``: onto the pager, and the feed."""

    def write(name: nu.ObjectRef) -> nu.Nu:
        n = nu.Str(name)
        sent = nu.Dict.of(at=nustd.time.time(), to=n, role=role, text=text, incident=incident)
        line = nu.Str("Paged ") + n + " (" + nu.Str(role) + "): " + nu.Str(text)
        return Ops.pager.set(push(Ops.pager.fallback([]), sent, 100)) >> event(
            "page", line, nu.Str("incident.") + incident
        )

    return landed(root, nu.let(_who(Ops.oncall.fallback([]), role), write))


def incident(
    root: nu.StrArg, key: nu.StrArg, title: nu.StrArg, sev: nu.IntArg, detail: nu.StrArg
) -> nu.Nu:
    """Open an incident for ``key``, or note ``detail`` on the one open for it; a new one gets its page."""

    def go(held: nu.ObjectRef) -> nu.Nu:
        def write(made: nu.ObjectRef) -> nu.Nu:
            m = nu.List(made)
            iid = nu.Str(m[1])
            text = nu.If(
                nu.Bool(m[2]),
                nu.Str("Opened ") + iid + ": " + nu.Str(title),
                iid + ": " + nu.Str(detail),
            )
            return (
                Ops.incidents[iid].set(m[0])
                >> held.set(m)
                >> event("incident", nu.Str(text), nu.Str("incident.") + iid)
            )

        made = _open(
            nu.Dict(Ops.incidents.extract()).fallback({}),
            key,
            title,
            sev,
            detail,
            nu.Str(Ops.release.fallback({})["version"]),
            nustd.time.time(),
        )
        h = nu.List(held)
        return landed(root, nu.let(made, write)) >> nu.IfDo(
            nu.Bool(h[2]), incident_made(root, nu.Str(h[1]), title)
        )

    return nu.let([], go)


def incident_made(root: nu.StrArg, iid: nu.Str, title: nu.StrArg) -> nu.Nu:
    """An incident's page under Incidents, made once."""
    from .cells import INCIDENT_CELLS

    return _page(
        incident_page(root, iid),
        root,
        nu.Str(root) + ".incidents",
        iid,
        INCIDENT,
        "incident",
        iid,
        "lucide:flame",
        INCIDENT_CELLS,
    )


@nu.host
def _open_key(incidents: dict, key: str) -> str:
    return next(
        (
            i
            for i, inc in (incidents or {}).items()
            if inc.get("key") == key and inc.get("status") != "resolved"
        ),
        "",
    )


def calm(root: nu.StrArg, key: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """The open incident for ``key``, if any, to monitoring, with ``text`` on its timeline."""

    def write(iid: nu.ObjectRef) -> nu.Nu:
        inc = Ops.incidents[nu.Str(iid)]
        moved = _note(
            _merge(inc.fallback({}), {"status": "monitoring"}), text, nustd.time.time(), "rule"
        )
        said = event(
            "incident", nu.Str(iid) + " monitoring: " + nu.Str(text), nu.Str("incident.") + iid
        )
        return nu.IfDo(nu.Str(iid) != "", inc.set(moved) >> said)

    return landed(
        root, nu.let(_open_key(nu.Dict(Ops.incidents.extract()).fallback({}), key), write)
    )


def settle_incident(
    root: nu.StrArg, iid: nu.StrArg, status: nu.StrArg, who: nu.StrArg = YOU
) -> nu.Nu:
    """Incident ``iid`` to ``status`` (``acked``, ``resolved``, ...), by ``who``, on its timeline and the feed."""
    inc = Ops.incidents[iid]
    text = nu.Str(iid) + " " + nu.Str(status) + " by " + nu.Str(who)
    return landed(
        root,
        nu.IfDo(
            inc.exists(),
            inc.set(_settle(inc.fallback({}), status, who, nustd.time.time()))
            >> event("incident", text, nu.Str("incident.") + iid),
        ),
    )


def remark(root: nu.StrArg, iid: nu.StrArg, text: nu.StrArg, who: nu.StrArg = YOU) -> nu.Nu:
    """``text`` on incident ``iid``'s timeline."""
    inc = Ops.incidents[iid]
    return landed(
        root, nu.IfDo(inc.exists(), inc.set(_note(inc.fallback({}), text, nustd.time.time(), who)))
    )


# --- rules ---------------------------------------------------------------------------------------


_decide = nu.host(model.decide, name="Decide")


def rule(
    plane: str,
    name: str,
    check: Callable[[nu.Nu], nu.Nu],
    act: Callable[[nu.Str, nu.Str], nu.Nu],
    *,
    hold: int = 1,
    every: float = 2.0,
    clear: Callable[[nu.Str], nu.Nu] | None = None,
    title: str = "",
    says: str = "",
    does: str = "",
) -> nu.Nu:
    """An alert rule: every ``every`` seconds, ``check`` the live numbers; ``act`` once it holds ``hold`` turns.

    Args:
        plane: The plane the rule's cell is on, to find its Ops root.
        name: The rule's name, its record in ``Ops.rules``.
        check: The live numbers (:func:`view`) to a reason, ``""`` when all is well.
        act: What it does when it fires, given the root and the reason.
        hold: Turns in a row the reason must hold before it fires.
        every: Seconds between turns.
        clear: What it does when the reason goes away after firing.
        title: Its name on the Rules page, else ``name``.
        says: When it fires, in words, for the Rules page.
        does: What it does, in words, for the Rules page.
    """
    words = {k: v for k, v in {"title": title, "says": says, "does": does}.items() if v}

    def run(root: nu.Str) -> nu.Nu:
        def turn(reason: nu.ObjectRef) -> nu.Nu:
            why = nu.Str(reason)

            def judged(verdict: nu.ObjectRef) -> nu.Nu:
                rec = Ops.rules[name]
                had = _merge(rec.fallback({}), words) if words else rec.fallback({})
                decided = _decide(had, why, hold, nustd.time.time())
                write = nu.let(
                    decided, lambda d: rec.set(nu.List(d)[0]) >> verdict.set(nu.List(d)[1])
                )
                said = nu.Str(verdict)
                fired = nu.IfDo(
                    said == "fire",
                    landed(root, event("rule", nu.Str(name) + " fired: " + why, "rules"))
                    >> act(root, why),
                )
                cleared = nu.IfDo(said == "clear", clear(root)) if clear is not None else nu.Noop()
                return landed(root, write) >> fired >> cleared

            return nu.let("", judged)

        step = nu.let(check(snap(at_root(root, view()))), turn)
        return nu.ForeverDo(step >> nu.Delay(every))

    return on_root(plane, run)


# --- pages ---------------------------------------------------------------------------------------


def _page(
    pid_: nu.Nu,
    base: nu.Nu,
    parent: nu.Nu,
    name: nu.Nu,
    made_by: str,
    kind: str,
    subject: nu.Nu,
    icon: nu.StrArg,
    cells: tuple[tuple[str, str], ...],
    wide: bool = True,
) -> nu.Nu:
    """A page under ``parent`` with its cells, made once: a page already there is left alone."""
    spec = Plane(made_by, kind.title(), cells=tuple(cells), backend="async")
    meta = nu.Dict.of(base=base, icon=icon, editable=True, full_width=wide, **{kind: subject})
    make = ops.create_plane(spec, parent=parent, name=name, plane_id=pid_) >> ops.set_plane_meta(
        pid_, meta
    )
    return nu.IfDo(nu.Bool(snap(ops.plane_exists(pid_))).not_(), make)


@nu.host
def _data_dir(space: str) -> str:
    if space:
        return str(Path(space) / "ops-data")
    return str(Path(tempfile.gettempdir()) / "nudemos-ops-data")


@nu.host
def _history(now: float) -> list:
    out: list[dict] = []
    prev = "1.8.1"
    for version, hours, who in model.HISTORY:
        out = model.push(
            out,
            {"version": version, "at": now - hours * 3600, "by": who, "why": "", "from": prev},
            50,
        )
        prev = version
    return out


def _rules_seed() -> dict:
    return {k: {**v, "on": True, "fired": 0} for k, v in model.RULES.items()}


def _jobs_seed() -> dict:
    return {
        k: {**v, "name": k, "status": "starting", "every": v["every"]}
        for k, v in model.JOBS.items()
    }


def seed(root: nu.Str) -> nu.Nu:
    """The first open: the knobs, the pages, the jobs and their schedules. Once per root, whoever is first."""
    from .cells import FOLDERS, JOB
    from .jobs import SOURCES

    def knobs() -> nu.Nu:
        now = nustd.time.time()
        data = _data_dir(nu.Str(Space.state.info.path.fallback("")))
        first = model.HISTORY[-1]
        return (
            Ops.settings.set(nu.Dict.of(port=GATEWAY_PORT, data=data))
            >> Ops.release.set(
                nu.Dict.of(
                    version=first[0],
                    at=now - first[1] * 3600,
                    by=first[2],
                    why="",
                    **{"from": model.HISTORY[0][0]},
                )
            )
            >> Ops.deploys.set(_history(now))
            >> Ops.load.set({"users": 16})
            >> Ops.oncall.set(model.ONCALL)
            >> nu.Sequential(*(Ops.jobs[k].set(v) for k, v in _jobs_seed().items()))
            >> nu.Sequential(*(Ops.rules[k].set(v) for k, v in _rules_seed().items()))
            >> Ops.events.set([])
            >> Ops.counts.set({})
            >> Ops.pager.set([])
            >> Ops.steps.set([])
        )

    def folders() -> nu.Nu:
        return nu.Sequential(
            *(
                _page(
                    nu.Str(root) + "." + key,
                    root,
                    root,
                    label,
                    ROOT + "_" + key,
                    "view",
                    key,
                    icon,
                    cells,
                )
                for key, label, icon, cells in FOLDERS
            )
        )

    def job_pages() -> nu.Nu:
        return nu.Sequential(
            *(
                _page(
                    job_page(root, name),
                    root,
                    nu.Str(root) + ".jobs",
                    spec["title"],
                    JOB_PAGE,
                    "job",
                    name,
                    "lucide:cog",
                    JOB,
                )
                for name, spec in model.JOBS.items()
            )
        )

    def jobs() -> nu.Nu:
        def one(name: str, spec: dict) -> nu.Nu:
            jid = job_plane(root, name)
            made = ops.add_plane(
                jid,
                backend=spec["backend"],
                name=name,
                parent=root,
                ui=False,
                made_by=WORKER,
                meta=nu.Dict.of(base=root, job=name),
            )
            cells = SOURCES[name]
            add = nu.Sequential(
                *(
                    ops.add_cell(jid, src, cell_id=nu.Str(jid) + "_" + cell, name=cell)
                    for cell, src in cells
                )
            )
            return made >> add >> _supervise(root, name)

        return nu.Sequential(*(one(n, s) for n, s in model.JOBS.items()))

    def first(mine: nu.ObjectRef) -> nu.Nu:
        take = nu.IfDo(Ops.booted.missing(), Ops.booted.set(True) >> mine.set(True) >> knobs())
        build = folders() >> job_pages() >> jobs()
        return landed(root, take) >> nu.IfDo(nu.Bool(mine), build)

    return nu.let(False, first)


# --- what pages share ----------------------------------------------------------------------------


def on_ops(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root)`` with :class:`Ops` landed at the root, bracketed step by step: a page cell's body."""
    return on_root(plane, lambda r: ops.bracketed(at_root(r, build(r))))


def on_subject(plane: str, kind: str, build: Callable[[nu.Str, nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root, subject)`` on a job or incident page, the subject read from the page's meta ``kind``."""
    about = nu.str(Space.planes[plane].meta[kind]).fallback("")
    return nu.let(snap(about), lambda s: on_ops(plane, lambda r: build(r, nu.Str(s))))


def go(nav: nu.Nu, uri: nu.StrArg) -> nu.Nu:
    """Navigate the shell to ``uri``: push it and one past it, then step back onto it."""
    return nu.let(uri, lambda u: nav.set(u) >> nav.set(nu.Str(u) + "?open") >> nav.back())


def tail(name: nu.StrArg, n: nu.IntArg) -> nu.List:
    """The newest ``n`` lines of job ``name``'s stream, newest first: a read the size of ``n``. Bare."""
    newest = Ops.logs[name].entries.reversed_values()
    row = lambda e: nu.Dict.of(ts_us=e["ts_us"], level=e["level"], msg=e["msg"], fields=e["fields"])  # noqa: E731
    return nu.Iterator(nustd.itertools.islice(newest, n)).map(row).to_list()


#: Two dicts as one, the second's keys over the first's.
merged = _merge


def paused(name: nu.StrArg) -> nu.Bool:
    """Whether job ``name`` is off its schedule. Bare read."""
    return nu.Bool(nu.Dict(Ops.jobs[name].fallback({})).get_item("paused", False))


def ran(step: nu.StrArg, said: nu.Nu) -> nu.Nu:
    """A runbook step into the steps log: ``said`` is ``[ok, what it found]``. Bare."""
    s = nu.List(said)
    entry = nu.Dict.of(at=nustd.time.time(), step=step, ok=s[0], said=s[1])
    return Ops.steps.set(push(Ops.steps.fallback([]), entry, 60)) >> event(
        "runbook", nu.Str(step) + ": " + nu.Str(s[1]), "runbooks"
    )


def resolve_open(root: nu.StrArg, key: nu.StrArg, who: nu.StrArg = YOU) -> nu.Nu:
    """Resolve the open incident for ``key``, if there is one."""
    iid = snap(at_root(root, _open_key(nu.Dict(Ops.incidents.extract()).fallback({}), key)))
    return nu.let(
        iid, lambda i: nu.IfDo(nu.Str(i) != "", settle_incident(root, nu.Str(i), "resolved", who))
    )
