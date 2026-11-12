"""nuverse's Cells, loaded the way the kernel loads them and run on a real store."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

import pytest

import nu
import nuspace
import nuverse
from nuspace.kernel.body import Rewrites
from nuspace.places import inside
from nuspace.shapes.content import CELL, PLANE, SPACE, kind_name
from nuspace.web.env import session_env
from nustd.ui.core import OP_NOTIFY, Frame, WsSession
from nustd.ui.core.session import Session
from nuverse.cells.content import (
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
from nuverse.cells.content._editing import BY_ID, BY_KEY, ITEM, Target
from nuverse.cells.debugging import (
    cell_content_lens,
    cell_lens,
    plane_content_lens,
    plane_lens,
    space_content_lens,
)
from nuverse.cells.examples import converter, password, ticker
from nuverse.contents.date import DateContent
from nuverse.contents.flag import FlagContent
from nuverse.contents.number import NumberContent
from nuverse.contents.row import RowContent
from nuverse.contents.text import TextContent


CELLS = nuverse.extension().cells


if TYPE_CHECKING:
    from collections.abc import Callable


Space = nuspace.Space


class _Browser(WsSession):
    """A session with no socket. Keeps frames, and plays the select's part.

    Attributes:
        select: The name of the select it plays.
    """

    select = "cell"

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []
        self.selected = ""

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)
        if frame.ref[-1] == self.select and isinstance(frame.payload, str):
            self.selected = frame.payload

    async def aread(self, path: tuple[str, ...]) -> object:
        assert path[-1] == self.select
        return self.selected

    def notify(self, path: tuple[str, ...], payload: object) -> None:
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=payload))

    def pick(self, cell_id: str) -> None:
        """What the dropdown does: select locally, notify with no payload."""
        self.selected = cell_id
        self.notify(self.path(self.select), None)

    def path(self, name: str) -> tuple[str, ...]:
        return next(f.ref for f in self.frames if f.ref[-1] == name)

    def last(self, name: str) -> object:
        return next(f.payload for f in reversed(self.frames) if f.ref[-1] == name)

    def options(self) -> list:
        """The dropdown's latest list."""
        writes = [f.payload for f in self.frames if f.ref[-1] == self.select]
        return next(w["options"] for w in reversed(writes) if isinstance(w, dict))


async def _until(check: Callable[[], bool], timeout: float = 3.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not check():
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.01)


# --- the space, as a test makes and reads it ---------------------------------------


async def _plane(store, plane: str = "p", **fields: object) -> None:
    """A plane on the async backend, one commit."""
    await store.do(nuspace.plane.add(id=plane, backend="async", **fields))


async def _cell(store, plane: str, prog: str, cell: str, **fields: object) -> None:
    """A cell from source, one commit."""
    await store.do(nuspace.cell.add(plane, prog, id=cell, **fields))


async def _spec_cell(store, spec: object, cell: str = "c", plane: str = "p") -> None:
    """A cell made from ``spec`` as ``cell``, on ``plane``, made first when missing."""
    if not await store.read(nuspace.plane.exists(plane)):
        await _plane(store, plane)
    await store.do(nuspace.specs.add_cell(plane, spec, id=cell))


async def _write(store, term: nu.Nu) -> None:
    """``term`` as a program would write it: one commit to the State store."""
    await store.do(term)


def _value(kind: type, cell: str = "c", key: str = ITEM) -> nu.Nu:
    """The ``value`` of an item of ``kind`` on ``cell``, by its address."""
    return nuspace.at.cell(id=cell).content(kind)[key].value


def _state(cell: str, shape: type) -> object:
    """``cell``'s own state, typed as ``shape``."""
    return nuspace.at.cell(id=cell).state(shape)


async def _load(store, plane: str, cell: str) -> nu.Nu:
    """The cell's program, loaded through the session env's rewrite, as a cell run loads it."""
    env = session_env("127.0.0.1:9")("s1")
    prog = Space.cells[cell].prog
    load = prog.load(scope={"plane": plane, "cell": cell}, rewrite=Rewrites(env.rewrite))
    return await store.run(nuspace.atomic(load))


