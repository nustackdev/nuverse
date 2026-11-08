"""The export: a release of the system, built by a job in its own process.

Cutting a release (Export) makes a page for it and a headless ``mp`` job
under the page, its one cell :func:`job_source` with the spec as it stood
baked in. The job draws every asset (:func:`plan`): token files (CSS, JSON,
a changelog against the language), the mark as SVG, PNGs at every size
drawn with Pillow (:mod:`.raster`), and a favicon. File by file, each lands
in the job's state as bytes with a line in its index, so the release page
fills in as they come. Done, it adds the release to the Design plane's list.

Restarted after it finished, it ends at once: a release is cut once.
"""

from __future__ import annotations

import json
import re
from typing import Any

import nu
import nuspace
import nuspace.specs
import nuspace.system.supervisor
import nustd.kv
from nuspace import Space

from .. import bases
from . import logo, raster
from . import spec as specs
from .draw import tokens_css


__all__ = [
    "JOB",
    "PAGE",
    "Build",
    "Made",
    "build_at",
    "build_source",
    "cut",
    "export_of",
    "job_cell",
    "job_of",
    "make",
    "plan",
    "release_page",
]


#: The spec names of a release page and of its job.
PAGE, JOB = "design_release", "design_build"

#: How many of a Design plane's first children are looked at for its Export page.
_FIRST = 16


class Build(nu.Shape):
    """A release's build, on its job's one cell."""

    version = nustd.kv.StrRef.slot()
    # building, done.
    status = nustd.kv.StrRef.slot()
    done = nustd.kv.IntRef.slot()
    total = nustd.kv.IntRef.slot()
    started = nustd.kv.FloatRef.slot()
    finished = nustd.kv.FloatRef.slot()
    current = nustd.kv.StrRef.slot()
    # One line per file written: ``{key, name, kind, size, bytes, ms}``. The bytes are in ``blobs`` by key.
    index = nustd.kv.PrimitiveListRef.slot()
    blobs = nustd.kv.DictRef.slot(bytes)


class Made(nu.Shape):
    """A release page's, in its plane's state: its job."""

    job = nustd.kv.StrRef.slot()


def job_of(page: nu.StrArg) -> nu.Str:
    """A release page's job, ``""`` while it has none. Bare read."""
    return nu.Str(nuspace.at.plane(id=page).state(Made).job.fallback(""))


def job_cell(job: nu.StrArg) -> nu.Str:
    """The job's one cell, NULL for a job with none. Bare read: one seek."""
    return nu.Str(Space.planes[job].cells.first())


def build_at(job: nu.StrArg) -> Build:
    """A release's build, at its job's cell, typed as :class:`Build`."""
    return nuspace.at.cell(id=job_cell(job)).state(Build)


def export_of(base: nu.StrArg) -> nu.Str:
    """The Export page under a Design plane, ``""`` when it has none. Bare read.

    One page of the plane's first children: the spec makes Export among them.
    """
    first = nu.List(Space.planes[base].children.keys(limit=_FIRST))
    found = first.iter().filter(
        lambda p: Space.planes[nu.Str(p)].spec.fallback("") == "design_export"
    )
    return nu.str(found.first(default=""))


