"""The pages under the overview, as Planes and their cells' sources.

Every dashboard cell is the same few lines: :func:`~.kit.read` a view from
:mod:`.calc`, follow what it depends on, draw. The pages:

- Revenue, Funnel, Cohorts, Customers (a page per customer, made on a
  click), Products (the catalog as a sheet), Forecast (what-ifs), Metrics (a
  cell per metric), Events (the web events, queried), Imports (the inbox),
  Sources (the tables and the stream).
"""

from __future__ import annotations

from nuspace import Plane

from .cells import BAR, FILTERS, cell


__all__ = ["CUSTOMER_CELLS", "PAGES"]


def _page(name: str, label: str, icon: str, description: str, cells: tuple) -> Plane:
    return Plane(
        f"data_{name}",
        label,
        icon=icon,
        description=description,
        meta={"editable": True, "full_width": True},
        cells=cells,
        backend="async",
    )


def _tiles(keys: dict[str, str], columns: int) -> str:
    """The source of a row of stat tiles, ``Tiles`` with a StatRef per key."""
    return (
        f"KEYS = {keys!r}\n\n"
        'Tiles = type("Tiles", (nustd.ui.Grid,), {k: nustd.ui.StatRef.slot(label=v) for k, v in KEYS.items()})\n'
        f"TILES = dict(columns={columns}, min_width=120, gap=3)\n"
    )


# --- revenue --------------------------------------------------------------------------------


REVENUE_CHARTS = cell(
    _tiles(
        {
            "revenue": "Revenue",
            "orders": "Orders",
            "aov": "Average order",
            "margin": "Gross margin",
            "units": "Units sold",
        },
        5,
    )
    + """

class Charts(nustd.ui.Grid):
    curve = nustd.ui.BarChart.slot(
        ("Web store", "Subscription", "Marketplace", "Wholesale"), title="Revenue by channel",
        x_type="time", stack=True, value_format="${value}", height=320, option={"legend": {"type": "plain"}},
    )
    cats = nustd.ui.BarChart.slot(title="By category", horizontal=True, value_format="${value}", height=320)


class View(nustd.ui.Column):
    tiles = Tiles.slot(**TILES)
    charts = Charts.slot(columns=2, min_width=380, gap=4)


def draw(v):
    tile = lambda k: getattr(View.tiles, k).set(v["tiles"][k][0], delta=v["tiles"][k][1], trend=v["tiles"][k][2])
    charts = View.charts.curve.set(v["series"]) >> View.charts.cats.set(v["cats"])
    return nu.IfDo(nu.Bool(v), nu.Sequential(*(tile(k) for k in KEYS)) >> charts)


def out(plane):
    read = kit.read("revenue", Shop.filters.fallback({}))
    return kit.on_shop(plane, lambda root: redraws(kit.changes(), read, draw))
"""
)


MONTHS = cell("""\
# The sheet's columns. Margin and the change on the month before are derived: computed, not stored.
COLUMNS = [
    {"key": "month", "label": "Month"},
    {"key": "revenue", "label": "Revenue, $", "kind": "number"},
    {"key": "orders", "label": "Orders", "kind": "number"},
    {"key": "aov", "label": "Average order, $", "kind": "number"},
    {"key": "margin", "label": "Margin, %", "kind": "number"},
    {"key": "change", "label": "vs month before, %", "kind": "number"},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    sheet = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="month", dense=True, label="Months")


def out(plane):
    read = kit.read("revenue", Shop.filters.fallback({}))
    draw = lambda v: nu.IfDo(nu.Bool(v), View.sheet.set_rows(v["months"]))
    return View.head.set("Month by month") >> kit.on_shop(plane, lambda root: redraws(kit.changes(), read, draw))
""")


REVENUE = _page(
    "revenue",
    "Revenue",
    "lucide:wallet",
    "Revenue by day, channel and category, under the shared filters.",
    (("status", BAR), ("filters", FILTERS), ("charts", REVENUE_CHARTS), ("months", MONTHS)),
)


# --- funnel ---------------------------------------------------------------------------------