async def _running(store, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell's program run as the kernel runs it: inside its ``Here`` frame."""
    term = inside(await _load(store, plane, cell), plane=plane, cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))


async def _settles(store, term: nu.Nu, check: Callable[[object], bool]) -> object:
    """``term`` read until ``check`` holds for it, then that value."""
    deadline = asyncio.get_running_loop().time() + 3.0
    while not check(value := await store.read(term)):
        assert asyncio.get_running_loop().time() < deadline, f"timed out on {value!r}"
        await asyncio.sleep(0.01)
    return value


async def _listening() -> None:
    """A beat for a running cell's reactions to subscribe after its first paint.

    An editor paints, then subscribes: a notify landing in between is lost,
    as it would be in a browser that typed within the same milliseconds.
    """
    await asyncio.sleep(0.1)


# --- lenses -------------------------------------------------------------------------


def _keys(columns: dict) -> dict:
    """``{key: preview}`` of a lens frame's first column."""
    return {e["key"]: e["preview"] for e in columns["columns"][0]["entries"]}


async def test_plane_lens_browses_its_own_plane(store):
    await _plane(store, name="Home")
    await _cell(store, "p", plane_lens.CELL.source, "me")
    browser = _Browser()
    task = await _running(store, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        shown = _keys(browser.last("lens"))
        assert shown["name"] == "Home"
        assert {"backend", "cells", "version"} <= set(shown)
        # State is in the other store: a lens on the plane does not see it.
        assert "state" not in shown
    finally:
        task.cancel()


async def test_cell_lens_follows_the_select(store):
    await _plane(store)
    await _cell(store, "p", cell_lens.CELL.source, "me", name="lens")
    await _cell(store, "p", "one", "c1")
    await _cell(store, "p", "two", "c2", name="second")
    await store.do(nuspace.cell.set_meta("c2", {"marker": 1}))
    browser = _Browser()
    task = await _running(store, "p", "me", browser)
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

        # A cell added shows up in the list, a cell removed leaves it.
        await _cell(store, "p", "three", "c3")
        await _until(lambda: browser.options()[-1] == {"value": "c3", "label": "c3"})
        await store.do(nuspace.cell.remove("c1"))
        await _until(lambda: {"value": "c1", "label": "c1"} not in browser.options())
    finally:
        task.cancel()


async def test_cell_lens_alone_on_its_plane_browses_itself(store):
    await _plane(store)
    await _cell(store, "p", cell_lens.CELL.source, "me")
    browser = _Browser()
    task = await _running(store, "p", "me", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
        assert browser.selected == "me"
        assert cell_lens.CELL.source.startswith(_keys(browser.last("lens"))["prog"][:20])
    finally:
        task.cancel()


# --- content lenses: one scope's items, by kind, raw and rendered -------------------


class _Lens(_Browser):
    """A content lens's session: its select picks the scope."""

    select = "pick"

    def shown(self, *names: str) -> list:
        """Every payload written to the ref ending in ``names``, oldest first."""
        return [f.payload for f in self.frames if f.ref[-len(names) :] == names]

    def column(self, index: int) -> dict:
        """``{key: preview}`` of the latest cascade's column ``index``, ``{}`` when it has none."""
        columns = self.last("lens")["columns"]
        return _rows(columns[index]) if index < len(columns) else {}

    async def nav(self, cursor: list[str]) -> None:
        """What a click does: the whole new cursor sent, then its cascade painted."""
        before = len(self.frames)
        self.notify(self.path("lens"), cursor)
        await _until(
            lambda: (
                any(f.ref[-1] == "lens" for f in self.frames[before:])
                and self.last("lens")["cursor"] == cursor
            )
        )


def _rows(column: dict) -> dict:
    return {e["key"]: e["preview"] for e in column["entries"]}


async def _painted(browser: _Lens) -> None:
    """The first cascade painted, and the lens listening for moves."""
    await _until(lambda: any(f.ref[-1] == "lens" for f in browser.frames))
    await _listening()


TEXT, NUMBER, FLAG = kind_name(TextContent), kind_name(NumberContent), kind_name(FlagContent)


def _item(kind: type, level: str, scope: str, key: str) -> nu.Nu:
    """An item's ``value`` at a place: a cell or a plane by id, or the space."""
    place = nuspace.at.space if level == SPACE else getattr(nuspace.at, level)(id=scope)
    return place.content(kind)[key].value


@pytest.mark.parametrize("module", [space_content_lens, plane_content_lens, cell_content_lens])
def test_a_content_lens_is_one_import_line(module):
    assert module.CELL.source == f"from {module.__name__} import out\n"
    assert module.CELL.group == "Debugging"


async def test_cell_content_lens_browses_a_cells_items_by_kind(store):
    await _plane(store)
    await _cell(store, "p", cell_content_lens.CELL.source, "me", name="lens")
    await _cell(store, "p", "one", "c1")
    await _write(
        store,
        _item(TextContent, CELL, "me", "value").set("# Basil")
        >> _item(NumberContent, CELL, "me", "n").set(42.0)
        >> _item(TextContent, CELL, "c1", "x").set("Thyme")
        >> _item(TextContent, PLANE, "p", "title").set("Garden"),
    )
    browser = _Lens()
    task = await _running(store, "p", "me", browser)
    try:
        # Its own cell first: the kinds holding its items, by title.
        await _painted(browser)
        assert browser.selected == "me"
        assert browser.options() == [
            {"value": "me", "label": "lens"},
            {"value": "c1", "label": "c1"},
        ]
        assert browser.column(0) == {NUMBER: "Number", TEXT: "Text"}

        # A kind: its content keys. An item: its stored fields, and drawn by its kind.
        await browser.nav([TEXT])
        assert browser.column(1) == {"value": ""}
        await browser.nav([TEXT, "value"])
        assert browser.column(2) == {"value": "# Basil"}
        await _until(lambda: browser.shown("drawn", "body")[-1:] == ["# Basil"])

        # A write repaints both, the cursor kept.
        await _write(store, _item(TextContent, CELL, "me", "value").set("# Thyme"))
        await _until(lambda: browser.column(2) == {"value": "# Thyme"})
        await _until(lambda: browser.shown("drawn", "body")[-1:] == ["# Thyme"])

        # Another cell picked: its items, from the root.
        browser.pick("c1")
        await _until(
            lambda: browser.last("lens")["cursor"] == [] and browser.column(0) == {TEXT: "Text"}
        )
        await browser.nav([TEXT])
        assert browser.column(1) == {"x": ""}
    finally:
        task.cancel()


async def test_plane_content_lens_browses_a_planes_own_items(store):
    await _plane(store, name="Home")
    await _plane(store, "q")
    await _plane(store, "r", name="Empty")
    await _cell(store, "p", plane_content_lens.CELL.source, "me")
    await _write(
        store,
        _item(TextContent, PLANE, "p", "title").set("Garden")
        >> _item(NumberContent, CELL, "me", "n").set(1.0)
        >> _item(FlagContent, PLANE, "q", "done").set(True),
    )
    browser = _Lens()
    task = await _running(store, "p", "me", browser)
    try:
        # Its own plane first, then the planes holding items: never every plane.
        await _painted(browser)
        assert browser.selected == "p"
        assert browser.options() == [
            {"value": "p", "label": "Home"},
            {"value": "q", "label": "q"},
        ]
        # Its cells' items left out.
        assert browser.column(0) == {TEXT: "Text"}
        await browser.nav([TEXT, "title"])
        assert browser.column(2) == {"value": "Garden"}
        await _until(lambda: browser.shown("drawn", "body")[-1:] == ["Garden"])

        browser.pick("q")
        await _until(lambda: browser.column(0) == {FLAG: "Flag"})
        await browser.nav([FLAG, "done"])
        assert browser.column(2) == {"value": "True"}

        # A plane's first item lists it.
        await _write(store, _item(NumberContent, PLANE, "r", "n").set(2.0))
        await _until(lambda: {"value": "r", "label": "Empty"} in browser.options())
    finally:
        task.cancel()


async def test_space_content_lens_browses_the_spaces_own_items(store):
    await _plane(store)
    await _cell(store, "p", space_content_lens.CELL.source, "me")
    await _write(
        store,
        _item(TextContent, SPACE, "", "readme").set("Hello")
        >> _item(NumberContent, PLANE, "p", "n").set(1.0),
    )
    browser = _Lens()
    task = await _running(store, "p", "me", browser)
    try:
        await _painted(browser)
        assert "pick" not in {f.ref[-1] for f in browser.frames}
        assert browser.column(0) == {TEXT: "Text"}
        await browser.nav([TEXT, "readme"])
        assert browser.column(1) == {"readme": ""}
        assert browser.column(2) == {"value": "Hello"}
        await _until(lambda: browser.shown("drawn", "body")[-1:] == ["Hello"])

        # A kind written later shows up.
        await _write(store, _item(NumberContent, SPACE, "", "n").set(3.0))
        await _until(lambda: browser.column(0) == {NUMBER: "Number", TEXT: "Text"})

        # A cursor naming no kind: one error column, the rest kept.
        await browser.nav(["nope", "x"])
        assert browser.column(0) == {NUMBER: "Number", TEXT: "Text"}
        assert list(browser.column(1)) == ["error"]
    finally:
        task.cancel()


# --- every Cell: a shim in the cell, the code in the package ------------------------


@pytest.mark.parametrize("spec", CELLS, ids=lambda s: s.name)
async def test_every_cell_runs_from_its_shim(store, spec):
    """The cell stores the shim and nothing else; loaded, it is the Cell's whole program."""
    await _spec_cell(store, spec)
    assert await store.read(Space.cells["c"].prog) == spec.source
    assert await store.read(Space.cells["c"].spec) == f"nuverse.{spec.name}"
    nu.validate(nu.compile(await _load(store, "p", "c")))


def test_every_cell_is_one_import_line_or_an_editable_lens():
    for spec in CELLS:
        lines = spec.source.strip().splitlines()
        if spec.group != "Debugging":
            assert lines == [f"from nuverse.cells.{_module(spec)} import out"], spec.name


def _module(spec: object) -> str:
    category = {"Examples": "examples"}.get(spec.group, "content")
    name = {"text": "text_editor"}.get(spec.name, spec.name)
    return f"{category}.{name}"


def _shown(browser: _Browser, text: str) -> Callable[[], bool]:
    """Whether the editor was handed ``text``."""
    return lambda: any(f.ref[-1] == "text" and f.payload == text for f in browser.frames)


async def test_text_editor_shows_what_a_program_writes_and_keeps_what_is_typed(store):
    await _spec_cell(store, text_editor.CELL)
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(_shown(browser, ""))
        await _write(store, _value(TextContent).set("Water the basil"))
        await _until(_shown(browser, "Water the basil"))
        browser.type("text", value="Basil likes sun")
        await _settles(store, _value(TextContent), lambda v: v == "Basil likes sun")
    finally:
        task.cancel()


async def test_add_cell_hands_the_new_cell_to_what_follows(store):
    """The id is minted when the term runs; ``into`` holds it for the writes after."""
    await _plane(store)
    made = nu.let(
        "",
        lambda cell: (
            nuspace.atomic(nuspace.specs.add_cell("p", text_editor.CELL, into=cell))
            >> nuspace.atomic(
                nuspace.at.cell(id=nu.Str(cell)).content(TextContent)[ITEM].value.set("Basil")
            )
        ),
    )
    await store.run(made >> made)
    first, second = await store.read(nu.list(Space.planes["p"].cells.keys()))
    assert first != second
    for cell in (first, second):
        assert await store.read(Space.cells[cell].spec) == "nuverse.text"
        assert await store.read(_value(TextContent, cell)) == "Basil"


async def test_table_seeds_once_and_stores_what_the_browser_asks(store):
    await _spec_cell(store, table.CELL)
    order = nu.ToList(_state("c", table.Sheet).order)
    name = nuspace.at.cell(id="c").content(RowContent)["r2"].cells["name"]
    browser = _Browser()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "table" for f in browser.frames))
        assert await store.read(order) == ["r1", "r2", "r3"]

        # An edit is stored as asked and shipped back.
        browser.notify(
            browser.path("table"),
            {"event": "edit", "key": "r2", "row_index": 1, "column": "name", "value": "Basil"},
        )
        await _settles(store, name, lambda v: v == "Basil")
        await _until(lambda: "Basil" in str(browser.last("table")))

        # A row added lands where asked under a fresh key; a delete takes it out again.
        browser.notify(browser.path("table"), {"event": "add", "index": 0})
        added = (await _settles(store, order, lambda v: len(v) == 4))[0]
        assert added not in ("r1", "r2", "r3")
        browser.notify(
            browser.path("table"), {"event": "delete", "keys": [added], "row_indexes": [0]}
        )
        await _settles(store, order, lambda v: v == ["r1", "r2", "r3"])
    finally:
        task.cancel()

    # A second run finds it seeded and leaves the rows alone.
    browser = _Browser()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(lambda: any(f.ref[-1] == "table" for f in browser.frames))
        assert await store.read(name) == "Basil"
        assert await store.read(order) == ["r1", "r2", "r3"]
    finally:
        task.cancel()


