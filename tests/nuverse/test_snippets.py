"""nuverse's snippets, loaded the way the kernel loads them and run on a real store."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

import nu
import nustd.kv
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.content import CELL, PLANE, SPACE, kind_name
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session
from nuverse.contents import DateContent, FlagContent, NumberContent, RowContent, TextContent
from nuverse.snippets import SNIPPETS
from nuverse.snippets.content import (
    checkbox,
    date_picker,
    item,
    item_picker,
    items,
    number_input,
    select,
    slider,
    switch,
    table,
    text_editor,
    text_input,
)
from nuverse.snippets.content._editing import ITEM, Target
from nuverse.snippets.debugging import cell_lens, plane_lens
from nuverse.snippets.examples import converter, password


if TYPE_CHECKING:
    from collections.abc import Callable


class _Hold(ScalarQuery):
    """Hands the ctx it runs in to ``opened``, then waits for ``done``."""

    def __init__(self, opened: asyncio.Future, done: asyncio.Event) -> None:
        super().__init__()
        self._payload = {"opened": opened, "done": done}

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        opened, done = self._payload["opened"], self._payload["done"]

        async def athunk(rt: object) -> object:
            opened.set_result(rt.ctx)
            await done.wait()

        return athunk


@pytest_asyncio.fixture
async def ctx():
    """An in memory store bound untagged, the way a worker binds its proxy."""
    loop = asyncio.get_running_loop()
    opened, done = loop.create_future(), asyncio.Event()
    held = asyncio.create_task(
        nu.arun(nu.With(nustd.kv.memory_navigator(), body=_Hold(opened, done)))
    )
    yield await opened
    done.set()
    await held


class _Browser(WsSession):
    """A session with no socket. Keeps frames, and plays the select's part."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []
        self.selected = ""

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)
        if frame.ref[-1] == "cell" and isinstance(frame.payload, str):
            self.selected = frame.payload

    async def aread(self, path: tuple[str, ...]) -> object:
        assert path[-1] == "cell"
        return self.selected

    def notify(self, path: tuple[str, ...], payload: object) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))

    def pick(self, cell_id: str) -> None:
        """What the dropdown does: select locally, notify with no payload."""
        self.selected = cell_id
        self.notify(self.path("cell"), None)

    def path(self, name: str) -> tuple[str, ...]:
        return next(f.ref for f in self.frames if f.ref[-1] == name)

    def last(self, name: str) -> object:
        return next(f.payload for f in reversed(self.frames) if f.ref[-1] == name)

    def options(self) -> list:
        """The dropdown's latest list."""
        writes = [f.payload for f in self.frames if f.ref[-1] == "cell"]
        return next(w["options"] for w in reversed(writes) if isinstance(w, dict))


async def _until(check: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


async def _load(ctx: nu.Context, plane: str, cell: str) -> nu.Nu:
    """The cell's program, loaded through the kernel's rewrites."""
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot(plane, cell), env.rewrite)
    prog = Space.cells[cell].prog
    load = prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite)
    term, _ = await nu.arun(nustd.kv.Snapshot(load, scope=Space), ctx)
    return term


def _keys(columns: dict) -> dict:
    """``{key: preview}`` of a lens frame's first column."""
    return {e["key"]: e["preview"] for e in columns["columns"][0]["entries"]}