TRAFFIC = cell("""\
RANGES = ["Last 7 days", "Last 30 days", "Last 90 days", "Last 12 months"]
SOURCES = ["All", "Organic search", "Instagram", "Newsletter", "Paid search", "Referral", "Direct"]
DEVICES = ["All", "Mobile", "Desktop", "Tablet"]


def pick(label, options):
    return type("Pick", (nustd.ui.Field,), {"choice": nustd.ui.SelectRef.slot(options=options)}).slot(label=label)


class Traffic(nustd.ui.Grid):
    range = pick("Range", RANGES)
    source = pick("Traffic source", SOURCES)
    device = pick("Device", DEVICES)


class View(nustd.ui.Column):
    filters = Traffic.slot(columns=3, min_width=180, gap=3)


def out(plane):
    def follow(root):
        F = View.filters
        shown = lambda f: F.range.choice.set(f["range"]) >> F.source.choice.set(f["source"]) >> F.device.choice.set(f["device"])
        asked = nu.Dict.of(range=nu.Str(F.range.choice), source=nu.Str(F.source.choice), device=nu.Str(F.device.choice))
        save = ops.atomic_state(at(root, Shop.traffic.set(asked)))
        return nu.ParallelAsync(
            redraws([Shop.traffic.on_change()], Shop.traffic.fallback({}), shown),
            *(nu.ReactForever(p.choice.on_change(), save) for p in (F.range, F.source, F.device)),
        )

    return kit.on_shop(plane, follow)
""")


FUNNEL_CHARTS = cell("""\
STEPS = [
    {"key": "stage", "label": "Stage"},
    {"key": "sessions", "label": "Sessions", "kind": "number"},
    {"key": "of_prev", "label": "Of step before, %", "kind": "number"},
    {"key": "of_all", "label": "Of all, %", "kind": "number"},
]


class Top(nustd.ui.Grid):
    funnel = nustd.ui.FunnelChart.slot(title="Sessions down the funnel", sort="none", label_format="{b}", height=320,
                                       option={"series": [{"minSize": "22%"}]})
    steps = nustd.ui.TableRef.slot(columns=STEPS, row_key="stage", dense=True, label="Funnel steps")


class Rates(nustd.ui.Grid):
    source = nustd.ui.BarChart.slot(title="Purchase rate by source, %", horizontal=True, height=260)
    device = nustd.ui.BarChart.slot(title="Purchase rate by device, %", horizontal=True, height=260)


class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot()
    top = Top.slot(columns=2, min_width=380, gap=4)
    rates = Rates.slot(columns=2, min_width=380, gap=4)
    trend = nustd.ui.LineChart.slot(title="Purchase rate by day, %", x_type="time", height=240)


@nu.host
def note(v):
    return f"{v['stages'][0][1]:,} sessions counted from {v['scanned']:,} web events in {v['ms']:.0f} ms, every time the data moves."


def draw(v):
    return nu.IfDo(nu.Bool(v),
        View.note.set(note(v)) >> View.top.funnel.set(v["stages"]) >> View.top.steps.set_rows(v["steps"])
        >> View.rates.source.set(v["by_source"]) >> View.rates.device.set(v["by_device"])
        >> View.trend.set(v["trend"]["Purchase rate"])
    )


def out(plane):
    read = kit.read("funnel", Shop.traffic.fallback({}), tables=("events",))
    return kit.on_shop(plane, lambda root: redraws([Shop.beat.on_change(), Shop.traffic.on_change()], read, draw))
""")


FUNNEL = _page(
    "funnel",
    "Funnel",
    "lucide:chart-pie",
    "From session to purchase, by source and device.",
    (("status", BAR), ("traffic", TRAFFIC), ("funnel", FUNNEL_CHARTS)),
)


# --- cohorts --------------------------------------------------------------------------------


COHORTS = cell("""\
METRICS = ["Retention", "Revenue per customer"]
ROWS = [
    {"key": "cohort", "label": "First order in"},
    {"key": "customers", "label": "Customers", "kind": "number"},
    {"key": "m1", "label": "Month 1", "kind": "number"},
    {"key": "m3", "label": "Month 3", "kind": "number"},
    {"key": "m6", "label": "Month 6", "kind": "number"},
]


class Pick(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=METRICS)


class Below(nustd.ui.Grid):
    curves = nustd.ui.LineChart.slot(
        (), title="What a customer has spent, months after their first order", x_type="category",
        y_format="${value}", legend=True, height=300,
    )
    table = nustd.ui.TableRef.slot(columns=ROWS, row_key="cohort", dense=True, label="Cohorts")


class View(nustd.ui.Column):
    metric = Pick.slot(label="Show")
    heat = nustd.ui.HeatmapChart.slot(title="Monthly cohorts", labels=True, height=420, x_label="Months since first order")
    below = Below.slot(columns=2, min_width=380, gap=4)


def draw(v):
    return nu.IfDo(nu.Bool(v),
        View.heat.set(v["cells"]) >> View.below.curves.set(v["curves"])
        >> View.below.table.set_rows(v["rows"])
    )


def out(plane):
    def build(root):
        save = ops.atomic_state(at(root, Shop.cohort.set(nu.Str(View.metric.choice))))
        read = kit.read("cohorts", Shop.cohort.fallback("Retention"))
        return nu.ParallelAsync(
            redraws([Shop.cohort.on_change()], Shop.cohort.fallback("Retention"), View.metric.choice.set),
            redraws([Shop.beat.on_change(), Shop.cohort.on_change()], read, draw, every=60.0),
            nu.ReactForever(View.metric.choice.on_change(), save),
        )

    return kit.on_shop(plane, build)
""")


