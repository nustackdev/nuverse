"""nuverse's Planes: what making ``jobs``, ``runs``, ``workers`` and ``planes`` seeds, and their cells.

A cell's prog is run here the way a program is: its module built, then its
``draw`` (or a handler) evaluated against the store with a recording
session bound, inside ``Here`` for the plane and cell it would run as.
"""

from __future__ import annotations

import asyncio
import zlib

import pytest
from _support.made import MADE

import nu
import nuspace
import nuverse
from nuspace.kernel import BACKENDS
from nuspace.places import Here, inside
from nuspace.shapes import ROOT, Space, State
from nuspace.specs import SpecCells, add_plane
from nuspace.system import ensure, init, supervisor
from nuspace.web import Web
from nuspace.web.shell import Shell
from nuspace.web.utils import CellRoot
from nustd.ui import Session
from nuverse.planes import jobs, planes, runs, workers


LIVE = [jobs, runs, workers, planes]
CELLS = {
    "jobs": [("jobs", jobs.TABLE), ("new", jobs.NEW), ("job", jobs.DETAIL)],
    "runs": [("counts", runs.COUNTS), ("live", runs.LIVE), ("cells", runs.CELLS)],
    "workers": [("counts", workers.COUNTS), ("workers", workers.TABLE)],
    "planes": [("by_spec", planes.BY_SPEC), ("planes", planes.TABLE)],
}


class _Recording:
    """A session that keeps the frames it is sent instead of sending them."""

    def __init__(self) -> None:
        self.frames: list = []

    async def send(self, frame: object) -> None:
        self.frames.append(frame)


class _Answering(_Recording):
    """A recording session that also answers reads, by the ref's own name."""

    def __init__(self, values: dict) -> None:
        super().__init__()
        self.values = values

    async def aread(self, path: tuple) -> object:
        return self.values[path[-1]]


async def _cells_of(store, plane: str) -> list[tuple[str, str]]:
    """A plane's cells in order, as ``(name, prog)``."""
    ids = await store.read(nu.list(Space.planes[plane].cells.keys()))
    return [
        (await store.read(Space.cells[c].name), await store.read(Space.cells[c].prog)) for c in ids
    ]


@pytest.mark.parametrize("module", LIVE, ids=lambda m: m.PLANE.name)
async def test_each_plane_is_made_on_the_web_with_its_cells(store, module):
    spec = module.PLANE
    p = await store.made(add_plane(spec, name="Live", into=MADE))
    row = await store.read(Space.planes[p].extract())
    assert (row["name"], row["spec"], row["backend"], row["system"]) == (
        "Live",
        f"nuverse.{spec.name}",
        "async",
        False,
    )
    assert (row["icon"], row["parent"], row["meta"]) == (f"lucide:{spec.icon}", ROOT, {})
    assert await _cells_of(store, p) == CELLS[spec.name]
    assert await store.read(Web.planes[p].extract()) == {
        "editable": True,
        "full_width": False,
        "compact": False,
    }
    # Each cell's id under its name, in the plane's state.
    ids = await store.read(nuspace.at.plane(id=p).state(SpecCells).ids.extract())
    assert sorted(ids) == sorted(name for name, _ in CELLS[spec.name])


async def test_a_plane_made_with_no_name_takes_the_label(store):
    p = await store.made(add_plane(runs.PLANE, into=MADE))
    assert await store.read(nuspace.plane.title(p)) == "Runs"
    assert len(await _cells_of(store, p)) == 3


@pytest.mark.parametrize(
    "source",
    [s for cells in CELLS.values() for _, s in cells],
    ids=lambda s: f"{zlib.crc32(s.encode()):08x}",
)
async def test_each_cell_loads_through_the_kernel_rewrites(store, source):
    await store.do(nuspace.plane.add("p", backend="async"))
    await store.do(nuspace.cell.add("p", source, id="c", fabrics=["ui"]))
    rewrite = CellRoot(Shell.viewer, Here.cell)
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite)
    term = await store.read(load)
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(inside(term, plane="p", cell="c")))


def _cell(source: str) -> dict:
    """A cell's module namespace, its functions callable from here."""
    namespace: dict = {}
    exec(compile(source, "cell", "exec"), namespace)  # noqa: S102
    return namespace


async def _frames(store, source: str, *, plane: str = "x", cell: str = "x") -> dict:
    """One draw of a cell against the store: ``{ref name: payload}``."""
    session = _Recording()
    term = inside(_cell(source)["draw"](), plane=plane, cell=cell)
    await nu.arun(term, store.ctx.bind(Session, session))
    return {frame.ref[-1]: frame.payload for frame in session.frames}


# --- runs and workers --------------------------------------------------------------------


