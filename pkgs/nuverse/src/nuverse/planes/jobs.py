"""The ``jobs`` Plane: headless planes, made, listed and set up from one place.

A job is a plane made from :data:`JOB` under this Plane: no web row, so
nothing draws it, and one cell ``main`` holding its code. The job keeps its
cell's id in its own plane state under that name
(:class:`~nuspace.specs.SpecCells`), so the cells here find it with one
read. The jobs this Plane lists are the ones it made, kept in its state as
it makes them (:class:`Jobs`), one page of them: never a scan of its
children or of the space.

Three cells, meeting in the plane's shared state (:class:`Jobs`):

- ``jobs``: every job, drawn again when a job, its boot, restart or run
  changes. A row click selects it.
- ``new``: a name and a button that makes a job, starting as :data:`MAIN`,
  and selects it.
- ``job``: the selected job's code, boot switch, restart setting and delete.
  Restart is plane level: the supervisor keeps the job running.

The cells are shims (:func:`~nuverse.planes.shim`): :func:`listing`,
:func:`new` and :func:`detail` here are their code. A job's own ``main``
is its source, kept in the space.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.ops.interactions import Fabrics
from nuspace.specs import PlaneSpec, SpecCells, WebOptions
from nuspace.system import init, supervisor
from nuverse.planes import shim


__all__ = [
    "DETAIL",
    "JOB",
    "MAIN",
    "MAX_JOBS",
    "NEW",
    "PLANE",
    "POLICY",
    "TABLE",
    "TABLE_REF",
    "Job",
    "Jobs",
    "Listing",
    "New",
    "apply_restart",
    "create",
    "detail",
    "draw_job",
    "draw_jobs",
    "listing",
    "made",
    "main",
    "new",
    "remove",
    "restart_label",
    "save",
    "select",
]


#: How many jobs the table lists: the oldest ones, one page.
MAX_JOBS = 200


class Jobs(nu.Shape):
    """The Jobs plane's state, shared by its cells, declared once here.

    ``made``: the jobs it made, oldest first, written by ``new`` when it
    makes one and dropped by ``job`` when it deletes one. ``selected``: the
    job ``job`` shows, ``""`` for none.
    """

    made = nustd.kv.LogDictRef.slot(bool)
    selected = nustd.kv.StrRef.slot()


#: What a new job's main cell starts as: one key in its own state, then done.
MAIN = """\
import nu
import nustd.kv
import nuspace


class Note(nu.Shape):
    hello = nustd.kv.StrRef.slot()


# This cell's own state.
out = nuspace.atomic(nuspace.here(Note).hello.set("world"))
"""


#: What a job is made from: a headless plane with its one cell. Not offered
#: by ``+``: only this Plane makes jobs. Named with the package in front, as
#: it records on the planes it makes.
JOB = PlaneSpec(
    "nuverse.job",
    "New job",
    description="A headless plane that runs code.",
    cells=(("main", MAIN),),
    backend="mp",
)


# --- what the cells share --------------------------------------------------------------------


JOBS = nuspace.at.plane.state(Jobs)

OFF = "off"

POLICIES = [
    {"value": OFF, "label": "Off"},
    {"value": supervisor.ON_FAILURE, "label": "On failure"},
    {"value": supervisor.ALWAYS, "label": "Always"},
]


def made() -> nu.Nu:
    """The jobs this plane made, kept in its state: one page, oldest first, a gone one left out. A read."""
    held = JOBS.made
    page = nu.list(nu.If(held.exists(), nu.list(held.keys(limit=MAX_JOBS)), []))
    return nu.List(page).iter().filter(lambda p: nuspace.plane.exists(nu.Str(p))).to_list()


# --- jobs: the table ---------------------------------------------------------------------------


class Listing(nu.Shape):
    """The ``jobs`` cell's root: a titled Card holding the table."""

    jobs = nustd.ui.CardRef.slot(title="Jobs", subtitle="Headless planes this page made")


TABLE_REF = Listing.jobs[0].to(
    nustd.ui.DataTableRef.slot(
        columns=[
            {"key": "name", "label": "Name", "sortable": False},
            {
                "key": "boot",
                "label": "Boot",
                "cell": nustd.ui.BadgeRef.slot(variant="secondary", size="sm"),
                "sortable": False,
            },
            {"key": "restart", "label": "Restart", "sortable": False},
            {
                "key": "running",
                "label": "Running",
                "cell": nustd.ui.StatusPillRef,
                "sortable": False,
            },
            {
                "key": "id",
                "label": "ID",
                "wrap": "truncate",
                "max_width": 160,
                "hide_below": 720,
                "sortable": False,
            },
        ],
        row_key="id",
        clickable_rows=True,
        label="Jobs",
    )
)


def restart_label(pid: nu.StrArg) -> nu.Str:
    """How job ``pid`` restarts, as the table says it: ``off``, ``always, 5s``. A read."""
    held = supervisor.supervised()[pid]
    policy = nu.Str(held.policy.fallback(""))
    label = nu.Str(
        nu.Switch(policy, {"always": "always", "on-failure": "on failure"}, default="off")
    )
    # No fixed delay is the backoff.
    timed = (policy != "").and_(held.delay.exists())
    return nu.Str(nu.If(timed, label + ", " + nu.format(held.delay, "g") + "s", label))


