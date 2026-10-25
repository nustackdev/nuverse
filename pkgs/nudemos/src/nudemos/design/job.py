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
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import snap

from . import logo, raster
from . import spec as specs
from .draw import tokens_css


__all__ = [
    "JOB",
    "PAGE",
    "Build",
    "build_source",
    "cut",
    "export_of",
    "job_cell",
    "job_of",
    "make",
    "plan",
    "release_page",
]


#: ``made_by`` of a release page and of its job.
PAGE, JOB = "design_release", "design_build"


class Build(nuspace.CellState):
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


def job_of(page: nu.StrArg) -> nu.Str:
    """A release page's job: fixed under the page."""
    return nu.Str(page) + ".build"


def job_cell(job: nu.StrArg) -> nu.Str:
    """The job's one cell."""
    return nu.Str(job) + "_main"


def made_by(plane: nu.StrArg) -> nu.Str:
    return Space.planes[plane].props.made_by.fallback("")


def export_of(base: nu.StrArg) -> nu.Str:
    """The Export page under a Design plane, ``""`` when it has none. Bare read."""
    found = ops.children(base).iter().filter(lambda p: made_by(nu.Str(p)) == "design_export")
    return nu.str(nu.First(found)).fallback("")


@nu.host
def _slug(version: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", version.lower()).strip("-") or "next"


def release_page(base: nu.StrArg, version: nu.StrArg) -> nu.Str:
    """A release page's id: the Design plane's, then the version."""
    return nu.Str(base) + ".release." + _slug(version)


def cut(base: nu.StrArg, export: nu.StrArg, version: nu.StrArg, spec: nu.Nu) -> nu.Nu:
    """A release: its page under Export, and its job under the page, supervised so it starts now.

    ``spec`` is read once and baked into the job's cell. A version already cut is left alone.
    """
    from nuspace import PlaneSpec

    from .cells import RELEASE

    page = release_page(base, version)
    jb = job_of(page)
    meta = nu.Dict.of(
        base=base, version=version, icon="lucide:tag", full_width=True, editable=True, compact=True
    )
    make = (
        ops.create_plane(
            PlaneSpec(PAGE, "Release", cells=RELEASE, backend="async"),
            parent=export,
            name=version,
            plane_id=page,
        )
        >> ops.set_plane_meta(page, meta)
        >> ops.add_plane(
            jb,
            backend="mp",
            name="build",
            parent=page,
            ui=False,
            made_by=JOB,
            meta=nu.Dict.of(base=base),
        )
        >> ops.add_cell(jb, build_source(version, spec), cell_id=job_cell(jb), name="build")
        >> nuspace.supervise(jb)
    )
    return nu.IfDo(nu.Bool(snap(ops.plane_exists(page))).not_(), make)


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
import nustd.time
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.design import job
from nudemos.design.job import Build
from nudemos.design.kit import System, root_of

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
        return ops.atomic_state(
            Build.blobs[nu.Str(item["key"])].set(m["blob"])
            >> Build.index.set(added(Build.index.fallback([]), m["line"]))
            >> Build.done.set(Build.done.fallback(0) + 1)
            >> Build.current.set(item["name"])
        )

    return nu.let(made(item), land)


def out(plane):
    page = snap(ops.parent(plane))
    fresh = ops.atomic_state(
        Build.version.set(VERSION) >> Build.status.set("building") >> Build.done.set(0)
        >> Build.index.set([]) >> Build.total.set(count()) >> Build.started.set(nustd.time.time())
    )

    def finish(root):
        ended = ops.atomic_state(Build.status.set("done") >> Build.finished.set(nustd.time.time()) >> Build.current.set(""))
        index = snap(Build.index.fallback([]))
        return ended >> ops.atomic_state(ops.plane_state(root, System.releases.set(
            release(System.releases.fallback([]), page, index, nustd.time.time())
        )))

    work = fresh >> nu.ForEachDo(nu.List(files()), one) >> nu.let(snap(root_of(page)), lambda r: finish(nu.Str(r)))
    return nu.IfDo(snap(Build.status.fallback("") == "done"), nu.Noop(), work)
"""


def job_source(version: str, spec: dict[str, str]) -> str:
    """:data:`BUILD` with the version and the spec baked in."""
    return BUILD.replace('VERSION = ""', f"VERSION = {version!r}").replace(
        "SPEC = {}", f"SPEC = {dict(spec)!r}"
    )


#: :func:`job_source` as a term, for the cell that cuts releases.
build_source = nu.host(job_source, name="BuildSource")
