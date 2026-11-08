"""nudemos.headless: jobs made, kept under the supervisor, stopped and restarted, on a real store.

No kernel runs here: the records are what is checked, and the test plays the
kernel's and the supervisor's side where a run has to exist.
"""

from __future__ import annotations

import pytest
from _support.made import MADE

import nuspace
from nudemos import headless
from nuspace import Space
from nuspace.system import supervisor


async def _job(store, pid: str = "j") -> None:
    cells = [("run", "def out(cell):\n    return None\n")]
    await store.run(
        headless.make(pid, parent="root", name="job", backend="mp", spec="demo_job", cells=cells)
    )


async def _policy(store, pid: str) -> object:
    return await store.read(supervisor.supervised()[pid].policy)


async def test_a_job_is_a_plane_with_its_cells_and_no_web_row(store):
    await _job(store)
    row = await store.read(Space.planes["j"].extract())
    assert (row["name"], row["backend"], row["spec"], row["parent"]) == (
        "job",
        "mp",
        "demo_job",
        "root",
    )
    # The cell's id is minted, and kept under its name in the plane's state.
    run = await store.read(headless.cell_of("j", "run"))
    assert await store.read(Space.planes["j"].cells.keys(limit=5)) == [run]
    cell = await store.read(Space.cells[run].extract())
    assert (cell["name"], cell["fabrics"]) == ("run", [])
    from nu.lang import is_null

    assert is_null(await store.read(headless.cell_of("j", "nope")))
    from nuspace.devices.web import Web

    assert not await store.read(Web.planes.contains("j"))


def test_a_job_refuses_two_cells_under_one_name():
    cells = [("run", "a"), ("run", "b")]
    with pytest.raises(ValueError, match="repeat"):
        headless.make("j", parent="root", name="job", backend="mp", spec="demo_job", cells=cells)


async def test_once_makes_a_plane_only_when_no_row_has_its_id(store):
    made = headless.once(
        "j", headless.make("j", parent="root", name="job", backend="mp", spec="demo_job", cells=[])
    )
    await store.run(made)
    await store.run(made)
    await store.do(nuspace.plane.remove("j"))
    # Removed stays removed: its id is never reused.
    await store.run(made)
    assert await store.read(nuspace.plane.exists("j")) is False
    with pytest.raises(nuspace.errors.Exists):
        await store.run(
            headless.make("j", parent="root", name="job", backend="mp", spec="x", cells=[])
        )


async def test_supervise_is_make_sure_and_takes_the_new_policy(store):
    await _job(store)
    await store.run(headless.supervise("j"))
    await store.run(headless.supervise("j"))
    assert await _policy(store, "j") == supervisor.ON_FAILURE
    await store.run(headless.supervise("j", supervisor.ALWAYS, 5.0))
    assert await _policy(store, "j") == supervisor.ALWAYS
    assert await store.read(supervisor.supervised()["j"].delay) == 5.0


async def test_unsupervise_stops_the_run_the_supervisor_started(store):
    await _job(store)
    await store.run(headless.supervise("j"))
    run = await store.made(nuspace.atomic(nuspace.plane_run.add("j", by=supervisor.BY, into=MADE)))
    await store.do(supervisor.supervised()["j"].run.set(run))
    assert await store.read(headless.live("j")) is True
    await store.run(headless.unsupervise("j"))
    assert await store.read(supervisor.supervised().contains("j")) is False
    row = Space.exec.plane_runs[run]
    assert await store.read(row.interrupt_at.exists()) is True
    assert await store.read(row.kill_at.exists()) is True
    # Not supervised is fine.
    await store.run(headless.unsupervise("j"))


async def test_restart_waits_the_run_out_then_asks_for_a_new_one(store):
    await _job(store)
    await store.run(headless.supervise("j"))
    run = await store.made(nuspace.atomic(nuspace.plane_run.add("j", by=supervisor.BY, into=MADE)))
    await store.do(supervisor.supervised()["j"].run.set(run))
    # The kernel's side: the run ended, so the wait returns at once.
    await store.do(nuspace.plane_run.end(run, "interrupted"))
    await store.run(headless.restart("j", supervisor.ALWAYS, 1.0))
    # Its run over, supervising it again forgets it: the supervisor asks for a new one.
    assert await store.read(supervisor.supervised()["j"].run.exists()) is False
    assert await _policy(store, "j") == supervisor.ALWAYS


async def test_live_is_false_for_a_plane_not_there(store):
    assert await store.read(headless.live("nowhere")) is False
    await _job(store)
    assert await store.read(headless.live("j")) is False
