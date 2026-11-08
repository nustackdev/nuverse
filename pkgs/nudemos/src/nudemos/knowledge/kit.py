"""What every Larkspur cell shares: the one store, where pages live, how pages are made.

- :class:`Base`: the store, in the root plane's state. Every page, fact and
  event, so a fact changed on Facts shows in every page that cites it, and a
  task ticked on Home is ticked in the page it is written in.
- :func:`on_base`, :func:`on_doc`: a cell's body given the root and its
  :class:`Base` (:func:`base_at`), wherever in the tree the cell's page
  sits. A page knows its root from its own plane state, written when it was
  made (:mod:`nudemos.bases`): a removed root raises, never reads another.
- Plane ids are minted. The base keeps them (:class:`Planes`), docs by slug
  and folder and tool pages by name, so any cell links any page with one
  read; the jobs' ids too (``Base.jobs``).
- :func:`seed`, :func:`add_doc`, :func:`ensure_pages`: cells writing planes.
- :func:`start_checker`, :func:`start_import`: the two jobs, each a headless
  plane in its own process (:mod:`.jobs`).

Cells import this module, so their own sources (:mod:`.cells`) stay short.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nuspace.specs
import nuspace.system.supervisor
import nustd.kv
import nustd.time
from nuspace import Space

from .. import bases
from . import seed as seeding
from . import text
from .data import DOCS, FACTS, PEOPLE


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "ME",
    "NAMES",
    "ROOT",
    "VIEWS",
    "Base",
    "Doc",
    "Fact",
    "Planes",
    "about",
    "add_doc",
    "base_at",
    "base_of",
    "collection_page",
    "doc_href",
    "doc_page",
    "ensure_pages",
    "event",
    "folder_page",
    "job_of",
    "live",
    "log",
    "now",
    "on_base",
    "on_doc",
    "opening",
    "reviewed",
    "seed",
    "set_fact",
    "set_status",
    "start_checker",
    "start_import",
    "tick",
    "touched",
    "view_page",
]


#: The root Plane's name. Pages it makes are ``knowledge_doc``, ``knowledge_view`` and so on.
ROOT = "knowledge"

#: Who "you" are in this space: edits and ticks made here are hers.
ME = "ines"


class Doc(nu.Shape):
    """One page: what it says and what it is (kind, folder, owner, status), and when it moved."""

    title = nustd.kv.StrRef.slot()
    kind = nustd.kv.StrRef.slot()
    folder = nustd.kv.StrRef.slot()
    body = nustd.kv.StrRef.slot()
    owner = nustd.kv.StrRef.slot()
    editor = nustd.kv.StrRef.slot()
    tags = nustd.kv.ListRef.slot(str)
    status = nustd.kv.StrRef.slot()
    created = nustd.kv.FloatRef.slot()
    updated = nustd.kv.FloatRef.slot()
    date = nustd.kv.FloatRef.slot()
    source = nustd.kv.StrRef.slot()


class Fact(nu.Shape):
    """A fact defined once and cited anywhere as ``{{key}}``: its label, its value as shown, who owns it."""

    label = nustd.kv.StrRef.slot()
    value = nustd.kv.StrRef.slot()
    owner = nustd.kv.StrRef.slot()
    note = nustd.kv.StrRef.slot()
    updated = nustd.kv.FloatRef.slot()


class Planes(nu.Shape):
    """The ids of the planes the base made: doc pages by slug, folder and tool pages by name."""

    doc = nustd.kv.DictRef.slot(str)
    view = nustd.kv.DictRef.slot(str)


class Base(nu.Shape):
    """The base, in the root plane's state: pages by slug, facts by key, what happened, what the two jobs say.

    Also the ids of what it made: its planes (:class:`Planes`) and its jobs by name.
    """

    docs = nustd.kv.DictRef.slot(Doc)
    facts = nustd.kv.DictRef.slot(Fact)
    # Events, newest first: {t, who, what, doc}.
    log = nustd.kv.PrimitiveListRef.slot()
    # The checker's last word, and the importer's progress.
    health = nustd.kv.PrimitiveDictRef.slot()
    imports = nustd.kv.PrimitiveDictRef.slot()
    # Questions asked of the base and Claude's answers, newest first: {t, q, a, cost, secs}.
    asks = nustd.kv.PrimitiveListRef.slot()
    seeded = nustd.kv.BoolRef.slot()
    planes = nustd.kv.ShapeRef.slot(Planes)
    jobs = nustd.kv.DictRef.slot(str)


# --- where things are -----------------------------------------------------------------------


def base_of(plane: nu.StrArg) -> nu.Str:
    """The base a plane belongs to: itself at the root, else the one its page or job recorded.

    Raises:
        Missing: A plane that recorded none.
        Removed: The base it recorded is removed.
    """
    from . import PLANE

    return bases.base_of(plane, PLANE)


def about(plane: nu.StrArg) -> nu.Str:
    """The page's subject from its meta: a doc's slug, or a view's name."""
    return nu.str(Space.planes[plane].meta["subject"].fallback(""))


