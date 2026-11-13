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
from nuspace.web import Web, url
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
        "width": "page",
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


async def _frames(store, term: nu.Nu, *, plane: str = "x", cell: str = "x") -> list:
    """The frames one run of ``term`` sends, inside ``Here`` for ``plane`` and ``cell``."""
    session = _Recording()
    await nu.arun(inside(term, plane=plane, cell=cell), store.ctx.bind(Session, session))
    return session.frames


def _tiles(frames: list) -> dict:
    """A counts grid's tiles, ``{tile key: value}``: each Stat sits in a Card at the tile's key."""
    return {f.ref[-2]: f.payload["value"] for f in frames}


def _rows(frames: list) -> list:
    """The rows the one table write carried."""
    (rows,) = [f.payload["rows"] for f in frames if "rows" in f.payload]
    return rows


def _started(rows: list) -> list:
    """The rows with ``started`` taken out, each checked to be epoch ms or blank."""
    for r in rows:
        started = r.pop("started")
        assert started == "" or (isinstance(started, int) and started > 1_000_000_000_000)
    return rows


def _page(pid: str, title: str, icon: str = "file-text") -> dict:
    """A plane link cell's value, as ``web.page`` reads it (``file-text`` is the default icon)."""
    return {"id": pid, "title": title, "icon": icon, "href": url(pid)}


def _columns(table: nu.Nu) -> list[str]:
    """A table's declared column keys."""
    return [c["key"] for c in table._payload["props"]["columns"]]


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


def test_system_cells_are_shims():
    assert workers.PLANE.cells == (
        (
            "counts",
            "from nuverse.planes import workers\n\n\ndef out(plane):\n    return workers.counts(plane)\n",
        ),
        (
            "workers",
            "from nuverse.planes import workers\n\n\ndef out(plane):\n    return workers.listing(plane)\n",
        ),
    )
    for module in LIVE:
        for _, prog in module.PLANE.cells:
            name, fn = prog.split("return ")[1].split("(")[0].split(".")
            assert name == module.PLANE.name
            assert callable(getattr(module, fn))


async def test_runs_draws_counts_and_tables(store):
    seeded = await _seed(store)
    assert _tiles(await _frames(store, runs.draw_counts())) == {
        "runs": "1",
        "cells": "2",
        "workers": "1",
    }
    assert _columns(runs.RUNS_TABLE) == [
        "plane",
        "backend",
        "by",
        "cells",
        "workers",
        "started",
        "run",
    ]
    live = _started(_rows(await _frames(store, runs.draw_live())))
    plane = _page("p", "P")
    assert live == [
        {
            "plane": plane,
            "backend": "async",
            "by": "nav",
            "cells": 2,
            "workers": 1,
            "run": seeded["run"],
        }
    ]
    assert _columns(runs.CELLS_TABLE) == [
        "plane",
        "cell",
        "state",
        "by",
        "version",
        "started",
        "worker",
        "id",
    ]
    rows = _rows(await _frames(store, runs.draw_cells()))
    assert [r.pop("started") == "" for r in rows] == [False, True]
    running = {"label": "running", "tone": "ok"}
    starting = {"label": "starting", "tone": "neutral"}
    assert rows == [
        {
            "plane": plane,
            "cell": "C",
            "state": running,
            "by": "nav",
            "version": 1,
            "worker": seeded["worker"],
            "id": seeded["x1"],
        },
        {
            "plane": plane,
            "cell": "C",
            "state": starting,
            "by": "reload",
            "version": 2,
            "worker": "",
            "id": seeded["x2"],
        },
    ]


async def test_runs_counts_redraw_on_a_change_and_never_while_idle(store):
    session = _Recording()
    task = asyncio.create_task(nu.arun(runs.counts("x"), store.ctx.bind(Session, session)))
    try:
        # Drawn once, on binding: no re-checks, so idle after that.
        await asyncio.sleep(0.5)
        idle = len(session.frames)
        assert _tiles(session.frames) == {"runs": "0", "cells": "0", "workers": "0"}
        await asyncio.sleep(0.5)
        assert len(session.frames) == idle
        await _seed(store)
        await asyncio.sleep(0.3)
        assert _tiles(session.frames[idle:]) == {"runs": "1", "cells": "2", "workers": "1"}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_workers_draws_counts_and_a_table(store):
    seeded = await _seed(store)
    assert _tiles(await _frames(store, workers.draw_counts())) == {
        "up": "1",
        "async": "1",
        "mp": "0",
    }
    assert _columns(workers.TABLE_REF) == ["plane", "backend", "cells", "started", "run", "id"]
    rows = _started(_rows(await _frames(store, workers.draw_listing())))
    assert rows == [
        {
            "plane": _page("p", "P"),
            "backend": "async",
            "cells": 1,
            "run": seeded["run"],
            "id": seeded["worker"],
        }
    ]


# --- planes ------------------------------------------------------------------------------


def _top(
    name: str, spec: str, system: str, cells: str, planes_: str, pid: str, icon: str = "activity"
) -> dict:
    """A top planes row: its name links to its page (a runs plane wears its spec icon)."""
    return {
        "name": _page(pid, name, "activity" if spec else "file-text"),
        "spec": spec,
        "system": system,
        "cells": cells,
        "planes": planes_,
        "id": pid,
    }


