"""The state every ops plane shares, and how each plane finds it.

Everything lives in the root Ops plane's state (:data:`OPS`, typed as
:class:`Ops`): the jobs write
their side (their records, runs, logs, metrics), the pages write the knobs
(the release, the load, the rules, the rota). One class, imported by every
cell and every job, so the slots are declared once.

Records a job rewrites whole each turn are primitive blobs: one row each in
the store, whatever they hold. Metrics are kh57 series keyed by unix second,
so a chart samples them at the same cost however long the space has run.
Logs keep nulog's own layout (:class:`nulog.messages.shapes.MessageStream`):
one append-only, log-indexed stream per job, read newest first at a cost of
what is read, never of how long the stream is.

The planes hang as the root makes them::

    Ops                     the root, made from :data:`nudemos.ops.PLANE`, keyed :data:`KEY`
      Jobs                  every job, and a page per job (spec ``ops_job``)
      Traffic, Logs, Machine, Deploys, Incidents, Runbooks, Rules, Status
      <job>                 the jobs themselves, headless, spec ``ops_worker``

One Ops per space: its gateway listens on a fixed port. The root is keyed
:data:`KEY`, so every cell and job finds it, and :data:`OPS`, its state, in
one index read. Every plane under it has a minted id, kept in :class:`Made`
when it is minted: a cell finds a folder, a job or an incident's page with
one read of :data:`OPS`, never by building an id.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nulog.messages.shapes import MessageStream
from nuspace import Space


__all__ = [
    "INCIDENT",
    "JOB_PAGE",
    "KEY",
    "OPS",
    "ROOT",
    "ROOT_ID",
    "SERIES",
    "WORKER",
    "Made",
    "Ops",
    "folder_of",
    "incident_view",
    "job_view",
    "worker_of",
]


#: ``spec`` of a job's page, a job's headless plane, an incident's page; ``ROOT`` names the demo.
ROOT, JOB_PAGE, WORKER, INCIDENT = "ops", "ops_job", "ops_worker", "ops_incident"

#: The root's key: one Ops per space.
KEY = "nudemos_ops"

#: The root's id, one index read. NULL while the space has no Ops.
ROOT_ID = Space.indexes.plane_keys[KEY]

#: The metric series, by slot: what each one is, for charts and the rules.
SERIES = {
    "rps": "requests a second",
    "err": "share of requests failing, last 15s",
    "p50": "median latency, ms",
    "p95": "95th percentile latency, ms",
    "cpu": "host cpu, %",
    "mem": "host memory, %",
    "disk": "disk used, %",
    "load": "load, 1 min",
    "gw_rss": "gateway memory, MB",
    "orders": "orders a minute",
}


class Made(nu.Shape):
    """The ids of the planes the root made, each minted before its plane is made.

    ``folders``: Jobs, Traffic, ... by key. ``views``: each job's page under
    Jobs, by job name. ``workers``: each job's headless plane, by job name.
    ``incidents``: each incident's page, by incident id.
    """

    folders = nustd.kv.DictRef.slot(str)
    views = nustd.kv.DictRef.slot(str)
    workers = nustd.kv.DictRef.slot(str)
    incidents = nustd.kv.DictRef.slot(str)


class Ops(nu.Shape):
    """The whole ops space: jobs, releases, incidents, logs, metrics, knobs, and the planes it made."""

    # The ids of the planes the root made (:class:`Made`).
    made = nustd.kv.ShapeRef.slot(Made)

    # A record per job (what it is, its schedule, its process, its last run), and its newest runs.
    jobs = nustd.kv.DictRef.slot(nustd.kv.PrimitiveDictRef)
    runs = nustd.kv.DictRef.slot(nustd.kv.PrimitiveListRef)
    # The release live now, and every deploy, newest first.
    release = nustd.kv.PrimitiveDictRef.slot()
    deploys = nustd.kv.PrimitiveListRef.slot()
    # Incidents by id, the pages sent to people, and the feed of everything that happened.
    incidents = nustd.kv.DictRef.slot(nustd.kv.PrimitiveDictRef)
    pager = nustd.kv.PrimitiveListRef.slot()
    events = nustd.kv.PrimitiveListRef.slot()
    # Knobs: which rules are on, how many shoppers, who is on call, where the gateway listens.
    rules = nustd.kv.DictRef.slot(nustd.kv.PrimitiveDictRef)
    load = nustd.kv.PrimitiveDictRef.slot()
    oncall = nustd.kv.PrimitiveListRef.slot()
    settings = nustd.kv.PrimitiveDictRef.slot()
    # What the jobs found: the gateway's live numbers, the machine, the help center, the archives.
    gw = nustd.kv.PrimitiveDictRef.slot()
    machine = nustd.kv.PrimitiveDictRef.slot()
    links = nustd.kv.PrimitiveDictRef.slot()
    backups = nustd.kv.PrimitiveListRef.slot()
    steps = nustd.kv.PrimitiveListRef.slot()
    digest = nustd.kv.StrRef.slot()
    # Moves once per gateway flush and per telemetry read: what live pages follow.
    beat = nustd.kv.IntRef.slot()
    tick = nustd.kv.IntRef.slot()
    booted = nustd.kv.BoolRef.slot()
    # Log lines per job, in nulog's layout, and how many each stream holds.
    logs = nustd.kv.DictRef.slot(MessageStream)
    counts = nustd.kv.PrimitiveDictRef.slot()
    # Metrics, a point every second or two, keyed by unix second.
    rps = nustd.kv.Kh57Ref.slot(float)
    err = nustd.kv.Kh57Ref.slot(float)
    p50 = nustd.kv.Kh57Ref.slot(float)
    p95 = nustd.kv.Kh57Ref.slot(float)
    cpu = nustd.kv.Kh57Ref.slot(float)
    mem = nustd.kv.Kh57Ref.slot(float)
    disk = nustd.kv.Kh57Ref.slot(float)
    load1 = nustd.kv.Kh57Ref.slot(float)
    gw_rss = nustd.kv.Kh57Ref.slot(float)
    orders = nustd.kv.Kh57Ref.slot(float)


#: The whole ops space, in the root's state: what every cell and job reads and writes.
OPS = nuspace.at.plane(KEY).state(Ops)


def worker_of(name: nu.StrArg) -> nu.Str:
    """Job ``name``'s headless plane, NULL before the first open mints it. Bare read."""
    return nu.Str(OPS.made.workers[name])


def job_view(name: nu.StrArg) -> nu.Str:
    """Job ``name``'s page under Jobs, NULL before the first open mints it. Bare read."""
    return nu.Str(OPS.made.views[name])


def folder_of(key: nu.StrArg) -> nu.Str:
    """The folder ``key`` (``jobs``, ``incidents``, ``runbooks``, ...), NULL before the first open. Bare read."""
    return nu.Str(OPS.made.folders[key])


def incident_view(iid: nu.StrArg) -> nu.Str:
    """Incident ``iid``'s page under Incidents, NULL before it is opened. Bare read."""
    return nu.Str(OPS.made.incidents[iid])