COHORT_PAGE = _page(
    "cohorts",
    "Cohorts",
    "lucide:layers",
    "Customers by the month of their first order, and how many came back.",
    (("cohorts", COHORTS),),
)


# --- customers ------------------------------------------------------------------------------


TOP = cell("""\
COLUMNS = [
    {"key": "rank", "label": "#", "kind": "number", "width": 60},
    {"key": "name", "label": "Customer"},
    {"key": "kind", "label": "Type", "width": 110},
    {"key": "city", "label": "City"},
    {"key": "orders", "label": "Orders", "kind": "number", "width": 90},
    {"key": "spend", "label": "Spent in range, $", "kind": "number"},
    {"key": "lifetime", "label": "Lifetime, $", "kind": "number"},
    {"key": "last", "label": "Last order"},
]


class Side(nustd.ui.Grid):
    mix = nustd.ui.PieChart.slot(title="Revenue by customer type", donut=True, legend=True, labels=False, height=280)
    new = nustd.ui.BarChart.slot(("New", "Returning"), title="New against returning, by week", stack=True, x_type="time",
                                 value_format="${value}", height=280)


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    side = Side.slot(columns=2, min_width=380, gap=4)
    head = nustd.ui.HeadingRef.slot(level=4)
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, dense=True, label="Top customers")


def draw(v):
    return nu.IfDo(nu.Bool(v),
        View.side.mix.set(v["mix"]) >> View.side.new.set(v["new_returning"]) >> View.head.set(views.top_head(v["count"]))
        >> View.table.set_rows(v["rows"])
    )


def out(plane):
    def build(root):
        def opened(ev):
            cid = nu.Str(ev["key"])
            name = snap(kit.read("who", cid))
            return kit.open_customer(root, cid, name, plane, View.nav)

        read = kit.read("customers", Shop.filters.fallback({}))
        return nu.ParallelAsync(redraws(kit.changes(), read, draw), nu.ReactForever(View.table.on_row_click(), opened))

    return kit.on_shop(plane, build)
""")


CUSTOMERS = _page(
    "customers",
    "Customers",
    "lucide:users",
    "The best customers under the shared filters; each opens a page of their own.",
    (("status", BAR), ("filters", FILTERS), ("top", TOP)),
)


PROFILE = cell(
    _tiles(
        {
            "lifetime": "Lifetime spend",
            "orders": "Orders",
            "aov": "Average order",
            "last": "Last order",
            "rank": "Rank",
        },
        5,
    )
    + """

class Who(nustd.ui.Column):
    name = nustd.ui.HeadingRef.slot(level=2)
    line = nustd.ui.TextRef.slot()


class Head(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="xl")
    who = Who.slot(gap=1)


class Charts(nustd.ui.Grid):
    curve = nustd.ui.AreaChart.slot(title="Spend over time, cumulative", x_type="time", y_format="${value}", height=260)
    buys = nustd.ui.BarChart.slot(title="What they buy, $", horizontal=True, height=260)


class View(nustd.ui.Column):
    head = Head.slot(gap=4)
    tiles = Tiles.slot(**TILES)
    charts = Charts.slot(columns=2, min_width=360, gap=4)


def draw(v):
    tile = lambda k: getattr(View.tiles, k).set_value(v["tiles"][k])
    return (
        View.head.face.set_name(v["name"]) >> View.head.who.name.set(v["name"]) >> View.head.who.line.set(v["line"])
        >> nu.Sequential(*(tile(k) for k in KEYS)) >> View.charts.curve.set(v["curve"]) >> View.charts.buys.set(v["buys"])
    )


def out(plane):
    def build(root):
        read = kit.read("customer", nu.ToInt(kit.subject(plane)))
        return redraws([Shop.beat.on_change()], read, lambda v: nu.IfDo(nu.Bool(v), draw(v)))

    return kit.on_shop(plane, build)
"""
)


