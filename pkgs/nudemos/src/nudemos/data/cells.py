"""The cells every Owlbridge page shares, and the root's own: the overview.

Every cell is ``def out(plane)``: the page it runs on comes in, and
:func:`~.kit.on_shop` brackets it over the store (:data:`~.kit.SHOP`), found
by the root's key. A dashboard
cell is one ``nu.Reconcile``: it follows the tables (``SHOP.beat``) and
the filters it reads, recomputes its view with :func:`~.kit.read`, and
redraws on every wake.

- :data:`BAR`: the stream's status in a line: on every dashboard.
- :data:`FILTERS`: the shared range, channel and category. Change it on any page, every page follows.
- The overview (:data:`ROOT`): the welcome, the headline tiles, today against last week, the month by
  channel, the orders as they land.
"""

from __future__ import annotations


__all__ = ["BAR", "FILTERS", "IMPORTS", "ROOT", "cell"]


#: What every cell imports.
IMPORTS = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.data import kit, views
from nudemos.data.kit import SHOP
"""


def cell(body: str) -> str:
    """A cell's source: the shared imports, then ``body``."""
    return IMPORTS + "\n\n" + body


BAR = cell("""\
class Bar(nustd.ui.Row):
    dot = nustd.ui.StatusDotRef.slot(tone="neutral")
    line = nustd.ui.TextRef.slot()


class View(nu.Shape):
    bar = Bar.slot(gap=2, align="center")


def out(plane):
    def follow(root):
        read = views.status(SHOP.stream.fallback({}), kit.live(root, "stream"), SHOP.index.extract(),
                            SHOP.pace.fallback("Busy"), nustd.time.time())
        draw = lambda v: View.bar.dot.set(v["tone"], pulse=v["pulse"]) >> View.bar.line.set(v["line"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change(), SHOP.stream.on_change()])), nu.let(nuspace.atomic(read), draw), every=1.0)

    return kit.on_shop(plane, follow)
""")


FILTERS = cell("""\
OPTIONS = {
    "range": ["Last 7 days", "Last 30 days", "Last 90 days", "Last 12 months", "All time"],
    "channel": ["All", "Web store", "Subscription", "Marketplace", "Wholesale", "Pop-up"],
    "category": ["All", "Blends", "Single origin", "Subscription", "Gear", "Merch"],
}
LABELS = {"range": "Range", "channel": "Channel", "category": "Category"}


class View(nu.Shape):
    filters = nustd.ui.GridRef.slot(max_columns=3, min_cell_width=180, gap=3)


# A labelled select per filter, each the control of a Field in the grid.
PICKS = {
    k: View.filters[k].to(nustd.ui.FieldRef.slot(label=LABELS[k])).control.to(nustd.ui.SelectRef.slot(options=v))
    for k, v in OPTIONS.items()
}


def out(plane):
    def follow(root):
        shown = lambda f: nu.Sequential(*(PICKS[k].set(f[k]) for k in OPTIONS))
        asked = nu.Dict.of(**{k: nu.Str(PICKS[k]) for k in OPTIONS})
        # One filter for the whole space: set here, every page that reads it moves.
        save = nuspace.atomic(SHOP.filters.set(asked))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.filters.on_change()])), nu.let(nuspace.atomic(SHOP.filters.fallback({})), shown)),
            *(nu.ReactEvery(p.on_change(), save) for p in PICKS.values()),
        )

    return kit.on_shop(plane, follow)
""")


# --- the overview ----------------------------------------------------------------------------


WELCOME = cell('''\
import nuspace.web as web

TEXT = """\\
Owlbridge roasts coffee in Portland and sells it four ways: the web store, a monthly subscription, \\
a marketplace, and wholesale to cafes. These are its numbers, live: orders land as they are placed, \\
exports dropped in the inbox are loaded in their own process, and every chart, table and metric here \\
is a small program you can open and change.
"""


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    ways = nustd.ui.GridRef.slot(max_columns=3, min_cell_width=220, gap=3)


def out(plane):
    def tiles(pages):
        # A tile per page, titled and marked off the store, with what it is for.
        tile = lambda key, what: nuspace.atomic(web.link(View.ways[key].to(nustd.ui.PageLinkRef.slot(variant="tile")), nu.Str(pages[key]), description=what))
        return nu.Sequential(*(tile(key, what) for key, what in views.PAGES))

    def build(root):
        return nu.let(nuspace.atomic(kit.pages(root)), tiles) >> nu.ForeverDo(nu.Delay(3600.0))

    # The first open writes two years of history and starts the jobs; every other cell waits for it.
    seeded = nu.let(nuspace.atomic(kit.ROOT_ID), lambda root: kit.seed(nu.Str(root)))
    return View.about.set(TEXT) >> seeded >> kit.on_shop(plane, build)
''')


TILES = cell("""\
KEYS = {
    "today": "Revenue today",
    "orders": "Orders today",
    "revenue": "Revenue, 30 days",
    "aov": "Average order",
    "conversion": "Web conversion",
    "subscribers": "Active subscribers",
    "margin": "Gross margin",
    "new": "New customers today",
}


class View(nu.Shape):
    tiles = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=4, min_cell_width=160, gap=3)


def draw(t):
    tile = lambda k: View.tiles[k][0].to(nustd.ui.StatRef).set(t[k]["value"], label=KEYS[k], delta=t[k]["delta"], trend=t[k]["trend"])
    return nu.IfDo(nu.Bool(t), nu.Sequential(*(tile(k) for k in KEYS)))


def out(plane):
    read = kit.read("kpis", tables=("lines", "people", "events"))
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change()])), nu.let(nuspace.atomic(read), draw)))
""")


TODAY = cell("""\
class View(nu.Shape):
    both = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)


today = View.both[0, 0].to(nustd.ui.LineChart.slot(
    ("Today", "Same day last week"), title="Revenue today, hour by hour", x_type="category",
    y_format="${value}", height=280, colors=("var(--chart-1)", "var(--chart-neutral, #9aa0a6)"),
))
month = View.both[0, 1].to(nustd.ui.BarChart.slot(
    ("Web store", "Subscription", "Marketplace", "Wholesale"), title="The last 30 days, by channel",
    stack=True, x_type="time", value_format="${value}", height=280, option={"legend": {"type": "plain"}},
))


def out(plane):
    def build(root):
        draw = lambda v: nu.IfDo(nu.Bool(v), today.set(v["today"]) >> month.set(v["month"]))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change()])), nu.let(nuspace.atomic(kit.read("overview")), draw))

    return kit.on_shop(plane, build)
""")


FEED = cell("""\
COLUMNS = [
    {"key": "time", "label": "Placed", "width": 120, "cell": nustd.ui.RelativeTimeRef},
    {"key": "order", "label": "Order", "width": 100},
    {"key": "customer", "label": "Customer"},
    {"key": "items", "label": "Items", "hide_below": 720},
    {"key": "channel", "label": "Channel", "width": 130, "cell": nustd.ui.BadgeRef.slot(size="sm"), "hide_below": 560},
    {"key": "total", "label": "Total", "kind": "number", "width": 100, "align": "end"},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Orders as they land", subtitle="newest first")


feed = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="order", density="compact", label="Orders as they land"))


def out(plane):
    def build(root):
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.feed.on_change()])), nu.let(nuspace.atomic(SHOP.feed.fallback([])), feed.set_rows))

    return kit.on_shop(plane, build)
""")


ROOT = (
    ("welcome", WELCOME),
    ("status", BAR),
    ("tiles", TILES),
    ("today", TODAY),
    ("feed", FEED),
)
