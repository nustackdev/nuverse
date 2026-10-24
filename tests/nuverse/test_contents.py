"""nuverse's content kinds: what each matches, how a hit draws, and the Cells' data found by kind."""

from __future__ import annotations

import datetime

import pytest
from tests.nuverse.test_cells import _Browser

import nu
import nustd.kv
import nuverse
from nuspace import ops
from nuspace.content import CELL, PLANE, info, kind_name
from nuspace.shapes import Reroot, Space, States
from nuspace.system import search
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core.session import Session
from nuverse.cells.content import (
    checkbox,
    date_picker,
    number_input,
    select,
    slider,
    switch,
    text_editor,
    text_input,
)
from nuverse.cells.content._editing import DEFAULT_KIND, ITEM
from nuverse.contents import (
    CONTENTS,
    DateContent,
    FlagContent,
    NumberContent,
    RowContent,
    TextContent,
)


def _at(kind: type, item_id: str = "x") -> nu.Shape:
    """An item of ``kind`` on cell ``c``."""
    return kind.at((CELL, "c"), item_id)


async def _put(store, *writes: nu.Nu) -> None:
    await store.run(ops.atomic_state(nu.Sequential(*writes)))


# --- registered ---------------------------------------------------------------------


def test_every_kind_is_registered_by_its_importable_name():
    names = [kind_name(k) for k in nuverse.extension().contents]
    assert names == [
        "nuverse.contents.text.TextContent",
        "nuverse.contents.number.NumberContent",
        "nuverse.contents.flag.FlagContent",
        "nuverse.contents.date.DateContent",
        "nuverse.contents.row.RowContent",
    ]
    assert nuverse.extension().contents == CONTENTS


def test_a_viewer_of_any_kind_shows_text_by_default():
    assert DEFAULT_KIND == kind_name(TextContent)


def test_each_kind_asks_by_its_keywords():
    fields = {k.title(): [(f["name"], f["input"]) for f in info(k)["fields"]] for k in CONTENTS}
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
    await nu.arun(ops.snapshot(term), store.ctx.bind(Session, browser))
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
    await store.run(
        ops.add_plane("p", ui=True, backend="async")
        >> ops.create_cell("p", module.CELL, cell_id="c")
    )
    item = kind.at((CELL, "c"), ITEM)
    await _put(store, item.value.set(value))
    assert ITEM == "value"
    assert await store.read(kind.match(item)) is True
    # Not in the cell's own state, which keeps only what configures it.
    assert "value" not in (await store.read(States.cells["c"].extract()) or {})


async def test_an_item_goes_with_its_cell(store):
    item = NumberContent.at((CELL, "c"), ITEM)
    await store.run(
        ops.add_plane("p", ui=True, backend="async")
        >> ops.create_cell("p", number_input.CELL, cell_id="c")
    )
    await _put(store, item.value.set(3.0))
    await store.run(ops.remove_cell("c"))
    assert await store.read(item.value.exists()) is False


async def test_a_table_keeps_one_row_item_per_row(store):
    rows = RowContent.items((CELL, "c"))
    await _put(
        store,
        rows["r1"].cells["name"].set("Basil"),
        rows["r2"].cells["name"].set("Mint"),
    )
    assert sorted(await store.read(nu.list(rows.keys()))) == ["r1", "r2"]
    for key, name in [("r1", "Basil"), ("r2", "Mint")]:
        item = RowContent.at((CELL, "c"), key)
        assert await store.read(RowContent.match(item, text=name)) is True
    # A plane's items of the same kind are apart from a cell's of the same id.
    assert await store.read(RowContent.match(RowContent.at((PLANE, "c"), "r1"))) is False


async def test_find_reaches_every_items_of_a_kind_from_a_program(store):
    await _put(
        store,
        NumberContent.at((CELL, "n"), ITEM).value.set(250.0),
        NumberContent.at((PLANE, "p"), "budget").value.set(40.0),
        NumberContent.at((CELL, "s"), ITEM).value.set(25.0),
    )
    found = await store.read(NumberContent.find(min=30))
    assert [(a["scope"], a["id"], item) for a, item in found] == [
        ([CELL, "n"], ITEM, {"value": 250.0}),
        ([PLANE, "p"], "budget", {"value": 40.0}),
    ]


# --- search, by kind ------------------------------------------------------------------


def _loaded(plane: str, cell: str) -> nu.Nu:
    """A search's cell loaded as the kernel loads it."""
    rewrite = Rewrites(Reroot(plane, cell))
    prog = Space.cells[cell].prog
    return nustd.kv.Snapshot(
        prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite), scope=Space
    )


async def _hits(store, request: dict) -> list[tuple[str, list, str]]:
    """``request`` searched, its cell run where the test runs: the hits as ``(kind, scope, id)``."""
    await store.run(search.search(request))
    pid = (await store.read(ops.children(search.SEARCHES)))[-1]
    (cell,) = await store.read(ops.cells(pid))
    await store.run(await store.run(_loaded(pid, cell)))
    hits = await store.read(ops.plane_state(pid, search.Search.hits.extract()))
    return [(h["kind"], list(h["scope"]), h["id"]) for h in hits]


async def test_a_search_by_kind_finds_what_cells_keep(store):
    def kept(kind: type, cell: str, value: object) -> nu.Nu:
        return kind.at((CELL, cell), ITEM).value.set(value)

    await store.run(
        ops.add_plane("p", name="Budget", ui=True, backend="async")
        >> ops.create_cell("p", number_input.CELL, cell_id="n")
        >> ops.create_cell("p", slider.CELL, cell_id="s")
        >> ops.create_cell("p", text_editor.CELL, cell_id="t")
        >> ops.create_cell("p", text_input.CELL, cell_id="i")
    )
    await _put(
        store,
        kept(NumberContent, "n", 250.0),
        kept(NumberContent, "s", 25.0),
        kept(TextContent, "t", "Basil likes sun"),
        kept(TextContent, "i", "mint"),
        RowContent.items((CELL, "g"))["r1"].cells["name"].set("Basil"),
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
