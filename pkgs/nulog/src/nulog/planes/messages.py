"""The Messages plane: one stream, read off either end, filtered, live.

- ``bar``: the store's state, as on every Log plane.
- ``messages`` (:func:`out`): a toolbar to pick a stream, newest or oldest
  first, how many, a level, a bit of text; tiles over the read; the entries
  in a table, newest first by default. Click a row to see the entry whole
  in a drawer, its fields as JSON.

Each read takes ``count`` entries off one end of the stream: a bounded
cursor scan, O(count) however long the stream. The level and text filters
keep rows of that read only, never search the stream. The table is read
again every few seconds (the ``every`` setting) and on every change of a
picker, and drawn again only when what it shows changed. The stream list
follows the store: a new stream shows up in the picker on its own.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.time
import nustd.ui as ui
from nuspace.specs import PlaneSpec, WebOptions

from . import consts, fmt, reads
from .cells import BAR, MESSAGES
from .state import following, root_of, with_store


__all__ = ["PLANE", "View", "out"]


#: Seconds between looks at the stream list.
NAMES_EVERY = 2.0

COLUMNS = [
    {
        "key": "time",
        "label": "Time",
        "width": 150,
        "wrap": "nowrap",
        "sortable": False,
        "cell": ui.TextRef.slot(mono=True, size="sm"),
    },
    {
        "key": "level",
        "label": "Level",
        "width": 96,
        "sortable": False,
        "cell": ui.BadgeRef.slot(size="sm"),
    },
    {"key": "message", "label": "Message", "wrap": "truncate", "sortable": False},
    {
        "key": "fields",
        "label": "Fields",
        "wrap": "truncate",
        "hide_below": 720,
        "sortable": False,
        "cell": ui.TextRef.slot(mono=True, size="sm", tone="muted"),
    },
]

#: The tiles over the table, in order: what of the read each counts.
TILES = (("shown", "Shown"), ("warnings", "Warnings"), ("errors", "Errors"), ("newest", "Newest"))


# ---- the view ---------------------------------------------------------------
#
#   [ stream ][ read from ][ how many ][ level ][ filter.......... ]   one per line when narrow
#   [ shown ][ warnings ][ errors ][ newest ]
#   [ Entries: the table, scrolling inside its card                ]


class View(nu.Shape):
    """The ``messages`` cell's root."""

    messages = ui.ColumnRef.slot(gap=4)


tools = View.messages[0].to(
    ui.RowRef.slot(gap=3, align="end", stack_below=720, grow={0: 3, 1: 2, 2: 2, 3: 2, 4: 3})
)


def _picker(i: int, label: str) -> ui.FieldRef:
    return tools[i].to(ui.FieldRef.slot(label=label))


stream = _picker(0, "Stream").control.to(
    ui.SelectRef.slot(placeholder="No streams yet", searchable=True)
)
mode = _picker(1, "Read from").control.to(
    ui.RadioGroupRef.slot(
        options=list(consts.MODE_OPTIONS), selected=consts.DEFAULT_MODE, orientation="horizontal"
    )
)
count = _picker(2, "How many").control.to(
    ui.NumberInputRef.slot(
        min=consts.MIN_COUNT, max=consts.MAX_COUNT, step=50, default=consts.DEFAULT_COUNT
    )
)
level = _picker(3, "Level").control.to(
    ui.SelectRef.slot(options=list(consts.LEVEL_OPTIONS), selected=consts.DEFAULT_LEVEL)
)
text = _picker(4, "Filter").control.to(
    ui.InputRef.slot(placeholder="Text in the message, then Enter")
)

empty = View.messages[1].to(ui.EmptyStateRef)
main = View.messages[2].to(ui.ColumnRef.slot(gap=4))

tiles = main[0].to(ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=3))
stats = [
    tiles[i].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=label))
    for i, (_, label) in enumerate(TILES)
]

entries = main[1].to(ui.CardRef.slot(title="Entries", max_height=640, scroll="y"))
table = entries[0].to(
    ui.DataTableRef.slot(
        columns=COLUMNS, row_key="key", clickable_rows=True, density="compact", label="Messages"
    )
)

entry = main[2].to(ui.SheetRef.slot(title="Entry", side="right", width=560))
whole = entry[0].to(ui.JsonViewerRef.slot(expand_depth=3, copyable=True))


class Pick(nu.Shape):
    # This tab's: what the pickers say, the entries last read (for a click to find its row),
    # and the rows and tiles last drawn (to draw again only on a change).
    stream = nu.StrRef.slot()
    mode = nu.StrRef.slot()
    count = nu.IntRef.slot()
    level = nu.StrRef.slot()
    text = nu.StrRef.slot()
    read = nu.ObjectRef.slot()
    rows = nu.ObjectRef.slot()
    tiles = nu.ObjectRef.slot()


