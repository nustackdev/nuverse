"""What every ops cell and job shares: the writes they make, the moves they make, the pages they make.

Bare terms (``logged``, ``job_started``, ``event``, ...) are writes over
:data:`~.state.OPS`, the root's state: the caller brackets them with
``nuspace.atomic``, so one job's turn is one short commit. The moves
(``deploy``, ``pause``, ``incident``, ``rule``, ...) bracket themselves:
each is a few commits and the supervisor calls it takes, safe from any
cell or job.

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
from nuspace import Space
from nuspace.specs import PlaneSpec, WebOptions
from nuspace.system.supervisor import ALWAYS, ON_FAILURE
from nuspace.utils import MintId

from .. import headless
from . import model
from .state import (
    INCIDENT,
    JOB_PAGE,
    OPS,
    ROOT,
    ROOT_ID,
    WORKER,
    folder_of,
    incident_view,
    worker_of,
)


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "GATEWAY_PORT",
    "ask",
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
    "view",
]


#: Where the gateway listens, on the loopback only.
GATEWAY_PORT = 8242

#: The metric series' slots on :class:`~.state.Ops`.
SERIES_SLOTS = ("rps", "err", "p50", "p95", "cpu", "mem", "disk", "load1", "gw_rss", "orders")

#: Who the space acts as when a person presses a button.
YOU = "you"

push = nu.host(model.push, name="Push")


@nu.host
def pid() -> int:
    """The process this term runs in: a job's own, or the space's for an async job."""
    return os.getpid()


def on_root(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root)``, the Ops root's id read once: ``build`` brackets what it reads.

    ``plane`` is the plane the cell runs on; every plane finds the one root by its key.
    """
    del plane
    return nu.let(nuspace.atomic(ROOT_ID), lambda r: build(nu.Str(r)))


# --- logs and the feed ---------------------------------------------------------------------------


@nu.host
def _counted(counts: dict, name: str, n: int) -> dict:
    return {**(counts or {}), name: (counts or {}).get(name, 0) + n}


