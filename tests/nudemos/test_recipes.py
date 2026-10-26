"""nudemos.recipes: the kit's page recipes, as programs and as planes made by their index and linked to each other.

Every recipe runs against a recording session first, checked for what a page
must be (one root, every node a kit type, links that go somewhere), then as
a plane on a real store.
"""

from __future__ import annotations

import ast
import asyncio

import pytest

import nu
import nustd.kv
import nustd.ui as ui
from nu import Context
from nudemos import recipes
from nudemos.recipes import meridian
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.protocol import OP_INIT
from nustd.ui.core.session import Session


class _Browser(WsSession):
    """A session with no socket. Keeps the frames it is sent."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)


def _frames(term: nu.Nu) -> list[Frame]:
    browser = _Browser()
    asyncio.run(nu.arun(term, Context().bind(Session, browser)))
    return browser.frames


def _drawn(name: str, links: dict | None = None) -> list[dict]:
    return [f.to_dict() for f in _frames(recipes.module(name).page(links=links))]


async def _cells(store, plane: str) -> dict:
    return {c["name"]: c["id"] for c in await store.read(ops.cell_rows(plane))}


async def _load(store, plane: str, cell: str) -> nu.Nu:
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot(plane, cell), env.rewrite)
    load = Space.cells[cell].prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite)
    return await store.run(nustd.kv.Snapshot(load, scope=Space))


async def _run_until_drawn(store, plane: str, cell: str, settle: float = 1.0) -> _Browser:
    """Run the cell as the kernel does, let it draw, then stop it (it waits forever after)."""
    browser = _Browser()
    term = nu.Frame(ops.Here, await _load(store, plane, cell), plane=plane, cell=cell)
    task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))
    await asyncio.sleep(settle)
    task.cancel()
    (result,) = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(result, asyncio.CancelledError), result
    return browser


def _props(frames: list) -> list[dict]:
    """Every props dict a frame carries: in its chain, or as a write's payload."""
    out = []
    for f in frames:
        f = f if isinstance(f, dict) else f.to_dict()
        out += [props for _, _, props in f.get("chain") or ()]
        if isinstance(f["payload"], dict):
            out.append(f["payload"])
    return out


def _hrefs(frames: list) -> set[str]:
    """Every href a frame put on a node, a breadcrumb's included."""
    found = set()
    for props in _props(frames):
        found |= {props[k] for k in ("href", "action_href") if props.get(k)}
        found |= {
            c["href"] for c in props.get("items") or () if isinstance(c, dict) and c.get("href")
        }
    return found


# --- the recipes, as programs ----------------------------------------------------------------

# The wire types the kit's own Refs and Shapes ship as: every one has a node.
# Only a declared one counts, not the class name an abstract base falls back to.
_KIT_TYPES = {
    obj._wire_type or getattr(getattr(obj, "_ref_cls", None), "_wire_type", "")
    for obj in vars(ui).values()
    if isinstance(obj, type) and issubclass(obj, (ui.Ref, ui.Section))
} - {""}


@pytest.mark.parametrize("name", recipes.RECIPES)
def test_a_recipe_is_one_page_under_its_own_root(name):
    frames = _drawn(name)
    assert frames
    assert {tuple(f["ref"][:1]) for f in frames} == {(name,)}
    # The root comes first, so the page exists before anything lands in it.
    assert frames[0]["ref"] == [name]
    assert frames[0]["chain"][0][1] == "Container"


@pytest.mark.parametrize("name", recipes.RECIPES)
def test_a_recipe_draws_the_same_page_every_time(name):
    assert _drawn(name) == _drawn(name)


@pytest.mark.parametrize("name", recipes.RECIPES)
def test_every_node_is_a_kit_type(name):
    types = {lvl[1] for f in _drawn(name) for lvl in f["chain"]}
    assert types <= _KIT_TYPES, sorted(types - _KIT_TYPES)


@pytest.mark.parametrize("name", recipes.RECIPES)
def test_links_are_text_or_muted_and_buttons_carry_the_rest(name):
    for f in _drawn(name):
        for _, typ, props in f["chain"]:
            if typ == "LinkRef":
                assert props.get("variant", "text") in {"text", "muted"}
                assert "size" not in props


@pytest.mark.parametrize("name", recipes.RECIPES)
def test_links_go_to_the_pages_and_follow_the_host(name):
    assert _hrefs(_drawn(name)) <= set(meridian.LINKS.values())
    routes = {page: f"/recipes.{page}" for page in recipes.RECIPES}
    assert _hrefs(_drawn(name, routes)) <= set(routes.values())


