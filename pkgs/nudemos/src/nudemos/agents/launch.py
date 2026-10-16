"""Making and steering agents, as terms: what the form, the pages and the flows all do.

- :func:`launch`: an agent page under the Agents plane, its headless job
  under the page with the spec baked in, put under the supervisor, which
  starts it.
- :func:`say`: a message into an agent's inbox, and the job brought up if it
  is down. A working agent takes it as its next turn, an idle one now.
- :func:`stop` and :func:`resume`: the stop flag, and the job brought back.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import snap

from .job import launch_source
from .page import PAGE
from .state import JOB, Agent, at, job_cell


__all__ = ["launch", "resume", "say", "stop"]


def launch(
    root: nu.StrArg,
    spec: nu.Nu,
    *,
    page: nu.Ref | None = None,
    job: nu.Ref | None = None,
    plane_id: str | None = None,
) -> nu.Nu:
    """An agent made from ``spec`` (see :func:`~.views.spec_from`) under ``root``, started.

    Args:
        root: The Agents plane.
        spec: The agent's spec, a dict term: ``name``, ``cwd``, ``model``, ``mode``, ``brief``.
        page: Set to the new page's id, for a caller that opens it or keeps it.
        job: Set to the new job's id, for a caller that follows it.
        plane_id: The page's id, its job's that with ``_run`` after it. Given, a
            launch run again makes only what the last one did not get to, so
            a flow that restarts halfway through making an agent makes it once.
    """

    def made(s: nu.Ref, p: nu.Ref, j: nu.Ref) -> nu.Nu:
        kept = [r.set(nu.Str(v)) for r, v in ((page, p), (job, j)) if r is not None]
        fixed = plane_id is not None
        new_page = ops.create_plane(
            PAGE, parent=root, name=nu.Dict(s)["name"], plane_id=plane_id, into=None if fixed else p
        )
        new_job = ops.add_plane(
            None if not fixed else f"{plane_id}_run",
            backend="mp",
            name="run",
            parent=nu.Str(p),
            ui=False,
            made_by=JOB,
            into=None if fixed else j,
        ) >> ops.add_cell(nu.Str(j), launch_source(s), cell_id=job_cell(nu.Str(j)), name="run")
        if fixed:
            new_page = nu.IfDo(snap(ops.plane_exists(plane_id).not_()), new_page)
            new_job = nu.IfDo(snap(ops.plane_exists(f"{plane_id}_run").not_()), new_job)
        return nu.Sequential(new_page, new_job, nuspace.supervise(nu.Str(j)), *kept)

    ids = ("", "") if plane_id is None else (plane_id, f"{plane_id}_run")
    # The spec is read once: it may make a folder, or read state that moves.
    return nu.let(spec, lambda s: nu.let(ids[0], lambda p: nu.let(ids[1], lambda j: made(s, p, j))))


def say(job: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """``text`` queued for agent ``job``, which is brought up if it is down or stopped."""
    told = at(job, Agent.inbox.append(nu.Str(text)) >> Agent.stop.set(False))
    return ops.atomic_state(told) >> nuspace.supervise(job)


def stop(job: nu.StrArg) -> nu.Nu:
    """Ask agent ``job`` to stop: a turn under way is cut, and the loop ends. One already down is stopped now."""
    live = snap(Space.kernel.planes_running.contains(job))

    def asked(up: nu.Nu) -> nu.Nu:
        said = nu.Str(nu.If(up, "stopping", "stopped"))
        return ops.atomic_state(at(job, Agent.stop.set(True) >> Agent.status.set(said)))

    return nu.let(live, asked)


def resume(job: nu.StrArg) -> nu.Nu:
    """Bring agent ``job`` back: its conversation reopened, a cut turn carried on."""
    cleared = at(job, Agent.stop.set(False) >> Agent.status.set("resuming"))
    return ops.atomic_state(cleared) >> nuspace.supervise(job)