async def _running(ctx: nu.Context, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell's program run as the kernel runs it: inside its ``Here`` frame."""
    term = nu.Frame(ops.Here, await _load(ctx, plane, cell), plane=plane, cell=cell)
    return asyncio.create_task(nu.arun(term, ctx.bind(Session, browser)))


async def test_plane_lens_browses_its_own_plane(ctx):
    await nu.arun(
        ops.add_plane("p", name="Home", backend="async")
        >> ops.add_cell("p", plane_lens.SNIPPET.source, cell_id="me"),
        ctx,
    )
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        shown = _keys(browser.last("lens"))
        assert shown["name"] == "Home"
        assert {"props", "meta", "cells"} <= set(shown)
        # State is in the other store: a lens on the plane does not see it.
        assert "state" not in shown
    finally:
        task.cancel()


async def test_cell_lens_follows_the_select(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async")
        >> ops.add_cell("p", cell_lens.SNIPPET.source, cell_id="me", name="lens")
        >> ops.add_cell("p", "one", cell_id="c1")
        >> ops.add_cell("p", "two", cell_id="c2", name="second")
        >> ops.set_cell_meta("c2", {"marker": 1}),
        ctx,
    )
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        # Every cell listed in order, named or by id. The first other cell picked.
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        assert browser.last("cell") == "c1"
        assert browser.options() == [
            {"value": "me", "label": "lens"},
            {"value": "c1", "label": "c1"},
            {"value": "c2", "label": "second"},
        ]
        assert _keys(browser.last("lens"))["prog"] == "one"

        # A pick restarts the lens on the other cell.
        before = len(browser.frames)
        browser.pick("c2")
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames[before:]))
        assert _keys(browser.last("lens"))["prog"] == "two"

        # Moving the cursor reads the picked cell, not the first one.
        before = len(browser.frames)
        browser.notify(browser.path("lens"), ["meta"])
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames[before:]))
        meta = browser.last("lens")["columns"][1]["entries"]
        assert [(e["key"], e["preview"]) for e in meta] == [("marker", "1")]

        # A cell added shows up in the list.
        await nu.arun(ops.add_cell("p", "three", cell_id="c3"), ctx)
        await _until(lambda: browser.options()[-1] == {"value": "c3", "label": "c3"})
    finally:
        task.cancel()


async def test_cell_lens_alone_on_its_plane_browses_itself(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async")
        >> ops.add_cell("p", cell_lens.SNIPPET.source, cell_id="me"),
        ctx,
    )
    browser = _Browser()
    task = await _running(ctx, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        assert browser.selected == "me"
        assert cell_lens.SNIPPET.source.startswith(_keys(browser.last("lens"))["prog"][:20])
    finally:
        task.cancel()


# --- every snippet: a shim in the cell, the code in the package ---------------------


@pytest.mark.parametrize("snippet", SNIPPETS, ids=lambda s: s.name)
async def test_every_snippet_runs_from_its_shim(ctx, snippet):
    """The cell stores the shim and nothing else; loaded, it is the snippet's whole program."""
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", snippet, cell_id="c"),
        ctx,
    )
    stored, _ = await nu.arun(ops.snapshot(ops.prog("c")), ctx)
    assert stored == snippet.source
    nu.validate(nu.compile(await _load(ctx, "p", "c")))


async def _read(ctx: nu.Context, term: nu.Nu) -> object:
    value, _ = await nu.arun(ops.snapshot(term), ctx)
    return value


async def _write(ctx: nu.Context, term: nu.Nu) -> None:
    """``term`` as a program would write it: one commit to the States store."""
    await nu.arun(ops.atomic_state(term), ctx)


def _value(kind: type, cell: str = "c", item_id: str = ITEM) -> nu.Nu:
    """The ``value`` of an item of ``kind`` on ``cell``, by its address."""
    return kind.at((CELL, cell), item_id).value


def test_every_snippet_is_one_import_line_or_an_editable_lens():
    for snippet in SNIPPETS:
        lines = snippet.source.strip().splitlines()
        if snippet.group != "Debugging":
            assert lines == [f"from nuverse.snippets.{_module(snippet)} import out"], snippet.name


def _module(snippet: object) -> str:
    category = {"Examples": "examples"}.get(snippet.group, "content")
    name = {"text": "text_editor"}.get(snippet.name, snippet.name)
    return f"{category}.{name}"


def _shown(browser: _Browser, text: str) -> Callable[[], bool]:
    """Whether the editor was handed ``text``."""
    return lambda: any(f.ref[-1] == "text" and f.payload == text for f in browser.frames)


async def test_text_editor_shows_what_a_program_writes_and_keeps_what_is_typed(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async")
        >> ops.insert_snippet("p", text_editor.SNIPPET, cell_id="c"),
        ctx,
    )
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(_shown(browser, ""))
        await _write(ctx, _value(TextContent).set("Water the basil"))
        await _until(_shown(browser, "Water the basil"))
        browser.type("text", value="Basil likes sun")
        await _settles(ctx, _value(TextContent), lambda v: v == "Basil likes sun")
    finally:
        task.cancel()


async def test_insert_snippet_hands_the_new_cell_to_what_follows(ctx):
    """The id is minted when the term runs; ``into`` holds it for the writes after."""
    made = nu.let(
        "",
        lambda cell: (
            ops.insert_snippet("p", text_editor.SNIPPET, into=cell)
            >> ops.atomic_state(TextContent.at((CELL, cell), ITEM).value.set("Basil likes sun"))
        ),
    )
    await nu.arun(ops.add_plane("p", backend="async") >> made >> made, ctx)
    rows = await _read(ctx, ops.cell_rows("p"))
    assert [row["props"]["made_by"] for row in rows] == ["nuverse.text", "nuverse.text"]
    first, second = (row["id"] for row in rows)
    assert first != second
    for cell in (first, second):
        assert await _read(ctx, _value(TextContent, cell)) == "Basil likes sun"


