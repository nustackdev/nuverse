"""nuverse.quickstart: the first page, five cells, each loaded and run as the kernel does.

Every cell runs against a recording session, a browser with no socket that
keeps the frames it is sent, on a plane made from the spec.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import nu
import nuspace
import nustd.kv
import nustd.ui
import nuverse
from nuspace.places import Here, inside
from nuspace.shapes import Space
from nuspace.specs import SpecCells, add_plane, registered_name
from nuspace.web import Web
from nuspace.web.shell import Shell
from nuspace.web.utils import CellRoot
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.protocol import OP_INIT, OP_NOTIFY
from nustd.ui.core.session import Session
from nuverse.planes import quickstart


class _Browser(WsSession):
    """A session with no socket. Keeps the frames it is sent."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)


SOURCES = dict(quickstart.PLANE.cells)


class _Page(nu.Shape):
    level = nustd.kv.FloatRef.slot()


def _level(plane: str) -> nu.Nu:
    return nuspace.at.plane(id=plane).state(_Page).level.fallback(-1.0)


async def _load(store, plane: str, cell: str) -> nu.Nu:
    """The cell's prog loaded as the kernel loads it for a tab: its ui under the cell's node."""
    rewrite = CellRoot(Shell.viewer, Here.cell)
    load = Space.cells[cell].prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite)
    return await store.read(load)


async def _cells(store, plane: str) -> dict:
    """The plane's cells by the names its spec gave them, as its plane state keeps them."""
    return await store.read(nuspace.at.plane(id=plane).state(SpecCells).ids.extract())


async def _plane(store) -> dict:
    await store.run(add_plane(quickstart.PLANE, "s"))
    return await _cells(store, "s")


async def _run(store, plane: str, cell: str, settle: float = 0.5, then=None) -> _Browser:
    """Run the cell as the kernel does, let it draw (and ``then`` run), then stop it."""
    browser = _Browser()
    term = inside(await _load(store, plane, cell), plane=plane, cell=cell)
    task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))
    await asyncio.sleep(settle)
    if then is not None:
        await then()
        await asyncio.sleep(settle)
    task.cancel()
    (result,) = await asyncio.gather(task, return_exceptions=True)
    # A cell with nothing left to do may finish on its own before the cancel
    # lands (rule 1: a finished arm is not respawned); only a real error fails.
    if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
        raise result
    return browser


def _dicts(browser: _Browser) -> list[dict]:
    return [f.to_dict() for f in browser.frames]


def _path(frame: dict) -> tuple[str, ...]:
    """The node a frame lands on, below the cell: its ref after ``viewer/cells/<cell>``."""
    return tuple(frame["ref"][3:])


def _first_seen(frames: list[dict]) -> list[tuple[str, ...]]:
    """Each node in the order it was first written, the order the browser keeps."""
    seen: list[tuple[str, ...]] = []
    for f in frames:
        chain = _path(f)
        for i in range(1, len(chain) + 1):
            if chain[:i] not in seen:
                seen.append(chain[:i])
    return seen


def _payloads(frames: list[dict], node: tuple[str, ...]) -> list[object]:
    """What each write to ``node`` carried, in order."""
    return [f["payload"] for f in frames if _path(f) == node and f["op"] == "write"]


def _texts(frames: list[dict]) -> str:
    """Every str a frame carries, in its chain's props or its payload, joined."""
    out = []
    for f in frames:
        for _, _, props in f.get("chain") or ():
            out += [str(v) for v in props.values() if isinstance(v, str)]
        payload = f["payload"]
        if isinstance(payload, dict):
            out += [str(v) for v in payload.values() if isinstance(v, str)]
        elif isinstance(payload, str):
            out.append(payload)
    return "\n".join(out)


# --- the spec --------------------------------------------------------------------------------


def test_quickstart_registers_first_with_its_five_cells():
    spec = nuverse.extension().planes[0]
    assert spec is quickstart.PLANE
    assert (spec.name, spec.label, spec.icon, spec.group, spec.backend) == (
        "quickstart",
        "Quickstart",
        "emoji:👋",
        "Quickstart",
        "async",
    )
    assert spec.meta == {}
    assert (spec.web.editable, spec.web.width) == (True, "page")
    assert spec.key == ""
    assert list(SOURCES) == ["welcome", "dial", "meter", "agent", "next"]