def base_at(base: nu.StrArg) -> Base:
    """The root ``base``'s :class:`Base`: its plane's state."""
    return nuspace.at.plane(id=base).state(Base)


def on_base(plane: str, build: Callable[[nu.Str, Base], nu.Nu]) -> nu.Nu:
    """``build(base, b)``: given the root and its :class:`Base`, bracketed step by step."""

    def landed(at: nu.ObjectRef) -> nu.Nu:
        base = nu.Str(at)
        return nuspace.bracketed(build(base, base_at(base)))

    return nu.let(nuspace.atomic(base_of(plane)), landed)


def on_doc(plane: str, build: Callable[[nu.Str, Base, nu.Str], nu.Nu]) -> nu.Nu:
    """``build(base, b, slug)`` on a doc page, as :func:`on_base`."""
    return nu.let(
        nuspace.atomic(about(plane)),
        lambda s: on_base(plane, lambda base, b: build(base, b, nu.Str(s))),
    )


def doc_page(b: Base, slug: nu.StrArg) -> nu.Str:
    """A doc page's plane id, ``""`` while it has none. Bare read."""
    return nu.Str(b.planes.doc[slug].fallback(""))


def folder_page(b: Base, name: nu.StrArg) -> nu.Str:
    """A folder or tool page's plane id (``handbook``, ``facts``, ``notes.lab-notebook``), ``""`` for none. Bare read."""
    return nu.Str(b.planes.view[name].fallback(""))


def doc_href(b: Base, slug: nu.StrArg) -> nu.Str:
    """A link to a doc page, for a cell to push or draw. Reads the base in its own snapshot."""
    import nuspace.devices.web

    return nuspace.devices.web.href(nuspace.atomic(doc_page(b, slug)))


# --- writing --------------------------------------------------------------------------------


@nu.host
def event(who: str, what: str, doc: str) -> dict[str, Any]:
    """One line of the activity log, stamped now."""
    return {"t": time.time(), "who": who, "what": what, "doc": doc}


@nu.host
def _logged(log: list, e: dict) -> list:
    return [e, *(log or [])][:200]


def log(b: Base, who: nu.StrArg, what: nu.StrArg, doc: nu.StrArg = "") -> nu.Nu:
    """An event onto ``b``'s log. Bare."""
    return b.log.set(_logged(b.log.fallback([]), event(who, what, doc)))


def now() -> nu.Float:
    """The time now, as a term: read again each time it is evaluated."""
    return nu.Float(nustd.time.time())


# --- what cells write -----------------------------------------------------------------------


@nu.host
def _task_at(key: str, body: str, done: bool) -> dict[str, Any]:
    """A task's page and line from its key, the page's body with it ticked, and what to log."""
    slug, _, line = str(key).rpartition(":")
    i = int(line or 0)
    lines = (body or "").split("\n")
    said = text.tasks_of(slug, {"body": body}) if 0 <= i < len(lines) else []
    task = next((t["text"] for t in said if t["line"] == i), "a task")
    return {
        "body": text.set_task(body or "", i, bool(done)),
        "what": ("ticked off " if done else "reopened ") + f"\u201c{task}\u201d",
    }


@nu.host
def _slug_of(key: str) -> str:
    return str(key).rpartition(":")[0]


def touched(b: Base, doc: nu.Nu, slug: nu.StrArg, what: nu.StrArg) -> nu.Nu:
    """A page of ``b`` marked edited by you now, and logged. Bare."""
    return doc.updated.set(now()) >> doc.editor.set(ME) >> log(b, ME, what, slug)


