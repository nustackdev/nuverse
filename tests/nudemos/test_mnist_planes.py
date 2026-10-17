"""nudemos mnist: found through the entry point, its Planes seeded, every cell loads through the kernel."""

from __future__ import annotations

from dataclasses import replace

import pytest

import nu
from nudemos.mnist import PLANE, compare, launch, read, run, views
from nudemos.mnist.job import job_source
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.kv import Snapshot


SPECS = [PLANE, launch.PLANE, compare.PLANE, read.PLANE, run.PAGE]
SOURCES = {f"{spec.name}.{name}": source for spec in SPECS for name, source in spec.cells}
SOURCES["job.train"] = job_source({})


def test_discovery_finds_the_mnist_plane():
    from nuspace.ext import discover

    (ext,) = [e for e in discover() if e.name == "nudemos"]
    assert replace(PLANE, name=f"nudemos.{PLANE.name}") in ext.planes


def test_the_mnist_plane_nests_launch_compare_and_read():
    from nuspace.system.backends import BACKENDS

    assert PLANE.group == "Demos"
    assert PLANE.children == (launch.PLANE, compare.PLANE, read.PLANE)
    assert all(spec.backend in BACKENDS and spec.icon and spec.description for spec in SPECS)


async def test_the_mnist_plane_is_created_with_its_children(store):
    await store.run(ops.create_plane(PLANE, plane_id="m"))
    kids = await store.read(ops.children("m"))
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert [rows[k]["props"]["made_by"] for k in kids] == [
        "mnist_launch",
        "mnist_compare",
        "mnist_read",
    ]
    for kid, spec in zip(kids, PLANE.children, strict=True):
        cells = await store.read(ops.cell_rows(kid))
        assert [(c["name"], c["prog"]) for c in cells] == list(spec.cells)


@pytest.mark.parametrize("name", list(SOURCES))
async def test_each_cell_loads_through_the_kernel_rewrites(store, name):
    source = SOURCES[name]
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("p", "c"), env.rewrite)
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite)
    term = await store.run(Snapshot(load, scope=Space))
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