def test_meter_opens_on_the_line_it_is_opened_for():
    lines = quickstart.METER.splitlines()
    assert lines[0].startswith("# Change me to 40")
    assert lines[1] == f"LIMIT = {quickstart.SHIPPED_LIMIT}"


def test_welcome_says_who_the_page_is_for():
    assert quickstart.WELCOME.startswith("# For agents: this is the person's Quickstart page.")


def test_no_copy_carries_an_em_dash():
    assert chr(0x2014) not in Path(quickstart.__file__).read_text()


# --- loading ---------------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(SOURCES))
async def test_each_cell_loads_through_the_kernel_rewrites(store, name):
    await store.do(nuspace.plane.add("p", backend="async"))
    await store.do(nuspace.cell.add("p", SOURCES[name], id="c", fabrics=["ui"]))
    term = await _load(store, "p", "c")
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(inside(term, plane="p", cell="c")))


async def test_every_cell_draws(store):
    cells = await _plane(store)
    assert sorted(cells) == sorted(SOURCES)
    fabrics = {name: await store.read(Space.cells[cid].fabrics) for name, cid in cells.items()}
    assert fabrics == {name: ["ui"] for name in SOURCES}


async def test_the_plane_shows_on_the_web(store):
    await _plane(store)
    assert await store.read(Web.planes["s"].editable) is True
    assert await store.read(Space.planes["s"].spec) == "nuverse.quickstart"


# --- drawing ---------------------------------------------------------------------------------

#: What each cell draws first, in the order its Shapes declare it.
ORDER = {
    "welcome": [("lead",), ("where",), ("again",), ("then",)],
    "dial": [("turn",)],
    "meter": [("reading",), ("tip",), ("done",)],
    "agent": [("ask",)],
    "next": [("where",)],
}


@pytest.mark.parametrize("name", list(SOURCES))
async def test_each_cell_draws_in_declared_order_and_writes_nothing_on_the_way_in(store, name):
    cells = await _plane(store)
    planes = await store.read(Space.planes.extract())
    frames = _dicts(await _run(store, "s", cells[name]))
    assert frames
    tops = [p for p in _first_seen(frames) if len(p) == 1]
    assert tops == ORDER[name]
    assert await store.read(_level("s")) == -1.0
    assert await store.read(Space.planes.extract()) == planes


async def test_the_slider_starts_at_the_stills_number(store):
    cells = await _plane(store)
    frames = _dicts(await _run(store, "s", cells["dial"]))
    # Reconcile re-checks early after subscribing, so the same value may draw
    # more than once; only the last one has to be right.
    assert _payloads(frames, ("turn", "level"))[-1] == quickstart.START


async def test_put_the_meter_back_never_shows_as_shipped(store):
    cells = await _plane(store)
    frames = [
        f for f in _dicts(await _run(store, "s", cells["dial"])) if _path(f) == ("turn", "actions")
    ]
    assert frames
    assert frames[0]["op"] == "hide"


async def test_meter_under_the_limit_draws_neutral_and_no_done_line(store):
    cells = await _plane(store)
    frames = _dicts(await _run(store, "s", cells["meter"]))
    # Reconcile re-checks early after subscribing, so the gauge may draw more
    # than once with the same value; only the last one has to be right.
    gauge = _payloads(frames, ("reading", "gauge"))[-1]
    assert gauge["value"] == pytest.approx(0.62)
    assert gauge["variant"] == "neutral"
    assert {"value": "Under the limit of 70."} in _payloads(frames, ("reading", "note"))
    assert [f["op"] for f in frames if _path(f) == ("done",)] == ["hide"]


async def test_meter_with_limit_40_draws_warn_and_the_done_line(store):
    cells = await _plane(store)
    edited = quickstart.METER.replace("LIMIT = 70", "LIMIT = 40")
    await store.do(nuspace.cell.set_prog(cells["meter"], edited, fabrics=["ui"]))
    frames = _dicts(await _run(store, "s", cells["meter"]))
    gauge = _payloads(frames, ("reading", "gauge"))[-1]
    assert gauge["variant"] == "warn"
    assert {"value": "Over the limit of 40."} in _payloads(frames, ("reading", "note"))
    done = [f for f in frames if _path(f) == ("done",)]
    assert [f["op"] for f in done] == [OP_INIT]


