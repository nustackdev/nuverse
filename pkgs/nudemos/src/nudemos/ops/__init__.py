"""The ``ops`` Plane: a small team's ops space, its jobs, logs and machine running for real inside it.

Halcyon sells camping gear online, and this is the space its platform team
runs it from. Opened the first time, the root's ``welcome`` cell brings up
the pages and the jobs, and puts the jobs under the supervisor:

- the storefront API (:mod:`.gateway`), a real HTTP server in its own
  process, and shoppers hitting it over real connections (:mod:`.work`);
- machine telemetry read from the kernel (:mod:`.machine`);
- scheduled scripts: an orders backup, an offsite copy, a help center
  link check, an ops digest, each a run in its own process on a schedule;
- a watchdog whose cells are the alert rules, a few lines of Nu each,
  opening incidents, paging people and pausing schedules on their own.

Every page reads and writes one store at the root (:class:`.state.Ops`):
deploy a release on Deploys and the gateway restarts on it, the rules open
an incident, the status page turns, the runbook rolls it back.

- :mod:`.state`: the store and where planes live.
- :mod:`.model`, :mod:`.views`: the records and what pages show of them, plain Python.
- :mod:`.kit`: the writes and moves cells and jobs share, and the first open.
- :mod:`.jobs`, :mod:`.cells`: every job's and every page's cells, as sources.
- :mod:`.gateway`, :mod:`.work`, :mod:`.machine`, :mod:`.calls`: the resources the jobs drive.
"""

from __future__ import annotations

from nuspace import Plane

from . import cells


__all__ = ["PLANE"]


PLANE = Plane(
    "ops",
    "Ops",
    icon="server",
    description="A small team's ops space: jobs, logs, deploys and incidents, all running live.",
    meta={"editable": True, "full_width": True},
    cells=cells.ROOT,
    group="Demos",
    backend="async",
)
