"""nuverse-demos agents: found through the entry point, its Planes seeded, every cell loads through the kernel."""

from __future__ import annotations

import pytest

import nu
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.kv import Snapshot
from nuverse_demos.agents import PLANE, orchestrate, page
from nuverse_demos.agents.flows import KINDS, flow_source
from nuverse_demos.agents.job import job_source


SPECS = [
    PLANE,
    orchestrate.FANOUT_PLANE,
    orchestrate.CHAIN_PLANE,
    orchestrate.TASKS_PLANE,
    page.PAGE,
]
SOURCES = {f"{spec.name}.{name}": source for spec in SPECS for name, source in spec.cells}
SOURCES["job.run"] = job_source(
    {"name": "a", "cwd": "/tmp", "model": "m", "mode": "acceptEdits", "brief": "b"}
)
for _kind in KINDS:
    SOURCES[f"flow.{_kind}"] = flow_source(
        _kind, "root", "/tmp/f", "Flow 1", {"brief": "b", "n": 2, "tasks": ["x"]}
    )


def test_discovery_finds_the_agents_plane():
    from nuspace.ext import discover

    (ext,) = [e for e in discover() if e.name == "nuverse-demos"]
    assert PLANE in ext.planes


def test_the_agents_plane_nests_its_flows():
    from nuspace.system.backends import BACKENDS

    assert PLANE.group == "Demos"
    assert PLANE.children == (
        orchestrate.FANOUT_PLANE,
        orchestrate.CHAIN_PLANE,
        orchestrate.TASKS_PLANE,
    )
    assert all(spec.backend in BACKENDS and spec.icon and spec.description for spec in SPECS)


async def test_the_agents_plane_is_created_with_its_children(store):
    await store.run(ops.create_plane(PLANE, plane_id="a"))
    kids = await store.read(ops.children("a"))
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert [rows[k]["props"]["made_by"] for k in kids] == [
        "agents_fanout",
        "agents_chain",
        "agents_tasks",
    ]


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