ORDERS = cell("""\
COLUMNS = [
    {"key": "order", "label": "Order", "width": 110},
    {"key": "date", "label": "Placed"},
    {"key": "channel", "label": "Channel", "width": 120},
    {"key": "items", "label": "Items"},
    {"key": "total", "label": "Total, $", "kind": "number", "width": 110},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    orders = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="order", dense=True, label="Orders")


def out(plane):
    def build(root):
        read = kit.read("customer", nu.ToInt(kit.subject(plane)))
        return redraws([Shop.beat.on_change()], read, lambda v: nu.IfDo(nu.Bool(v), View.orders.set_rows(v["rows"])))

    return View.head.set("Every order, newest first") >> kit.on_shop(plane, build)
""")


CUSTOMER_CELLS = (("profile", PROFILE), ("orders", ORDERS))


# --- products -------------------------------------------------------------------------------


SHEET = cell("""\
# What we set is editable: name, price, cost, stock. The rest is derived from the orders, every time they move.
COLUMNS = [
    {"key": "name", "label": "Product"},
    {"key": "category", "label": "Category", "editable": False},
    {"key": "price", "label": "Price, $", "kind": "number", "width": 100},
    {"key": "cost", "label": "Unit cost, $", "kind": "number", "width": 110},
    {"key": "margin", "label": "Margin, %", "kind": "number", "editable": False, "width": 100},
    {"key": "units", "label": "Units sold", "kind": "number", "editable": False, "width": 100},
    {"key": "revenue", "label": "Revenue, $", "kind": "number", "editable": False},
    {"key": "stock", "label": "In stock", "kind": "number", "width": 100},
    {"key": "cover", "label": "Days of cover", "kind": "number", "editable": False, "width": 120},
]
EDITS = {"name": nu.Str, "price": nu.ToFloat, "cost": nu.ToFloat, "stock": nu.ToInt}


class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot()
    sheet = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="sku", editable=True, dense=True, label="Catalog")
    revenue = nustd.ui.BarChart.slot(title="Revenue by product, in range", horizontal=True, value_format="${value}", height=380)


@nu.host
def bars(rows):
    return [[r["name"], r["revenue"]] for r in sorted(rows, key=lambda r: r["revenue"])]


def edit(root, ev):
    row, column = Shop.products[nu.Str(ev["key"])], nu.Str(ev["column"])
    writes = [nu.IfDo(column == k, getattr(row, k).set(cast(ev["value"]))) for k, cast in EDITS.items()]
    return ops.atomic_state(at(root, nu.Sequential(*writes)))


def out(plane):
    def build(root):
        read = kit.read("products", Shop.products.extract(), Shop.filters.fallback({}))
        draw = lambda rows: nu.IfDo(nu.Bool(rows), View.sheet.set_rows(rows) >> View.revenue.set(bars(rows)))
        follows = [Shop.beat.on_change(), Shop.filters.on_change(), Shop.products.on_change()]
        return nu.ParallelAsync(redraws(follows, read, draw), nu.ReactForever(View.sheet.on_edit(), lambda ev: edit(root, ev)))

    note = "The prices here are what the store sells at: change one and the next orders are sold at it. Stock goes down as they land."
    return View.note.set(note) >> kit.on_shop(plane, build)
""")


PRODUCTS = _page(
    "products",
    "Products",
    "lucide:coffee",
    "The catalog as a sheet: prices, costs, stock, and what each sells.",
    (("filters", FILTERS), ("sheet", SHEET)),
)


# --- forecast -------------------------------------------------------------------------------


PLAN = cell("""\
class Knobs(nustd.ui.Grid):
    price = nustd.ui.SliderRef.slot(label="Price change, %", min=-20, max=20, step=1)
    marketing = nustd.ui.SliderRef.slot(label="Marketing spend, % change", min=-50, max=100, step=5)
    churn = nustd.ui.SliderRef.slot(label="Subscriber churn, % a month", min=2, max=14, step=0.5)
    cafes = nustd.ui.SliderRef.slot(label="New wholesale cafes", min=0, max=12, step=1)


class Go(nustd.ui.Row):
    reset = nustd.ui.ButtonRef.slot(label="Back to baseline", variant="secondary", icon="rotate-ccw")


class View(nustd.ui.Column):
    knobs = Knobs.slot(columns=4, min_width=200, gap=4)
    go = Go.slot(gap=2)


K = View.knobs
KEYS = ("price", "marketing", "churn", "cafes")


def out(plane):
    def build(root):
        shown = lambda p: nu.Sequential(*(getattr(K, k).set(p[k]) for k in KEYS))
        asked = nu.Dict.of(**{k: nu.float(getattr(K, k)) for k in KEYS}, months=12)
        save = ops.atomic_state(at(root, Shop.plan.set(asked)))
        reset = ops.atomic_state(at(root, Shop.plan.set(kit.PLAN)))
        return nu.ParallelAsync(
            redraws([Shop.plan.on_change()], Shop.plan.fallback(kit.PLAN), shown),
            *(nu.ReactForever(getattr(K, k).on_change(), save) for k in KEYS),
            nu.ReactForever(View.go.reset.on_click(), reset),
        )

    return kit.on_shop(plane, build)
""")