async def _seed(store) -> dict:
    """One live plane run with two live cell runs, one placed on its worker, and an ended run.

    Made the way the kernel makes them, through the ops. The ids, by name.
    """
    do, made = store.do, store.made
    await do(nuspace.plane.add("p", name="P", backend="async"))
    await do(nuspace.cell.add("p", "x", id="c", name="C", fabrics=[]))
    r = await made(nuspace.atomic(nuspace.plane_run.add("p", by="nav", into=MADE)))
    await do(nuspace.plane_run.start(r))
    w = await made(nuspace.atomic(nuspace.worker.add(r, "async", into=MADE)))
    await do(nuspace.worker.start(w, handle={"pid": 7}))
    x1 = await made(nuspace.atomic(nuspace.cell_run.add(r, "c", by="nav", into=MADE)))
    await do(nuspace.cell_run.start(x1, worker=w))
    await do(nuspace.cell.set_prog("c", "y", fabrics=[]))
    x2 = await made(nuspace.atomic(nuspace.cell_run.add(r, "c", by="reload", into=MADE)))
    gone = await made(nuspace.atomic(nuspace.plane_run.add("p", into=MADE)))
    w2 = await made(nuspace.atomic(nuspace.worker.add(gone, "mp", into=MADE)))
    await do(nuspace.worker.end(w2, "failed"))
    await do(nuspace.plane_run.end(gone, "failed"))
    return {"run": r, "worker": w, "x1": x1, "x2": x2}


async def test_runs_draws_counts_and_tables(store):
    seeded = await _seed(store)
    counts = await _frames(store, runs.COUNTS)
    assert {name: counts[name]["value"] for name in counts} == {
        "runs": "1",
        "cells": "2",
        "workers": "1",
    }
    (live,) = (await _frames(store, runs.LIVE)).values()
    assert live["columns"] == ["Plane", "Backend", "By", "Cells", "Workers", "Age"]
    assert live["rows"] == [["P", "async", "nav", 2, 1, "<1m"]]
    (table,) = (await _frames(store, runs.CELLS)).values()
    assert table["columns"] == ["Plane", "Cell", "By", "Version", "Worker", "Age"]
    assert table["rows"] == [
        ["P", "C", "nav", 1, seeded["worker"], "<1m"],
        ["P", "C", "reload", 2, "", "starting"],
    ]


async def test_runs_counts_redraw_on_a_change_and_never_while_idle(store):
    out = _cell(runs.COUNTS)["out"]
    session = _Recording()
    task = asyncio.create_task(nu.arun(out, store.ctx.bind(Session, session)))
    try:
        # Drawn once, on binding: no re-checks, so idle after that.
        await asyncio.sleep(0.5)
        idle = len(session.frames)
        assert {f.ref[-1]: f.payload["value"] for f in session.frames} == {
            "runs": "0",
            "cells": "0",
            "workers": "0",
        }
        await asyncio.sleep(0.5)
        assert len(session.frames) == idle
        await _seed(store)
        await asyncio.sleep(0.3)
        drawn = {f.ref[-1]: f.payload["value"] for f in session.frames[idle:]}
        assert drawn == {"runs": "1", "cells": "2", "workers": "1"}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_workers_draws_counts_and_a_table(store):
    seeded = await _seed(store)
    counts = await _frames(store, workers.COUNTS)
    assert {name: counts[name]["value"] for name in counts} == {
        "up": "1",
        "async": "1",
        "mp": "0",
    }
    (table,) = (await _frames(store, workers.TABLE)).values()
    assert table["columns"] == ["ID", "Backend", "Plane", "Run", "Cells", "Age"]
    assert table["rows"] == [[seeded["worker"], "async", "P", seeded["run"], 1, "<1m"]]


# --- planes ------------------------------------------------------------------------------


async def test_planes_draws_specs_and_the_top_planes(store):
    r = await store.made(add_plane(runs.PLANE, name="R", into=MADE))
    await store.run(add_plane(runs.PLANE, name="R2"))
    await store.run(add_plane(workers.PLANE, name="W", parent=r))
    await store.do(nuspace.plane.add("s", name="S", system=True, backend="async"))
    (by_spec,) = (await _frames(store, planes.BY_SPEC)).values()
    assert by_spec["columns"] == ["Spec", "Planes", "Newest"]
    assert sorted(by_spec["rows"]) == [["nuverse.runs", "2", "R2"], ["nuverse.workers", "1", "W"]]
    (top,) = (await _frames(store, planes.TABLE)).values()
    assert top["columns"] == ["Name", "Spec", "System", "Cells", "Planes", "ID"]
    assert top["row_key"] == "ID"
    assert [row[:5] for row in top["rows"]] == [
        ["R", "nuverse.runs", "no", "3", "1"],
        ["R2", "nuverse.runs", "no", "3", "0"],
        ["S", "-", "yes", "0", "0"],
    ]
    assert [row[5] for row in top["rows"]][::2] == [r, "s"]


