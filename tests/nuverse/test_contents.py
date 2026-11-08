"""nuverse's content kinds: what each matches, how a hit draws, and the Cells' data found by kind."""

from __future__ import annotations

import datetime

import pytest
from _support.made import MADE

import nu
import nuspace
import nuverse
from nuspace.devices.web import search
from nuspace.devices.web.planes import ensure
from nuspace.places import inside
from nuspace.shapes import Space, State
from nuspace.shapes.content import CELL, PLANE, entries
from nuspace.specs import add_cell, content_spec, kind_name, space_registry
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.session import Session
from nuverse.cells.content import (
    checkbox,
    date_picker,
    number_input,
    select,
    slider,
    switch,
    table,
    text_editor,
    text_input,
)
from nuverse.cells.content._editing import DEFAULT_KIND, ITEM
from nuverse.contents.date import DateContent
from nuverse.contents.flag import FlagContent
from nuverse.contents.number import NumberContent
from nuverse.contents.row import RowContent
from nuverse.contents.text import TextContent


CONTENTS = nuverse.extension().contents


class _Browser(WsSession):
    """A session with no socket. Keeps the frames it is sent."""

    def __init__(self) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    def last(self, name: str) -> object:
        return next(f.payload for f in reversed(self.frames) if f.ref[-1] == name)


def _at(kind: type, key: str = "x", cell: str = "c") -> nu.Shape:
    """An item of ``kind`` on cell ``cell``, by content key."""
    return nuspace.at.cell(id=cell).content(kind)[key]


async def _put(store, *writes: nu.Nu) -> None:
    await store.do(nu.Sequential(*writes))


# --- registered ---------------------------------------------------------------------


def test_every_kind_is_registered_by_its_package_and_name():
    names = [kind_name(c.kind) for c in nuverse.extension().contents]
    assert names == [
        "nuverse.Text",
        "nuverse.Number",
        "nuverse.Flag",
        "nuverse.Date",
        "nuverse.Row",
    ]
    assert nuverse.extension().contents == CONTENTS
    assert [content_spec(n) for n in names] == list(CONTENTS)
    assert list(space_registry(extensions=["nuverse"]).contents) == names


def test_a_viewer_of_any_kind_shows_text_by_default():
    assert DEFAULT_KIND == kind_name(TextContent)


def test_each_kind_asks_by_its_keywords():
    fields = {c.label: [(f.name, f.input) for f in c.kind.form()] for c in CONTENTS}
    assert fields == {
        "Text": [("text", "text")],
        "Number": [("min", "number"), ("max", "number")],
        "Flag": [("on", "switch")],
        "Date": [("min", "text"), ("max", "text")],
        "Row": [("text", "text")],
    }


# --- match ----------------------------------------------------------------------------


async def test_text_matches_whole_words_ignoring_case(store):
    await _put(store, _at(TextContent).value.set("Water the Basil daily"))
    item = _at(TextContent)
    for asked, hit in [("basil", True), ("WATER THE", True), ("bas", False), ("mint", False)]:
        assert await store.read(TextContent.match(item, text=asked)) is hit, asked


async def test_number_matches_within_either_bound(store):
    await _put(store, _at(NumberContent).value.set(42.0))
    item = _at(NumberContent)
    cases = [
        ({"min": 10, "max": 50}, True),
        ({"min": 42}, True),
        ({"max": 42}, True),
        ({"min": 43}, False),
        ({"max": 41.5}, False),
        ({"min": 50, "max": 60}, False),
    ]
    for asked, hit in cases:
        assert await store.read(NumberContent.match(item, **asked)) is hit, asked


async def test_flag_matches_on_or_off(store):
    await _put(store, _at(FlagContent, "on").value.set(True))
    await _put(store, _at(FlagContent, "off").value.set(False))
    on, off = _at(FlagContent, "on"), _at(FlagContent, "off")
    assert await store.read(FlagContent.match(on, on=True)) is True
    assert await store.read(FlagContent.match(on, on=False)) is False
    assert await store.read(FlagContent.match(off, on=False)) is True


async def test_date_matches_within_iso_bounds(store):
    await _put(store, _at(DateContent).value.set(datetime.date(2026, 10, 6)))
    item = _at(DateContent)
    cases = [
        ({"min": "2026-10-01", "max": "2026-10-31"}, True),
        ({"min": "2026-10-06"}, True),
        ({"max": " 2026-10-06 "}, True),
        ({"max": "2026-10-05"}, False),
        ({"min": "2027-01-01"}, False),
    ]
    for asked, hit in cases:
        assert await store.read(DateContent.match(item, **asked)) is hit, asked


