"""Starting and stopping the sync, and opening a token's page: the ops the planes share.

The sync is a headless job plane under the root, made the first time it is
started (:func:`start`) and kept under the supervisor from then on, so it
comes back after a crash and when the space opens again. Stopping it sets
the root's ``stop`` flag: the job ends its loop at the next turn, writes
"stopped", and exits cleanly, which the supervisor leaves down. Starting
again clears the flag and supervises it again.

A token page is made on demand (:func:`open_token`), the first time someone
clicks the token, never for every token seen: there are thousands. A block
of the user's can make one without opening it (:func:`make_token`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
import nuspace.specs
import nuspace.system.supervisor
import nuspace.web

from .. import bases
from .job import SYNC
from .state import JOB, TOKEN, control_at, made_at, memes_at, overview_of


if TYPE_CHECKING:
    import nustd.ui


__all__ = ["live", "make_token", "open_token", "restart", "start", "stop"]


def live(root: nu.StrArg) -> nu.Bool:
    """Whether the sync job has a run now, False before its first start. Bare read."""
    job = nu.Str(made_at(root).job.fallback(""))
    return nu.Bool(nu.If(job == "", False, nuspace.plane_run.any_live(job)))


def _job(root: nu.StrArg) -> nu.Nu:
    """The job plane and its one cell, made once, the job's id kept in the root's state.

    Two commits: the plane and its cell in Space, then the id in the root's
    state and the root in the job's (:mod:`nudemos.bases`). The cell draws nothing, so its fabrics are none.
    """
    made = made_at(root)

    def make(job: nu.ObjectRef) -> nu.Nu:
        plane = nuspace.plane.add(parent=root, name="sync", backend="mp", spec=JOB, into=job)
        one = nuspace.cell.add(nu.Str(job), SYNC, name="sync", fabrics=[])
        kept = made.job.set(nu.Str(job)) >> bases.belongs(nu.Str(job), root)
        return nuspace.atomic(plane >> one) >> nuspace.atomic(kept)

    absent = nu.Bool(nuspace.atomic(made.job.exists())).not_()
    return nu.IfDo(absent, nu.let(make, job=""))


def start(root: nu.StrArg) -> nu.Nu:
    """Run the sync: made if it is not there, the stop flag cleared, put under the supervisor.

    Supervised on failure: a crash brings it back, a stop asked for leaves it down.
    """
    clear = nuspace.atomic(control_at(root).stop.set(False))
    policy = nuspace.system.supervisor.ON_FAILURE

    def supervised(job: nu.ObjectRef) -> nu.Nu:
        return nuspace.atomic(
            nuspace.system.supervisor.supervise(nu.Str(job), policy=policy, exists_ok=True)
        )

    return _job(root) >> clear >> nu.let(supervised, job=nuspace.atomic(made_at(root).job))


def stop(root: nu.StrArg) -> nu.Nu:
    """Ask the sync to stop: it ends its loop at the next turn and says so."""
    return nuspace.atomic(control_at(root).stop.set(True))


def restart(root: nu.StrArg, slot: nu.IntArg) -> nu.Nu:
    """Start over from ``slot``, or from the tip when it is 0, then run."""
    c = control_at(root)
    over = c.start.set(nu.Int(slot)) >> c.epoch.set(c.epoch.fallback(0) + 1)
    return nuspace.atomic(over) >> start(root)


def make_token(root: nu.StrArg, mint: nu.StrArg, name: nu.StrArg | None = None) -> nu.Nu:
    """Make ``mint``'s page under the Overview if the root holds none yet, without opening it.

    A new page is a row of commits: the plane with its cells and its web row,
    its meta (its mint), then its id kept in the root's state and the root
    in its own (:mod:`nudemos.bases`). It is named ``name`` (the mint when
    none) until its first run names it by its ticker.
    """
    from .token import CELLS

    spec = nuspace.specs.PlaneSpec(
        TOKEN,
        "Token",
        icon="coins",
        cells=CELLS,
        web=nuspace.specs.WebOptions(editable=True, width="board"),
        backend="async",
    )
    held = made_at(root).token_planes[mint]

    def make(page: nu.ObjectRef, under: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(page)
        meta = nu.Dict.of(mint=mint)
        return (
            nuspace.specs.add_plane(
                spec, parent=nu.Str(under), name=mint if name is None else name, into=page
            )
            >> nuspace.atomic(nuspace.plane.set_meta(pid, meta))
            >> nuspace.atomic(held.set(pid) >> bases.belongs(pid, root))
        )

    def made(page: nu.ObjectRef) -> nu.Nu:
        new = nu.let(lambda under: make(page, under), under=nuspace.atomic(overview_of(root)))
        return nu.IfDo(nu.Str(page) == "", new)

    return nu.let(made, page=nuspace.atomic(held.fallback("")))


def open_token(root: nu.StrArg, mint: nu.StrArg, history: nustd.ui.HistoryRef) -> nu.Nu:
    """Open ``mint``'s page on ``history``, made under the Overview first if needed (:func:`make_token`).

    A new page is named by the token's ticker when the sync knows it, so it
    never shows its mint while it opens.
    """
    held = made_at(root).token_planes[mint]

    def opened(rec: nu.ObjectRef) -> nu.Nu:
        symbol = nu.Str(nu.Dict(rec).get_item("symbol", "")).strip()
        name = nu.Str(nu.If(symbol == "", mint, symbol))
        return make_token(root, mint, name) >> history.push(nuspace.web.href(nuspace.atomic(held)))

    return nu.let(opened, rec=nuspace.atomic(memes_at(root).tokens[mint].fallback({})))