async def test_table_rows_are_the_cells_row_content(store):
    """The grid's typed rows and the place's row items are one mapping in State."""
    await _write(store, table.rows("c")["r1"].cells["name"].set("Basil"))
    placed = nuspace.at.cell(id="c").content(RowContent)
    assert await store.read(placed["r1"].cells["name"]) == "Basil"
    assert await store.read(RowContent.find(text="basil")) == [
        (
            {"kind": kind_name(RowContent), "scope": [CELL, "c"], "key": "r1"},
            {"cells": {"name": "Basil"}},
        )
    ]


async def test_a_row_a_program_adds_shows_last_and_leaves_the_order_alone(store):
    await _spec_cell(store, table.CELL)
    order = nu.ToList(_state("c", table.Sheet).order)
    browser = _Browser()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(lambda: _painted_whole(browser))
        rows = nuspace.at.cell(id="c").content(RowContent)
        await _write(store, rows["a0"].cells["name"].set("Mint"))
        await _until(lambda: "Mint" in str(browser.last("table")))
        assert await store.read(order) == ["r1", "r2", "r3"]
    finally:
        task.cancel()

    # Painted whole, it comes after every row the order names.
    browser = _Browser()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(lambda: _painted_whole(browser))
        whole = next(f.payload for f in browser.frames if f.ref[-1] == "table")
        keys = [row["_key"] for row in whole["rows"]]
        assert keys == ["r1", "r2", "r3", "a0"]
    finally:
        task.cancel()