async def test_row_matches_words_in_any_cell(store):
    row = _at(RowContent, "r1")
    await _put(
        store,
        row.cells["name"].set("Mint"),
        row.cells["notes"].set("spreads fast"),
        row.cells["done"].set(False),
    )
    for asked, hit in [("mint", True), ("SPREADS", True), ("fast", True), ("basil", False)]:
        assert await store.read(RowContent.match(row, text=asked)) is hit, asked


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (TextContent, "Basil"),
        (NumberContent, 0.0),
        (FlagContent, False),
        (DateContent, datetime.date(2026, 10, 6)),
    ],
    ids=lambda v: getattr(v, "__name__", None),
)
async def test_asked_nothing_every_item_holding_a_value_matches(store, kind, value):
    await _put(store, _at(kind, "held").value.set(value))
    assert await store.read(kind.match(_at(kind, "held"))) is True
    assert await store.read(kind.match(_at(kind, "never"))) is False


@pytest.mark.parametrize(
    ("kind", "asked"),
    [
        (TextContent, {"text": "basil"}),
        (NumberContent, {"min": 0}),
        (NumberContent, {"max": 0}),
        (FlagContent, {"on": False}),
        (DateContent, {"max": "9999-12-31"}),
        (RowContent, {"text": "basil"}),
    ],
    ids=lambda v: getattr(v, "__name__", None) or ",".join(v),
)
async def test_an_item_never_written_is_nothing_to_find(store, kind, asked):
    assert await store.read(kind.match(_at(kind, "never"), **asked)) is False


async def test_a_row_never_written_is_not_listed(store):
    await _put(store, _at(RowContent, "r1").cells["name"].set("Mint"))
    assert await store.read(RowContent.match(_at(RowContent, "r1"))) is True
    assert await store.read(RowContent.match(_at(RowContent, "never"))) is False


# --- render_hit -------------------------------------------------------------------------


async def _drawn(store, term: nu.Nu) -> _Browser:
    """``term`` run in a browserless session: the frames it wrote."""
    browser = _Browser()
    await nu.arun(nuspace.atomic(term), store.ctx.bind(Session, browser))
    return browser


async def test_each_kind_draws_a_hit_on_one_line(store):
    row = _at(RowContent, "r1")
    await _put(
        store,
        _at(TextContent).value.set("Water the basil\ndaily"),
        _at(NumberContent).value.set(42.0),
        _at(FlagContent).value.set(True),
        _at(DateContent).value.set(datetime.date(2026, 10, 6)),
        row.cells["name"].set("Mint"),
        row.cells["done"].set(True),
        row.cells["notes"].set("spreads"),
    )
    texts = [
        (TextContent, "Water the basil daily"),
        (NumberContent, "42"),
        (DateContent, "2026-10-06"),
    ]
    for kind, shown in texts:
        assert (await _drawn(store, kind.render_hit(_at(kind)))).last("text") == shown
    drawn = await _drawn(store, RowContent.render_hit(row))
    assert drawn.last("text") in ("Mint · spreads", "spreads · Mint")
    badge = (await _drawn(store, FlagContent.render_hit(_at(FlagContent)))).last("badge")
    assert badge == {"label": "on", "variant": "ok"}


async def test_each_kind_draws_in_full(store):
    await _put(
        store,
        _at(TextContent).value.set("# Basil"),
        _at(NumberContent).value.set(7.5),
        _at(FlagContent).value.set(False),
    )
    assert (await _drawn(store, TextContent.render(_at(TextContent)))).last("body") == "# Basil"
    stat = (await _drawn(store, NumberContent.render(_at(NumberContent)))).last("stat")
    assert stat == {"value": "7.5"}
    badge = (await _drawn(store, FlagContent.render(_at(FlagContent)))).last("badge")
    assert badge == {"label": "off", "variant": "neutral"}


async def test_a_long_text_hit_is_cut(store):
    await _put(store, _at(TextContent).value.set("word " * 40))
    shown = (await _drawn(store, TextContent.render_hit(_at(TextContent)))).last("text")
    assert len(shown) == 81
    assert shown.endswith("…")


async def test_a_hit_on_an_item_never_written_draws_blank(store):
    for kind, shown in [(TextContent, ""), (NumberContent, "0"), (DateContent, "")]:
        assert (await _drawn(store, kind.render_hit(_at(kind, "never")))).last("text") == shown


# --- Cells keep their data in items -----------------------------------------------------


async def _plane(store, plane: str = "p", **kwargs: object) -> None:
    await store.do(nuspace.plane.add(plane, backend="async", **kwargs))


