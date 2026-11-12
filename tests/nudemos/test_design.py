"""The design demo's plain logic: the spec, its knobs, the checks, the history, the export's files."""

from __future__ import annotations

import io
import json

import pytest

from nudemos.design import checks, color, job, kit, logo, studio
from nudemos.design import spec as specs


def test_defaults_round_trip_through_oklch():
    for key, value in specs.DEFAULTS.items():
        if value.startswith("#"):
            assert color.hexof(*color.oklch(value)) == value, key


def test_the_language_passes_its_own_checks():
    s = checks.summary(specs.merged({}))
    assert s["fail"] == 0
    assert s["pass"] + s["under"] == s["total"]


def test_a_knob_turns_hue_and_keeps_lightness():
    writes = specs.apply_knob({}, "knob.afterglow", 320)
    assert writes["knob.afterglow"] == "320"
    before = color.oklch(specs.DEFAULTS["dusk:afterglow"])
    after = color.oklch(writes["dusk:afterglow"])
    assert after[0] == pytest.approx(before[0], abs=0.01)
    assert after[2] == pytest.approx(320, abs=2)
    assert "mark.from" in writes and "dawn:ink-1" not in writes


def test_tint_zero_makes_the_sky_neutral():
    writes = specs.apply_knob({}, "knob.tint", 0)
    assert color.oklch(writes["dusk:ground"])[1] < 0.003


def test_a_bright_afterglow_fails_white_labels():
    proposal = studio.POOL[0][3]
    assert studio.verdict(specs.merged({}), proposal).endswith("fails")
    rows = {r["key"]: r for r in checks.run({**specs.merged({}), **proposal})["pairs"]}
    assert rows["on-afterglow on afterglow"]["verdict"] == "fail"


def test_a_five_pixel_grid_breaks_the_rule():
    rules = {
        r["key"]: r["ok"] for r in checks.run({**specs.merged({}), "space.unit": "5"})["rules"]
    }
    assert rules["grid is 4px"] is False


def test_edits_drop_defaults_and_refuse_bad_hex():
    stored = kit._applied({}, {"radius.md": "8", "dusk:ground": "not a color"})
    assert stored == {"radius.md": "8"}
    assert kit._applied(stored, {"radius.md": "6"}) == {}


def test_history_merges_a_drag_into_one_line():
    log = kit._logged([], {}, {"radius.md": "7"}, "you", "Rounded", 100.0)
    log = kit._logged(log, {"radius.md": "7"}, {"radius.md": "9"}, "you", "Rounded", 102.0)
    assert len(log) == 1
    assert log[0]["changes"]["radius.md"] == ["6", "9"]
    log = kit._logged(log, {"radius.md": "9"}, {"radius.md": "10"}, "you", "Rounded", 200.0)
    assert len(log) == 2


def test_ago_reads_like_a_person():
    assert kit.ago(1000.0, 1005.0) == "just now"
    assert kit.ago(0.0, 3 * 86400.0) == "3 days ago"


def test_variants_are_six_and_differ():
    vs = logo.variants(specs.merged({}))
    assert len(vs) == 6
    assert all(v["mark.from"] != specs.DEFAULTS["mark.from"] for v in vs[:4])


def test_a_release_plans_every_file_once():
    names = [f["name"] for f in job.plan(specs.merged({}))]
    assert len(names) == len(set(names))
    assert {"tokens.css", "tokens.json", "favicon.ico", "nu-square-1024.png"} <= set(names)


def test_release_files_are_what_they_say():
    from PIL import Image

    sp = specs.merged({"radius.md": "8"})
    plan = {f["name"]: f for f in job.plan(sp)}
    tokens = json.loads(job.make(sp, plan["tokens.json"]))
    assert tokens["dusk"]["afterglow"] == "#8946db" and tokens["radius"]["md"] == "8"
    assert b"--r-md:8px" in job.make(sp, plan["tokens.css"])
    assert job.make(sp, plan["nu-square.svg"]).startswith(b"<svg")
    png = Image.open(io.BytesIO(job.make(sp, plan["nu-square-32.png"])))
    assert png.size == (32, 32) and png.mode == "RGBA"
    assert b"radius.md" in job.make(sp, plan["CHANGES.md"])


# --- on a store --------------------------------------------------------------------------------


def _sources() -> dict[str, str]:
    """Every cell source the design demo writes: its planes', a release page's, the studio's, a build's."""
    from nudemos.design import PLANE, cells

    def walk(spec):
        yield from ((f"{spec.name}.{name}", source) for name, source in spec.cells)
        for child in spec.children:
            yield from walk(child)

    found = dict(walk(PLANE))
    found.update({f"release.{name}": source for name, source in cells.RELEASE})
    found["studio"] = studio.STUDIO
    found["build"] = job.job_source("v1.0.0", specs.DEFAULTS)
    return found


