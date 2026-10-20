"""The base's two jobs, each a headless plane in its own process under the root.

- :data:`CHECKER`: the health checker. Reads every page and fact, flags what
  a careful editor would (stale pages, broken links, orphans, missing facts,
  late tasks), and writes it to :attr:`.kit.Base.health`. It checks when the
  base changes, and every :data:`EVERY` seconds when it does not, because
  pages go stale with time alone. What it newly finds goes in the activity log.
- :data:`IMPORTER`: reads a bundled export (an Obsidian-style vault of
  markdown with frontmatter) and writes it into the base note by note, each
  a page of its own, its links resolved into what is already there. The
  notes land in one commit, then their pages stream in one by one.

The plain-Python halves (:func:`check`, :func:`plan`, :func:`step`) are
tested on their own; the cells are short Nu loops over them.
"""

from __future__ import annotations

import time
from typing import Any

import nu

from . import seed, text


__all__ = ["CHECKER", "EVERY", "IMPORTER", "check", "checked", "plan", "planned", "step", "stepped"]


#: Seconds between two checks when nothing changes.
EVERY = 20.0


def check(docs: dict, facts: dict, before: dict, now: float, took: float = 0.0) -> dict[str, Any]:
    """A check of the base: the new health, and the events for what it newly flags."""
    h = text.health(docs or {}, facts or {}, now)
    was = {s["doc"] for s in (before or {}).get("stale", [])}
    events = []
    if before:
        for s in h["stale"]:
            if s["doc"] not in was:
                events.append(
                    {"t": now, "who": "checker", "what": "flagged as stale", "doc": s["doc"]}
                )
        for s in was - {s["doc"] for s in h["stale"]}:
            events.append({"t": now, "who": "checker", "what": "cleared, fresh again", "doc": s})
        was_broken = {(b["doc"], b["to"]) for b in before.get("broken", [])}
        for b in h["broken"]:
            if (b["doc"], b["to"]) not in was_broken:
                events.append(
                    {
                        "t": now,
                        "who": "checker",
                        "what": f"found a broken link to {b['to']}",
                        "doc": b["doc"],
                    }
                )
    runs = int((before or {}).get("runs", 0)) + 1
    history = [*(before or {}).get("history", []), [round(now), h["score"]]][-60:]
    h.update(checked_at=now, runs=runs, took_ms=round(took * 1000, 1), history=history)
    return {"health": h, "events": events}