def _row(at: nu.ObjectRef) -> nu.Dict:
    j = nu.Str(at)
    running = nuspace.plane_run.any_live(j)
    return nu.Dict.of(
        name=nuspace.plane.title(j),
        boot=nu.If(init.boot_list().contains(j), "boot", ""),
        restart=restart_label(j),
        running=nu.Dict.of(
            label=nu.If(running, "running", "stopped"), tone=nu.If(running, "ok", "neutral")
        ),
        id=j,
    )


def draw_jobs() -> nu.Nu:
    """Read the jobs once and draw the table."""
    return nu.let(nuspace.atomic(made().iter().map(_row).to_list()), TABLE_REF.set_rows)


def select(click: nu.ObjectRef) -> nu.Nu:
    """A row click selects its job, by the row's key."""
    c = nu.Dict(click)
    return nu.IfDo(c.contains("key"), nuspace.atomic(JOBS.selected.set(nu.Str(c["key"]))))


def listing(plane: nu.StrArg) -> nu.Nu:
    """The ``jobs`` cell: every job, drawn again when one is made, booted, supervised or runs."""
    # A job made or deleted here, one removed or moved elsewhere, booted, supervised, or up or down.
    changes = [
        JOBS.made.on_children_change(),
        nuspace.plane.on_children_change(plane),
        init.boot_list().on_change(),
        supervisor.supervised().on_change(),
        nuspace.plane_run.on_live_change(),
    ]
    return nu.ParallelAsync(
        nu.Reconcile(nuspace.atomic(nu.OnAny(*changes)), draw_jobs()),
        nu.ReactEvery(TABLE_REF.on_row_click(), select),
    )


# --- new: make a job ---------------------------------------------------------------------------


class NewJob(nustd.ui.Row):
    """A job's name and the button that makes it."""

    name = nustd.ui.InputRef.slot(label="New job", placeholder="Job name")
    create = nustd.ui.ButtonRef.slot(label="Create job")


class New(nu.Shape):
    """The ``new`` cell's root."""

    form = NewJob.slot(gap=2, align="end", grow={"name": 1})


def create(plane: nu.StrArg, name: nu.StrArg) -> nu.Nu:
    """Make job ``name`` under ``plane``, the Jobs plane: its own commits, then listed and picked."""

    def make(into: nu.ObjectRef) -> nu.Nu:
        job = nu.Str(into)
        return nuspace.specs.add_plane(JOB, parent=plane, name=name, into=into) >> nuspace.atomic(
            JOBS.made.set_item(job, True) >> JOBS.selected.set(job)
        )

    return nu.let("", make)


def new(plane: nu.StrArg) -> nu.Nu:
    """The ``new`` cell: a click makes a job, named as typed or ``New job``, and selects it."""
    form = New.form
    typed = nu.Str(form.name)
    name = nu.If(typed == "", "New job", typed)
    make = nu.let(name, lambda held: create(plane, nu.Str(held)) >> form.name.set(""))
    return form.name.set("") >> form.create.init() >> nu.ReactEvery(form.create.on_click(), make)


# --- job: the selected one ---------------------------------------------------------------------


class Actions(nustd.ui.Row):
    """The job Card's header buttons."""

    save = nustd.ui.ButtonRef.slot(label="Save", variant="secondary", size="sm")
    delete = nustd.ui.ButtonRef.slot(label="Delete job", variant="danger", size="sm")


class Restart(nustd.ui.Row):
    """How the supervisor restarts the job."""

    policy = nustd.ui.FieldRef.slot(label="Restart")
    delay = nustd.ui.NumberInputRef.slot(label="Delay in seconds, 0 backs off", min=0.0)


class Detail(nustd.ui.Card):
    """The selected job: its code, whether it starts with the space, how it restarts."""

    actions = Actions.slot(gap=2)
    editor = nustd.ui.CodeRef.slot(language="python", editable=True, min_height=160, max_height=560)
    boot = nustd.ui.SwitchRef.slot(label="Start when the space opens")
    restart = Restart.slot(gap=4, align="end", grow={"policy": 1, "delay": 1}, stack_below=480)


class Job(nu.Shape):
    """The ``job`` cell's roots: a hint while no job is selected, else the job."""

    empty = nustd.ui.EmptyStateRef.slot(
        label="Select a job",
        description="Pick one above, or make one.",
        icon="briefcase",
        size="sm",
    )
    detail = Detail.slot(gap=4)


POLICY = Job.detail.restart.policy.control.to(nustd.ui.SelectRef.slot(options=POLICIES))


class _Asked(nu.Shape):
    # What the restart controls say, read once per change.
    choice = nu.StrRef.slot()
    delay = nu.FloatRef.slot()


def main(job: nu.StrArg) -> nu.Str:
    """Job ``job``'s one cell, by the name its spec gave it, in the job's own plane state. NULL for none."""
    return nu.Str(nuspace.at.plane(id=job).state(SpecCells).ids["main"])