async def _settles(ctx: nu.Context, term: nu.Nu, check: Callable[[object], bool]) -> object:
    """``term`` read until ``check`` holds for it, then that value."""
    deadline = asyncio.get_running_loop().time() + 3.0
    while not check(value := await _read(ctx, term)):
        assert asyncio.get_running_loop().time() < deadline, f"timed out on {value!r}"
        await asyncio.sleep(0.01)
    return value


async def test_table_seeds_once_and_stores_what_the_browser_asks(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", table.SNIPPET, cell_id="c"),
        ctx,
    )
    order = ops.cell_state("c", nu.ToList(table.Sheet.order))
    name = RowContent.at((CELL, "c"), "r2").cells["name"]
    browser = _Browser()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "table" for f in browser.frames))
        assert await _read(ctx, order) == ["r1", "r2", "r3"]

        # An edit is stored as asked and shipped back.
        browser.notify(
            browser.path("table"),
            {"event": "edit", "key": "r2", "row_index": 1, "column": "name", "value": "Basil"},
        )
        await _settles(ctx, name, lambda v: v == "Basil")
        await _until(lambda: "Basil" in str(browser.last("table")))

        # A row added lands where asked under a fresh key; a delete takes it out again.
        browser.notify(browser.path("table"), {"event": "add", "index": 0})
        added = (await _settles(ctx, order, lambda v: len(v) == 4))[0]
        assert added not in ("r1", "r2", "r3")
        browser.notify(
            browser.path("table"), {"event": "delete", "keys": [added], "row_indexes": [0]}
        )
        await _settles(ctx, order, lambda v: v == ["r1", "r2", "r3"])
    finally:
        task.cancel()

    # A second run finds it seeded and leaves the rows alone.
    browser = _Browser()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "table" for f in browser.frames))
        assert await _read(ctx, name) == "Basil"
        assert await _read(ctx, order) == ["r1", "r2", "r3"]
    finally:
        task.cancel()


async def test_a_row_a_program_adds_shows_last_and_leaves_the_order_alone(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", table.SNIPPET, cell_id="c"),
        ctx,
    )
    order = ops.cell_state("c", nu.ToList(table.Sheet.order))
    browser = _Browser()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: await_order_seeded(browser))
        rows = RowContent.items((CELL, "c"))
        await _write(ctx, rows["a0"].cells["name"].set("Mint"))
        await _until(lambda: "Mint" in str(browser.last("table")))
        assert await _read(ctx, order) == ["r1", "r2", "r3"]
    finally:
        task.cancel()

    # Painted whole, it comes after every row the order names.
    browser = _Browser()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: await_order_seeded(browser))
        whole = next(f.payload for f in browser.frames if f.ref[-1] == "table")
        keys = [row["_key"] for row in whole["rows"]]
        assert keys == ["r1", "r2", "r3", "a0"]
    finally:
        task.cancel()


def await_order_seeded(browser: _Browser) -> bool:
    """Whether the table was painted whole once."""
    return any(f.ref[-1] == "table" and isinstance(f.payload, dict) for f in browser.frames)


# --- inputs: user input, stored, shown back -----------------------------------------


class _Inputs(_Browser):
    """A session whose inputs hold what was typed, by ref path, and answer reads with it.

    A read of an input nothing was typed into answers what was last written to it.
    """

    def __init__(self) -> None:
        super().__init__()
        self.values: dict[tuple[str, ...], object] = {}

    async def aread(self, path: tuple[str, ...]) -> object:
        typed = [k for k in self.values if path[-len(k) :] == k]
        if typed:
            return self.values[max(typed, key=len)]
        written = [
            f.payload for f in self.frames if f.ref == path and not isinstance(f.payload, dict)
        ]
        return written[-1] if written else ""

    def type(self, *names: str, value: object) -> None:
        """What an input does: hold the value locally, notify with no payload."""
        self.values[names] = value
        self.notify(next(f.ref for f in self.frames if f.ref[-len(names) :] == names), None)

    def shown(self, *names: str) -> list:
        """Every payload written to the ref ending in ``names``, oldest first."""
        return [f.payload for f in self.frames if f.ref[-len(names) :] == names]