@nu.host
def _slug(version: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", version.lower()).strip("-") or "next"


def release_page(base: nu.StrArg, version: nu.StrArg) -> nu.Str:
    """A release page's id, as the Design plane keeps it by version, ``""`` for one not cut. Bare read."""
    from .kit import system

    return nu.Str(system(base).release_planes[_slug(version)].fallback(""))


def cut(base: nu.StrArg, export: nu.StrArg, version: nu.StrArg, spec: nu.Nu) -> nu.Nu:
    """A release: its page under Export, and its job under the page, supervised so it starts now.

    ``spec`` is read once and baked into the job's cell. A version already
    cut is left alone. A row of commits: the page with its cells and web
    row, its meta, the job and its cell (it draws nothing), then the ids kept
    (the page on the Design plane, the job on the page, the Design plane on
    both, :mod:`nudemos.bases`) and the job supervised.
    """
    from .cells import RELEASE
    from .kit import system

    page_spec = nuspace.specs.PlaneSpec(
        PAGE,
        "Release",
        icon="tag",
        cells=RELEASE,
        web=nuspace.specs.WebOptions(editable=True, full_width=True, compact=True),
        backend="async",
    )
    held = system(base).release_planes[_slug(version)]
    source = build_source(version, spec)

    def made(page: nu.ObjectRef, job: nu.ObjectRef) -> nu.Nu:
        p, j = nu.Str(page), nu.Str(job)
        meta = nu.Dict.of(version=version)
        add = nuspace.plane.add(
            parent=p, name="build", backend="mp", spec=JOB, into=job
        ) >> nuspace.cell.add(j, source, name="build", fabrics=[])
        ids = nuspace.at.plane(id=p).state(Made)
        policy = nuspace.system.supervisor.ON_FAILURE
        kept = (
            held.set(p)
            >> ids.job.set(j)
            >> bases.belongs(p, base)
            >> bases.belongs(j, base)
            >> nuspace.system.supervisor.supervise(j, policy=policy, exists_ok=True)
        )
        return (
            nuspace.specs.add_plane(page_spec, parent=export, name=version, into=page)
            >> nuspace.atomic(nuspace.plane.set_meta(p, meta) >> add)
            >> nuspace.atomic(kept)
        )

    fresh = nu.Bool(nuspace.atomic(held.exists())).not_()
    return nu.IfDo(fresh, nu.let("", lambda p: nu.let("", lambda j: made(p, j))))


# --- the files ----------------------------------------------------------------------------------


#: PNG sizes per asset.
SIZES = {
    "square": (16, 32, 48, 64, 128, 256, 512, 1024),
    "circle": (64, 128, 256, 512),
    "full-bleed": (256, 512, 1024),
    "text-only": (32, 64, 128, 256),
}


def plan(spec: dict[str, str]) -> list[dict[str, Any]]:
    """Every file a release writes, in order: ``{key, name, kind, asset, size}``."""
    items: list[dict[str, Any]] = [
        {"name": "tokens.css", "kind": "css"},
        {"name": "tokens.json", "kind": "json"},
        {"name": "CHANGES.md", "kind": "md"},
    ]
    for a in logo.ASSETS:
        items.append({"name": f"nu-{a}.svg", "kind": "svg", "asset": a})
    items.append({"name": "nu-square-small.svg", "kind": "svg", "asset": "square", "small": True})
    items.append(
        {"name": "nustack-lockup-dusk.svg", "kind": "svg", "asset": "lockup", "theme": "dusk"}
    )
    items.append(
        {"name": "nustack-lockup-dawn.svg", "kind": "svg", "asset": "lockup", "theme": "dawn"}
    )
    for a, sizes in SIZES.items():
        for s in sizes:
            items.append({"name": f"nu-{a}-{s}.png", "kind": "png", "asset": a, "size": s})
    items.append({"name": "favicon.ico", "kind": "ico"})
    for i, it in enumerate(items):
        it["key"] = f"f{i:02d}"
    return items


def _json(spec: dict[str, str]) -> str:
    out: dict[str, Any] = {t: {} for t in specs.THEMES}
    for _, tok, *_ in specs.COLORS:
        for t in specs.THEMES:
            out[t][tok] = spec[f"{t}:{tok}"]
    for g, k, *_ in specs.SCALARS:
        out.setdefault(g, {})[k.split(".", 1)[1]] = spec[k]
    return json.dumps(out, indent=2) + "\n"


def _changes(spec: dict[str, str], version: str) -> str:
    diff = {
        k: v for k, v in spec.items() if v != specs.DEFAULTS.get(k) and not k.startswith("knob.")
    }
    lines = [
        f"# {version}",
        "",
        f"{len(diff)} tokens differ from the language." if diff else "As the language ships it.",
        "",
    ]
    lines += [f"- `{k}`: {specs.DEFAULTS[k]} -> {v}" for k, v in sorted(diff.items())]
    return "\n".join(lines) + "\n"


def make(spec: dict[str, str], item: dict[str, Any], version: str = "") -> bytes:
    """One file's bytes."""
    kind = item["kind"]
    if kind == "css":
        head = f"/* nustack design tokens {version}. Dawn on :root, Dusk under prefers-color-scheme: dark. */\n"
        return (
            head
            + tokens_css(spec, "auto")
            .replace(";", ";\n  ")
            .replace("{", " {\n  ")
            .replace("}", "\n}\n")
        ).encode()
    if kind == "json":
        return _json(spec).encode()
    if kind == "md":
        return _changes(spec, version).encode()
    if kind == "svg":
        if item["asset"] == "lockup":
            ink = specs.theme(spec, item["theme"])["ink-1"]
            return logo.lockup(spec, ink).encode()
        return logo.asset(spec, item["asset"], small=bool(item.get("small"))).encode()
    if kind == "png":
        return raster.png(spec, item["asset"], int(item["size"]))
    if kind == "ico":
        return raster.favicon(spec)
    raise ValueError(f"no such kind: {kind}")


# --- the job ---------------------------------------------------------------------------------------


BUILD = """\
import nu
import nuspace
import nustd.time
from nudemos.design import job
from nudemos.design.job import Build
from nudemos.design.kit import root_of, system

#: This release's build: the job's own cell's state.
BUILT = nuspace.here(Build)

#: This release: its version and the spec it was cut from, baked in when it was cut.
VERSION = ""
SPEC = {}


@nu.host
def files():
    return job.plan(SPEC)


@nu.host
def count():
    return len(job.plan(SPEC))


@nu.host
def made(item):
    import time
    t = time.perf_counter()
    blob = job.make(SPEC, item, VERSION)
    return {"blob": blob, "line": {**item, "bytes": len(blob), "ms": round((time.perf_counter() - t) * 1000)}}


@nu.host
def added(index, line):
    return [*list(index or []), line]


@nu.host
def release(releases, page, index, now):
    keep = [r for r in list(releases or []) if r.get("page") != page]
    total = sum(f["bytes"] for f in index or [])
    return [*keep, {"version": VERSION, "page": page, "at": now, "files": len(index or []), "bytes": total, "spec": SPEC}]


def one(item):
    def land(m):
        return nuspace.atomic(
            BUILT.blobs[nu.Str(item["key"])].set(m["blob"])
            >> BUILT.index.set(added(BUILT.index.fallback([]), m["line"]))
            >> BUILT.done.set(BUILT.done.fallback(0) + 1)
            >> BUILT.current.set(item["name"])
        )

    return nu.let(made(item), land)


def out(plane):
    page = nuspace.atomic(nuspace.Space.planes[plane].parent)
    fresh = nuspace.atomic(
        BUILT.version.set(VERSION) >> BUILT.status.set("building") >> BUILT.done.set(0)
        >> BUILT.index.set([]) >> BUILT.total.set(count()) >> BUILT.started.set(nustd.time.time())
    )

    def finish(root):
        ended = nuspace.atomic(BUILT.status.set("done") >> BUILT.finished.set(nustd.time.time()) >> BUILT.current.set(""))
        index = nuspace.atomic(BUILT.index.fallback([]))
        releases = system(root).releases
        return ended >> nuspace.atomic(releases.set(release(releases.fallback([]), page, index, nustd.time.time())))

    work = fresh >> nu.ForEachDo(nu.List(files()), one) >> nu.let(nuspace.atomic(root_of(page)), lambda r: finish(nu.Str(r)))
    return nu.IfDo(nuspace.atomic(BUILT.status.fallback("") == "done"), nu.Noop(), work)
"""


def job_source(version: str, spec: dict[str, str]) -> str:
    """:data:`BUILD` with the version and the spec baked in."""
    return BUILD.replace('VERSION = ""', f"VERSION = {version!r}").replace(
        "SPEC = {}", f"SPEC = {dict(spec)!r}"
    )


#: :func:`job_source` as a term, for the cell that cuts releases.
build_source = nu.host(job_source, name="BuildSource")