async def test_a_broken_meter_shows_put_back_and_set_prog_hides_it(store):
    cells = await _plane(store)
    meter = cells["meter"]
    broken = quickstart.METER.replace("LIMIT = 70", "LIMIT = = 40")
    await store.do(nuspace.cell.set_prog(meter, broken, fabrics=[]))

    async def put_back():
        await store.do(nuspace.cell.set_prog(meter, quickstart.METER, fabrics=["ui"]))

    frames = _dicts(await _run(store, "s", cells["dial"], then=put_back))
    ops_seen = [f["op"] for f in frames if _path(f) == ("turn", "actions")]
    assert ops_seen[0] == "hide"
    assert "display" in ops_seen
    assert ops_seen[-1] == "hide"
    assert await store.read(Space.cells[meter].prog) == quickstart.METER


class _Panel(nustd.ui.Column):
    go = nustd.ui.ButtonRef.slot(label="Put back")


async def test_clicking_put_back_restores_meter(store):
    cells = await _plane(store)
    meter = cells["meter"]
    await store.do(nuspace.cell.set_prog(meter, "broken", fabrics=[]))
    browser = _Browser()
    term = inside(quickstart.put_back("s", _Panel.go), plane="s", cell="c")
    task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))
    try:
        await asyncio.sleep(0.3)
        (clicked,) = browser._subs
        browser._dispatch(Frame(OP_NOTIFY, ref=clicked, payload={"event": "click"}))
        await asyncio.sleep(0.5)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert await store.read(Space.cells[meter].prog) == quickstart.METER
    assert await store.read(Space.cells[meter].version) == 3
    assert await store.read(Space.cells[meter].fabrics) == ["ui"]


async def test_a_plane_with_no_meter_keeps_put_back_down(store):
    cells = await _plane(store)
    await store.do(nuspace.cell.remove(cells["meter"]))
    frames = [
        f for f in _dicts(await _run(store, "s", cells["dial"])) if _path(f) == ("turn", "actions")
    ]
    seen = [f["op"] for f in frames]
    assert "display" not in seen
    assert seen[-1] == "hide"


async def test_a_slider_left_off_start_says_so(store):
    cells = await _plane(store)
    first = _dicts(await _run(store, "s", cells["dial"]))
    assert "Still at" not in _texts(first)
    await store.do(nuspace.at.plane(id="s").state(_Page).level.set(48.0))
    frames = _dicts(await _run(store, "s", cells["dial"]))
    assert "Still at 48, where you left it." in _texts(frames)
    assert 48.0 in _payloads(frames, ("turn", "level"))


# --- the path ---------------------------------------------------------------------------------


async def test_where_shows_home_as_tilde(store):
    home = quickstart.HOME
    assert await store.run(quickstart.where(f"{home}/my-world")) == "~/my-world"
    assert await store.run(quickstart.where("/srv/space")) == "/srv/space"


async def test_a_throwaway_space_says_so_and_offers_the_line_that_keeps_one(store):
    cells = await _plane(store)
    await store.do(Space.info.path.set(quickstart.THROWAWAY + "1a2b3c4d"))
    frames = _dicts(await _run(store, "s", cells["welcome"]))
    text = _texts(frames)
    assert "This space is throwaway" in text
    assert "nuspace run --with quickstart" in text
    agent = _texts(_dicts(await _run(store, "s", cells["agent"])))
    assert "Your agent finds a space by its folder" in agent
    assert "nuspace run --with quickstart" in agent
    assert "In my nuspace space at" not in agent


async def test_the_come_back_line_names_the_path_only_off_home(store):
    home = quickstart.HOME
    assert await store.run(quickstart.again("")) == "nuspace run --with quickstart"
    throwaway = quickstart.THROWAWAY + "1a2b3c4d"
    assert await store.run(quickstart.again(throwaway)) == "nuspace run --with quickstart"
    assert await store.run(quickstart.again(home)) == "nuspace run --with quickstart"
    assert (
        await store.run(quickstart.again(f"{home}/work")) == "nuspace run ~/work --with quickstart"
    )
    assert (
        await store.run(quickstart.again("/srv/space"))
        == "nuspace run /srv/space --with quickstart"
    )


