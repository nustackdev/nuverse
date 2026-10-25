"""What every desk cell shares: the store, where pages live, how pages and runs are made.

- :class:`Desk`: the one store, in the desk plane's state. Sources, claims,
  the evidence linking them, models, eval runs with their answers, the
  probe's answers, the notebook. Every page reads and writes it there, so a
  piece of evidence added on a source page moves the claim, the board, the
  week's digest and the notebook at once.
- :func:`on_desk`: a cell's body with :class:`Desk` landed at its desk,
  wherever in the tree the cell's page sits. A page knows its desk from its
  own meta, written when it was made.
- Page ids are the desk's id plus a path (``<base>.src.kaplan2020``), so any
  cell links any page without looking anything up.
- :func:`seed`, :func:`add_source`, :func:`add_claim`, :func:`launch_run`:
  cells writing planes. A run is a page and a headless job under it, the job
  asking Claude in its own process (:mod:`.job`).

The reading of the store, scores and digests, is plain Python in :mod:`.views`.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.kv
import nustd.time
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import snap

from . import views


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "ROOT",
    "Desk",
    "add_claim",
    "add_evidence",
    "add_source",
    "base_of",
    "changes",
    "claim_page",
    "folder_page",
    "go",
    "launch_run",
    "merged",
    "on_desk",
    "on_page",
    "patch",
    "run_page",
    "seed",
    "set_status",
    "source_page",
    "whole",
]


#: The root Plane's name. Pages it makes are ``research_source``, ``research_claim`` and so on.
ROOT = "research"

#: ``made_by`` of a run's job, and of the probe's.
RUN_JOB, PROBE_JOB = "research_run_job", "research_probe_job"


class Desk(nuspace.PlaneState):
    """The desk's store. Values are plain dicts (see :mod:`.data` for their fields)."""

    sources = nustd.kv.DictRef.slot(dict)
    claims = nustd.kv.DictRef.slot(dict)
    evidence = nustd.kv.DictRef.slot(dict)
    models = nustd.kv.DictRef.slot(dict)
    # A run: {key, model, style, context, status, at, done_at, answers: {qid: answer}, by}.
    runs = nustd.kv.DictRef.slot(dict)
    # The probe's answers, newest last, and what steers it.
    probes = nustd.kv.ListRef.slot(dict)
    probe = nustd.kv.ObjectRef.slot()
    paused = nustd.kv.BoolRef.slot()
    asked = nustd.kv.IntRef.slot()
    notebook = nustd.kv.ListRef.slot(dict)
    seeded = nustd.kv.BoolRef.slot()


# --- where things are -----------------------------------------------------------------------


def base_of(plane: nu.StrArg) -> nu.Str:
    """The desk a page belongs to: its meta's ``base``, or the plane itself at the root."""
    return nu.str(Space.planes[plane].meta["base"]).fallback(plane)


def about(plane: nu.StrArg) -> nu.Str:
    """What a page is about, from its meta: a source's, a claim's or a run's key."""
    return nu.str(Space.planes[plane].meta["subject"]).fallback("")