def _painted_whole(browser: _Browser) -> bool:
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


async def _input(store, module: object, cell: str = "c") -> tuple[_Inputs, asyncio.Task]:
    """A cell of ``module`` made as ``cell`` on ``p``, running, its first paint done."""
    await _spec_cell(store, module.CELL, cell)
    browser = _Inputs()
    task = await _running(store, "p", cell, browser)
    await _until(lambda: browser.shown("entry") and browser.shown("entry", "input"))
    await _listening()
    return browser, task


async def test_number_input_stores_what_is_typed_and_shows_what_is_set(store):
    browser, task = await _input(store, number_input)
    try:
        # Labelled with the cell's name, bounded 0 to 100, a step of 1.
        assert {"label": "number_input"} in browser.shown("entry")
        assert {"min": 0.0} in browser.shown("entry", "input")
        assert {"max": 100.0} in browser.shown("entry", "input")
        assert {"step": 1.0} in browser.shown("entry", "input")

        browser.type("entry", "input", value=42)
        await _settles(store, _value(NumberContent), lambda v: v == 42.0)

        # Set by a program: the running cell shows it.
        await _write(store, _value(NumberContent).set(7.5))
        await _until(lambda: {"value": 7.5} in browser.shown("entry", "input"))

        # Config: a bound typed is stored in the cell's own state and applied.
        browser.type("settings", "min", value=-3)
        await _until(lambda: {"min": -3.0} in browser.shown("entry", "input"))
        assert await store.read(_state("c", number_input.Bounds).min) == -3.0

        # Renamed under Config: the cell is renamed.
        browser.type("settings", "name", value="budget")
        await _until(lambda: {"label": "budget"} in browser.shown("entry"))
        assert await store.read(Space.cells["c"].name) == "budget"
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
    store, module, kind, typed, stored, set_to, shown
):
    browser, task = await _input(store, module)
    try:
        browser.type("entry", "input", value=typed)
        await _settles(store, _value(kind), lambda v: v == stored)
        await _write(store, _value(kind).set(set_to))
        await _until(lambda: browser.shown("entry", "input")[-1] == shown)
        # Labelled by the cell's name, renamed from Config.
        browser.type("settings", "name", value="mine")
        await _until(lambda: {"label": "mine"} in browser.shown("entry"))
        assert await store.read(Space.cells["c"].name) == "mine"
    finally:
        task.cancel()


