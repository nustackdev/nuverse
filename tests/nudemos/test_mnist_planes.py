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
from nuspace.devices.web.env import session_env


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
    env = session_env("127.0.0.1:9")("s1")
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
