"""Starting and stopping the sync, and opening a token's page: the ops the planes share.

The sync is a headless job plane under the root, made the first time it is
started (:func:`start`) and kept under the supervisor from then on, so it
comes back after a crash and when the space opens again. Stopping it sets
the root's ``stop`` flag: the job ends its loop at the next turn, writes
"stopped", and exits cleanly, which the supervisor leaves down. Starting
again clears the flag and supervises it again.

A token page is made on demand (:func:`open_token`), the first time someone
clicks the token, never for every token seen: there are thousands.
"""

from __future__ import annotations

import nu
import nuspace
from nuspace import PlaneSpec, ops
from nuspace.shapes import Space
from nuspace.system.utils import snap

from .job import SYNC
from .state import JOB, TOKEN, Control, at_root, job_cell, job_of, overview_of, token_page


__all__ = ["go", "live", "open_token", "restart", "start", "stop"]


def live(root: nu.StrArg) -> nu.Bool:
    """Whether the sync job has a run now. Bare read."""
    return nu.Bool(Space.kernel.planes_running.contains(job_of(root)))


def _job(root: nu.StrArg) -> nu.Nu:
    """The job plane and its one cell, made once."""
    job = job_of(root)
    made = ops.add_plane(
        job,
        backend="mp",
        name="sync",
        parent=root,
        ui=False,
        made_by=JOB,
        meta=nu.Dict.of(base=root),
    ) >> ops.add_cell(job, SYNC, cell_id=job_cell(job), name="sync")
    return nu.IfDo(nu.Bool(snap(ops.plane_exists(job))).not_(), made)


def start(root: nu.StrArg) -> nu.Nu:
    """Run the sync: made if it is not there, the stop flag cleared, put under the supervisor."""
    clear = ops.atomic_state(at_root(root, Control.stop.set(False)))
    return _job(root) >> clear >> nuspace.supervise(job_of(root))


def stop(root: nu.StrArg) -> nu.Nu:
    """Ask the sync to stop: it ends its loop at the next turn and says so."""
    return ops.atomic_state(at_root(root, Control.stop.set(True)))


def restart(root: nu.StrArg, slot: nu.IntArg) -> nu.Nu:
    """Start over from ``slot``, or from the tip when it is 0, then run."""
    over = Control.start.set(nu.Int(slot)) >> Control.epoch.set(Control.epoch.fallback(0) + 1)
    return ops.atomic_state(at_root(root, over)) >> start(root)


def go(nav: nu.Nu, uri: nu.StrArg) -> nu.Nu:
    """Navigate the shell to ``uri``.

    The shell follows the browser's back and forward only, so push the page
    and one past it, and step back onto it.
    """
    return nu.let(uri, lambda u: nav.set(u) >> nav.set(nu.Str(u) + "?open") >> nav.back())


def open_token(root: nu.StrArg, mint: nu.StrArg, nav: nu.Nu, beside: nu.StrArg = "") -> nu.Nu:
    """Open ``mint``'s page, made under the Overview if it is not there yet.

    With ``beside`` a plane id, the page opens next to that plane, both
    side by side; otherwise alone.
    """
    from .token import CELLS

    spec = PlaneSpec(TOKEN, "Token", cells=CELLS, backend="async")

    def opened(page: nu.ObjectRef, under: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(page)
        meta = nu.Dict.of(base=root, mint=mint, icon="lucide:coins", editable=True, full_width=True)
        make = ops.create_plane(
            spec, parent=nu.Str(under), name=mint, plane_id=pid
        ) >> ops.set_plane_meta(pid, meta)
        route = nu.If(
            nu.Str(beside) == "", nu.Str("/") + pid, nu.Str("/") + nu.Str(beside) + "+" + pid
        )
        return nu.IfDo(nu.Bool(snap(ops.plane_exists(pid))).not_(), make) >> go(nav, route)

    return nu.let(
        token_page(root, mint),
        lambda page: nu.let(snap(overview_of(root)), lambda under: opened(page, under)),
    )