async def test_a_cleared_date_is_gone(store):
    browser, task = await _input(store, date_picker)
    try:
        assert browser.shown("entry", "input")[0] == ""
        browser.type("entry", "input", value="2026-10-06")
        await _settles(store, _value(DateContent), lambda v: v == datetime.date(2026, 10, 6))
        browser.type("entry", "input", value="")
        await _settles(store, _value(DateContent).exists(), lambda v: not v)
    finally:
        task.cancel()


async def test_select_options_come_from_config(store):
    browser, task = await _input(store, select)
    try:
        assert {"options": select.OPTIONS} in browser.shown("entry", "input")
        browser.type("settings", "options", value=["Red", "Blue"])
        await _until(lambda: browser.shown("entry", "input")[-1] == {"options": ["Red", "Blue"]})
        assert browser.shown("settings", "options")[-1] == ["Red", "Blue"]
        assert await store.read(nu.ToList(_state("c", select.Choice).options)) == ["Red", "Blue"]
    finally:
        task.cancel()


async def test_slider_range_comes_from_config(store):
    browser, task = await _input(store, slider)
    try:
        assert {"max": 100.0} in browser.shown("entry", "input")
        browser.type("settings", "max", value=10)
        await _until(lambda: {"max": 10.0} in browser.shown("entry", "input"))
        assert {"value": 10.0} in browser.shown("settings", "max")
    finally:
        task.cancel()


