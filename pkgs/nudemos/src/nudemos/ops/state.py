"""The state every ops plane shares, and how each plane finds it.

Everything lives in the root Ops plane's state (:class:`Ops`): the jobs write
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

    Ops                     the root, made from :data:`nudemos.ops.PLANE`
      Jobs                  every job, and a page per job (made_by ``ops_job``)
      Traffic, Logs, Machine, Deploys, Incidents, Runbooks, Rules, Status
      <root>.job.<name>     the jobs themselves, headless, made_by ``ops_worker``
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nulog.messages.shapes import MessageStream
from nuspace import ops
from nuspace.shapes import Space


__all__ = [
    "INCIDENT",
    "JOB_PAGE",
    "MADE_BY",
    "ROOT",
    "SERIES",
    "WORKER",
    "Ops",
    "at_root",
    "incident_page",
    "job_cell",
    "job_page",
    "job_plane",
    "root_of",
]


#: ``made_by`` of the root, a job's page, a job's headless plane, an incident's page.
ROOT, JOB_PAGE, WORKER, INCIDENT = "ops", "ops_job", "ops_worker", "ops_incident"

#: What a root records as ``made_by``, the name the space registers it under.
MADE_BY = f"nudemos.{ROOT}"

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


class Ops(nuspace.PlaneState):
    """The whole ops space: jobs, releases, incidents, logs, metrics, knobs."""

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


def _made_by(plane: nu.StrArg) -> nu.Str:
    return Space.planes[plane].props.made_by.fallback("")


def root_of(plane: nu.StrArg) -> nu.Str:
    """The Ops root a plane belongs to: itself, its meta's ``base``, or its parent. Bare read."""
    base = nu.str(Space.planes[plane].meta["base"]).fallback(ops.parent(plane))
    return nu.Str(nu.If(_made_by(plane) == MADE_BY, plane, base))


def at_root(root: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`Ops`, landed on the root's state. Bare."""
    return ops.plane_state(root, term)


def job_plane(root: nu.StrArg, name: nu.StrArg) -> nu.Str:
    """A job's headless plane: fixed under the root, so every cell finds it without a look."""
    return nu.Str(root) + ".job." + nu.Str(name)


def job_cell(job: nu.StrArg) -> nu.Str:
    """A job's one cell: its plane id with ``_main`` after it."""
    return nu.Str(job) + "_main"


def job_page(root: nu.StrArg, name: nu.StrArg) -> nu.Str:
    """A job's page, under Jobs."""
    return nu.Str(root) + ".jobs." + nu.Str(name)


def incident_page(root: nu.StrArg, iid: nu.StrArg) -> nu.Str:
    """An incident's page, under Incidents."""
    return nu.Str(root) + ".incident." + nu.Str(iid)
