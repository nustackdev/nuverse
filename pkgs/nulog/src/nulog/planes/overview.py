"""The root Log plane's own cells: what this is, and the store at a glance.

- ``intro`` (:func:`intro`): what the planes under it do, a tile each that
  opens it.
- ``overview`` (:func:`out`): every stream with its newest entry, every
  series with its latest point, side by side. One entry or a small sample
  per name, the first :data:`~nulog.planes.consts.OVERVIEW_CAP` names of
  each, drawn again only when what they show changed.
"""

from __future__ import annotations

import nu
import nuspace
import nuspace.web as web
import nustd.ui as ui

from . import config, consts, fmt, messages, metrics, reads
from .state import child, following, root_of, with_store


__all__ = ["Intro", "View", "intro", "out"]


# ---- intro ------------------------------------------------------------------

TEXT = """\
### Logs and metrics, live

A nulog store, read as it is written: every stream of log entries and every metric series in it. \
The store is opened read only, as a RocksDB secondary, so it is safe on a store another process is writing.
"""

#: The planes the tiles open, as the root makes them.
PAGES = (messages.PLANE, metrics.PLANE, config.PLANE)


class Intro(nu.Shape):
    """The ``intro`` cell's root."""

    intro = ui.ColumnRef.slot(gap=4)


text = Intro.intro[0].to(ui.MarkdownRef)
pages = Intro.intro[1].to(ui.GridRef.slot(max_columns=3, min_cell_width=220, gap=3))


def intro(plane: nu.StrArg) -> nu.Nu:
    """The ``intro`` cell on the root ``plane``: what this is, and a tile per child plane."""

    def tile(i: int, spec: str, description: str) -> nu.Nu:
        to = pages[i].to(ui.PageLinkRef.slot(variant="tile"))

        def go(p: nu.Nu) -> nu.Nu:
            there = nu.Str(p)
            return nu.IfDo(
                there != "", nuspace.atomic(web.link(to, there, description=description))
            )

        return nu.let(nuspace.atomic(child(plane, spec)), go)

    tiles = (tile(i, p.name, p.description) for i, p in enumerate(PAGES))
    return text.set(TEXT) >> nu.Sequential(*tiles) >> nu.ForeverDo(nu.Delay(3600.0))


# ---- overview: two cards side by side, one under the other on a narrow pane --

STREAMS = [
    {"key": "stream", "label": "Stream", "wrap": "nowrap", "sortable": False},
    {
        "key": "newest",
        "label": "Newest",
        "width": 110,
        "cell": ui.RelativeTimeRef,
        "sortable": False,
    },
    {
        "key": "level",
        "label": "Level",
        "width": 90,
        "cell": ui.BadgeRef.slot(size="sm"),
        "sortable": False,
    },
    {"key": "message", "label": "Message", "wrap": "truncate", "sortable": False},
]
SERIES = [
    {"key": "series", "label": "Series", "wrap": "nowrap", "sortable": False},
    {"key": "latest", "label": "Latest", "kind": "number", "align": "end", "sortable": False},
    {"key": "at", "label": "At", "width": 110, "cell": ui.RelativeTimeRef, "sortable": False},
]


class View(nu.Shape):
    """The ``overview`` cell's root."""

    overview = ui.ColumnRef.slot(gap=4)


empty = View.overview[0].to(ui.EmptyStateRef)
board = View.overview[1].to(ui.GridRef.slot(cols="3fr 2fr", gap=4, stack_below=900))


def _card(r: int, c: int, title: str, subtitle: str) -> ui.CardRef:
    return board[r, c].to(
        ui.CardRef.slot(title=title, subtitle=subtitle, max_height=480, scroll="y")
    )


streams = _card(0, 0, "Streams", "Each with its newest entry")[0].to(
    ui.DataTableRef.slot(columns=STREAMS, row_key="stream", density="compact", label="Streams")
)
series = _card(0, 1, "Series", "Each with its latest point")[0].to(
    ui.DataTableRef.slot(columns=SERIES, row_key="series", density="compact", label="Series")
)


class Shown(nu.Shape):
    # This tab's: the rows last drawn, to draw again only on a change.
    rows = nu.ObjectRef.slot()


def draw(said: nu.Nu) -> nu.Nu:
    v = nu.Dict(said)
    both = streams.set_rows(v["streams"]) >> series.set_rows(v["series"])
    return nu.IfDo(Shown.rows != said, both >> Shown.rows.set(said))


def off(seen: nu.Dict) -> nu.Nu:
    return board.erase() >> Shown.rows.set(None) >> empty.set(seen["title"], seen["note"])


def live(s: nu.Dict) -> nu.Nu:
    cap = consts.OVERVIEW_CAP

    def read() -> nu.Nu:
        both = nu.let(
            reads.streams(cap),
            lambda names: nu.let(reads.series(cap), lambda kinds: reads.newest(names, kinds)),
        )
        return nu.let(both, lambda b: fmt.overview(nu.List(b)[0], nu.List(b)[1]))

    return empty.erase() >> nu.ForeverDo(nu.let(read(), draw) >> nu.Delay(s["every"]))


def out(plane: nu.StrArg) -> nu.Nu:
    """The ``overview`` cell on the root ``plane``: both tables, drawn again on a change."""

    def follow(root: nu.Str) -> nu.Nu:
        body = following(root, lambda s: with_store(s, lambda: live(s), off))
        return nu.Frame(Shown, body, rows=None)

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