def tick(b: Base, key: nu.StrArg, done: nu.BoolArg) -> nu.Nu:
    """Tick (or untick) the task ``key`` (``slug:line``) in the page it is written in. Bare."""

    def at(s: nu.ObjectRef) -> nu.Nu:
        slug = nu.Str(s)
        doc = b.docs[slug]
        return nu.let(
            _task_at(key, doc.body.fallback(""), done),
            lambda r: doc.body.set(nu.Dict(r)["body"]) >> touched(b, doc, slug, nu.Dict(r)["what"]),
        )

    return nu.let(_slug_of(key), at)


def set_fact(b: Base, key: nu.StrArg, value: nu.StrArg) -> nu.Nu:
    """A fact's new value, logged. Every page citing it follows. Bare."""
    fact = b.facts[key]
    said = nu.Str("set ") + nu.Str(fact.label.fallback("")) + " to " + nu.Str(value)
    return fact.value.set(value) >> fact.updated.set(now()) >> log(b, ME, said, "")


def set_status(b: Base, slug: nu.StrArg, status: nu.StrArg) -> nu.Nu:
    """A decision's or project's status, logged. Bare."""
    doc = b.docs[slug]
    return doc.status.set(status) >> touched(b, doc, slug, nu.Str("marked ") + nu.Str(status))


def reviewed(b: Base, slugs: nu.Nu) -> nu.Nu:
    """Pages marked reviewed now: fresh again for another while. Bare."""
    return nu.ForEachDo(
        nu.List(slugs), lambda s: touched(b, b.docs[nu.Str(s)], nu.Str(s), "reviewed")
    )


# --- making pages ---------------------------------------------------------------------------


#: The icon of each kind of doc page.
ICONS = {
    "wiki": "lucide:file-text",
    "project": "lucide:kanban",
    "meeting": "lucide:calendar",
    "decision": "lucide:flag",
    "person": "lucide:user",
    "note": "lucide:notebook-pen",
}

#: The folder and tool pages, in the order they hang under the root: name, label, icon.
VIEWS = (
    ("handbook", "Handbook", "lucide:book-open"),
    ("projects", "Projects", "lucide:kanban"),
    ("meetings", "Meetings", "lucide:calendar"),
    ("decisions", "Decisions", "lucide:flag"),
    ("people", "People", "lucide:users"),
    ("notes", "My notes", "lucide:notebook-pen"),
    ("ask", "Ask Larkspur", "lucide:sparkles"),
    ("tasks", "Tasks", "lucide:list-checks"),
    ("facts", "Facts", "lucide:hash"),
    ("glossary", "Glossary", "lucide:library"),
    ("graph", "Graph", "lucide:network"),
    ("digest", "Weekly digest", "lucide:newspaper"),
    ("health", "Health", "lucide:activity"),
    ("import", "Import", "lucide:inbox"),
)