@pytest.mark.parametrize(
    ("module", "kind", "value"),
    [
        (text_editor, TextContent, "Basil likes sun"),
        (text_input, TextContent, "Basil"),
        (select, TextContent, "Two"),
        (number_input, NumberContent, 42.0),
        (slider, NumberContent, 7.5),
        (switch, FlagContent, True),
        (checkbox, FlagContent, True),
        (date_picker, DateContent, datetime.date(2026, 10, 6)),
    ],
    ids=lambda v: getattr(v, "__name__", "").rpartition(".")[2] or None,
)
async def test_an_editor_keeps_its_value_in_its_cells_value_item(store, module, kind, value):
    await _plane(store)
    await store.do(add_cell("p", module.CELL, id="c", fabrics=["ui"]))
    item = _at(kind, ITEM)
    await _put(store, item.value.set(value))
    assert ITEM == "value"
    assert await store.read(kind.match(item)) is True
    # Not in the cell's own state, which keeps only what configures it.
    assert "value" not in (await store.read(State.cells["c"].extract()) or {})


async def test_a_table_keeps_one_row_item_per_row(store):
    rows = nuspace.at.cell(id="c").content(RowContent)
    await _put(
        store,
        rows["r1"].cells["name"].set("Basil"),
        rows["r2"].cells["name"].set("Mint"),
    )
    assert sorted(await store.read(nu.list(rows.keys()))) == ["r1", "r2"]
    for key, name in [("r1", "Basil"), ("r2", "Mint")]:
        assert await store.read(RowContent.match(rows[key], text=name)) is True
    # A plane's items of the same kind are apart from a cell's of the same id.
    on_plane = nuspace.at.plane(id="c").content(RowContent)["r1"]
    assert await store.read(RowContent.match(on_plane)) is False


async def test_find_reaches_every_items_of_a_kind_from_a_program(store):
    await _put(
        store,
        _at(NumberContent, ITEM, cell="n").value.set(250.0),
        nuspace.at.plane(id="p").content(NumberContent)["budget"].value.set(40.0),
        _at(NumberContent, ITEM, cell="s").value.set(25.0),
    )
    found = await store.read(NumberContent.find(min=30))
    assert [(a["scope"], a["key"], item) for a, item in found] == [
        ([CELL, "n"], ITEM, {"value": 250.0}),
        ([PLANE, "p"], "budget", {"value": 40.0}),
    ]


# --- search, by kind ------------------------------------------------------------------


async def _hits(store, request: dict) -> list[tuple[str, list, str]]:
    """``request`` searched, its cell run where the test runs: the hits as ``(kind, scope, key)``."""
    await store.run(search.search(request, into=MADE))
    pid = await store.run(MADE)
    (cell,) = await store.read(nu.list(Space.planes[pid].cells.keys()))
    source = await store.read(Space.cells[cell].prog)
    namespace: dict = {}
    exec(compile(source, "search", "exec"), namespace)  # noqa: S102
    await store.run(inside(namespace["out"](), plane=pid, cell=cell))
    hits = nuspace.at.plane(id=pid).state(search.Search).hits
    found = await store.read(nu.If(hits.exists(), hits.extract(), nu.Literal([])))
    return [(h["kind"], list(h["scope"]), h["key"]) for h in found]


async def test_a_search_by_kind_finds_what_cells_keep(store):
    def kept(kind: type, cell: str, value: object) -> nu.Nu:
        return _at(kind, ITEM, cell=cell).value.set(value)

    await store.run(ensure())
    await _plane(store, name="Budget")
    made = [(number_input, "n"), (slider, "s"), (text_editor, "t"), (text_input, "i"), (table, "g")]
    for module, cid in made:
        await store.do(add_cell("p", module.CELL, id=cid, fabrics=["ui"]))
    await _put(
        store,
        kept(NumberContent, "n", 250.0),
        kept(NumberContent, "s", 25.0),
        kept(TextContent, "t", "Basil likes sun"),
        kept(TextContent, "i", "mint"),
        entries(RowContent, CELL, "g")["r1"].cells["name"].set("Basil"),
    )
    numbers = kind_name(NumberContent)
    assert await _hits(store, {numbers: {"min": 100}}) == [(numbers, [CELL, "n"], ITEM)]
    # Asked nothing, every number, a slider's too.
    assert sorted(await _hits(store, {numbers: {}})) == [
        (numbers, [CELL, "n"], ITEM),
        (numbers, [CELL, "s"], ITEM),
    ]
    # Two kinds at once: the text cell and the table's row, not the text input.
    texts, rows = kind_name(TextContent), kind_name(RowContent)
    found = await _hits(store, {texts: {"text": "basil"}, rows: {"text": "basil"}})
    assert found == [(texts, [CELL, "t"], ITEM), (rows, [CELL, "g"], "r1")]
