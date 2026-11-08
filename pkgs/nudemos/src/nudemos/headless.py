"""Headless jobs as the demos make and steer them: a plane the web never shows, its cells, the supervisor.

A demo's background work is a job: a plane with a backend and no web row,
its cells a few lines of Nu each, kept up or scheduled by the supervisor.
Cells make and steer them, so every helper here brackets itself: run it on
its own, in a flow, or under ``nuspace.bracketed`` (a bracket already in a
term is kept, never doubled).

- :func:`make`: the plane and its cells, then each cell's id under its name
  in the plane's state, the way ``nuspace.specs.add_plane`` leaves a spec
  plane's; :func:`cell_of` reads one back. :func:`once` makes a plane only
  when no row has its id.
- :func:`supervise`: under the supervisor, or its policy changed; brought up
  when it is down. :func:`unsupervise`: off it, its run stopped.
  :func:`restart`: its run stopped, waited out, and a fresh one.
- :func:`live`: whether it has a live run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nuspace
from nuspace.specs import SpecCells
from nuspace.system import supervisor
from nuspace.utils import MintId


if TYPE_CHECKING:
    from collections.abc import Sequence


__all__ = ["cell_of", "live", "make", "once", "restart", "supervise", "unsupervise"]


class _Minted(nu.Shape):
    """The cell ids :func:`make` mints before any commit, under names fixed at build."""

    ids = nu.DictRef.slot(str)


def make(
    plane: nu.StrArg,
    *,
    parent: nu.StrArg,
    name: nu.StrArg,
    backend: str,
    spec: str,
    cells: Sequence[tuple[str, nu.StrArg]],
    meta: dict[str, Any] | nu.Nu | None = None,
) -> nu.Nu:
    """A headless plane under ``parent`` with its cells: two commits, Space then State.

    The cell ids are minted first, then the plane and its cells go in one
    commit on Space, then each cell's id under its name in the plane's
    state (:class:`~nuspace.specs.SpecCells`), so a cell or a page finds a
    job's cell by name with one read (:func:`cell_of`). A failure in the
    second leaves the job without its names.

    A job draws nothing, so its cells' fabrics are none, given rather than
    worked out: nothing is built inside the commit.

    Args:
        plane: Its id.
        parent: The plane it hangs under.
        name: Display text.
        backend: What its runs execute on: ``mp`` for a job in its own process.
        spec: What it records as ``spec``, what the demo calls this kind of job.
        cells: ``(name, source)`` per cell, in order. Names are unique per job.
        meta: Its free dict.

    Raises:
        Exists: The plane's id is taken.
        Missing: No ``parent``.
    """
    names = [cname for cname, _ in cells]
    if len(set(names)) != len(names):
        msg = f"headless.make: cell names repeat in {names}"
        raise ValueError(msg)
    ids = [nu.Str(_Minted.ids[cname]) for cname in names]
    mints = [_Minted.ids[cname].set(MintId("c")) for cname in names]
    made = nuspace.plane.add(plane, parent=parent, name=name, backend=backend, spec=spec, meta=meta)
    added = [
        nuspace.cell.add(plane, src, id=cid, name=cname, fabrics=[])
        for cid, (cname, src) in zip(ids, cells, strict=True)
    ]
    named = nuspace.at.plane(id=plane).state(SpecCells).ids
    kept = [named.set_item(cname, cid) for cid, cname in zip(ids, names, strict=True)]
    steps = [*mints, nuspace.atomic(nu.Sequential(made, *added))]
    if kept:
        steps.append(nuspace.atomic(nu.Sequential(*kept)))
    return nu.Frame(_Minted, nu.Sequential(*steps), ids={})


def cell_of(plane: nu.StrArg, name: nu.StrArg) -> nu.Str:
    """The id of job ``plane``'s cell named ``name`` (:func:`make`), NULL for none. A State read, bare."""
    return nu.Str(nuspace.at.plane(id=plane).state(SpecCells).ids[name])


def once(plane: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term``, the making of ``plane``, only when no row has its id.

    A removed plane counts: ids are never reused, so one removed stays removed.
    """
    there = nuspace.atomic(nuspace.plane.exists(plane, removed=True))
    return nu.IfDo(nu.Bool(there).not_(), term)


def supervise(
    plane: nu.StrArg, policy: nu.StrArg = supervisor.ON_FAILURE, delay: nu.FloatArg | None = None
) -> nu.Nu:
    """Make sure ``plane`` is under the supervisor with ``policy``: one supervised already takes it. One commit.

    A plane its supervisor run left down is brought up again.

    Raises:
        Missing: No plane with that id.
        Removed: It is removed.
    """
    return nuspace.atomic(supervisor.supervise(plane, policy=policy, delay=delay, exists_ok=True))


def _run(plane: nu.StrArg) -> nu.Str:
    """The plane run the supervisor last asked for of ``plane``, ``""`` for none. A State read."""
    return nu.Str(supervisor.supervised()[plane].run.fallback(""))


def unsupervise(plane: nu.StrArg) -> nu.Nu:
    """Take ``plane`` off the supervisor and stop the run it started, if it is live. Two commits.

    A plane not supervised is fine. Its run is asked to stop (interrupted,
    killed after the grace); nothing waits for it to end.
    """

    def off(run: nu.ObjectRef) -> nu.Nu:
        r = nu.Str(run)
        stop = nuspace.atomic(nuspace.plane_run.stop(r))
        return nuspace.atomic(supervisor.unsupervise(plane, missing_ok=True)) >> nu.IfDo(
            r != "", stop
        )

    return nu.let(nuspace.atomic(_run(plane)), off)


def restart(
    plane: nu.StrArg, policy: nu.StrArg = supervisor.ON_FAILURE, delay: nu.FloatArg | None = None
) -> nu.Nu:
    """A fresh run of ``plane``: the supervisor's run stopped and waited out, then supervised again.

    A stopped run ends interrupted, which the supervisor leaves down, so
    supervising it again asks for the new run.
    """

    def again(run: nu.ObjectRef) -> nu.Nu:
        r = nu.Str(run)
        stopped = nuspace.atomic(nuspace.plane_run.stop(r)) >> nuspace.bracketed(
            nuspace.plane_run.wait(r)
        )
        return nu.IfDo(r != "", stopped) >> supervise(plane, policy, delay)

    return nu.let(nuspace.atomic(_run(plane)), again)


def live(plane: nu.StrArg) -> nu.Bool:
    """Whether ``plane`` has a live plane run, False when there is no such plane. A Space read, bare."""
    known = nuspace.plane.exists(plane, removed=True)
    return nu.Bool(nu.If(known, nuspace.plane_run.any_live(plane), False))