def logged(name: str | nu.Str, lines: nu.Nu) -> nu.Nu:
    """``lines`` (``{id, ts_us, level, msg, fields}`` each) into job ``name``'s stream. Bare."""
    stream = OPS.logs[name].entries

    def one(line: nu.Attr) -> nu.Nu:
        ln = nu.Dict(line)
        entry = nu.Dict.of(ts_us=ln["ts_us"], level=ln["level"], msg=ln["msg"], fields=ln["fields"])
        return stream.set_item(nu.Str(ln["id"]), entry)

    many = nu.List(lines)
    return nu.IfDo(
        many.len() > 0,
        nu.ForEachDo(many, one)
        >> OPS.counts.set(_counted(OPS.counts.fallback({}), name, many.len())),
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
    return OPS.events.set(push(OPS.events.fallback([]), entry, 300))


# --- jobs ----------------------------------------------------------------------------------------


_up = nu.host(model.job_up, name="JobUp")
_done = nu.host(model.job_done, name="JobDone")


def job_started(name: str) -> nu.Nu:
    """Job ``name``'s record as a run starts in this process. Bare."""
    rec = OPS.jobs[name]
    return rec.set(_up(rec.fallback({}), name, pid(), nustd.time.time()))


def job_finished(name: str, result: nu.Nu) -> nu.Nu:
    """A scheduled job's run into its record, its runs, its stream and what it keeps. Bare.

    ``result`` is :meth:`.work.Worker.run`'s: ``{ok, summary, lines, result, ms}``.
    """
    res = nu.Dict(result)
    kept = nu.Dict(res["result"])

    def write(both: nu.ObjectRef) -> nu.Nu:
        pair = nu.List(both)
        runs = OPS.runs[name]
        return OPS.jobs[name].set(pair[0]) >> runs.set(push(runs.fallback([]), pair[1], 40))

    keep = {
        "backup": OPS.backups.set(kept["archives"]),
        "linkcheck": OPS.links.set(kept),
        "digest": OPS.digest.set(nu.Str(kept["text"])),
    }.get(name, nu.Noop())
    failed = event("job", nu.Str(f"{name} failed: ") + nu.Str(res["summary"]), f"jobs.{name}")
    return (
        nu.let(_done(OPS.jobs[name].fallback({}), name, res, nustd.time.time()), write)
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
        OPS.settings.fallback({}),
        OPS.gw.fallback({}),
        OPS.release.fallback({}),
        nu.Dict(OPS.jobs.extract()).fallback({}),
        nu.Dict(OPS.incidents.extract()).fallback({}),
        OPS.machine.fallback({}),
    )


def view() -> nu.Nu:
    """What rules and pages look at: ``{gw, jobs, release, load, machine, now}``. Bare read."""
    return nu.Dict.of(
        gw=OPS.gw.fallback({}),
        jobs=nu.Dict(OPS.jobs.extract()).fallback({}),
        release=OPS.release.fallback({}),
        load=OPS.load.fallback({}),
        machine=OPS.machine.fallback({}),
        now=nustd.time.time(),
    )


@nu.host
def _merge(rec: dict | None, fields: dict) -> dict:
    return {**(rec or {}), **(fields or {})}


def _job_note(root: nu.StrArg, name: nu.StrArg, fields: dict, text: nu.StrArg) -> nu.Nu:
    rec = OPS.jobs[name]
    return nuspace.atomic(
        rec.set(_merge(rec.fallback({}), fields)) >> event("job", text, nu.Str("jobs.") + name)
    )


def run_now(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Run job ``name`` once now, beside its schedule."""
    return nuspace.atomic(nuspace.plane_run.add(worker_of(name), by="ops")) >> nuspace.atomic(
        event("job", nu.Str(name) + " run by hand", nu.Str("jobs.") + name)
    )


@nu.host
def _every(name: str) -> float:
    return float(model.JOBS[name]["every"])


def _scheduled(root: nu.StrArg, name: nu.StrArg, move: Callable[..., nu.Nu]) -> nu.Nu:
    """``move(job, policy, delay)`` on job ``name`` with its schedule's policy.

    A scheduled job runs again its interval after each run (``always``),
    a service is restarted when it fails (``on-failure``, the backoff). The
    job's plane id is read once, from :class:`~.state.Made`.
    """

    def moved(held: nu.ObjectRef) -> nu.Nu:
        jid = nu.Str(held)
        if isinstance(name, str):
            every = float(model.JOBS[name]["every"])
            return move(jid, ALWAYS, every) if every else move(jid, ON_FAILURE, None)
        every = nu.Float(_every(name))
        return nu.IfDo(every > 0.0, move(jid, ALWAYS, every), move(jid, ON_FAILURE, None))

    return nu.let(nuspace.atomic(worker_of(name)), moved)


def _supervise(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Job ``name`` under the supervisor on its schedule, or kept there."""
    return _scheduled(root, name, headless.supervise)


def pause(root: nu.StrArg, name: nu.StrArg, why: nu.StrArg = "by hand") -> nu.Nu:
    """Take job ``name`` off its schedule and stop its run: it runs no more until resumed."""
    note = _job_note(
        root, name, {"paused": True, "status": "paused"}, nu.Str(name) + " paused " + why
    )
    return (
        nu.let(nuspace.atomic(worker_of(name)), lambda j: headless.unsupervise(nu.Str(j))) >> note
    )


def resume(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Put job ``name`` back on its schedule: it runs now, then every interval."""
    note = _job_note(root, name, {"paused": False, "status": "starting"}, nu.Str(name) + " resumed")
    return _supervise(root, name) >> note


def restart(root: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Stop job ``name``'s run and start a fresh one: a new process for a service."""
    note = _job_note(root, name, {"status": "restarting"}, nu.Str(name) + " restarted")
    return note >> _scheduled(root, name, headless.restart)


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
            OPS.release.set(pair[0]) >> OPS.deploys.set(pair[1]) >> event("deploy", text, "deploys")
        )

    made = _deployed(
        OPS.release.fallback({}), OPS.deploys.fallback([]), version, who, why, nustd.time.time()
    )
    return nuspace.atomic(nu.let(made, write)) >> restart(root, "gateway")


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
        return OPS.pager.set(push(OPS.pager.fallback([]), sent, 100)) >> event(
            "page", line, nu.Str("incident.") + incident
        )

    return nuspace.atomic(nu.let(_who(OPS.oncall.fallback([]), role), write))


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
            # A new incident's page id, minted with it: its page is made after.
            minted = nu.IfDo(nu.Bool(m[2]), OPS.made.incidents[iid].init(MintId("p")))
            return (
                OPS.incidents[iid].set(m[0])
                >> minted
                >> held.set(m)
                >> event("incident", nu.Str(text), nu.Str("incident.") + iid)
            )

        made = _open(
            nu.Dict(OPS.incidents.extract()).fallback({}),
            key,
            title,
            sev,
            detail,
            nu.Str(OPS.release.fallback({})["version"]),
            nustd.time.time(),
        )
        h = nu.List(held)
        return nuspace.atomic(nu.let(made, write)) >> nu.IfDo(
            nu.Bool(h[2]), incident_made(root, nu.Str(h[1]), title)
        )

    return nu.let([], go)


def incident_made(root: nu.StrArg, iid: nu.Str, title: nu.StrArg) -> nu.Nu:
    """An incident's page under Incidents, made once, at the id minted when it opened."""
    from .cells import INCIDENT_CELLS

    del root, title

    def made(ids: nu.ObjectRef) -> nu.Nu:
        pid, parent = nu.Str(nu.List(ids)[0]), nu.Str(nu.List(ids)[1])
        return _page(pid, parent, iid, INCIDENT, "incident", iid, "lucide:flame", INCIDENT_CELLS)

    return nu.let(nuspace.atomic(nu.List.of(incident_view(iid), folder_of("incidents"))), made)


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
        inc = OPS.incidents[nu.Str(iid)]
        moved = _note(
            _merge(inc.fallback({}), {"status": "monitoring"}), text, nustd.time.time(), "rule"
        )
        said = event(
            "incident", nu.Str(iid) + " monitoring: " + nu.Str(text), nu.Str("incident.") + iid
        )
        return nu.IfDo(nu.Str(iid) != "", inc.set(moved) >> said)

    return nuspace.atomic(
        nu.let(_open_key(nu.Dict(OPS.incidents.extract()).fallback({}), key), write)
    )


def settle_incident(
    root: nu.StrArg, iid: nu.StrArg, status: nu.StrArg, who: nu.StrArg = YOU
) -> nu.Nu:
    """Incident ``iid`` to ``status`` (``acked``, ``resolved``, ...), by ``who``, on its timeline and the feed."""
    inc = OPS.incidents[iid]
    text = nu.Str(iid) + " " + nu.Str(status) + " by " + nu.Str(who)
    return nuspace.atomic(
        nu.IfDo(
            inc.exists(),
            inc.set(_settle(inc.fallback({}), status, who, nustd.time.time()))
            >> event("incident", text, nu.Str("incident.") + iid),
        )
    )


def remark(root: nu.StrArg, iid: nu.StrArg, text: nu.StrArg, who: nu.StrArg = YOU) -> nu.Nu:
    """``text`` on incident ``iid``'s timeline."""
    inc = OPS.incidents[iid]
    return nuspace.atomic(
        nu.IfDo(inc.exists(), inc.set(_note(inc.fallback({}), text, nustd.time.time(), who)))
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
        name: The rule's name, its record in ``OPS.rules``.
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
                rec = OPS.rules[name]
                had = _merge(rec.fallback({}), words) if words else rec.fallback({})
                decided = _decide(had, why, hold, nustd.time.time())
                write = nu.let(
                    decided, lambda d: rec.set(nu.List(d)[0]) >> verdict.set(nu.List(d)[1])
                )
                said = nu.Str(verdict)
                fired = nu.IfDo(
                    said == "fire",
                    nuspace.atomic(event("rule", nu.Str(name) + " fired: " + why, "rules"))
                    >> act(root, why),
                )
                cleared = nu.IfDo(said == "clear", clear(root)) if clear is not None else nu.Noop()
                return nuspace.atomic(write) >> fired >> cleared

            return nu.let("", judged)

        step = nu.let(check(nuspace.atomic(view())), turn)
        return nu.ForeverDo(step >> nu.Delay(every))

    return on_root(plane, run)


# --- pages ---------------------------------------------------------------------------------------


def _page(
    pid_: nu.Nu,
    parent: nu.Nu,
    name: nu.Nu,
    spec: str,
    kind: str,
    subject: nu.Nu,
    icon: nu.StrArg,
    cells: tuple[tuple[str, str], ...],
    wide: bool = True,
) -> nu.Nu:
    """A page under ``parent`` with its cells, made once: a page already there, or removed, is left alone.

    Made from a spec named ``spec``, on the web; its icon and what it is
    about (``kind`` for its subject) written after, in one commit.
    """
    page = PlaneSpec(
        spec,
        kind.title(),
        cells=tuple(cells),
        web=WebOptions(editable=True, width="board" if wide else "page"),
        backend="async",
    )
    about = nu.Dict.of(**{kind: subject})
    marked = nuspace.plane.set_icon(pid_, icon) >> nuspace.plane.set_meta(pid_, about)
    make = nuspace.specs.add_plane(page, pid_, parent=parent, name=name) >> nuspace.atomic(marked)
    return headless.once(pid_, make)


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
        data = _data_dir(nu.Str(Space.info.path.fallback("")))
        first = model.HISTORY[-1]
        return (
            OPS.settings.set(nu.Dict.of(port=GATEWAY_PORT, data=data))
            >> OPS.release.set(
                nu.Dict.of(
                    version=first[0],
                    at=now - first[1] * 3600,
                    by=first[2],
                    why="",
                    **{"from": model.HISTORY[0][0]},
                )
            )
            >> OPS.deploys.set(_history(now))
            >> OPS.load.set({"users": 16})
            >> OPS.oncall.set(model.ONCALL)
            >> nu.Sequential(*(OPS.jobs[k].set(v) for k, v in _jobs_seed().items()))
            >> nu.Sequential(*(OPS.rules[k].set(v) for k, v in _rules_seed().items()))
            >> OPS.events.set([])
            >> OPS.counts.set({})
            >> OPS.pager.set([])
            >> OPS.steps.set([])
            >> made()
        )

    def made() -> nu.Nu:
        # Every series and every job's stream made empty, so a page reading one before its job writes finds it.
        series = (getattr(OPS, slot) for slot in SERIES_SLOTS)
        streams = (OPS.logs[name].entries for name in model.JOBS)
        return nu.Sequential(*(ref.init(nu.Dict.create()) for ref in (*series, *streams)))

    def minted() -> nu.Nu:
        # Every plane's id, minted with the knobs: the planes are made after, at these ids.
        made = OPS.made
        return nu.Sequential(
            *(made.folders[key].set(MintId("p")) for key, _, _, _ in FOLDERS),
            *(made.views[name].set(MintId("p")) for name in model.JOBS),
            *(made.workers[name].set(MintId("p")) for name in model.JOBS),
        )

    def folders(ids: nu.Dict) -> nu.Nu:
        return nu.Sequential(
            *(
                _page(
                    nu.Str(ids["folders"][key]),
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

    def job_pages(ids: nu.Dict) -> nu.Nu:
        return nu.Sequential(
            *(
                _page(
                    nu.Str(ids["views"][name]),
                    nu.Str(ids["folders"]["jobs"]),
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

    def jobs(ids: nu.Dict) -> nu.Nu:
        def one(name: str, spec: dict) -> nu.Nu:
            jid = nu.Str(ids["workers"][name])
            made = headless.make(
                jid,
                parent=root,
                name=name,
                backend=spec["backend"],
                spec=WORKER,
                cells=list(SOURCES[name]),
                meta=nu.Dict.of(job=name),
            )
            return headless.once(jid, made) >> _supervise(root, name)

        return nu.Sequential(*(one(n, s) for n, s in model.JOBS.items()))

    def first(mine: nu.ObjectRef) -> nu.Nu:
        take = nu.IfDo(
            OPS.booted.is_null(), OPS.booted.set(True) >> mine.set(True) >> knobs() >> minted()
        )

        def build(held: nu.ObjectRef) -> nu.Nu:
            ids = nu.Dict(held)
            return folders(ids) >> job_pages(ids) >> jobs(ids)

        made = nu.let(nuspace.atomic(OPS.made.extract()), build)
        return nuspace.atomic(take) >> nu.IfDo(nu.Bool(mine), made)

    return nu.let(False, first)


# --- what pages share ----------------------------------------------------------------------------


def on_ops(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root)``, bracketed step by step: a page cell's body over :data:`~.state.OPS`."""
    return on_root(plane, lambda r: nuspace.bracketed(build(r)))


def on_subject(plane: str, kind: str, build: Callable[[nu.Str, nu.Str], nu.Nu]) -> nu.Nu:
    """``build(root, subject)`` on a job or incident page, the subject read from the page's meta ``kind``."""
    about = nu.str(Space.planes[plane].meta[kind].fallback(""))
    return nu.let(nuspace.atomic(about), lambda s: on_ops(plane, lambda r: build(r, nu.Str(s))))


def tail(name: nu.StrArg, n: nu.IntArg) -> nu.List:
    """The newest ``n`` lines of job ``name``'s stream, newest first: a read the size of ``n``. Bare."""
    newest = OPS.logs[name].entries.reversed_values()
    row = lambda e: nu.Dict.of(ts_us=e["ts_us"], level=e["level"], msg=e["msg"], fields=e["fields"])  # noqa: E731
    return nu.Iterator(nustd.itertools.islice(newest, n)).map(row).to_list()


#: Two dicts as one, the second's keys over the first's.
merged = _merge


def paused(name: nu.StrArg) -> nu.Bool:
    """Whether job ``name`` is off its schedule. Bare read."""
    return nu.Bool(nu.Dict(OPS.jobs[name].fallback({})).get_item("paused", False))


def ran(step: nu.StrArg, said: nu.Nu) -> nu.Nu:
    """A runbook step into the steps log: ``said`` is ``[ok, what it found]``. Bare."""
    s = nu.List(said)
    entry = nu.Dict.of(at=nustd.time.time(), step=step, ok=s[0], said=s[1])
    return OPS.steps.set(push(OPS.steps.fallback([]), entry, 60)) >> event(
        "runbook", nu.Str(step) + ": " + nu.Str(s[1]), "runbooks"
    )


def resolve_open(root: nu.StrArg, key: nu.StrArg, who: nu.StrArg = YOU) -> nu.Nu:
    """Resolve the open incident for ``key``, if there is one."""
    iid = nuspace.atomic(_open_key(nu.Dict(OPS.incidents.extract()).fallback({}), key))
    return nu.let(
        iid, lambda i: nu.IfDo(nu.Str(i) != "", settle_incident(root, nu.Str(i), "resolved", who))
    )