SOURCES = _sources()


@pytest.mark.parametrize("name", list(SOURCES))
async def test_every_cell_loads(store, name):
    import nu
    import nuspace
    from nuspace import Space

    await store.do(nuspace.plane.add("p", backend="async"))
    await store.do(nuspace.cell.add("p", SOURCES[name], id="c"))
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"})
    nu.validate(nu.compile(await store.run(nuspace.atomic(load))))


async def _design(store) -> None:
    import nuspace.specs
    from nudemos.design import PLANE

    await store.run(nuspace.specs.add_plane(PLANE, "d"))


async def test_every_page_finds_its_design_plane(store):
    import nu
    from nuspace import Space

    await _design(store)
    tokens = (await store.read(nu.list(Space.planes["d"].children.keys())))[0]
    color_page = (await store.read(nu.list(Space.planes[tokens].children.keys())))[0]
    for plane in ("d", tokens, color_page):
        assert await store.read(kit.root_of(plane)) == "d"


async def test_an_edit_lands_in_the_system_and_undoes(store):
    import nu
    import nuspace

    await _design(store)
    s = kit.system("d")
    await store.run(nuspace.atomic(kit.edit(s, nu.Dict.of(**{"radius.md": "9"}), "you", "Rounded")))
    assert await store.read(s.spec) == {"radius.md": "9"}
    assert await store.read(s.rev) == 1
    assert (await store.read(s.log))[-1]["who"] == "you"
    await store.run(nuspace.atomic(kit.undo(s)))
    assert await store.read(s.spec) == {}
    assert await store.read(s.rev) == 2


async def test_a_cut_makes_its_release_once_under_export(store):
    import nu
    import nuspace
    from nuspace import Space
    from nuspace.system.supervisor import ON_FAILURE, Policy

    await _design(store)
    export = await store.read(job.export_of("d"))
    assert await store.read(Space.planes[export].spec) == "design_export"
    cut = job.cut("d", export, "v1.2.0", nu.Dict.of(**specs.DEFAULTS))
    await store.run(cut >> cut)
    page = await store.read(job.release_page("d", "v1.2.0"))
    assert await store.read(nu.list(Space.planes[export].children.keys())) == [page]
    assert await store.read(Space.planes[page].meta.extract()) == {"version": "v1.2.0"}
    assert await store.read(Space.planes[page].icon) == "lucide:tag"
    jb = await store.read(job.job_of(page))
    assert await store.read(Space.planes[jb].parent) == page
    assert await store.read(Space.planes[jb].backend) == "mp"
    # Both record their Design plane, read back checked.
    assert await store.read(kit.root_of(page)) == "d"
    assert await store.read(kit.root_of(jb)) == "d"
    cell = await store.read(job.job_cell(jb))
    assert "VERSION = 'v1.2.0'" in await store.read(Space.cells[cell].prog)
    policy = nuspace.at.plane(id="supervisor").state(Policy).planes[jb].policy
    assert await store.read(policy) == ON_FAILURE
    assert await store.read(job.release_page("d", "v9.9.9")) == ""


async def test_the_first_open_seeds_once(store):
    import asyncio

    import nu
    import nuspace
    import nuspace.places
    from nuspace import Space
    from nuspace.specs import SpecCells
    from nuspace.web.env import session_env
    from nustd.ui.core import WsSession
    from nustd.ui.core.session import Session

    class Browser(WsSession):
        def __init__(self) -> None:
            super().__init__(ws=None)

        async def send(self, frame: object) -> None:
            pass

    await _design(store)
    cell = await store.read(nuspace.at.plane(id="d").state(SpecCells).ids["welcome"])
    env = session_env("127.0.0.1:9")("s1")
    load = Space.cells[cell].prog.load(scope={"plane": "d", "cell": cell}, rewrite=env.rewrite)
    s = kit.system("d")

    async def opened() -> None:
        term = nuspace.places.inside(await store.run(nuspace.atomic(load)), plane="d", cell=cell)
        task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, Browser())))
        try:
            for _ in range(400):
                if await store.read(s.release_planes.get_item("v1-0-0", "")):
                    break
                await asyncio.sleep(0.05)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    await opened()
    await opened()
    studio_job = await store.read(s.studio)
    assert await store.read(Space.planes[studio_job].spec) == "design_studio"
    assert await store.read(Space.planes[studio_job].parent) == "d"
    assert await store.read(s.seeded) is True
    assert len(await store.read(s.decided)) == len(studio.PAST)
    export = await store.read(job.export_of("d"))
    assert len(await store.read(nu.list(Space.planes[export].children.keys()))) == 1