# --- one item, many editors ----------------------------------------------------------


async def test_config_points_an_editor_at_another_cells_item(store):
    mine, first = await _input(store, text_input, "a")
    theirs, second = await _input(store, text_input, "b")
    try:
        # Its Config shows where its item is: this cell's value, the scope by id.
        assert theirs.shown("item", "level", "input")[-1] == CELL
        assert theirs.shown("item", "key")[-1] == ""
        assert theirs.shown("scope", "by")[-1] == BY_ID

        mine.type("entry", "input", value="Basil")
        await _settles(store, _value(TextContent, "a"), lambda v: v == "Basil")

        # Pointed at a's item, b shows it and edits it.
        theirs.type("scope", "value", "input", value="a")
        target = _state("b", Target).target
        await _settles(store, target, lambda v: (v or {}).get("scope") == "a")
        await _until(lambda: theirs.shown("entry", "input")[-1] == "Basil")
        theirs.type("entry", "input", value="Thyme")
        await _settles(store, _value(TextContent, "a"), lambda v: v == "Thyme")
        await _until(lambda: mine.shown("entry", "input")[-1] == "Thyme")
        # b's own item was never written.
        assert await store.read(_value(TextContent, "b").exists()) is False
    finally:
        first.cancel()
        second.cancel()


@pytest.mark.parametrize(
    ("level", "scope", "key"), [(PLANE, "", "title"), (SPACE, "", "readme"), (CELL, "x", "v")]
)
async def test_a_program_points_an_editor_at_any_scope(store, level, scope, key):
    await _spec_cell(store, number_input.CELL)
    pointed = {"level": level, "scope": scope, "key": key}
    await _write(store, _state("c", Target).target.set(pointed))
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(lambda: browser.shown("entry", "input"))
        await _listening()
        browser.type("entry", "input", value=12)
        owner = {PLANE: "p", SPACE: "", CELL: scope}[level]
        await _settles(store, _item(NumberContent, level, owner, key), lambda v: v == 12.0)
    finally:
        task.cancel()