async def test_a_home_space_shows_its_data_dir_and_comes_back_with_no_path(store):
    cells = await _plane(store)
    await store.do(Space.info.path.set(quickstart.HOME))
    text = _texts(_dicts(await _run(store, "s", cells["welcome"])))
    assert "~/.nuspace." in text
    assert "nuspace run --with quickstart" in text
    assert "throwaway" not in text


async def test_a_space_off_home_shows_its_path_and_comes_back_with_it(store):
    cells = await _plane(store)
    await store.do(Space.info.path.set(f"{quickstart.HOME}/work"))
    text = _texts(_dicts(await _run(store, "s", cells["welcome"])))
    assert "This space lives in" in text
    assert "~/work/.nuspace." in text
    assert "nuspace run ~/work --with quickstart" in text


# --- paths out -------------------------------------------------------------------------------


def _next() -> dict:
    """The next cell's source run as a module, for its handlers."""
    scope: dict = {}
    exec(compile(quickstart.NEXT, "next", "exec"), scope)  # noqa: S102
    return scope


async def _handle(store, term: nu.Nu) -> _Browser:
    browser = _Browser()
    await nu.arun(inside(term, plane="s", cell="c"), store.ctx.bind(Session, browser))
    return browser


def _pushed(browser: _Browser) -> list[str]:
    return [
        f["payload"]["uri"]
        for f in _dicts(browser)
        if isinstance(f["payload"], dict) and f["payload"].get("uri")
    ]


async def test_where_next_draws_a_card_per_demo_and_two_link_tiles(store):
    cells = await _plane(store)
    frames = _dicts(await _run(store, "s", cells["next"]))
    seen = _first_seen(frames)
    places = {
        name: [p[2] for p in seen if p[:2] == ("where", name) and len(p) == 3]
        for name in ("demos", "links")
    }
    assert places == {"demos": ["0", "1", "2"], "links": ["0", "1"]}
    labels = _texts(frames)
    for words in (
        "Where next",
        "Make a page",
        "Your personal movie tracker.",
        "A team of agents, run from one space.",
        "Pages to poke at",
        "https://nustack.dev/docs/nuspace",
        "https://discord.gg/tCa8YE7XVr",
        "This page is yours.",
    ):
        assert words in labels


async def test_make_a_page_makes_an_empty_page_under_quickstart_and_goes_there(store):
    await _plane(store)
    browser = await _handle(store, _next()["make_page"]("s"))
    (kid,) = await store.read(nu.list(Space.planes["s"].children.keys()))
    assert await store.read(Space.planes[kid].name) == "My first page"
    assert await store.read(nu.list(Space.planes[kid].cells.keys())) == []
    assert await store.read(Web.planes.contains(kid)) is True
    assert _pushed(browser) == [f"/p/{kid}"]


async def test_a_demo_opens_the_newest_plane_of_its_spec_made_once(store):
    # Any spec opens the same way: a nuverse one, so nudemos need not be installed.
    from nuverse.planes import runs as demo

    await _plane(store)
    made = Space.indexes.spec_planes[registered_name(demo.PLANE)].ids
    open_made = _next()["open_made"]
    first = await _handle(store, open_made(demo.PLANE))
    (pid,) = await store.read(nu.list(made.keys()))
    assert _pushed(first) == [f"/p/{pid}"]
    again = await _handle(store, open_made(demo.PLANE))
    assert await store.read(nu.list(made.keys())) == [pid]
    assert _pushed(again) == [f"/p/{pid}"]
    # Removed, the next open makes a new one, and it is the newest.
    await store.do(nuspace.plane.remove(pid))
    third = await _handle(store, open_made(demo.PLANE))
    newest = await store.read(made.last())
    assert newest != pid
    assert _pushed(third) == [f"/p/{newest}"]


# --- telemetry -------------------------------------------------------------------------------


async def test_a_run_tracks_its_first_move_only(store, monkeypatch):
    from nuspace import _telemetry

    told: list[str] = []
    monkeypatch.setattr(_telemetry, "track", told.append)
    await store.run(
        quickstart.counting(quickstart.moved() >> quickstart.moved() >> quickstart.moved())
    )
    assert told == ["quickstart_moved"]