OUTLOOK = cell(
    _tiles(
        {
            "next": "Next 12 months",
            "vs_base": "Against baseline",
            "growth": "On the last 12 months",
            "gross": "Gross profit",
            "margin": "Gross margin",
        },
        5,
    )
    + """

class View(nustd.ui.Column):
    tiles = Tiles.slot(**TILES)
    chart = nustd.ui.LineChart.slot(("Actual", "Baseline", "Plan"), title="Monthly revenue: the last year, the next", x_type="category",
                                    y_format="${value}", height=340)
    fit = nustd.ui.TextRef.slot()


def draw(v):
    tile = lambda k: getattr(View.tiles, k).set_value(v["tiles"][k])
    return nu.IfDo(nu.Bool(v),
        nu.Sequential(*(tile(k) for k in KEYS)) >> View.chart.set(views.outlook(v))
        >> View.fit.set(views.fit_line(v["tiles"]))
    )


def out(plane):
    read = kit.read("forecast", Shop.plan.fallback(kit.PLAN), Shop.products.extract())
    follows = [Shop.beat.on_change(), Shop.plan.on_change(), Shop.products.on_change()]
    return kit.on_shop(plane, lambda root: redraws(follows, read, draw, every=60.0))
"""
)


PNL = cell("""\
COLUMNS = [
    {"key": "month", "label": "Month"},
    {"key": "baseline", "label": "Baseline, $", "kind": "number"},
    {"key": "plan", "label": "Plan, $", "kind": "number"},
    {"key": "change", "label": "Change, %", "kind": "number"},
    {"key": "gross", "label": "Gross profit, $", "kind": "number"},
    {"key": "low", "label": "Low (80%), $", "kind": "number"},
    {"key": "high", "label": "High (80%), $", "kind": "number"},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="month", dense=True, label="Forecast by month")


def out(plane):
    read = kit.read("forecast", Shop.plan.fallback(kit.PLAN), Shop.products.extract())
    draw = lambda v: nu.IfDo(nu.Bool(v), View.table.set_rows(v["rows"]))
    return View.head.set("The plan, month by month") >> kit.on_shop(
        plane, lambda root: redraws([Shop.beat.on_change(), Shop.plan.on_change(), Shop.products.on_change()], read, draw, every=60.0)
    )
""")


FORECAST = _page(
    "forecast",
    "Forecast",
    "lucide:trending-up",
    "Twelve months ahead, fitted on the history, with what-ifs on top.",
    (("plan", PLAN), ("outlook", OUTLOOK), ("months", PNL)),
)


# --- metrics --------------------------------------------------------------------------------


def _metric(label: str, fmt: str, body: str) -> str:
    """A metric cell: ``value(t, keep)`` in a few lines, drawn as a tile and its last 26 weeks."""
    return cell(
        f"""\
import numpy as np


class View(nustd.ui.Column):
    stat = nustd.ui.StatRef.slot(label={label!r})
    weeks = nustd.ui.Sparkline.slot(area=True, height=48)


{body}

def draw(m):
    return nu.IfDo(nu.Bool(m), View.stat.set(m["value"], delta=m["delta"], trend=m["trend"]) >> View.weeks.set(m["spark"]))


def out(plane):
    return kit.on_shop(plane, lambda root: redraws(kit.changes(), kit.metric(value, {fmt!r}), draw))
"""
    )