async def test_config_points_an_editor_at_a_cell_by_its_key(store):
    mine, first = await _input(store, text_input, "a")
    theirs, second = await _input(store, text_input, "b")
    try:
        await store.do(nuspace.cell.set_key("a", "herbs"))
        mine.type("entry", "input", value="Basil")
        await _settles(store, _value(TextContent, "a"), lambda v: v == "Basil")

        # Switched to key, the input holds a's key: b edits a's item.
        theirs.type("scope", "by", value=BY_KEY)
        theirs.type("scope", "value", "input", value="herbs")
        target = _state("b", Target).target
        await _settles(store, target, lambda v: (v or {}).get("scope") == "herbs")
        assert (await store.read(target))["by"] == BY_KEY
        await _until(lambda: theirs.shown("entry", "input")[-1] == "Basil")
        theirs.type("entry", "input", value="Thyme")
        await _settles(store, _value(TextContent, "a"), lambda v: v == "Thyme")
        assert await store.read(_value(TextContent, "b").exists()) is False
    finally:
        first.cancel()
        second.cancel()


async def test_an_editor_by_a_key_no_row_holds_says_so_and_follows_it_when_set(store):
    await _spec_cell(store, text_input.CELL, "a")
    await _write(store, _value(TextContent, "a").set("Basil"))
    await _spec_cell(store, text_input.CELL, "b")
    await _write(store, _state("b", Target).target.set({"scope": "herbs", "by": BY_KEY}))
    browser = _Inputs()
    task = await _running(store, "p", "b", browser)
    try:
        # Nothing holds the key: said on the entry, nothing written anywhere.
        await _until(lambda: {"error": "No cell has the key herbs"} in browser.shown("entry"))
        assert await store.read(_value(TextContent, "b").exists()) is False

        # The key set on a: resolved, the error cleared, a's item edited.
        await store.do(nuspace.cell.set_key("a", "herbs"))
        await _until(lambda: browser.shown("entry", "input")[-1:] == ["Basil"])
        assert browser.shown("entry")[-1] == {"error": ""}
        await _listening()
        browser.type("entry", "input", value="Thyme")
        await _settles(store, _value(TextContent, "a"), lambda v: v == "Thyme")
    finally:
        task.cancel()


# --- items of any kind ---------------------------------------------------------------


async def test_item_draws_any_item_in_full_and_again_when_it_changes(store):
    await _spec_cell(store, item.CELL)
    await _write(store, _value(TextContent).set("# Basil"))
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    try:
        # Left as it is: its own cell's text, drawn by the kind's render.
        await _until(lambda: browser.shown("body") and browser.shown("body")[-1] == "# Basil")
        await _write(store, _value(TextContent).set("# Thyme"))
        await _until(lambda: browser.shown("body")[-1] == "# Thyme")

        # Pointed at a number on the plane.
        await _write(store, _item(NumberContent, PLANE, "p", "n").set(42.0))
        number = kind_name(NumberContent)
        pointed = {"kind": number, "level": PLANE, "scope": "", "key": "n"}
        await _write(store, _state("c", Target).target.set(pointed))
        await _until(lambda: {"value": "42"} in browser.shown("stat"))
        assert browser.shown("which", "kind", "input")[-1] == number
        # The number written again: drawn again.
        await _write(store, _item(NumberContent, PLANE, "p", "n").set(7.0))
        await _until(lambda: {"value": "7"} in browser.shown("stat"))
    finally:
        task.cancel()


async def test_item_draws_a_plane_item_by_the_planes_key(store):
    await _spec_cell(store, item.CELL)
    await _plane(store, "q", key="pantry")
    await _write(store, _item(NumberContent, PLANE, "q", "n").set(42.0))
    pointed = {"kind": NUMBER, "level": PLANE, "scope": "pantry", "by": BY_KEY, "key": "n"}
    await _write(store, _state("c", Target).target.set(pointed))
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(lambda: {"value": "42"} in browser.shown("stat"))
        assert browser.shown("which", "scope", "by")[-1] == BY_KEY
        # The key dropped: nothing left to draw, and why.
        await store.do(nuspace.plane.remove_key("q"))
        await _until(lambda: "No plane has the key pantry" in browser.shown("note"))
    finally:
        task.cancel()