async def _input(ctx: nu.Context, module: object, cell: str = "c") -> tuple[_Inputs, asyncio.Task]:
    """A cell of ``module`` made as ``cell`` on ``p``, running, its first paint done."""
    made = ops.insert_snippet("p", module.SNIPPET, cell_id=cell)
    there = await _read(ctx, ops.plane_exists("p"))
    await nu.arun(made if there else ops.add_plane("p", backend="async") >> made, ctx)
    browser = _Inputs()
    task = await _running(ctx, "p", cell, browser)
    await _until(lambda: browser.shown("entry") and browser.shown("entry", "input"))
    await _listening()
    return browser, task


async def _listening() -> None:
    """A beat for a running cell's reactions to subscribe after its first paint.

    An editor paints, then subscribes: a notify landing in between is lost,
    as it would be in a browser that typed within the same milliseconds.
    """
    await asyncio.sleep(0.1)


async def test_number_input_stores_what_is_typed_and_shows_what_is_set(ctx):
    browser, task = await _input(ctx, number_input)
    try:
        # Labelled with the cell's name, bounded 0 to 100, a step of 1.
        assert {"label": "number_input"} in browser.shown("entry")
        assert {"min": 0.0} in browser.shown("entry", "input")
        assert {"max": 100.0} in browser.shown("entry", "input")
        assert {"step": 1.0} in browser.shown("entry", "input")

        browser.type("entry", "input", value=42)
        await _settles(ctx, _value(NumberContent), lambda v: v == 42.0)

        # Set by a program: the running cell shows it.
        await _write(ctx, _value(NumberContent).set(7.5))
        await _until(lambda: {"value": 7.5} in browser.shown("entry", "input"))

        # Config: a bound typed is stored and applied.
        browser.type("settings", "min", value=-3)
        await _until(lambda: {"min": -3.0} in browser.shown("entry", "input"))

        # Renamed under Config: the cell is renamed, and findable by it.
        browser.type("settings", "name", value="budget")
        await _until(lambda: {"label": "budget"} in browser.shown("entry"))
        assert await _read(ctx, ops.cell_named("p", "budget")) == "c"
    finally:
        task.cancel()


@pytest.mark.parametrize(
    ("module", "kind", "typed", "stored", "set_to", "shown"),
    [
        (text_input, TextContent, "Basil", "Basil", "Thyme", "Thyme"),
        (switch, FlagContent, True, True, False, False),
        (checkbox, FlagContent, True, True, False, False),
        (select, TextContent, "Two", "Two", "Three", "Three"),
        (
            date_picker,
            DateContent,
            "2026-10-06",
            datetime.date(2026, 10, 6),
            "2027-01-01",
            "2027-01-01",
        ),
        (slider, NumberContent, 30, 30.0, 55.0, {"value": 55.0}),
    ],
    ids=lambda v: getattr(v, "__name__", "").rpartition(".")[2] or None,
)
async def test_an_input_stores_what_is_typed_and_shows_what_is_set(
    ctx, module, kind, typed, stored, set_to, shown
):
    browser, task = await _input(ctx, module)
    try:
        browser.type("entry", "input", value=typed)
        await _settles(ctx, _value(kind), lambda v: v == stored)
        await _write(ctx, _value(kind).set(set_to))
        await _until(lambda: browser.shown("entry", "input")[-1] == shown)
        # Labelled by the cell's name, renamed from Config.
        browser.type("settings", "name", value="mine")
        await _until(lambda: {"label": "mine"} in browser.shown("entry"))
        assert await _read(ctx, ops.cell_named("p", "mine")) == "c"
    finally:
        task.cancel()


async def test_a_cleared_date_is_gone(ctx):
    browser, task = await _input(ctx, date_picker)
    try:
        assert browser.shown("entry", "input")[0] == ""
        browser.type("entry", "input", value="2026-10-06")
        await _settles(ctx, _value(DateContent), lambda v: v == datetime.date(2026, 10, 6))
        browser.type("entry", "input", value="")
        await _settles(ctx, _value(DateContent).exists(), lambda v: not v)
    finally:
        task.cancel()