def draw_job(job: nu.StrArg) -> nu.Nu:
    """Draw job ``job``: its name and id, code, boot switch and restart setting."""
    d = Job.detail
    held = supervisor.supervised()[job]
    policy = nu.Str(held.policy.fallback(""))
    cell = main(job)
    prog = nu.If(nu.IsNull(cell), "", nuspace.Space.cells[cell].prog.fallback(""))
    return nuspace.atomic(
        d.set_title(nuspace.plane.title(job))
        >> d.set_subtitle(job)
        >> d.actions.save.init()
        >> d.actions.delete.set("Delete job", variant="danger")
        >> d.editor.set(nu.str(prog))
        >> d.boot.set(init.boot_list().contains(job))
        >> POLICY.set(nu.If(policy == "", OFF, policy))
        >> d.restart.delay.set(nu.float(held.delay.fallback(0.0)))
    )


def apply_restart(job: nu.StrArg) -> nu.Nu:
    """Set job ``job``'s restart as the controls ask. Plane level: the supervisor keeps it running.

    Set as asked whether or not it was supervised: the wanted state is what
    counts. Off stops its run.
    """
    choice, delay = _Asked.choice, _Asked.delay
    apply = nu.IfDo(
        choice == OFF,
        supervisor.unsupervise(job, missing_ok=True),
        nu.IfDo(
            delay > 0.0,
            supervisor.supervise(job, policy=choice, delay=delay, exists_ok=True),
            supervisor.supervise(job, policy=choice, exists_ok=True),
        ),
    )
    asked = Job.detail.restart
    return nu.Frame(
        _Asked, nuspace.atomic(apply), choice=nu.Str(POLICY), delay=nu.float(asked.delay)
    )


def save(job: nu.StrArg, source: nu.StrArg) -> nu.Nu:
    """Write ``source`` as job ``job``'s code."""

    # The fabrics worked out before the commit, so no build runs inside it.
    def commit(cell: nu.Str, used: nu.ObjectRef) -> nu.Nu:
        return nuspace.atomic(nuspace.cell.set_prog(cell, source, fabrics=used))

    def written(cid: nu.ObjectRef) -> nu.Nu:
        cell = nu.Str(cid)
        return nu.let(Fabrics(source, job, cell), lambda used: commit(cell, used))

    return nu.let(nuspace.atomic(main(job)), written)


def remove(job: nu.StrArg) -> nu.Nu:
    """Delete job ``job``: off the boot list and the supervisor first, then the plane."""
    # Removing the plane ends its live runs.
    off = supervisor.unsupervise(job, missing_ok=True) >> init.unboot(job, missing_ok=True)
    return (
        nuspace.atomic(off)
        >> nuspace.atomic(nuspace.plane.remove(job))
        >> nuspace.atomic(JOBS.made.del_item(job, missing_ok=True) >> JOBS.selected.set(""))
    )


def _delete(job: nu.StrArg) -> nu.Nu:
    # Two clicks: the first arms the button, the second deletes.
    button = Job.detail.actions.delete

    def clicks(armed: nu.ObjectRef) -> nu.Nu:
        click = nu.IfDo(
            nu.Bool(armed),
            remove(job),
            armed.set(True) >> button.set("Click again to delete", variant="danger"),
        )
        return nu.ReactEvery(button.on_click(), click)

    return nu.let(False, clicks)


def _shown(job: nu.Str) -> nu.Nu:
    d = Job.detail
    edited = nu.let(nu.Str(d.editor), lambda source: save(job, nu.Str(source)))
    boot = d.boot
    on = nu.IfDo(nu.bool(boot), init.boot(job, exists_ok=True), init.unboot(job, missing_ok=True))
    return (
        Job.empty.erase()
        >> draw_job(job)
        >> nu.ParallelAsync(
            nu.ReactEvery(d.actions.save.on_click(), edited),
            nu.ReactEvery(boot.on_change(), nuspace.atomic(on)),
            nu.ReactEvery(POLICY.on_change(), apply_restart(job)),
            nu.ReactEvery(d.restart.delay.on_change(), apply_restart(job)),
            _delete(job),
        )
    )


def _showing(at: nu.ObjectRef) -> nu.Nu:
    job = nu.Str(at)
    there = (job != "").and_(nuspace.atomic(nuspace.plane.exists(job)))
    return nu.IfDo(there, _shown(job), Job.detail.erase() >> Job.empty.init())


def detail(plane: nu.StrArg) -> nu.Nu:
    """The ``job`` cell: the selected job, drawn again when another is selected."""
    selected = nuspace.atomic(nu.Str(JOBS.selected.fallback("")))
    return nu.ReconcileLatest(selected, nuspace.atomic(JOBS.selected.on_change()), _showing)


TABLE = shim("jobs", "listing")
NEW = shim("jobs", "new")
DETAIL = shim("jobs", "detail")


PLANE = PlaneSpec(
    "jobs",
    "Jobs",
    icon="briefcase",
    description="Headless planes that run code: make them, boot them, restart them.",
    cells=(("jobs", TABLE), ("new", NEW), ("job", DETAIL)),
    group="System",
    web=WebOptions(editable=True),
    backend="async",
)