async def test_item_says_why_it_cannot_draw_a_kind_not_installed(store):
    await _spec_cell(store, item.CELL)
    await _write(store, _state("c", Target).target.set({"kind": "nowhere.Kind"}))
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    try:
        await _until(lambda: any("Cannot draw this item" in str(n) for n in browser.shown("note")))
    finally:
        task.cancel()


async def test_items_lists_adds_opens_and_removes(store):
    await _spec_cell(store, items.CELL)
    held = nuspace.at.cell(id="c").content(TextContent)
    await _write(store, held["one"].value.set("Basil"))
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    opened = _state("c", items.Open).opened
    try:
        # Each item a line drawn by its kind's render_hit.
        await _until(lambda: "Basil" in browser.shown("i_one", "hit", "text"))

        # Add: a new item under a fresh key, opened. Written by its address, as an
        # editor does, its line follows.
        browser.notify((*browser.path("lines")[:-1], "head", "add"), None)
        made = await _settles(store, opened, lambda v: bool(v))
        assert made.startswith("i_")
        assert sorted(await store.read(nu.list(held.keys()))) == sorted(["one", made])
        await _write(store, held[made].value.set("Thyme"))
        await _until(lambda: "Thyme" in browser.shown(f"i_{made}", "hit", "text"))

        # Open another, then remove it.
        browser.notify((*browser.path("lines"), "i_one", "open"), None)
        await _settles(store, opened, lambda v: v == "one")
        browser.notify((*browser.path("lines"), "i_one", "remove"), None)
        await _settles(store, nu.list(held.keys()), lambda v: v == [made])
        await _settles(store, opened, lambda v: v == "")
    finally:
        task.cancel()


async def test_item_picker_keeps_the_picked_items_address(store):
    await _spec_cell(store, item_picker.CELL)
    await _write(
        store,
        _value(TextContent, "x").set("Basil")
        >> _item(TextContent, PLANE, "p", "title").set("Garden"),
    )
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    link = _state("c", item_picker.Link).address
    try:
        # Every text, cells first, then planes.
        await _until(lambda: "Garden" in browser.shown("c1", "hit", "text"))
        assert "Basil" in browser.shown("c0", "hit", "text")
        assert "Nothing picked." in browser.shown("none")
        await _listening()

        browser.notify((*browser.path("rows"), "c1", "pick"), None)
        picked = await _settles(store, link, lambda v: bool(v))
        assert picked == {"kind": kind_name(TextContent), "scope": [PLANE, "p"], "key": "title"}
        await _until(lambda: "Garden" in browser.shown("picked", "hit", "text"))

        # A text written anywhere lists again.
        await _write(store, _item(TextContent, SPACE, "", "readme").set("Mint"))
        await _until(lambda: "Mint" in browser.shown("c2", "hit", "text"))

        browser.notify((*browser.path("hit")[:-1], "unpick"), None)
        await _settles(store, link.exists(), lambda v: not v)
    finally:
        task.cancel()


# --- examples ------------------------------------------------------------------------


async def _example(store, kind: object, first: tuple[str, ...]) -> tuple[_Inputs, asyncio.Task]:
    await _spec_cell(store, kind.CELL)
    browser = _Inputs()
    task = await _running(store, "p", "c", browser)
    await _until(lambda: browser.shown(*first))
    return browser, task


async def test_password_draws_again_when_an_option_changes(store):
    browser, task = await _example(store, password, ("options", "symbols"))
    try:
        first = browser.shown("password")[-1]
        assert len(first) == 20
        assert await store.read(_state("c", password.Pass).password) == first
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


async def test_converter_follows_either_side(store):
    browser, task = await _example(store, converter, ("right", "amount"))
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
        assert await store.read(_state("c", converter.Convert).kind) == "Temperature"
    finally:
        task.cancel()


async def test_ticker_counts_in_its_own_state(store):
    await _spec_cell(store, ticker.CELL)
    browser = _Browser()
    task = await _running(store, "p", "c", browser)
    try:
        await _settles(store, _state("c", ticker.Tick).n, lambda v: v == 1)
        await _until(lambda: any(f.payload == {"value": "1"} for f in browser.frames))
    finally:
        task.cancel()