# ---- the program ------------------------------------------------------------


def draw(v: nu.Dict) -> nu.Nu:
    shown = nu.Dict(v["tiles"])
    counts = nu.Sequential(
        *(
            stats[i].set(shown[k]["value"], delta=shown[k]["delta"])
            for i, (k, _) in enumerate(TILES)
        )
    )
    rows = entries.set_caption(v["empty"]) >> table.set_rows(v["rows"])
    return nu.IfDo(Pick.tiles != v["tiles"], counts >> Pick.tiles.set(v["tiles"])) >> nu.IfDo(
        Pick.rows != v["rows"], rows >> Pick.rows.set(v["rows"])
    )


def paint() -> nu.Nu:
    # One read of `count` entries, shaped once, drawn where it changed.
    got = nu.If(Pick.stream == "", nu.List.of(), reads.entries(Pick.stream, Pick.mode, Pick.count))

    def show(read: nu.Nu) -> nu.Nu:
        shaped = fmt.messages(read, Pick.level, Pick.text, nustd.time.time())
        return Pick.read.set(read) >> nu.let(shaped, lambda v: draw(nu.Dict(v)))

    return nu.let(got, show)


def names() -> nu.Nu:
    # New streams show up; a tab whose stream went away moves to the first one there is.
    def show(got: nu.Nu) -> nu.Nu:
        def moved(k: nu.Nu) -> nu.Nu:
            to = nu.Str(k)
            return nu.IfDo(to != Pick.stream, Pick.stream.set(to) >> stream.set(to) >> paint())

        return stream.set_options(fmt.options(got)) >> nu.let(fmt.pick(got, Pick.stream), moved)

    return nu.let(reads.streams(), show)


def opened(e: nu.Nu) -> nu.Nu:
    # A row gone from the last read opens nothing.
    shown = nu.Dict(e)
    return nu.IfDo(
        nu.Is(e, None),
        nu.Noop(),
        whole.set_value(shown) >> entry.set(open=True, title=shown["title"]),
    )


def picked() -> list[nu.Nu]:
    def on(control: ui.Ref, keep: nu.Nu) -> nu.Nu:
        return nu.ReactEvery(control.on_change(), keep >> paint())

    held = fmt.bounded(count, Pick.count, consts.MIN_COUNT, consts.MAX_COUNT)
    return [
        on(stream, Pick.stream.set(nu.Str(stream))),
        on(mode, Pick.mode.set(nu.Str(mode))),
        on(count, Pick.count.set(nu.int(held))),
        on(level, Pick.level.set(nu.Str(level))),
        on(text, Pick.text.set(nu.Str(text))),
        nu.ReactEvery(
            table.on_row_click(), lambda ev: nu.let(fmt.entry(Pick.read, ev["key"]), opened)
        ),
        # Closed in the tab (Esc, the backdrop, the button): the drawer stays open until told.
        nu.ReactEvery(entry.on_change(), entry.set_open(False)),
    ]


def off(seen: nu.Dict) -> nu.Nu:
    return main.erase() >> empty.set(seen["title"], seen["note"])


def live(s: nu.Dict) -> nu.Nu:
    # Drawn afresh: the main view was erased while the store was away.
    fresh = empty.erase() >> Pick.rows.set(None) >> Pick.tiles.set(None) >> Pick.read.set([])
    loops = [
        nu.ForeverDo(names() >> nu.Delay(NAMES_EVERY)),
        nu.ForeverDo(paint() >> nu.Delay(s["every"])),
    ]
    return fresh >> nu.ParallelAsync(*loops, *picked())


def out(plane: nu.StrArg) -> nu.Nu:
    """The ``messages`` cell on ``plane``: the toolbar, the tiles and the table, live."""

    def view(s: nu.Dict) -> nu.Nu:
        shown = (
            stream.init()
            >> mode.set(Pick.mode)
            >> count.set_value(Pick.count)
            >> level.set(Pick.level)
            >> text.set(Pick.text)
        )
        return Pick.count.set(nu.int(s["count"])) >> shown >> with_store(s, lambda: live(s), off)

    def follow(root: nu.Str) -> nu.Nu:
        return nu.Frame(
            Pick,
            following(root, view),
            stream="",
            mode=consts.DEFAULT_MODE,
            count=consts.DEFAULT_COUNT,
            level=consts.DEFAULT_LEVEL,
            text="",
            read=[],
            rows=None,
            tiles=None,
        )

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))


PLANE = PlaneSpec(
    "nulog_messages",
    "Messages",
    icon="list",
    description="One log stream, read off either end, filtered, live.",
    web=WebOptions(editable=True, full_width=True),
    cells=(("bar", BAR), ("messages", MESSAGES)),
    backend="async",
)
