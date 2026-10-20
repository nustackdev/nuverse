"""The cells every Owlbridge page shares, and the root's own: the overview.

Every cell is ``def out(plane)``: the page it runs on comes in, and
:func:`~.kit.on_shop` lands the store at the root from there. A dashboard
cell is one :func:`~nuspace.system.utils.redraws`: it follows the tables
(``Shop.beat``) and the filters it reads, recomputes its view with
:func:`~.kit.read`, and redraws only what reads differently.

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
import nustd.time
import nustd.ui
from nuspace import ops
from nuspace.system.utils import redraws, snap
from nudemos.data import kit, views
from nudemos.data.kit import Shop, at
"""


def cell(body: str) -> str:
    """A cell's source: the shared imports, then ``body``."""
    return IMPORTS + "\n\n" + body


BAR = cell("""\
class Bar(nustd.ui.Row):
    dot = nustd.ui.StatusDotRef.slot(tone="neutral")
    line = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    bar = Bar.slot(gap=2, align="center")


def out(plane):
    def follow(root):
        read = views.status(Shop.stream.fallback({}), kit.live(root, "stream"), Shop.index.extract(),
                            Shop.pace.fallback("Busy"), nustd.time.time())
        draw = lambda v: View.bar.dot.set(v["tone"], pulse=v["pulse"]) >> View.bar.line.set(v["line"])
        return redraws([Shop.beat.on_change(), Shop.stream.on_change()], read, draw, every=1.0)

    return kit.on_shop(plane, follow)
""")


FILTERS = cell("""\
RANGES = ["Last 7 days", "Last 30 days", "Last 90 days", "Last 12 months", "All time"]
CHANNELS = ["All", "Web store", "Subscription", "Marketplace", "Wholesale", "Pop-up"]
CATEGORIES = ["All", "Blends", "Single origin", "Subscription", "Gear", "Merch"]


def pick(label, options):
    return type("Pick", (nustd.ui.Field,), {"choice": nustd.ui.SelectRef.slot(options=options)}).slot(label=label)


class Filters(nustd.ui.Grid):
    range = pick("Range", RANGES)
    channel = pick("Channel", CHANNELS)
    category = pick("Category", CATEGORIES)


class View(nustd.ui.Column):
    filters = Filters.slot(columns=3, min_width=180, gap=3)


def out(plane):
    def follow(root):
        F = View.filters
        shown = lambda f: F.range.choice.set(f["range"]) >> F.channel.choice.set(f["channel"]) >> F.category.choice.set(f["category"])
        asked = nu.Dict.of(range=nu.Str(F.range.choice), channel=nu.Str(F.channel.choice), category=nu.Str(F.category.choice))
        # One filter for the whole space: set here, every page that reads it moves.
        save = ops.atomic_state(at(root, Shop.filters.set(asked)))
        return nu.ParallelAsync(
            redraws([Shop.filters.on_change()], Shop.filters.fallback({}), shown),
            *(nu.ReactForever(p.choice.on_change(), save) for p in (F.range, F.channel, F.category)),
        )

    return kit.on_shop(plane, follow)
""")


# --- the overview ----------------------------------------------------------------------------


WELCOME = cell('''\
TEXT = """\\
Owlbridge roasts coffee in Portland and sells it four ways: the web store, a monthly subscription, \\
a marketplace, and wholesale to cafes. These are its numbers, live: orders land as they are placed, \\
exports dropped in the inbox are loaded in their own process, and every chart, table and metric here \\
is a small program you can open and change.
"""


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    ways = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(root):
        return View.about.set(TEXT) >> nu.let(snap(kit.pages(root)), lambda p: View.ways.set(views.ways(p))) >> nu.ForeverDo(nu.Delay(3600.0))

    # The first open writes two years of history and starts the jobs; every other cell waits for it.
    seeded = nu.let(snap(kit.root_of(plane)), lambda root: kit.seed(nu.Str(root)))
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

Tiles = type("Tiles", (nustd.ui.Grid,), {k: nustd.ui.StatRef.slot(label=v) for k, v in KEYS.items()})


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=4, min_width=180, gap=3)


def draw(t):
    tile = lambda k: getattr(View.tiles, k).set(t[k]["value"], delta=t[k]["delta"], trend=t[k]["trend"])
    return nu.IfDo(nu.Bool(t), nu.Sequential(*(tile(k) for k in KEYS)))


def out(plane):
    read = kit.read("kpis", tables=("lines", "people", "events"))
    return kit.on_shop(plane, lambda root: redraws([Shop.beat.on_change()], read, draw))
""")


TODAY = cell("""\
class Both(nustd.ui.Grid):
    today = nustd.ui.LineChart.slot(
        ("Today", "Same day last week"), title="Revenue today, hour by hour", x_type="category",
        y_format="${value}", height=280, colors=("var(--chart-1)", "var(--chart-neutral, #9aa0a6)"),
    )
    month = nustd.ui.BarChart.slot(
        ("Web store", "Subscription", "Marketplace", "Wholesale"), title="The last 30 days, by channel",
        stack=True, x_type="time", value_format="${value}", height=280, option={"legend": {"type": "plain"}},
    )


class View(nustd.ui.Column):
    both = Both.slot(columns=2, min_width=420, gap=4)


def out(plane):
    def build(root):
        draw = lambda v: nu.IfDo(nu.Bool(v), View.both.today.set(v["today"]) >> View.both.month.set(v["month"]))
        return redraws([Shop.beat.on_change()], kit.read("overview"), draw)

    return kit.on_shop(plane, build)
""")


FEED = cell("""\
COLUMNS = [
    {"key": "time", "label": "Time", "width": 90},
    {"key": "order", "label": "Order", "width": 100},
    {"key": "customer", "label": "Customer"},
    {"key": "items", "label": "Items"},
    {"key": "channel", "label": "Channel", "width": 120},
    {"key": "total", "label": "Total", "kind": "number", "width": 100},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    feed = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="order", dense=True, label="Orders as they land")


def out(plane):
    def build(root):
        return View.head.set("Orders as they land") >> redraws([Shop.feed.on_change()], Shop.feed.fallback([]), View.feed.set_rows)

    return kit.on_shop(plane, build)
""")


ROOT = (
    ("welcome", WELCOME),
    ("status", BAR),
    ("tiles", TILES),
    ("today", TODAY),
    ("feed", FEED),
)