async def test_a_removed_plane_leaves_its_spec_row(store):
    r = await store.made(add_plane(runs.PLANE, name="R", into=MADE))
    await store.run(add_plane(runs.PLANE, name="R2"))
    newest = await store.read(Space.indexes.spec_planes["nuverse.runs"].ids.last())
    await store.do(nuspace.plane.remove(newest))
    (by_spec,) = (await _frames(store, planes.BY_SPEC)).values()
    assert by_spec["rows"] == [["nuverse.runs", "1", "R"]]
    await store.do(nuspace.plane.remove(r))
    (by_spec,) = (await _frames(store, planes.BY_SPEC)).values()
    assert by_spec["rows"] == [["nuverse.runs", "0", "-"]]


async def test_a_count_past_a_page_says_so(store):
    await store.do(nuspace.plane.add("big", name="Big"))
    for i in range(planes.PAGE + 1):
        await store.do(nuspace.plane.add(f"k{i:03d}", parent="big"))
    (top,) = (await _frames(store, planes.TABLE)).values()
    assert top["rows"] == [["Big", "-", "no", "0", f"{planes.PAGE}+", "big"]]


async def test_planes_redraws_a_shown_row_alone_and_ignores_planes_not_shown(store):
    await store.do(nuspace.plane.add("a", name="A", backend="async"))
    await store.do(nuspace.plane.add("deep", name="Deep", parent="a", backend="async"))
    out = _cell(planes.TABLE)["out"]
    session = _Recording()
    task = asyncio.create_task(nu.arun(out, store.ctx.bind(Session, session)))
    try:
        await asyncio.sleep(0.5)
        idle = len(session.frames)
        # A cell on a plane the table does not show: no frame.
        await store.do(nuspace.cell.add("deep", "x", id="c1", fabrics=[]))
        await asyncio.sleep(0.3)
        assert len(session.frames) == idle
        # A cell on a shown plane: its row alone, in place.
        await store.do(nuspace.cell.add("a", "x", id="c2", fabrics=[]))
        await asyncio.sleep(0.3)
        later = [f.payload for f in session.frames[idle:]]
        assert later, "no frame for the shown plane"
        assert all("rows" not in p for p in later)
        assert later[-1]["key"] == "a"
        assert later[-1]["row"] == ["A", "-", "no", "1", "1", "a"]
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


# --- jobs --------------------------------------------------------------------------------


JOBS = nuspace.at.plane(id="jp").state(jobs.Jobs)
SELECTED = JOBS.selected


def _as(cell: str, term: nu.Nu, plane: str = "jp") -> nu.Nu:
    """``term`` as the Jobs plane's ``cell`` would run it, inside its Here."""
    return inside(term, plane=plane, cell=cell)


async def _job(store, name: str = "Nightly") -> str:
    """The system planes, the Jobs plane at ``jp``, and a job made by its ``new`` cell."""
    if not await store.read(nuspace.plane.exists("jp")):
        await store.run(ensure())
        await store.run(add_plane(jobs.PLANE, "jp"))
    await store.run(_as("new", _cell(jobs.NEW)["create"](nu.Str(name))))
    return await store.read(SELECTED)


def _main(job: str) -> nu.Nu:
    return nuspace.at.plane(id=job).state(SpecCells).ids["main"]


async def test_the_jobs_plane_registers_after_quickstart():
    specs = nuverse.extension().planes

    assert [p.name for p in specs[:2]] == ["quickstart", "jobs"]
    assert (jobs.PLANE.label, jobs.PLANE.icon) == ("Jobs", "briefcase")
    assert jobs.JOB not in specs


async def test_creating_a_job_makes_a_headless_plane_with_a_main_cell(store):
    job = await _job(store)
    row = await store.read(Space.planes[job].extract())
    assert (row["name"], row["spec"], row["backend"], row["parent"]) == (
        "Nightly",
        "nuverse.job",
        "mp",
        "jp",
    )
    assert await store.read(Web.planes.contains(job)) is False
    main = await store.read(_main(job))
    assert await _cells_of(store, job) == [("main", jobs.MAIN)]
    assert await store.read(nu.list(Space.planes[job].cells.keys())) == [main]


async def test_a_new_job_runs_its_starter(store):
    job = await _job(store)
    main = await store.read(_main(job))
    out = _cell(jobs.MAIN)["out"]
    await store.run(inside(out, plane=job, cell=main))
    assert await store.read(State.cells[main].extract()) == {"hello": "world"}


