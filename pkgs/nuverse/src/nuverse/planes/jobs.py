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
"""

from __future__ import annotations

import nu
import nustd.kv
from nuspace.specs import PlaneSpec, WebOptions


__all__ = ["DETAIL", "JOB", "MAIN", "MAX_JOBS", "NEW", "PLANE", "TABLE", "Jobs"]


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


TABLE = """\
import nu
import nustd.ui
import nuspace
from nuspace.places import Here
from nuspace.system import init, supervisor
from nuverse.planes.jobs import MAX_JOBS, Jobs


JOBS = nuspace.at.plane.state(Jobs)


class Listing(nustd.ui.Column):
    table = nustd.ui.TableRef.slot(
        columns=["Name", "ID", "Boot", "Restart", "Running"], clickable_rows=True
    )


def jobs():
    # The jobs this plane made, kept in its state: one page, oldest first, a gone one left out.
    made = JOBS.made
    page = nu.list(nu.If(made.exists(), nu.list(made.keys(limit=MAX_JOBS)), []))
    return page.iter().filter(lambda p: nuspace.plane.exists(nu.Str(p))).to_list()


def restart(pid):
    held = supervisor.supervised()[pid]
    policy = nu.Str(held.policy.fallback(""))
    label = nu.Str(
        nu.Switch(policy, {"always": "always", "on-failure": "on failure"}, default="off")
    )
    # No fixed delay is the backoff.
    timed = (policy != "").and_(held.delay.exists())
    return nu.If(timed, label + ", " + nu.format(held.delay, "g") + "s", label)


def rows():
    def row(at):
        j = nu.Str(at)
        return nu.List.of(
            nuspace.plane.title(j),
            j,
            nu.If(init.boot_list().contains(j), "yes", "no"),
            restart(j),
            nu.If(nuspace.plane_run.any_live(j), "yes", "no"),
        )

    return jobs().iter().map(row).to_list()


def table(shown):
    columns = ["Name", "ID", "Boot", "Restart", "Running"]
    return Listing.table.set(nu.Dict.of(columns=columns, rows=shown))


def draw():
    return nu.let(nuspace.atomic(rows()), table)


def select(click):
    at = nu.int(click["row_index"])

    def pick(ids):
        return nu.IfDo(nu.List(ids).len() > at, JOBS.selected.set(nu.str(nu.List(ids)[at])))

    # The rows are the jobs in order: the same read finds the one clicked.
    return nu.IfDo(click.contains("row_index"), nuspace.atomic(nu.let(jobs(), pick)))


# A job made or deleted here, one removed or moved elsewhere, booted, supervised, or up or down.
changes = [
    JOBS.made.on_children_change(),
    nuspace.plane.on_children_change(Here.plane),
    init.boot_list().on_change(),
    supervisor.supervised().on_change(),
    nuspace.plane_run.on_live_change(),
]
out = nu.ParallelAsync(
    nu.Reconcile(nuspace.atomic(nu.OnAny(*changes)), draw()),
    nu.ReactEvery(Listing.table.on_row_click(), select),
)
"""


NEW = """\
import nu
import nustd.ui
import nuspace
from nuspace.places import Here
from nuverse.planes.jobs import JOB, Jobs


JOBS = nuspace.at.plane.state(Jobs)


class Form(nustd.ui.Row):
    name = nustd.ui.InputRef.slot(placeholder="Job name")
    create = nustd.ui.ButtonRef.slot(label="Create job")


def create(name):
    # Under the plane running this cell: the Jobs plane. Its own commits, then listed and picked.
    def make(made):
        job = nu.Str(made)
        return (
            nuspace.specs.add_plane(JOB, parent=Here.plane, name=name, into=made)
            >> nuspace.atomic(JOBS.made.set_item(job, True) >> JOBS.selected.set(job))
        )

    return nu.let("", make)


typed = nu.Str(Form.name)
name = nu.If(typed == "", "New job", typed)
make = nu.let(name, lambda held: create(nu.Str(held)) >> Form.name.set(""))

out = (
    Form.name.set("")
    >> Form.create.set("Create job")
    >> nu.ReactEvery(Form.create.on_click(), make)
)
"""


DETAIL = """\
import nu
import nustd.ui
import nuspace
from nuspace.ops.interactions import Fabrics
from nuspace.specs import SpecCells
from nuspace.system import init, supervisor
from nuverse.planes.jobs import Jobs

OFF = "off"

POLICIES = [
    {"value": OFF, "label": "Off"},
    {"value": supervisor.ON_FAILURE, "label": "On failure"},
    {"value": supervisor.ALWAYS, "label": "Always"},
]


JOBS = nuspace.at.plane.state(Jobs)


def main(job):
    # A job's one cell, by the name its spec gave it, in the job's own plane state.
    return nu.Str(nuspace.at.plane(id=job).state(SpecCells).ids["main"])


class Policy(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=POLICIES)


class Restart(nustd.ui.Row):
    policy = Policy.slot(label="Restart")
    delay = nustd.ui.NumberInputRef.slot(label="Delay in seconds, 0 backs off", min=0.0)