def _page(
    held: nu.Nu,
    base: nu.Nu,
    parent: nu.Nu,
    name: nu.Nu,
    kind: str,
    subject: nu.Nu,
    icon: nu.StrArg,
    cells: tuple[tuple[str, str], ...],
) -> nu.Nu:
    """A page under ``parent`` with its cells, made once: a page the base holds already is left alone.

    ``held`` is the base's slot for the page's id (eg ``b.planes.doc[slug]``).
    ``parent`` is read in a snapshot of its own first. Made in a row of
    commits: the plane with every cell and its web row
    (``nuspace.specs.add_plane``), then its meta and icon, then its id into
    ``held`` with its base recorded in its own state
    (:func:`nudemos.bases.belongs`).
    """
    spec = nuspace.specs.PlaneSpec(
        f"{ROOT}_{kind}",
        kind.title(),
        cells=tuple(cells),
        web=nuspace.specs.WebOptions(editable=True, full_width=True, compact=True),
        backend="async",
    )
    meta = nu.Dict.of(subject=subject)

    def make(made: nu.ObjectRef, under: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(made)
        return (
            nuspace.specs.add_plane(spec, parent=nu.Str(under), name=name, into=made)
            >> nuspace.atomic(
                nuspace.plane.set_meta(pid, meta) >> nuspace.plane.set_icon(pid, icon)
            )
            >> nuspace.atomic(held.set(pid) >> bases.belongs(pid, base))
        )

    new = nu.let("", lambda made: nu.let(nuspace.atomic(parent), lambda under: make(made, under)))
    return nu.IfDo(nu.Bool(nuspace.atomic(held.exists())).not_(), new)


def _doc_page(base: nu.Str, slug: nu.Nu, title: nu.Nu, kind: str, folder: nu.Nu) -> nu.Nu:
    from .cells import DOC_CELLS

    b = base_at(base)
    return _page(
        b.planes.doc[slug],
        base,
        b.planes.view[folder].fallback(base),
        title,
        "doc",
        slug,
        ICONS[kind],
        DOC_CELLS[kind],
    )


def _any_doc_page(base: nu.Str, p: nu.Nu) -> nu.Nu:
    """A doc page for ``p`` (``{slug, title, kind, folder}``), its cells picked by its kind."""
    p = nu.Dict(p)
    kind = nu.Str(p["kind"])
    pick = _doc_page(base, p["slug"], p["title"], "wiki", p["folder"])
    for k in ("project", "meeting", "decision", "person", "note"):
        pick = nu.IfDo(kind == k, _doc_page(base, p["slug"], p["title"], k, p["folder"]), pick)
    return pick


def view_page(base: nu.Str, name: str, label: str, icon: str, parent: nu.Nu | None = None) -> nu.Nu:
    """One of the folder or tool pages, under the root or ``parent``."""
    from .cells import VIEW_CELLS

    return _page(
        base_at(base).planes.view[name],
        base,
        parent if parent is not None else base,
        label,
        "view",
        name,
        icon,
        VIEW_CELLS[name],
    )


def collection_page(base: nu.Str, folder: nu.Nu, label: nu.Nu, parent: nu.Nu) -> nu.Nu:
    """A sub-folder of pages, eg an imported notebook under My notes."""
    from .cells import COLLECTION

    views = base_at(base).planes.view
    return _page(
        views[folder],
        base,
        views[parent].fallback(base),
        label,
        "view",
        folder,
        "lucide:folder",
        COLLECTION,
    )


@nu.host
def _pages(docs: dict) -> list[dict[str, str]]:
    """Every doc as ``{slug, title, kind, folder}``: meetings newest first, the rest as written."""
    rows = [
        {
            "slug": k,
            "title": d.get("title", k),
            "kind": d.get("kind", "wiki"),
            "folder": d.get("folder", "handbook"),
        }
        for k, d in docs.items()
    ]
    meetings = sorted(
        (r for r in rows if r["kind"] == "meeting"),
        key=lambda r: -(docs[r["slug"]].get("date") or 0),
    )
    return [r for r in rows if r["kind"] != "meeting"] + meetings


def ensure_pages(base: nu.Str) -> nu.Nu:
    """A page for every doc that has none yet. Pages there already are left alone."""
    docs = nuspace.atomic(base_at(base).docs.extract())
    return nu.let(
        _pages(docs), lambda rows: nu.ForEachDo(nu.List(rows), lambda p: _any_doc_page(base, p))
    )


def add_doc(base: nu.Str, slug: nu.Nu, doc: nu.Nu, what: nu.StrArg = "created") -> nu.Nu:
    """``doc`` into the base under ``slug``, logged, and its page. A slug already there keeps its page."""

    def add(s: nu.ObjectRef, d: nu.ObjectRef) -> nu.Nu:
        k, doc = nu.Str(s), nu.Dict(d)
        b = base_at(base)
        keep = nuspace.atomic(b.docs[k].set(doc) >> log(b, ME, what, k))
        row = nu.Dict.of(slug=k, title=doc["title"], kind=doc["kind"], folder=doc["folder"])
        return keep >> _any_doc_page(base, row)

    return nu.let(slug, lambda s: nu.let(doc, lambda d: add(s, d)))


@nu.host
def opening() -> dict[str, Any]:
    """The opening base, dated from now, and an activity log made from when its pages last moved."""
    t = time.time()
    docs, facts = seeding.base(DOCS, FACTS, t)
    recent = sorted(docs.items(), key=lambda kv: -kv[1]["updated"])[:40]
    events = [
        {"t": d["updated"], "who": d["editor"], "what": "edited", "doc": k} for k, d in recent
    ]
    return {"docs": docs, "facts": facts, "log": events}


def seed(base: nu.Str) -> nu.Nu:
    """The first run: the folders, the opening pages, then the checker. Once per base."""
    b = base_at(base)

    def write(o: nu.ObjectRef) -> nu.Nu:
        o = nu.Dict(o)
        docs = nu.ForEachDo(
            nu.list(nu.Dict(o["docs"]).items()),
            lambda kv: b.docs[nu.Str(nu.List(kv)[0])].set(nu.List(kv)[1]),
        )
        facts = nu.ForEachDo(
            nu.list(nu.Dict(o["facts"]).items()),
            lambda kv: b.facts[nu.Str(nu.List(kv)[0])].set(nu.List(kv)[1]),
        )
        return nuspace.atomic(docs >> facts >> b.log.set(o["log"]))

    def first(mine: nu.ObjectRef) -> nu.Nu:
        take = nu.IfDo(b.seeded.is_null(), b.seeded.set(True) >> mine.set(True))
        views = nu.Sequential(*(view_page(base, n, label, icon) for n, label, icon in VIEWS))
        # the root reads as the team's own wiki, not the category it is registered under
        named = nuspace.atomic(nuspace.plane.rename(base, "Larkspur"))
        build = (
            named >> views >> nu.let(opening(), write) >> ensure_pages(base) >> start_checker(base)
        )
        return nuspace.atomic(take) >> nu.IfDo(nu.Bool(mine), build)

    return nu.let(False, first)


# --- the jobs -------------------------------------------------------------------------------


def job_of(base: nu.StrArg, name: str) -> nu.Str:
    """A job's plane id, ``checker`` or ``importer``, ``""`` before it is made. Bare read."""
    return nu.Str(base_at(base).jobs[name].fallback(""))


def live(base: nu.StrArg, name: str) -> nu.Bool:
    """Whether a job has a run now, False before it is made. Bare read."""
    job = job_of(base, name)
    return nu.Bool(nu.If(job == "", False, nuspace.plane_run.any_live(job)))


def _job(base: nu.Str, name: str, source: nu.StrArg) -> nu.Nu:
    """A headless job plane in its own process, and its one cell, its id kept in the base.

    Made the first time (two commits: the plane and its cell, then the id
    with its base recorded in its own state), its cell's prog rewritten
    every time after. The cell draws nothing, so
    its fabrics are none.
    """
    held = base_at(base).jobs[name]

    def make(job: nu.ObjectRef) -> nu.Nu:
        plane = nuspace.plane.add(
            parent=base,
            name=name,
            backend="mp",
            spec=f"{ROOT}_{name}",
            into=job,
        )
        one = nuspace.cell.add(nu.Str(job), source, name=name, fabrics=[])
        kept = held.set(nu.Str(job)) >> bases.belongs(nu.Str(job), base)
        return nuspace.atomic(plane >> one) >> nuspace.atomic(kept)

    def again(job: nu.ObjectRef) -> nu.Nu:
        cell = Space.planes[nu.Str(job)].cells.first()
        return nuspace.atomic(nuspace.cell.set_prog(cell, source, fabrics=[]))

    return nu.let(
        nuspace.atomic(held.fallback("")),
        lambda job: nu.IfDo(nu.Str(job) == "", make(job), again(job)),
    )


def _supervised(base: nu.Str, name: str) -> nu.Nu:
    """The job put under the supervisor, restarted on a failure. Running again if its last run is over."""
    policy = nuspace.system.supervisor.ON_FAILURE
    return nu.let(
        nuspace.atomic(job_of(base, name)),
        lambda job: nuspace.atomic(
            nuspace.system.supervisor.supervise(nu.Str(job), policy=policy, exists_ok=True)
        ),
    )


def start_checker(base: nu.Str) -> nu.Nu:
    """The health checker: made once, kept up by the supervisor from then on."""
    from .jobs import CHECKER

    return _job(base, "checker", CHECKER) >> _supervised(base, "checker")


def start_import(base: nu.Str, key: nu.StrArg) -> nu.Nu:
    """Import the bundled export ``key``: its job written for it, then run once."""
    from .jobs import IMPORTER

    imports = base_at(base).imports
    progress = imports.set(nu.Dict.of(status="starting", key=key, done=0, total=0, lines=[]))
    return (
        nuspace.atomic(progress)
        >> _job(base, "importer", IMPORTER)
        >> _supervised(base, "importer")
    )


#: Names, for cells: slug to full name.
NAMES = {k: v[0] for k, v in PEOPLE.items()}