def on_desk(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(base)`` with :class:`Desk` landed at the desk, bracketed step by step."""

    def landed(base: nu.ObjectRef) -> nu.Nu:
        b = nu.Str(base)
        return ops.bracketed(ops.plane_state(b, build(b)))

    return nu.let(snap(base_of(plane)), landed)


def on_page(plane: str, build: Callable[[nu.Str, nu.Str], nu.Nu]) -> nu.Nu:
    """``build(base, subject)`` on an item page, as :func:`on_desk`."""
    return nu.let(snap(about(plane)), lambda s: on_desk(plane, lambda b: build(b, nu.Str(s))))


def source_page(base: nu.StrArg, key: nu.StrArg) -> nu.Str:
    """A source page's plane id."""
    return nu.Str(base) + ".src." + key


def claim_page(base: nu.StrArg, key: nu.StrArg) -> nu.Str:
    """A claim page's plane id."""
    return nu.Str(base) + ".claim." + key


def run_page(base: nu.StrArg, key: nu.StrArg) -> nu.Str:
    """A run page's plane id."""
    return nu.Str(base) + ".run." + key


def folder_page(base: nu.StrArg, name: str) -> nu.Str:
    """A section's plane id: ``reading``, ``claims``, ``models``, ``evals``, ``watch``, ``notebook``."""
    return nu.Str(base) + "." + name


# --- reading the desk ------------------------------------------------------------------------


def whole() -> nu.Dict:
    """The whole desk as one dict of plain values, for a view that reads across it."""
    return nu.Dict.of(
        sources=Desk.sources.extract(),
        claims=Desk.claims.extract(),
        evidence=Desk.evidence.extract(),
        models=Desk.models.extract(),
        runs=Desk.runs.extract(),
        probes=Desk.probes.extract(),
        probe=Desk.probe.fallback({}),
        notebook=Desk.notebook.extract(),
    )


def changes(*names: str) -> list[nu.Nu]:
    """The subscriptions a view follows: every part of the desk, or the ``names`` given."""
    every = ("sources", "claims", "evidence", "models", "runs", "probes", "probe", "notebook")
    return [getattr(Desk, n).on_change() for n in names or every]


@nu.host
def merged(value: dict | None, fields: dict) -> dict:
    """``value`` with ``fields`` written over it."""
    return {**(value or {}), **fields}


def patch(ref: nu.Nu, fields: nu.Nu) -> nu.Nu:
    """Write ``fields`` over the dict at ``ref``, in the commit that reads it."""
    return ops.atomic_state(ref.set(merged(ref.fallback({}), fields)))


def go(nav: nu.Nu, uri: nu.StrArg) -> nu.Nu:
    """Navigate the shell to ``uri``: push it and one past it, and step back onto it."""
    return nu.let(uri, lambda u: nav.set(u) >> nav.set(nu.Str(u) + "?open") >> nav.back())


# --- making pages ---------------------------------------------------------------------------


def _page(
    pid: nu.Nu,
    base: nu.Nu,
    parent: nu.Nu,
    name: nu.Nu,
    kind: str,
    subject: nu.Nu,
    icon: nu.StrArg,
    cells: tuple[tuple[str, str], ...],
) -> nu.Nu:
    """A page under ``parent`` with its cells, made once: a page already there is left alone."""
    from nuspace import PlaneSpec

    spec = PlaneSpec(f"{ROOT}_{kind}", kind.title(), cells=tuple(cells), backend="async")
    meta = nu.Dict.of(base=base, icon=icon, editable=True, full_width=True, subject=subject)
    make = ops.create_plane(spec, parent=parent, name=name, plane_id=pid) >> ops.set_plane_meta(
        pid, meta
    )
    return nu.IfDo(nu.Bool(snap(ops.plane_exists(pid))).not_(), make)


#: A source page's icon by its status, and a claim page's by its standing.
SOURCE_ICONS = {
    "queued": "lucide:bookmark",
    "reading": "lucide:book-open",
    "read": "lucide:file-text",
}
CLAIM_ICONS = {"ok": "emoji:🟢", "info": "emoji:🔵", "warn": "emoji:🟠", "danger": "emoji:🔴"}

source_icon = nu.host(
    lambda status: SOURCE_ICONS.get(status, "lucide:file-text"), name="SourceIcon"
)


def _source_page(base: nu.Str, key: nu.Nu, title: nu.Nu, status: nu.Nu) -> nu.Nu:
    from .cells import SOURCE

    parent = folder_page(base, "reading")
    icon = source_icon(status)
    return _page(source_page(base, key), base, parent, title, "source", key, icon, SOURCE)


def set_status(base: nu.StrArg, key: nu.Nu, status: nu.Nu) -> nu.Nu:
    """A source's reading status, kept, and its page's icon to match. Inside :func:`on_desk`."""
    return patch(Desk.sources[key], nu.Dict.of(status=status)) >> ops.set_plane_meta(
        source_page(base, key), nu.Dict.of(icon=source_icon(status))
    )


def _claim_page(base: nu.Str, key: nu.Nu, label: nu.Nu, icon: nu.StrArg = "emoji:⚪") -> nu.Nu:
    from .cells import CLAIM

    parent = folder_page(base, "claims")
    return _page(claim_page(base, key), base, parent, label, "claim", key, icon, CLAIM)


def _run_page(base: nu.Str, key: nu.Nu, label: nu.Nu) -> nu.Nu:
    from .cells import RUN

    parent = folder_page(base, "evals")
    return _page(run_page(base, key), base, parent, label, "run", key, "lucide:chart-column", RUN)


def _keep(base: nu.Str, term: nu.Nu) -> nu.Nu:
    return ops.atomic_state(ops.plane_state(base, term))


def add_source(base: nu.Str, source: nu.Nu) -> nu.Nu:
    """``source`` (a dict, ``key`` and ``title`` at least) into the desk, and its page. Once per key."""

    def add(s: nu.ObjectRef) -> nu.Nu:
        src = nu.Dict(s)
        key = nu.Str(src["key"])
        kept = _keep(base, nu.IfDo(Desk.sources.contains(key).not_(), Desk.sources[key].set(src)))
        return kept >> _source_page(base, key, src["title"], src["status"])

    return nu.let(source, add)


def add_claim(base: nu.Str, claim: nu.Nu) -> nu.Nu:
    """``claim`` (a dict, ``key``, ``text`` and ``label``) into the desk, and its page. Once per key."""

    def add(c: nu.ObjectRef) -> nu.Nu:
        cl = nu.Dict(c)
        key = nu.Str(cl["key"])
        kept = _keep(base, nu.IfDo(Desk.claims.contains(key).not_(), Desk.claims[key].set(cl)))
        return kept >> _claim_page(base, key, cl["label"])

    return nu.let(claim, add)


def add_evidence(base: nu.Str, ev: nu.Nu) -> nu.Nu:
    """A piece of evidence (``source``, ``claim``, ``stance``, ``weight``, ``note``) into the desk."""
    return nu.let(ev, lambda e: _keep(base, Desk.evidence[nu.Str(nu.Dict(e)["key"])].set(e)))


opening = nu.host(views.opening, name="Opening")
run_title = nu.host(views.title_of_run, name="RunTitle")


@nu.host
def _due_pages(d: dict) -> dict[str, list]:
    """Every item the desk holds, as what its page needs: ``[key, title, status or icon]``."""
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"])
    return {
        "sources": [[k, s["title"], s.get("status", "queued")] for k, s in d["sources"].items()],
        "claims": [[k, c["label"], CLAIM_ICONS[sc[k]["tone"]]] for k, c in d["claims"].items()],
        "runs": [[k, views.title_of_run(r)] for k, r in d["runs"].items()],
    }


def seed(base: nu.Str) -> nu.Nu:
    """The desk made whole: its opening content once, then every page it should have.

    The content goes in one commit, the first time, whichever tab gets there
    first: the flag is taken in the commit that writes it. Times in
    :mod:`.data` are days ago; they are made real here, against now.

    The pages are made on every open, each only if it is missing: a first
    open cut short (its tab closed while the pages were being made) is
    finished by the next.
    """
    from . import cells

    def section(name: str, label: str, icon: str, cs: tuple[tuple[str, str], ...]) -> nu.Nu:
        pid = folder_page(base, name)
        return _page(pid, base, base, label, "section", name, icon, cs)

    def store(o: nu.ObjectRef) -> nu.Nu:
        od = nu.Dict(o)
        return (
            Desk.sources.set(od["sources"])
            >> Desk.claims.set(od["claims"])
            >> Desk.evidence.set(od["evidence"])
            >> Desk.models.set(od["models"])
            >> Desk.runs.set(od["runs"])
            >> Desk.notebook.set(od["notebook"])
            >> Desk.probes.set(od["probes"])
            >> Desk.probe.set(od["probe"])
            >> Desk.paused.set(False)
            >> Desk.seeded.set(True)
        )

    content = _keep(base, nu.IfDo(Desk.seeded.missing(), nu.let(opening(nustd.time.time()), store)))

    def pages(due: nu.ObjectRef) -> nu.Nu:
        d = nu.Dict(due)

        def src(s: nu.Attr) -> nu.Nu:
            row = nu.List(s)
            return _source_page(base, nu.Str(row[0]), row[1], row[2])

        def claim(c: nu.Attr) -> nu.Nu:
            row = nu.List(c)
            return _claim_page(base, nu.Str(row[0]), row[1], row[2])

        def run(r: nu.Attr) -> nu.Nu:
            row = nu.List(r)
            return _run_page(base, nu.Str(row[0]), row[1])

        return (
            nu.ForEachDo(nu.List(d["sources"]), src)
            >> nu.ForEachDo(nu.List(d["claims"]), claim)
            >> nu.ForEachDo(nu.List(d["runs"]), run)
        )

    held = snap(ops.plane_state(base, _due_pages(whole())))
    return (
        content
        >> section("reading", "Reading list", "lucide:library", cells.READING)
        >> section("claims", "Claims", "lucide:list-checks", cells.CLAIMS)
        >> section("models", "Models", "lucide:boxes", cells.MODELS)
        >> section("evals", "Evals", "lucide:gauge", cells.EVALS)
        >> section("watch", "Watch", "lucide:activity", cells.WATCH)
        >> section("notebook", "Notebook", "lucide:notebook-pen", cells.NOTEBOOK)
        >> nu.let(held, pages)
        >> start_probe(base)
    )


# --- runs and the probe ---------------------------------------------------------------------


@nu.host
def new_run(model: str, style: str, context: str, by: str, n: int) -> dict[str, Any]:
    """A run as launched: queued, no answers yet, keyed by when and what."""
    return {
        "key": f"r{int(time.time()) % 10_000_000:07d}{'abcdefgh'[n % 8]}",
        "model": model,
        "style": style,
        "context": context,
        "status": "queued",
        "at": time.time(),
        "done_at": 0.0,
        "answers": {},
        "by": by,
    }


def launch_run(base: nu.Str, run: nu.Nu) -> nu.Nu:
    """A run into the desk, its page, and its job under the page, supervised: it starts now."""
    from .job import job_source

    source = nu.host(job_source, name="RunSource")

    def made(r: nu.ObjectRef, job: nu.ObjectRef) -> nu.Nu:
        rd = nu.Dict(r)
        key = nu.Str(rd["key"])
        page = run_page(base, key)
        return (
            _keep(base, Desk.runs[key].set(rd))
            >> _run_page(base, key, run_title(rd))
            >> ops.add_plane(
                backend="mp", name="job", parent=page, ui=False, made_by=RUN_JOB, into=job
            )
            >> ops.add_cell(
                nu.Str(job), source(base, rd), cell_id=nu.Str(job) + "_main", name="ask"
            )
            >> nuspace.supervise(nu.Str(job))
        )

    return nu.let(run, lambda r: nu.let("", lambda j: made(r, j)))


def start_probe(base: nu.Str) -> nu.Nu:
    """The probe: a headless job under Watch, put under the supervisor. Once per desk."""
    from .job import probe_source

    source = nu.host(probe_source, name="ProbeSource")
    pid = folder_page(base, "watch") + ".probe"
    make = ops.add_plane(
        pid, backend="mp", name="probe", parent=folder_page(base, "watch"), made_by=PROBE_JOB
    ) >> ops.add_cell(pid, source(base), cell_id=pid + "_main", name="probe")
    there = nu.Bool(snap(ops.plane_exists(pid)))
    return nu.IfDo(there.not_(), make) >> nuspace.supervise(pid)


# --- what is typed ---------------------------------------------------------------------------


def _tag(text: str) -> str:
    return hashlib.blake2b(text.encode(), digest_size=2).hexdigest()


@nu.host
def typed_source(title: str, authors: str, year: str, venue: str, arxiv: str, by: str) -> dict:
    """A source from the add form: an arXiv id like ``2501.12948`` gives the link."""
    title = title.strip()
    key = re.sub(r"[^a-z0-9]+", "", (authors.split()[0] if authors.strip() else title).lower())
    try:
        yr = int(year)
    except ValueError:
        yr = 0
    ident = arxiv.strip().removeprefix("arXiv:").removeprefix("https://arxiv.org/abs/")
    return {
        "tldr": "",
        "notes": "",
        "key": f"{key[:16]}{yr or ''}{_tag(title)}",
        "title": title,
        "authors": authors.strip() or "Unknown",
        "year": yr,
        "venue": venue.strip() or "arXiv",
        "arxiv": ident,
        "url": f"https://arxiv.org/abs/{ident}" if ident else "",
        "status": "queued",
        "at": time.time(),
        "by": by,
    }


@nu.host
def typed_claim(text: str, topic: str, by: str) -> dict:
    """A claim from the add form."""
    text = text.strip()
    words = re.sub(r"[^a-z0-9 ]+", "", text.lower()).split()
    return {
        "key": "c" + "".join(w[0] for w in words[:6]) + f"{_tag(text)}",
        "text": text,
        "label": views.short(text),
        "topic": topic.strip() or "Open",
        "at": time.time(),
        "by": by,
    }


@nu.host
def typed_evidence(source: str, claim: str, stance: str, weight: str, note: str, by: str) -> dict:
    """A piece of evidence from a source page's form."""
    try:
        w = max(1, min(3, int(float(weight))))
    except ValueError:
        w = 1
    return {
        "key": f"{source}:{claim}",
        "source": source,
        "claim": claim,
        "stance": "against" if stance == "against" else "for",
        "weight": w,
        "note": note.strip(),
        "at": time.time(),
        "by": by,
    }