@nu.host
def checked(read: dict) -> dict[str, Any]:
    """:func:`check` over what the job read, timed."""
    t0 = time.perf_counter()
    r = check(
        read.get("docs") or {}, read.get("facts") or {}, read.get("health") or {}, time.time()
    )
    r["health"]["took_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return r


@nu.host
def logged(log: list, events: list) -> list:
    """``events`` onto the activity log, newest first."""
    return [*reversed(events or []), *(log or [])][:200]


CHECKER = """\
import nu
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.knowledge import kit
from nudemos.knowledge.kit import Base
from nudemos.knowledge.jobs import EVERY, checked, logged


def out(plane):
    def run(base):
        at = lambda term: ops.plane_state(base, term)
        read = at(nu.Dict.of(docs=Base.docs.extract(), facts=Base.facts.extract(), health=Base.health.fallback({})))

        def write(r):
            r = nu.Dict(r)
            return ops.atomic_state(at(Base.health.set(r["health"]) >> nu.IfDo(
                nu.List(r["events"]).len() > 0, Base.log.set(logged(Base.log.fallback([]), r["events"]))
            )))

        # A check now, then on every change to the pages or the facts, and every EVERY seconds regardless.
        turn = nu.let(checked(snap(read)), write)
        changes = [at(Base.docs.on_change()), at(Base.facts.on_change())]
        return turn >> nu.ParallelAsync(*(nu.ReconcileReactive(snap(c), turn, every=EVERY) for c in changes))

    return nu.let(snap(kit.base_of(plane)), lambda b: run(nu.Str(b)))
"""


# --- the importer ---------------------------------------------------------------------------


def _n(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def plan(key: str, have: dict, now: float) -> dict[str, Any]:
    """What importing export ``key`` will do: its folder, and each note as a page, ``new`` or not."""
    label = seed.NAMES.get(key, key)
    folder = f"notes.{key}"
    notes = []
    for name, body in seed.export(key):
        slug, doc = seed.parse_note(name, body, now, folder, label)
        links = text.links_of(doc["body"])
        tasks = text.tasks_of(slug, doc)
        notes.append(
            {
                "slug": slug,
                "doc": doc,
                "name": name,
                "new": slug not in have,
                "said": f"{name}: {_n(len(links), 'link')}, {_n(len(tasks), 'task')}, {len(doc['body'].split())} words",
            }
        )
    return {
        "key": key,
        "label": label,
        "folder": folder,
        "short": label.split(" (")[0],
        "notes": notes,
    }


@nu.host
def planned(key: str, have: dict) -> dict[str, Any]:
    """:func:`plan`, dated now."""
    return plan(key or "lab-notebook", have or {}, time.time())


def step(
    progress: dict, note: dict | None, total: int, now: float, label: str = ""
) -> dict[str, Any]:
    """The importer's progress after one note (or at the start, with none, and at the end)."""
    p = dict(progress or {})
    lines = list(p.get("lines") or [])
    if note is None and p.get("status") != "importing":
        p.update(status="importing", done=0, total=total, label=label, started=now, lines=[])
        return p
    if note is None:
        p.update(status="done", finished=now, current="")
        return p
    lines.append(("Imported " if note["new"] else "Already here, kept: ") + note["said"])
    p.update(done=int(p.get("done", 0)) + 1, current=note["doc"]["title"], lines=lines[-40:])
    return p


@nu.host
def stepped(progress: dict, note: dict | None, total: int, label: str = "") -> dict[str, Any]:
    """:func:`step`, now."""
    return step(progress, note, total, time.time(), label)


IMPORTER = """\
import nu
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.knowledge import kit
from nudemos.knowledge.kit import Base
from nudemos.knowledge.jobs import planned, stepped

#: Seconds between two notes: slow enough to watch the base grow.
PACE = 0.3


def out(plane):
    def run(base):
        at = lambda term: ops.plane_state(base, term)
        read = at(nu.Dict.of(key=nu.str(Base.imports["key"]).fallback(""), have=Base.docs.extract()))

        def go(p):
            p = nu.Dict(p)
            total = nu.List(p["notes"]).len()
            # Every note lands in one commit, so the notebook's own links resolve at once and the
            # checker never sees half a notebook. The pages then stream in, one every PACE.
            notes = nu.ForEachDo(nu.List(p["notes"]), lambda n: nu.IfDo(
                nu.Bool(nu.Dict(n)["new"]), Base.docs[nu.Str(nu.Dict(n)["slug"])].set(nu.Dict(n)["doc"])
            ))
            begin = ops.atomic_state(at(notes >> Base.imports.set(stepped(Base.imports.fallback({}), None, total, p["label"]))))
            folder = kit.collection_page(base, p["folder"], p["short"], "notes")

            def one(n):
                n = nu.Dict(n)
                slug = nu.Str(n["slug"])
                progress = Base.imports.set(stepped(Base.imports.fallback({}), n, total))
                row = nu.Dict.of(slug=slug, title=nu.Dict(n["doc"])["title"], kind="note", folder=p["folder"])
                return nu.Delay(PACE) >> ops.atomic_state(at(progress)) >> kit._any_doc_page(base, row)

            said = nu.Str("imported ") + nu.ToStr(total) + " notes from " + nu.Str(p["short"])
            end = ops.atomic_state(at(Base.imports.set(stepped(Base.imports.fallback({}), None, total)) >> kit.log("importer", said, "")))
            return begin >> folder >> nu.ForEachDo(nu.List(p["notes"]), one) >> end

        return nu.let(snap(read), lambda r: nu.let(planned(nu.Dict(r)["key"], nu.Dict(r)["have"]), go))

    return nu.let(snap(kit.base_of(plane)), lambda b: run(nu.Str(b)))
"""