async def test_planes_draws_specs_and_the_top_planes(store):
    r = await store.made(add_plane(runs.PLANE, name="R", into=MADE))
    await store.run(add_plane(runs.PLANE, name="R2"))
    await store.run(add_plane(workers.PLANE, name="W", parent=r))
    await store.do(nuspace.plane.add("s", name="S", system=True, backend="async"))
    assert _columns(planes.SPEC_TABLE) == ["spec", "planes", "newest"]
    by_spec = _rows(await _frames(store, planes.draw_by_spec()))
    newest = {row["spec"]: row.pop("newest")["title"] for row in by_spec}
    assert newest == {"nuverse.runs": "R2", "nuverse.workers": "W"}
    assert sorted(by_spec, key=lambda row: row["spec"]) == [
        {"spec": "nuverse.runs", "planes": "2"},
        {"spec": "nuverse.workers", "planes": "1"},
    ]
    assert _columns(planes.TABLE_REF) == ["name", "spec", "system", "cells", "planes", "id"]
    top = _rows(await _frames(store, planes.draw_listing()))
    r2 = top[1]["id"]
    assert top == [
        _top("R", "nuverse.runs", "", "3", "1", r),
        _top("R2", "nuverse.runs", "", "3", "0", r2),
        _top("S", "", "system", "0", "0", "s"),
    ]


async def test_a_removed_plane_leaves_its_spec_row(store):
    r = await store.made(add_plane(runs.PLANE, name="R", into=MADE))
    await store.run(add_plane(runs.PLANE, name="R2"))
    newest = await store.read(Space.indexes.spec_planes["nuverse.runs"].ids.last())
    await store.do(nuspace.plane.remove(newest))
    by_spec = _rows(await _frames(store, planes.draw_by_spec()))
    assert by_spec == [{"spec": "nuverse.runs", "planes": "1", "newest": _page(r, "R", "activity")}]
    await store.do(nuspace.plane.remove(r))
    by_spec = _rows(await _frames(store, planes.draw_by_spec()))
    assert by_spec == [{"spec": "nuverse.runs", "planes": "0", "newest": ""}]


async def test_a_count_past_a_page_says_so(store):
    await store.do(nuspace.plane.add("big", name="Big"))
    for i in range(planes.PAGE + 1):
        await store.do(nuspace.plane.add(f"k{i:03d}", parent="big"))
    top = _rows(await _frames(store, planes.draw_listing()))
    assert top == [_top("Big", "", "", "0", f"{planes.PAGE}+", "big")]


async def test_planes_redraws_a_shown_row_alone_and_ignores_planes_not_shown(store):
    await store.do(nuspace.plane.add("a", name="A", backend="async"))
    await store.do(nuspace.plane.add("deep", name="Deep", parent="a", backend="async"))
    session = _Recording()
    task = asyncio.create_task(nu.arun(planes.listing("x"), store.ctx.bind(Session, session)))
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
        assert later[-1]["row"] == _top("A", "", "", "1", "1", "a")
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
    await store.run(_as("new", jobs.create("jp", nu.Str(name))))
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
    scope: dict = {}
    exec(compile(jobs.MAIN, "main", "exec"), scope)  # noqa: S102
    out = scope["out"]
    await store.run(inside(out, plane=job, cell=main))
    assert await store.read(State.cells[main].extract()) == {"hello": "world"}


async def test_the_jobs_table_lists_jobs_only_and_selects_on_click(store):
    job = await _job(store)
    other = await _job(store, "Hourly")
    # A page nested under the Jobs plane is no job.
    await store.do(nuspace.plane.add("page", parent="jp", backend="async"))
    await store.do(init.boot(job))
    await store.do(supervisor.supervise(job, policy=supervisor.ALWAYS, delay=5.0))
    rows = _rows(await _frames(store, jobs.draw_jobs(), plane="jp", cell="jobs"))
    stopped = {"label": "stopped", "tone": "neutral"}
    assert rows == [
        {"name": "Nightly", "boot": "boot", "restart": "always, 5s", "running": stopped, "id": job},
        {"name": "Hourly", "boot": "", "restart": "off", "running": stopped, "id": other},
    ]
    # Listed from the plane's state, the order the jobs were made in.
    assert await store.read(nu.list(JOBS.made.keys())) == [job, other]
    # The row click handed to ``select`` as the table's reaction hands it over: by key.
    click = nu.ForEachDo(nu.Iter(nu.Literal([{"row_index": 0, "key": other}])), jobs.select)
    await store.run(_as("jobs", click))
    assert await store.read(SELECTED) == other


async def test_a_running_job_shows_as_running(store):
    job = await _job(store)
    await store.do(nuspace.plane_run.add(job))
    (row,) = _rows(await _frames(store, jobs.draw_jobs(), plane="jp", cell="jobs"))
    assert row["running"] == {"label": "running", "tone": "ok"}


async def _restart(store, job: str, policy: str, delay: float) -> None:
    """The ``job`` cell's restart handler, the select and delay reading as given."""
    session = _Answering({"control": policy, "delay": delay})
    term = _as("job", jobs.apply_restart(nu.Str(job)))
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
    draw = _as("job", jobs.draw_job(nu.Str(job)))
    await nu.arun(draw, store.ctx.bind(Session, session))
    shown = {frame.ref[-1]: frame.payload for frame in session.frames}
    assert (shown["boot"], shown["control"], shown["delay"]) == (True, "always", 2.5)
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
    await store.run(_as("job", jobs.save(nu.Str(job), nu.Str(edited))))
    assert await store.read(Space.cells[main].prog) == edited
    assert await store.read(Space.cells[main].version) == 2


async def test_deleting_a_job_cleans_boot_and_supervision(store):
    job = await _job(store)
    await store.do(init.boot(job))
    await store.do(supervisor.supervise(job, policy=supervisor.ALWAYS, delay=1.0))
    await store.run(_as("job", jobs.remove(nu.Str(job))))
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