async def test_select_options_come_from_config(ctx):
    browser, task = await _input(ctx, select)
    try:
        assert {"options": select.OPTIONS} in browser.shown("entry", "input")
        browser.type("settings", "options", value=["Red", "Blue"])
        await _until(lambda: browser.shown("entry", "input")[-1] == {"options": ["Red", "Blue"]})
        assert browser.shown("settings", "options")[-1] == ["Red", "Blue"]
    finally:
        task.cancel()


async def test_slider_range_comes_from_config(ctx):
    browser, task = await _input(ctx, slider)
    try:
        assert {"max": 100.0} in browser.shown("entry", "input")
        browser.type("settings", "max", value=10)
        await _until(lambda: {"max": 10.0} in browser.shown("entry", "input"))
        assert {"value": 10.0} in browser.shown("settings", "max")
    finally:
        task.cancel()


# --- one item, many editors ----------------------------------------------------------


async def test_config_points_an_editor_at_another_cells_item(ctx):
    mine, first = await _input(ctx, text_input, "a")
    theirs, second = await _input(ctx, text_input, "b")
    try:
        # Its Config shows where its item is: this cell's value.
        assert theirs.shown("item", "level", "input")[-1] == CELL
        assert theirs.shown("item", "id")[-1] == ""

        mine.type("entry", "input", value="Basil")
        await _settles(ctx, _value(TextContent, "a"), lambda v: v == "Basil")

        # Pointed at a's item, b shows it and edits it.
        theirs.type("item", "scope", value="a")
        target = ops.cell_state("b", Target.target)
        await _settles(ctx, target, lambda v: (v or {}).get("scope") == "a")
        await _until(lambda: theirs.shown("entry", "input")[-1] == "Basil")
        theirs.type("entry", "input", value="Thyme")
        await _settles(ctx, _value(TextContent, "a"), lambda v: v == "Thyme")
        await _until(lambda: mine.shown("entry", "input")[-1] == "Thyme")
        # b's own item was never written.
        assert await _read(ctx, _value(TextContent, "b").exists()) is False
    finally:
        first.cancel()
        second.cancel()


@pytest.mark.parametrize(
    ("level", "scope", "item_id"), [(PLANE, "", "title"), (SPACE, "", "readme"), (CELL, "x", "v")]
)
async def test_a_program_points_an_editor_at_any_scope(ctx, level, scope, item_id):
    await nu.arun(
        ops.add_plane("p", backend="async")
        >> ops.insert_snippet("p", number_input.SNIPPET, cell_id="c"),
        ctx,
    )
    pointed = {"level": level, "scope": scope, "id": item_id}
    await _write(ctx, ops.cell_state("c", Target.target.set(pointed)))
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    try:
        await _until(lambda: browser.shown("entry", "input"))
        await _listening()
        browser.type("entry", "input", value=12)
        owner = {PLANE: "p", SPACE: "", CELL: scope}[level]
        held = NumberContent.at((level, owner), item_id).value
        await _settles(ctx, held, lambda v: v == 12.0)
    finally:
        task.cancel()


# --- items of any kind ---------------------------------------------------------------


async def test_item_draws_any_item_in_full_and_again_when_it_changes(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", item.SNIPPET, cell_id="c"),
        ctx,
    )
    await _write(ctx, _value(TextContent).set("# Basil"))
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    try:
        # Left as it is: its own cell's text, drawn by the kind's render.
        await _until(lambda: browser.shown("body") and browser.shown("body")[-1] == "# Basil")
        await _write(ctx, _value(TextContent).set("# Thyme"))
        await _until(lambda: browser.shown("body")[-1] == "# Thyme")

        # Pointed at a number on the plane.
        await _write(ctx, NumberContent.at((PLANE, "p"), "n").value.set(42.0))
        number = kind_name(NumberContent)
        pointed = {"kind": number, "level": PLANE, "scope": "", "id": "n"}
        await _write(ctx, ops.cell_state("c", Target.target.set(pointed)))
        await _until(lambda: {"value": "42"} in browser.shown("stat"))
        assert browser.shown("which", "kind", "input")[-1] == number
    finally:
        task.cancel()


