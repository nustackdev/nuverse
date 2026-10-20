"""Every :mod:`.shape` function as a host term, so a cell calls ``views.pulse(...)`` over the store.

The shaping itself is plain Python in :mod:`.shape`, tested there.
"""

from __future__ import annotations

import nu

from . import shape


__all__ = [
    "TONES",
    "clock",
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


TONES = nu.host(shape.TONES, name="Tones")
clock = nu.host(shape.clock, name="Clock")
components = nu.host(shape.components, name="Components")
deploy_rows = nu.host(shape.deploy_rows, name="DeployRows")
feed_rows = nu.host(shape.feed_rows, name="FeedRows")
incident_head = nu.host(shape.incident_head, name="IncidentHead")
incident_rows = nu.host(shape.incident_rows, name="IncidentRows")
job_head = nu.host(shape.job_head, name="JobHead")
job_rows = nu.host(shape.job_rows, name="JobRows")
job_runs = nu.host(shape.job_runs, name="JobRuns")
joined = nu.host(shape.joined, name="Joined")
log_rows = nu.host(shape.log_rows, name="LogRows")
machine_tiles = nu.host(shape.machine_tiles, name="MachineTiles")
named = nu.host(shape.named, name="Named")
proc_rows = nu.host(shape.proc_rows, name="ProcRows")
pulse = nu.host(shape.pulse, name="Pulse")
release_notes = nu.host(shape.release_notes, name="ReleaseNotes")
route_rows = nu.host(shape.route_rows, name="RouteRows")
rule_rows = nu.host(shape.rule_rows, name="RuleRows")
run_rows = nu.host(shape.run_rows, name="RunRows")
series = nu.host(shape.series, name="Series")
timeline = nu.host(shape.timeline, name="Timeline")