METRICS = (
    (
        "aov",
        _metric(
            "Average order value",
            "money",
            """\
def value(t, keep):
    # Revenue over the number of orders.
    orders = len(np.unique(t.lines["order"][keep]))
    return t.money[keep].sum() / max(orders, 1)
""",
        ),
    ),
    (
        "repeat",
        _metric(
            "Repeat customers",
            "pct",
            """\
def value(t, keep):
    # Share of customers in range with two orders or more.
    pairs = np.unique(np.stack([t.lines["customer"][keep], t.lines["order"][keep]]), axis=1)
    _, n = np.unique(pairs[0], return_counts=True)
    return (n >= 2).mean() if len(n) else 0.0
""",
        ),
    ),
    (
        "mrr",
        _metric(
            "Subscription revenue",
            "money",
            """\
def value(t, keep):
    # What the subscriptions brought in.
    return t.money[keep & (t.lines["channel"] == 1)].sum()
""",
        ),
    ),
    (
        "margin",
        _metric(
            "Gross margin",
            "pct",
            """\
def value(t, keep):
    # What is left after the beans, the bags and the gear cost us.
    return t.margin[keep].sum() / max(t.money[keep].sum(), 1)
""",
        ),
    ),
    (
        "wholesale",
        _metric(
            "Wholesale share",
            "pct",
            """\
def value(t, keep):
    # Share of revenue from the cafes.
    return t.money[keep & (t.lines["channel"] == 3)].sum() / max(t.money[keep].sum(), 1)
""",
        ),
    ),
    (
        "basket",
        _metric(
            "Items per order",
            "ratio",
            """\
def value(t, keep):
    # Units over orders: how full the basket is.
    return t.lines["qty"][keep].sum() / max(len(np.unique(t.lines["order"][keep])), 1)
""",
        ),
    ),
)


METRICS_INTRO = cell('''\
TEXT = """\\
Each metric below is its own cell: a few lines saying what it is, over the order lines the filters keep. \\
Open one to read it, change it, or copy it into a new metric. The tile compares the range with the one before; \\
the line under it is the last 26 weeks.
"""


def out(plane):
    return nustd.ui.MarkdownRef("about").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
''')


METRICS_PAGE = _page(
    "metrics",
    "Metrics",
    "lucide:gauge",
    "A cell per metric, each a few lines over the order lines.",
    (("about", METRICS_INTRO), ("filters", FILTERS), *METRICS),
)


# --- events ---------------------------------------------------------------------------------


QUERY = cell("""\
OPTIONS = {
    "range": ["Last 7 days", "Last 30 days", "Last 90 days", "Last 12 months", "All time"],
    "kind": ["All", "Session", "Product view", "Add to cart", "Checkout", "Purchase"],
    "source": ["All", "Organic search", "Instagram", "Newsletter", "Paid search", "Referral", "Direct"],
    "device": ["All", "Mobile", "Desktop", "Tablet"],
    "sku": ["All", "LK-HB", "LK-E9", "LK-DC", "LK-ET", "LK-CO", "LK-KE", "LK-GU", "SB-01", "SB-02", "GR-V6", "GR-HG", "GR-KT", "GR-PF", "MR-MG", "MR-TT"],
}
LABELS = {"range": "Range", "kind": "Event", "source": "Source", "device": "Device", "sku": "Product"}


def pick(label, options):
    return type("Pick", (nustd.ui.Field,), {"choice": nustd.ui.SelectRef.slot(options=options)}).slot(label=label)


Query = type("Query", (nustd.ui.Grid,), {k: pick(LABELS[k], v) for k, v in OPTIONS.items()})


class View(nustd.ui.Column):
    query = Query.slot(columns=5, min_width=150, gap=3)


def out(plane):
    def follow(root):
        Q = View.query
        shown = lambda q: nu.Sequential(*(getattr(Q, k).choice.set(q[k]) for k in OPTIONS))
        asked = nu.Dict.of(**{k: nu.Str(getattr(Q, k).choice) for k in OPTIONS})
        save = ops.atomic_state(at(root, Shop.query.set(asked)))
        return nu.ParallelAsync(
            redraws([Shop.query.on_change()], Shop.query.fallback(kit.QUERY), shown),
            *(nu.ReactForever(getattr(Q, k).choice.on_change(), save) for k in OPTIONS),
        )

    return kit.on_shop(plane, follow)
""")


