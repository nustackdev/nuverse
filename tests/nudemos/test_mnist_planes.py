"""nudemos mnist: found through the entry point, its Planes seeded, every cell loads through the kernel."""

from __future__ import annotations

from dataclasses import replace

import pytest

import nu
import nuspace
import nuspace.specs
from nudemos.mnist import PLANE, compare, launch, read, run, views
from nudemos.mnist.job import job_source
from nuspace import Space
from nuspace.web.env import session_env


SPECS = [PLANE, launch.PLANE, compare.PLANE, read.PLANE, run.PAGE]
SOURCES = {f"{spec.name}.{name}": source for spec in SPECS for name, source in spec.cells}
SOURCES["job.train"] = job_source({})


def test_discovery_finds_the_mnist_plane():
    from nuspace.specs import discover

    ext = discover()["nudemos"]
    assert replace(PLANE, name=f"nudemos.{PLANE.name}") in ext.planes


def test_the_mnist_plane_nests_launch_compare_and_read():
    from nuspace.kernel.backends import BACKENDS

    assert PLANE.group == "Demos"
    assert PLANE.children == (launch.PLANE, compare.PLANE, read.PLANE)
    assert all(spec.backend in BACKENDS and spec.icon and spec.description for spec in SPECS)


async def test_the_mnist_plane_is_created_with_its_children(store):
    await store.run(nuspace.specs.add_plane(PLANE, "m"))
    kids = await store.read(nu.list(Space.planes["m"].children.keys()))
    assert [await store.read(Space.planes[k].spec) for k in kids] == [
        "mnist_launch",
        "mnist_compare",
        "mnist_read",
    ]
    for kid, spec in zip(kids, PLANE.children, strict=True):
        ids = await store.read(nu.list(Space.planes[kid].cells.keys()))
        cells = [
            (await store.read(Space.cells[c].name), await store.read(Space.cells[c].prog))
            for c in ids
        ]
        assert cells == list(spec.cells)


@pytest.mark.parametrize("name", list(SOURCES))
async def test_each_cell_loads_through_the_kernel_rewrites(store, name):
    source = SOURCES[name]
    await store.do(nuspace.plane.add("p", backend="async"))
    await store.do(nuspace.cell.add("p", source, id="c"))
    env = session_env(lambda: "127.0.0.1:9")("s1")
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=env.rewrite)
    term = await store.run(nuspace.atomic(load))
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


def test_lr_text_reads_like_people_write_it():
    assert [views.lr_text(x) for x in (3e-4, 1e-3, 0.0003162, 0.01, 0.03, 0)] == [
        "3e-4",
        "1e-3",
        "3.2e-4",
        "0.01",
        "0.03",
        "-",
    ]


async def test_compare_ticks_are_made_once_and_kept(store):
    from nudemos.mnist.state import Pick, picks_made

    await store.run(nuspace.specs.add_plane(PLANE, "m"))
    kids = await store.read(nu.list(Space.planes["m"].children.keys()))
    specs = [await store.read(Space.planes[k].spec) for k in kids]
    c = kids[specs.index("mnist_compare")]
    ticks = nuspace.at.plane(id=c).state(Pick).planes
    read = nuspace.atomic(nu.list(ticks.fallback([])))
    # A fresh Compare has no ticks container: its table and overlay read them first.
    with pytest.raises(Exception, match="Container does not exist"):
        await store.read(read)
    await store.run(nuspace.atomic(picks_made(nuspace.at.plane(id=c).state(Pick))))
    assert await store.read(read) == []
    await store.run(nuspace.atomic(ticks.set(["r"])))
    await store.run(nuspace.atomic(picks_made(nuspace.at.plane(id=c).state(Pick))))
    assert await store.read(read) == ["r"]


@pytest.mark.parametrize("cell", ["table", "overlay"])
def test_compare_makes_its_ticks_before_reading_them(cell):
    source = dict(compare.PLANE.cells)[cell]
    assert "return TICKS >> " in source


async def test_a_series_never_written_samples_as_empty(store):
    from nudemos.mnist.state import Run, sampled

    await store.do(nuspace.plane.add("j", backend="async"))
    await store.do(nuspace.cell.add("j", "def out(cell):\n    return None\n", id="c"))
    run = nuspace.at.cell(id="c").state(Run)
    # A fresh run has no test scores before its first eval: the curves read nothing, not fail.
    assert await store.read(nuspace.atomic(nu.list(sampled(run.test_loss, 10)))) == []
    await store.run(nuspace.atomic(run.test_loss.set_item(200, 0.5)))
    assert len(await store.read(nuspace.atomic(nu.list(sampled(run.test_loss, 10))))) == 1
