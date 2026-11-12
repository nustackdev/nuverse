"""nudemos agents: found through the entry point, its Planes seeded, every cell loads through the kernel."""

from __future__ import annotations

from dataclasses import replace

import pytest

import nu
import nuspace
from nudemos.agents import PLANE, orchestrate, page
from nudemos.agents.flows import KINDS, flow_source
from nudemos.agents.job import job_source
from nudemos.agents.state import spec_of
from nuspace import Space
from nuspace.web.env import session_env


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
    from nuspace.specs import discover

    ext = discover()["nudemos"]
    assert replace(PLANE, name=f"nudemos.{PLANE.name}") in ext.planes


def test_the_agents_plane_nests_its_flows():
    from nuspace.kernel.backends import BACKENDS

    assert PLANE.group == "Demos"
    assert PLANE.children == (
        orchestrate.FANOUT_PLANE,
        orchestrate.CHAIN_PLANE,
        orchestrate.TASKS_PLANE,
    )
    assert all(spec.backend in BACKENDS and spec.icon and spec.description for spec in SPECS)


async def test_the_agents_plane_is_created_with_its_children(store):
    await store.run(nuspace.specs.add_plane(PLANE, "a"))
    kids = await store.read(Space.planes["a"].children.keys(limit=3))
    assert [await store.read(spec_of(k)) for k in kids] == [
        "agents_fanout",
        "agents_chain",
        "agents_tasks",
    ]


@pytest.mark.parametrize("name", list(SOURCES))
async def test_each_cell_loads_through_the_kernel_rewrites(store, name):
    source = SOURCES[name]
    await store.do(nuspace.plane.add("p", backend="async") >> nuspace.cell.add("p", source, id="c"))
    env = session_env("127.0.0.1:9")("s1")
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=env.rewrite)
    term = await store.read(load)
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))