async def test_the_jobs_table_lists_jobs_only_and_selects_on_click(store):
    job = await _job(store)
    other = await _job(store, "Hourly")
    # A page nested under the Jobs plane is no job.
    await store.do(nuspace.plane.add("page", parent="jp", backend="async"))
    await store.do(init.boot(job))
    await store.do(supervisor.supervise(job, policy=supervisor.ALWAYS, delay=5.0))
    (table,) = (await _frames(store, jobs.TABLE, plane="jp", cell="jobs")).values()
    assert table["rows"] == [
        ["Nightly", job, "yes", "always, 5s", "no"],
        ["Hourly", other, "no", "off", "no"],
    ]
    # Listed from the plane's state, the order the jobs were made in.
    assert await store.read(nu.list(JOBS.made.keys())) == [job, other]
    select = _cell(jobs.TABLE)["select"]
    # The row click handed to ``select`` as the table's reaction hands it over.
    click = nu.ForEachDo(nu.Iter(nu.Literal([{"row_index": 0}])), select)
    await store.run(_as("jobs", click))
    assert await store.read(SELECTED) == job


async def test_a_running_job_shows_as_running(store):
    job = await _job(store)
    await store.do(nuspace.plane_run.add(job))
    (table,) = (await _frames(store, jobs.TABLE, plane="jp", cell="jobs")).values()
    assert table["rows"] == [["Nightly", job, "no", "off", "yes"]]


async def _restart(store, job: str, policy: str, delay: float) -> None:
    """The ``job`` cell's restart handler, the select and delay reading as given."""
    session = _Answering({"choice": policy, "delay": delay})
    term = _as("job", _cell(jobs.DETAIL)["restart"](nu.Str(job)))
    await nu.arun(term, store.ctx.bind(Session, session))


def _policy(job: str) -> nu.Nu:
    held = supervisor.supervised()[job]
    return nu.List.of(held.policy.fallback(""), held.delay.fallback(-1.0))


async def test_boot_and_restart_settings_round_trip(store):
    job = await _job(store)
    await store.do(init.boot(job))
    await _restart(store, job, supervisor.ALWAYS, 2.5)
    assert await store.read(_policy(job)) == [supervisor.ALWAYS, 2.5]
    session = _Recording()
    draw = _as("job", _cell(jobs.DETAIL)["draw"](nu.Str(job)))
    await nu.arun(draw, store.ctx.bind(Session, session))
    shown = {frame.ref[-1]: frame.payload for frame in session.frames}
    assert (shown["boot"], shown["choice"], shown["delay"]) == (True, "always", 2.5)
    assert shown["editor"] == jobs.MAIN
    # Asked again while supervised: the new policy holds. No delay backs off.
    await _restart(store, job, supervisor.ON_FAILURE, 0.0)
    assert await store.read(_policy(job)) == [supervisor.ON_FAILURE, -1.0]
    # Off takes the job off the supervisor, twice as well as once.
    await _restart(store, job, "off", 3.0)
    await _restart(store, job, "off", 3.0)
    assert await store.read(_policy(job)) == ["", -1.0]


async def test_saving_a_jobs_code_rewrites_its_main_cell(store):
    job = await _job(store)
    main = await store.read(_main(job))
    edited = jobs.MAIN.replace('"world"', '"there"')
    await store.run(_as("job", _cell(jobs.DETAIL)["save"](nu.Str(job), nu.Str(edited))))
    assert await store.read(Space.cells[main].prog) == edited
    assert await store.read(Space.cells[main].version) == 2


async def test_deleting_a_job_cleans_boot_and_supervision(store):
    job = await _job(store)
    await store.do(init.boot(job))
    await store.do(supervisor.supervise(job, policy=supervisor.ALWAYS, delay=1.0))
    await store.run(_as("job", _cell(jobs.DETAIL)["remove"](nu.Str(job))))
    assert await store.read(nuspace.plane.exists(job)) is False
    assert await store.read(nu.list(Space.planes["jp"].children.keys())) == []
    assert await store.read(nu.list(JOBS.made.keys())) == []
    assert await store.read(init.boot_list().contains(job)) is False
    assert await store.read(_policy(job)) == ["", -1.0]
    assert await store.read(SELECTED) == ""


def test_every_plane_names_a_registered_backend():
    specs = nuverse.extension().planes

    assert all(spec.backend in BACKENDS for spec in (*specs, jobs.JOB))
    assert {spec.name: spec.backend for spec in specs} == dict.fromkeys(
        ("quickstart", "jobs", "runs", "workers", "planes"), "async"
    )