async def test_items_lists_adds_opens_edits_and_removes(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", items.SNIPPET, cell_id="c"),
        ctx,
    )
    held = TextContent.items((CELL, "c"))
    await _write(ctx, held["one"].value.set("Basil"))
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    opened = ops.cell_state("c", items.Open.opened)
    try:
        # Each item a line drawn by its kind's render_hit.
        await _until(lambda: "Basil" in browser.shown("i_one", "hit", "text"))

        # Add: a new item, opened, edited through its field.
        browser.notify((*browser.path("lines")[:-1], "head", "add"), None)
        made = await _settles(ctx, opened, lambda v: bool(v))
        assert sorted(await _read(ctx, nu.list(held.keys()))) == sorted(["one", made])
        await _until(lambda: browser.shown("form", "value", "input"))
        browser.type("form", "value", "input", value="Thyme")
        await _settles(ctx, held[made].value, lambda v: v == "Thyme")
        await _until(lambda: "Thyme" in browser.shown(f"i_{made}", "hit", "text"))

        # Open another, then remove it.
        browser.notify((*browser.path("lines"), "i_one", "open"), None)
        await _settles(ctx, opened, lambda v: v == "one")
        browser.notify((*browser.path("lines"), "i_one", "remove"), None)
        await _settles(ctx, nu.list(held.keys()), lambda v: v == [made])
        await _settles(ctx, opened, lambda v: v == "")
    finally:
        task.cancel()


async def test_item_picker_keeps_the_picked_items_address(ctx):
    await nu.arun(
        ops.add_plane("p", backend="async")
        >> ops.insert_snippet("p", item_picker.SNIPPET, cell_id="c"),
        ctx,
    )
    await _write(
        ctx,
        _value(TextContent, "x").set("Basil")
        >> TextContent.at((PLANE, "p"), "title").value.set("Garden"),
    )
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    link = ops.cell_state("c", item_picker.Link.address)
    try:
        # Every text, cells first, then planes.
        await _until(lambda: "Garden" in browser.shown("c1", "hit", "text"))
        assert "Basil" in browser.shown("c0", "hit", "text")
        assert "Nothing picked." in browser.shown("none")

        browser.notify((*browser.path("rows"), "c1", "pick"), None)
        picked = await _settles(ctx, link, lambda v: bool(v))
        assert picked == {"kind": kind_name(TextContent), "scope": [PLANE, "p"], "id": "title"}
        await _until(lambda: "Garden" in browser.shown("picked", "hit", "text"))

        browser.notify((*browser.path("hit")[:-1], "unpick"), None)
        await _settles(ctx, link.exists(), lambda v: not v)
    finally:
        task.cancel()


# --- examples ------------------------------------------------------------------------


async def _example(
    ctx: nu.Context, kind: object, first: tuple[str, ...]
) -> tuple[_Inputs, asyncio.Task]:
    await nu.arun(
        ops.add_plane("p", backend="async") >> ops.insert_snippet("p", kind.SNIPPET, cell_id="c"),
        ctx,
    )
    browser = _Inputs()
    task = await _running(ctx, "p", "c", browser)
    await _until(lambda: browser.shown(*first))
    return browser, task


async def test_password_draws_again_when_an_option_changes(ctx):
    browser, task = await _example(ctx, password, ("options", "symbols"))
    try:
        first = browser.shown("password")[-1]
        assert len(first) == 20
        browser.type("length", value=12)
        await _until(lambda: len(browser.shown("password")[-1]) == 12)
        browser.type("digits", value=False)
        browser.type("symbols", value=False)
        browser.type("upper", value=False)
        await _until(lambda: browser.shown("password")[-1].isalpha())
        # Generate draws a new one with the same options.
        last = browser.shown("password")[-1]
        # Never written, so no frame names it: its address is its sibling's.
        browser.notify((*browser.path("upper")[:-1], "generate"), None)
        await _until(lambda: browser.shown("password")[-1] != last)
        assert browser.shown("password")[-1].islower()
    finally:
        task.cancel()


async def test_converter_follows_either_side(ctx):
    browser, task = await _example(ctx, converter, ("right", "amount"))
    try:
        # 1 m on the left, in km on the right.
        assert browser.shown("left", "amount")[-1] == {"value": 1.0}
        assert browser.shown("right", "amount")[-1] == {"value": 0.001}
        browser.type("right", "amount", value=2)
        await _until(lambda: browser.shown("left", "amount")[-1] == {"value": 2000.0})

        # Temperature: 100 °C is 212 °F, and back.
        browser.type("kind", value="Temperature")
        await _until(lambda: browser.shown("right", "unit")[-1] == "°F")
        browser.type("left", "amount", value=100)
        await _until(lambda: browser.shown("right", "amount")[-1] == {"value": 212.0})
        browser.type("right", "amount", value=32)
        await _until(lambda: browser.shown("left", "amount")[-1] == {"value": 0.0})
    finally:
        task.cancel()