EXPLORE = cell("""\
COLUMNS = [
    {"key": "time", "label": "Time", "width": 150},
    {"key": "session", "label": "Session", "kind": "number", "width": 100},
    {"key": "event", "label": "Event", "width": 130},
    {"key": "source", "label": "Source"},
    {"key": "device", "label": "Device", "width": 100},
    {"key": "product", "label": "Product"},
]
HOURS = [f"{h:02d}" for h in range(24)]
DAYS = ["Sun", "Sat", "Fri", "Thu", "Wed", "Tue", "Mon"]


class Result(nustd.ui.Grid):
    total = nustd.ui.StatRef.slot(label="Web events, all of them")
    matched = nustd.ui.StatRef.slot(label="Matching the query")
    sessions = nustd.ui.StatRef.slot(label="From sessions")
    ms = nustd.ui.StatRef.slot(label="Scanned in")


class Charts(nustd.ui.Grid):
    heat = nustd.ui.HeatmapChart.slot(HOURS, DAYS, title="When they happen, local time", legend=False, height=260)
    daily = nustd.ui.BarChart.slot(title="Per day", x_type="time", height=260)


class View(nustd.ui.Column):
    result = Result.slot(columns=4, min_width=160, gap=3)
    charts = Charts.slot(columns=2, min_width=420, gap=4)
    head = nustd.ui.HeadingRef.slot(level=4)
    rows = nustd.ui.TableRef.slot(columns=COLUMNS, dense=True, label="Events")


def draw(v):
    return nu.IfDo(nu.Bool(v),
        View.result.total.set(views.count(v["total"])) >> View.result.matched.set(views.count(v["matched"]))
        >> View.result.sessions.set(views.count(v["sessions"])) >> View.result.ms.set(views.took(v["ms"]))
        >> View.charts.heat.set(v["heat"]) >> View.charts.daily.set(v["daily"])
        >> View.head.set("The newest 50 that match") >> View.rows.set_rows(v["rows"])
    )


def out(plane):
    read = kit.read("events", Shop.query.fallback(kit.QUERY), tables=("events",))
    return kit.on_shop(plane, lambda root: redraws([Shop.beat.on_change(), Shop.query.on_change()], read, draw))
""")


EVENTS = _page(
    "events",
    "Events",
    "lucide:activity",
    "Every web event, over a million and growing, queried as you pick.",
    (("status", BAR), ("query", QUERY), ("explore", EXPLORE)),
)


# --- imports --------------------------------------------------------------------------------


INBOX = cell("""\
from nudemos.data import imports


class Drop(nustd.ui.Row):
    wholesale = nustd.ui.ButtonRef.slot(label="Wholesale order sheet", icon="file-down", variant="secondary")
    marketplace = nustd.ui.ButtonRef.slot(label="Marketplace settlement", icon="file-down", variant="secondary")
    popup = nustd.ui.ButtonRef.slot(label="Pop-up till export", icon="file-down", variant="secondary")


class Watch(nustd.ui.Row):
    dot = nustd.ui.StatusDotRef.slot(tone="neutral")
    line = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    watch = Watch.slot(gap=2, align="center")
    drop = Drop.slot(gap=2, wrap=True)
    waiting = nustd.ui.TextRef.slot()


ABOUT = (
    "Exports land in the **inbox** folder in this space's folder: a cafe's order sheet, the marketplace's "
    "settlement, the pop-up market's till. The importer, a job in its own process, picks each one up, "
    "checks it row by row and loads it as a new shard of the tables. Every dashboard follows. "
    "Drop one of these in to watch it happen, or copy any CSV of the same shape into the folder."
)


def out(plane):
    def build(root):
        inbox = Shop.inbox.fallback("")
        status = imports.watch(Shop.importer.fallback({}), kit.live(root, "importer"), inbox)
        draw = lambda v: View.watch.dot.set(v["tone"], pulse=v["pulse"]) >> View.watch.line.set(v["line"]) >> View.waiting.set(v["waiting"])
        drop = lambda kind: imports.drop(snap(inbox), kind)
        return nu.ParallelAsync(
            redraws([Shop.importer.on_change(), Shop.imports.on_change()], status, draw, every=1.0),
            nu.ReactForever(View.drop.wholesale.on_click(), drop("wholesale")),
            nu.ReactForever(View.drop.marketplace.on_click(), drop("marketplace")),
            nu.ReactForever(View.drop.popup.on_click(), drop("popup")),
        )

    D = View.drop
    buttons = (
        D.wholesale.set("Wholesale order sheet", icon="file-down", variant="secondary")
        >> D.marketplace.set("Marketplace settlement", icon="file-down", variant="secondary")
        >> D.popup.set("Pop-up till export", icon="file-down", variant="secondary")
    )
    return View.about.set(ABOUT) >> buttons >> kit.on_shop(plane, build)
""")