def test_the_pages_link_to_each_other():
    # Every page is reachable from some other page.
    reached = set()
    for name in recipes.RECIPES:
        reached |= {h.lstrip("#") for h in _hrefs(_drawn(name))} - {name}
    assert reached == set(recipes.RECIPES)


@pytest.mark.parametrize("name", recipes.RECIPES)
def test_a_recipe_is_plain_nustd_ui(name):
    tree = ast.parse(recipes.source(name))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            # Absolute only: the source runs as a program of its own.
            assert node.level == 0, ast.unparse(node)
            imported |= {f"{node.module}.{a.name}" for a in node.names}
    roots = {"__future__", "typing", "collections", "nu", "nustd"}
    assert {m for m in imported if m.split(".")[0] not in roots} == {"nudemos.recipes.meridian"}


@pytest.mark.parametrize("name", recipes.RECIPES)
def test_the_source_is_a_program_once_page_is_called(name):
    scope: dict = {}
    exec(compile(recipes.source(name) + "\nout = page()\n", name, "exec"), scope)  # noqa: S102
    assert [f.to_dict() for f in _frames(scope["out"])] == _drawn(name)


def test_an_unknown_recipe_says_which_there_are():
    with pytest.raises(KeyError, match="dashboard"):
        recipes.module("nope")


# --- the specs -------------------------------------------------------------------------------


def test_the_group_is_registered_with_an_index_cell():
    spec = recipes.PLANE
    assert (spec.name, spec.group, spec.backend) == ("recipes", "Recipes", "async")
    assert spec.meta["editable"] is True
    assert [name for name, _ in spec.cells] == ["index"]
    # The pages are made by the index, so each one's id is known: not declared children.
    assert spec.children == ()


def test_a_page_per_recipe_whose_cell_is_the_recipe_source():
    assert list(recipes.PAGES) == list(recipes.RECIPES)
    for name, spec in recipes.PAGES.items():
        assert spec.icon
        assert spec.description
        ((cell, source),) = spec.cells
        assert cell == name
        # The whole recipe, as it ships, then the entry that links it.
        assert source.startswith(recipes.source(name))
        assert "def out(plane):" in source[len(recipes.source(name)) :]


@pytest.mark.parametrize(
    "source",
    [s for _, s in recipes.PLANE.cells] + [spec.cells[0][1] for spec in recipes.PAGES.values()],
    ids=["index", *recipes.PAGES],
)
async def test_each_cell_loads_through_the_kernel_rewrites(store, source):
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    term = await _load(store, "p", "c")
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


# --- running them ----------------------------------------------------------------------------


async def test_the_index_makes_every_page_once_under_itself(store):
    await store.run(ops.create_plane(recipes.PLANE, plane_id="r"))
    index = (await _cells(store, "r"))["index"]
    browser = await _run_until_drawn(store, "r", index)
    kids = await store.read(ops.children("r"))
    assert kids == [f"r.{name}" for name in recipes.RECIPES]
    rows = {row["id"]: row for row in await store.read(ops.plane_rows())}
    assert [rows[k]["name"] for k in kids] == [
        "Dashboard",
        "Detail",
        "Catalog",
        "Settings",
        "Landing",
    ]
    # A tile per page, pointing at it.
    assert _hrefs(browser.frames) == {f"/r.{name}" for name in recipes.RECIPES}
    # Run again: nothing made twice.
    await _run_until_drawn(store, "r", index, settle=0.5)
    assert await store.read(ops.children("r")) == kids


async def test_a_page_draws_its_recipe_linked_to_its_siblings(store):
    await store.run(ops.create_plane(recipes.PLANE, plane_id="r"))
    await _run_until_drawn(store, "r", (await _cells(store, "r"))["index"])
    page = "r.catalog"
    browser = await _run_until_drawn(store, page, (await _cells(store, page))["catalog"])
    inits = [f for f in browser.frames if f.op == OP_INIT]
    assert inits
    # The recipe's root lands under the cell, everything else under it.
    roots = {f.ref.index("catalog") for f in inits}
    assert len(roots) == 1
    siblings = {f"/r.{name}" for name in recipes.RECIPES}
    hrefs = _hrefs(browser.frames)
    assert hrefs
    assert hrefs <= siblings