class Detail(nustd.ui.Column):
    title = nustd.ui.HeadingRef.slot(level=3)
    editor = nustd.ui.CodeRef.slot(
        language="python", editable=True, min_height=160, max_height=560
    )
    save = nustd.ui.ButtonRef.slot(label="Save", variant="secondary")
    boot = nustd.ui.SwitchRef.slot(label="Start when the space opens")
    restart = Restart.slot(gap=4, align="end", wrap=True)
    delete = nustd.ui.ButtonRef.slot(label="Delete job", variant="danger")


class Empty(nustd.ui.Column):
    hint = nustd.ui.DividerRef.slot()


class View(nustd.ui.Column):
    empty = Empty.slot()
    detail = Detail.slot(gap=4)


class Asked(nu.Shape):
    # What the restart controls say, read once per change.
    choice = nu.StrRef.slot()
    delay = nu.FloatRef.slot()


def draw(job):
    d = View.detail
    held = supervisor.supervised()[job]
    policy = nu.Str(held.policy.fallback(""))
    return nuspace.atomic(
        d.title.set(nuspace.plane.title(job))
        >> d.editor.set(nu.str(nuspace.Space.cells[main(job)].prog.fallback("")))
        >> d.save.set("Save")
        >> d.boot.set(init.boot_list().contains(job))
        >> d.restart.policy.choice.set(nu.If(policy == "", OFF, policy))
        >> d.restart.delay.set(nu.float(held.delay.fallback(0.0)))
        >> d.delete.set("Delete job", variant="danger")
    )


def restart(job):
    # Plane level: the supervisor keeps the job running, off stops its run.
    # Set as asked whether or not it was supervised: the wanted state is what counts.
    choice, delay = Asked.choice, Asked.delay
    apply = nu.IfDo(
        choice == OFF,
        supervisor.unsupervise(job, missing_ok=True),
        nu.IfDo(
            delay > 0.0,
            supervisor.supervise(job, policy=choice, delay=delay, exists_ok=True),
            supervisor.supervise(job, policy=choice, exists_ok=True),
        ),
    )
    asked = View.detail.restart
    return nu.Frame(
        Asked, nuspace.atomic(apply), choice=nu.Str(asked.policy.choice), delay=nu.float(asked.delay)
    )


def save(job, source):
    # The fabrics worked out before the commit, so no build runs inside it.
    def commit(cell, used):
        return nuspace.atomic(nuspace.cell.set_prog(cell, source, fabrics=used))

    def written(cid):
        cell = nu.Str(cid)
        return nu.let(Fabrics(source, job, cell), lambda used: commit(cell, used))

    return nu.let(nuspace.atomic(main(job)), written)


def remove(job):
    # Off the boot list and the supervisor first, then the plane: removing it ends its live runs.
    off = supervisor.unsupervise(job, missing_ok=True) >> init.unboot(job, missing_ok=True)
    return (
        nuspace.atomic(off)
        >> nuspace.atomic(nuspace.plane.remove(job))
        >> nuspace.atomic(JOBS.made.del_item(job, missing_ok=True) >> JOBS.selected.set(""))
    )


def delete(job):
    # Two clicks: the first arms the button, the second deletes.
    button = View.detail.delete

    def clicks(armed):
        click = nu.IfDo(
            nu.Bool(armed),
            remove(job),
            armed.set(True) >> button.set("Click again to delete", variant="danger"),
        )
        return nu.ReactEvery(button.on_click(), click)

    return nu.let(False, clicks)


def shown(job):
    d = View.detail
    edited = nu.let(nu.Str(d.editor), lambda source: save(job, nu.Str(source)))
    on = nu.IfDo(nu.bool(d.boot), init.boot(job, exists_ok=True), init.unboot(job, missing_ok=True))
    return (
        View.empty.erase()
        >> draw(job)
        >> nu.ParallelAsync(
            nu.ReactEvery(d.save.on_click(), edited),
            nu.ReactEvery(d.boot.on_change(), nuspace.atomic(on)),
            nu.ReactEvery(d.restart.policy.choice.on_change(), restart(job)),
            nu.ReactEvery(d.restart.delay.on_change(), restart(job)),
            delete(job),
        )
    )


def hint():
    return View.detail.erase() >> View.empty.hint.set("Select a job")


def showing(job):
    there = (nu.Str(job) != "").and_(nuspace.atomic(nuspace.plane.exists(job)))
    return nu.IfDo(there, shown(job), hint())


selected = nuspace.atomic(nu.Str(JOBS.selected.fallback("")))
out = nu.ReconcileLatest(selected, nuspace.atomic(JOBS.selected.on_change()), showing)
"""


PLANE = PlaneSpec(
    "jobs",
    "Jobs",
    icon="briefcase",
    description="Headless planes that run code: make them, boot them, restart them.",
    cells=(("jobs", TABLE), ("new", NEW), ("job", DETAIL)),
    group="System",
    web=WebOptions(editable=True, full_width=False),
    backend="async",
)