LOG = cell("""\
from nudemos.data import imports

COLUMNS = [
    {"key": "when", "label": "Loaded", "width": 100},
    {"key": "file", "label": "File"},
    {"key": "kind", "label": "Export", "width": 120},
    {"key": "loaded", "label": "Rows kept", "kind": "number", "width": 110},
    {"key": "rejected", "label": "Turned down", "kind": "number", "width": 120},
    {"key": "orders", "label": "Orders", "kind": "number", "width": 90},
    {"key": "revenue", "label": "Revenue, $", "kind": "number", "width": 120},
    {"key": "took", "label": "Parsed in", "width": 100},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    log = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Imports")
    latest = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(root):
        read = imports.log(Shop.imports.fallback([]))
        draw = lambda v: View.log.set_rows(v["rows"]) >> View.latest.set(v["latest"])
        return redraws([Shop.imports.on_change()], read, draw)

    return View.head.set("Loaded so far") >> kit.on_shop(plane, build)
""")


IMPORTS = _page(
    "imports",
    "Imports",
    "lucide:inbox",
    "Exports dropped in the inbox, parsed and loaded by a job in its own process.",
    (("inbox", INBOX), ("log", LOG)),
)


# --- sources --------------------------------------------------------------------------------


STREAM = cell("""\
PACES = ["Quiet", "Busy", "Launch day"]


class Pace(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=PACES)


class Controls(nustd.ui.Row):
    pace = Pace.slot(label="Pace of orders")
    toggle = nustd.ui.ButtonRef.slot(label="Pause stream", icon="pause", variant="secondary")


class View(nustd.ui.Column):
    controls = Controls.slot(gap=3, align="end")
    sold = nustd.ui.BarChart.slot(title="Revenue landing, the last ten minutes", x_type="time", value_format="${value}", height=220)


def out(plane):
    def build(root):
        C = View.controls
        running = Shop.stop.fallback(False).not_()
        button = lambda run: nu.IfDo(nu.Bool(run), C.toggle.set("Pause stream", icon="pause", variant="secondary"),
                                     C.toggle.set("Resume stream", icon="play", variant="primary"))
        toggle = nu.IfDo(snap(at(root, running)), kit.stop(root), kit.start(root))
        pace = ops.atomic_state(at(root, Shop.pace.set(nu.Str(C.pace.choice))))
        sold = views.recent(Shop.sold.sample(200, begin=views.since(600)))
        return nu.ParallelAsync(
            redraws([Shop.pace.on_change()], Shop.pace.fallback("Busy"), C.pace.choice.set),
            redraws([Shop.stop.on_change()], running, button),
            redraws([Shop.beat.on_change()], sold, View.sold.set, every=5.0),
            nu.ReactForever(C.pace.choice.on_change(), pace),
            nu.ReactForever(C.toggle.on_click(), toggle),
        )

    return kit.on_shop(plane, build)
""")


TABLES = cell("""\
COLUMNS = [
    {"key": "table", "label": "Table", "width": 110},
    {"key": "rows", "label": "Rows", "kind": "number"},
    {"key": "shards", "label": "Shards", "kind": "number", "width": 90},
    {"key": "size", "label": "Size"},
    {"key": "from", "label": "Where the rows came from"},
    {"key": "latest", "label": "Last write", "width": 110},
]
SHARDS = [
    {"key": "id", "label": "Shard", "kind": "number", "width": 90},
    {"key": "table", "label": "Table", "width": 100},
    {"key": "rows", "label": "Rows", "kind": "number", "width": 100},
    {"key": "origin", "label": "Origin"},
    {"key": "v", "label": "Version", "kind": "number", "width": 100},
    {"key": "at", "label": "Written", "width": 110},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    tables = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="table", dense=True, label="Tables")
    schema = nustd.ui.MarkdownRef.slot()
    shards_head = nustd.ui.HeadingRef.slot(level=4)
    shards = nustd.ui.TableRef.slot(columns=SHARDS, row_key="id", dense=True, label="Newest shards")


def draw(v):
    return (
        View.head.set("Tables") >> View.tables.set_rows(v["tables"]) >> View.schema.set(views.SCHEMA)
        >> View.shards_head.set("The newest shards") >> View.shards.set_rows(v["shards"])
    )


def out(plane):
    return kit.on_shop(plane, lambda root: redraws([Shop.beat.on_change()], views.sources(Shop.index.extract()), draw, every=2.0))
""")


SOURCES = _page(
    "sources",
    "Sources",
    "lucide:database",
    "The tables, the shards they are stored in, and the stream that keeps them growing.",
    (("status", BAR), ("stream", STREAM), ("tables", TABLES)),
)


#: The pages under the overview, in order.
PAGES = (
    REVENUE,
    FUNNEL,
    COHORT_PAGE,
    CUSTOMERS,
    PRODUCTS,
    FORECAST,
    METRICS_PAGE,
    EVENTS,
    IMPORTS,
    SOURCES,
)
