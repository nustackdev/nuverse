"""The root Log plane's own cells: what this is, and the store at a glance.

- :data:`INTRO`: what the planes under it do, with a link to each.
- :data:`OVERVIEW`: every stream with its newest entry, every series with
  its latest point. One entry or a small sample per name, the first
  :data:`~nulog.planes.consts.OVERVIEW_CAP` names of each.
"""

from __future__ import annotations

from .cells import cell


__all__ = ["INTRO", "OVERVIEW", "ROOT"]


INTRO = '''\
import nu
import nustd.ui
from nuspace.system.utils import snap
from nulog.planes.state import child

TEXT = """\\
### Logs and metrics, live

A nulog store, read as it is written: every stream of log entries and every metric series in it.

- **Messages** reads one stream, newest or oldest first, filtered by level and text. Click an entry to see it whole.
- **Metrics** charts one series over a window, from a sample: the same cost at a thousand points or a billion.
- **Config** picks the store and how often to read it. Changing it takes effect at once.

The store is opened read only, as a RocksDB secondary, so it is safe on a store another process is writing.
"""


class Links(nustd.ui.Row):
    messages = nustd.ui.LinkRef.slot()
    metrics = nustd.ui.LinkRef.slot()
    config = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    links = Links.slot(gap=4)


def to(ref, plane, made_by, label):
    def go(p):
        return nu.IfDo(nu.Str(p) != "", ref.set(href=nu.Str("/") + nu.Str(p), label=label))

    return nu.let(snap(child(plane, made_by)), go)


def out(plane):
    L = View.links
    links = (
        to(L.messages, plane, "nulog_messages", "Read messages")
        >> to(L.metrics, plane, "nulog_metrics", "Chart metrics")
        >> to(L.config, plane, "nulog_config", "Config")
    )
    return View.text.set(TEXT) >> links >> nu.ForeverDo(nu.Delay(3600.0))
'''


OVERVIEW = cell("""\
STREAMS = [
    {"key": "stream", "label": "Stream", "sortable": False},
    {"key": "newest", "label": "Newest", "width": 110, "sortable": False},
    {"key": "level", "label": "Level", "width": 90, "sortable": False},
    {"key": "message", "label": "Message", "sortable": False},
]
SERIES = [
    {"key": "series", "label": "Series", "sortable": False},
    {"key": "latest", "label": "Latest", "kind": "number", "width": 120, "sortable": False},
    {"key": "at", "label": "At", "width": 130, "sortable": False},
]


class Streams(nustd.ui.Card):
    table = nustd.ui.TableRef.slot(columns=STREAMS, row_key="stream", dense=True, label="Streams")


class Series(nustd.ui.Card):
    table = nustd.ui.TableRef.slot(columns=SERIES, row_key="series", dense=True, label="Series")


class Lists(nustd.ui.Grid):
    streams = Streams.slot(title="Streams", subtitle="Each with its newest entry")
    series = Series.slot(title="Series", subtitle="Each with its latest point")


class View(nustd.ui.Column):
    empty = nustd.ui.EmptyStateRef.slot()
    lists = Lists.slot(columns=2, min_width=360, gap=3)


def draw(said):
    v = nu.Dict(said)
    return View.lists.streams.table.set_rows(v["streams"]) >> View.lists.series.table.set_rows(v["series"])


def off(said):
    seen = nu.Dict(said)
    return View.lists.erase() >> View.empty.set(seen["title"], seen["note"])


def live(s):
    cap = consts.OVERVIEW_CAP

    def read():
        both = nu.let(reads.streams(cap), lambda names: nu.let(reads.series(cap), lambda kinds: reads.newest(names, kinds)))
        return nu.let(both, lambda b: fmt.overview(nu.List(b)[0], nu.List(b)[1], nustd.time.time()))

    return View.empty.erase() >> drawing(nu.ForeverDo(redraw(read(), draw) >> nu.Delay(s["every"])))


def out(plane):
    def follow(root):
        return following(root, lambda s: with_store(s, lambda: live(s), off))

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


ROOT = (("intro", INTRO), ("overview", OVERVIEW))
