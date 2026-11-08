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
from nuspace.specs import add_plane
from nuspace.utils import MintId

from .. import headless
from .job import launch_source
from .page import PAGE
from .state import JOB, RUN_CELL, agent, agents_at, job_of, page_at


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

    The page, then its job's id minted and kept on the page, then the job
    under the page, then who finds whom in plane state (``root`` its
    agents) with the agent's inbox and log, one commit, then the
    supervisor, which starts it.

    Args:
        root: The Agents plane.
        spec: The agent's spec, a dict term: ``name``, ``cwd``, ``model``, ``mode``, ``brief``.
        page: Set to the new page's id, for a caller that opens it or keeps it.
        job: Set to the new job's id, for a caller that follows it.
        plane_id: The page's id. Given, a launch run again makes only what
            the last one did not get to, so a flow that restarts halfway
            through making an agent makes it once: the job's id is kept on
            the page before the job is made.
    """

    def made(s: nu.Ref, p: nu.Ref) -> nu.Nu:
        pid = nu.Str(p)
        new_page = add_plane(PAGE, plane_id, parent=root, name=nu.Dict(s)["name"], into=p)
        if plane_id is not None:
            new_page = headless.once(plane_id, new_page)
        # The job's id, minted once and kept on the page first: a launch run again finds it there.
        claimed = nuspace.atomic(page_at(pid).job.init(MintId("p")))

        def run(j: nu.Ref) -> nu.Nu:
            jid = nu.Str(j)
            kept = [r.set(v) for r, v in ((page, pid), (job, jid)) if r is not None]
            cells = [(RUN_CELL, launch_source(s))]
            new_job = headless.make(
                jid, parent=pid, name="run", backend="mp", spec=JOB, cells=cells
            )
            # Who finds whom, and its inbox and log, made with it: the page and the flow read them from the start.
            a = agent(jid)
            found = (
                agents_at(root).jobs.set_item(pid, jid)
                >> a.inbox.init(nu.List.create())
                >> a.log.init(nu.List.create())
            )
            return nu.Sequential(
                headless.once(jid, new_job),
                nuspace.atomic(found),
                headless.supervise(jid),
                *kept,
            )

        return new_page >> claimed >> nu.let(nuspace.atomic(job_of(pid)), run)

    # The spec is read once: it may make a folder, or read state that moves.
    first = "" if plane_id is None else plane_id
    return nu.let(spec, lambda s: nu.let(first, lambda p: made(s, p)))


def say(job: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """``text`` queued for agent ``job``, which is brought up if it is down or stopped."""
    a = agent(job)
    told = a.inbox.append(nu.Str(text)) >> a.stop.set(False)
    return nuspace.atomic(told) >> headless.supervise(job)


def stop(job: nu.StrArg) -> nu.Nu:
    """Ask agent ``job`` to stop: a turn under way is cut, and the loop ends. One already down is stopped now."""
    live = nuspace.atomic(headless.live(job))
    a = agent(job)

    def asked(up: nu.Nu) -> nu.Nu:
        said = nu.Str(nu.If(up, "stopping", "stopped"))
        return nuspace.atomic(a.stop.set(True) >> a.status.set(said))

    return nu.let(live, asked)


def resume(job: nu.StrArg) -> nu.Nu:
    """Bring agent ``job`` back: its conversation reopened, a cut turn carried on."""
    a = agent(job)
    cleared = a.stop.set(False) >> a.status.set("resuming")
    return nuspace.atomic(cleared) >> headless.supervise(job)
