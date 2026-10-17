"""The Messages plane: one stream, read off either end, filtered, live.

- ``bar``: the store's state, as on every Log plane.
- ``messages``: pick a stream, newest or oldest first, how many, a level,
  a bit of text; the entries read in a table, newest first by default, with
  tiles over them. Click a row to see the entry whole in a drawer, its fields as JSON.

Each read takes ``count`` entries off one end of the stream: a bounded
cursor scan, O(count) however long the stream. The level and text filters
keep rows of that read only, never search the stream. The table is read
again every few seconds (the ``every`` setting) and on every change of a
picker, and drawn again only when what it shows changed. The stream list
follows the store: a new stream shows up in the picker on its own.
"""

from __future__ import annotations

from nuspace import Plane

from .cells import BAR, cell


__all__ = ["MESSAGES", "PLANE"]


MESSAGES = cell("""\
#: Seconds between looks at the stream list.
NAMES_EVERY = 2.0

COLUMNS = [
    {"key": "time", "label": "Time", "width": 150, "sortable": False},
    {"key": "level", "label": "Level", "width": 96, "sortable": False},
    {"key": "message", "label": "Message", "sortable": False},
    {"key": "fields", "label": "Fields", "sortable": False},
]


class StreamField(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(placeholder="No streams yet", searchable=True)


class ModeField(nustd.ui.Field):
    choice = nustd.ui.RadioGroupRef.slot(options=list(consts.MODE_OPTIONS), selected=consts.DEFAULT_MODE, orientation="horizontal")


class CountField(nustd.ui.Field):
    choice = nustd.ui.NumberInputRef.slot(min=consts.MIN_COUNT, max=consts.MAX_COUNT, step=50, default=consts.DEFAULT_COUNT)


class LevelField(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=list(consts.LEVEL_OPTIONS), selected=consts.DEFAULT_LEVEL)


class TextField(nustd.ui.Field):
    choice = nustd.ui.InputRef.slot(placeholder="Text in the message, then Enter")


class Pickers(nustd.ui.Grid):
    stream = StreamField.slot(label="Stream")
    mode = ModeField.slot(label="Read from")
    count = CountField.slot(label="How many")
    level = LevelField.slot(label="Level")
    text = TextField.slot(label="Filter")


class Tiles(nustd.ui.Grid):
    shown = nustd.ui.StatRef.slot(label="Shown")
    warnings = nustd.ui.StatRef.slot(label="Warnings")
    errors = nustd.ui.StatRef.slot(label="Errors")
    newest = nustd.ui.StatRef.slot(label="Newest")


class Entry(nustd.ui.Sheet):
    json = nustd.ui.JsonViewerRef.slot(expand_depth=3, copyable=True)


class Main(nustd.ui.Column):
    tiles = Tiles.slot(columns=4, min_width=140, gap=3)
    note = nustd.ui.TextRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, dense=True, label="Messages")
    entry = Entry.slot(title="Entry", side="right", size="lg")


class View(nustd.ui.Column):
    pickers = Pickers.slot(columns=5, min_width=150, gap=3)
    empty = nustd.ui.EmptyStateRef.slot()
    main = Main.slot(gap=3)


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


P, M = View.pickers, View.main


def tile(ref, t):
    return ref.set(t["value"], delta=t["delta"])


def draw(v):
    t, shown = M.tiles, nu.Dict(v["tiles"])
    tiles = tile(t.shown, shown["shown"]) >> tile(t.warnings, shown["warnings"]) >> tile(t.errors, shown["errors"]) >> tile(t.newest, shown["newest"])
    rows = M.note.set(v["empty"]) >> M.table.set_rows(v["rows"])
    return nu.IfDo(Pick.tiles != v["tiles"], tiles >> Pick.tiles.set(v["tiles"])) >> nu.IfDo(Pick.rows != v["rows"], rows >> Pick.rows.set(v["rows"]))


def paint():
    # One read of `count` entries, shaped once, drawn where it changed.
    got = nu.If(Pick.stream == "", nu.List.of(), reads.entries(Pick.stream, Pick.mode, Pick.count))

    def show(entries):
        shaped = fmt.messages(entries, Pick.level, Pick.text, nustd.time.time())
        return Pick.read.set(entries) >> nu.let(shaped, lambda v: draw(nu.Dict(v)))

    return nu.let(got, show)


def names():
    # New streams show up; a tab whose stream went away moves to the first one there is.
    def show(got):
        kept = fmt.pick(got, Pick.stream)
        moved = lambda k: nu.IfDo(nu.Str(k) != Pick.stream, Pick.stream.set(nu.Str(k)) >> P.stream.choice.set(nu.Str(k)) >> paint())
        return P.stream.choice.set_options(fmt.options(got)) >> nu.let(kept, moved)

    return redraw(reads.streams(), show)


def opened(e):
    # A row gone from the last read opens nothing.
    shown = nu.Dict(e)
    return nu.IfDo(nu.Is(e, None), nu.Noop(), M.entry.json.set_value(shown) >> M.entry.set(open=True, title=shown["title"]))


def picked():
    def on(field, keep):
        return nu.ReactForever(field.choice.on_change(), keep >> paint())

    count = fmt.bounded(P.count.choice, Pick.count, consts.MIN_COUNT, consts.MAX_COUNT)
    return [
        on(P.stream, Pick.stream.set(nu.Str(P.stream.choice))),
        on(P.mode, Pick.mode.set(nu.Str(P.mode.choice))),
        on(P.count, Pick.count.set(nu.int(count))),
        on(P.level, Pick.level.set(nu.Str(P.level.choice))),
        on(P.text, Pick.text.set(nu.Str(P.text.choice))),
        nu.ReactForever(M.table.on_row_click(), lambda ev: nu.let(fmt.entry(Pick.read, ev["key"]), opened)),
        # Closed in the tab (Esc, the backdrop, the button): the drawer stays open until told.
        nu.ReactForever(M.entry.on_change(), M.entry.set_open(False)),
    ]


def off(said):
    seen = nu.Dict(said)
    return View.main.erase() >> View.empty.set(seen["title"], seen["note"])


def live(s):
    # Drawn afresh: the main view was erased while the store was away.
    fresh = View.empty.erase() >> Pick.rows.set(None) >> Pick.tiles.set(None) >> Pick.read.set([])
    loops = [
        drawing(nu.ForeverDo(names() >> nu.Delay(NAMES_EVERY))),
        nu.ForeverDo(paint() >> nu.Delay(s["every"])),
    ]
    return fresh >> nu.ParallelAsync(*loops, *picked())


def placed():
    # A slot shows once it is first written, in the order written: the pickers come first.
    return (
        P.stream.choice.set_options([]) >> P.mode.choice.set(Pick.mode) >> P.count.choice.set_value(Pick.count)
        >> P.level.choice.set(Pick.level) >> P.text.choice.set(Pick.text)
    )


def out(plane):
    def view(s):
        return Pick.count.set(nu.int(s["count"])) >> placed() >> with_store(s, lambda: live(s), off)

    def follow(root):
        seeds = dict(stream="", mode=consts.DEFAULT_MODE, count=consts.DEFAULT_COUNT, level=consts.DEFAULT_LEVEL, text="")
        return nu.Frame(Pick, following(root, view), **seeds, read=[], rows=None, tiles=None)

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


PLANE = Plane(
    "nulog_messages",
    "Messages",
    icon="list",
    description="One log stream, read off either end, filtered, live.",
    meta={"editable": True, "full_width": True},
    cells=(("bar", BAR), ("messages", MESSAGES)),
    backend="async",
)
