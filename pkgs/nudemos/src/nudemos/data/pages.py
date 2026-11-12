"""The pages under the overview, as Planes and their cells' sources.

Every dashboard cell is the same few lines: :func:`~.kit.read` a view from
:mod:`.calc`, follow what it depends on, draw. The pages:

- Revenue, Funnel, Cohorts, Customers (a page per customer, made on a
  click), Products (the catalog as a sheet), Forecast (what-ifs), Metrics (a
  cell per metric), Events (the web events, queried), Imports (the inbox),
  Sources (the tables and the stream).
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions

from .cells import BAR, FILTERS, cell


__all__ = ["CUSTOMER_CELLS", "PAGES"]


def _page(name: str, label: str, icon: str, description: str, cells: tuple) -> PlaneSpec:
    return PlaneSpec(
        f"data_{name}",
        label,
        icon=icon,
        description=description,
        cells=cells,
        web=WebOptions(editable=True, full_width=True),
        backend="async",
    )


# --- revenue --------------------------------------------------------------------------------


REVENUE_CHARTS = cell("""\
KEYS = {"revenue": "Revenue", "orders": "Orders", "aov": "Average order", "margin": "Gross margin", "units": "Units sold"}


class View(nustd.ui.Column):
    tiles = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=5, min_cell_width=160, gap=3)
    charts = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)


curve = View.charts[0, 0].to(nustd.ui.BarChart.slot(
    ("Web store", "Subscription", "Marketplace", "Wholesale"), title="Revenue by channel",
    x_type="time", stack=True, value_format="${value}", height=320, option={"legend": {"type": "plain"}},
))
cats = View.charts[0, 1].to(nustd.ui.BarChart.slot(title="By category", horizontal=True, value_format="${value}", height=320))


def draw(v):
    tile = lambda k: View.tiles[k][0].to(nustd.ui.StatRef).set(v["tiles"][k][0], label=KEYS[k], delta=v["tiles"][k][1], trend=v["tiles"][k][2])
    return nu.IfDo(nu.Bool(v), nu.Sequential(*(tile(k) for k in KEYS)) >> curve.set(v["series"]) >> cats.set(v["cats"]))


def out(plane):
    read = kit.read("revenue", SHOP.filters.fallback({}))
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(read), draw)))
""")


MONTHS = cell("""\
# The sheet's columns. Margin and the change on the month before are derived: computed, not stored.
COLUMNS = [
    {"key": "month", "label": "Month"},
    {"key": "revenue", "label": "Revenue, $", "kind": "number"},
    {"key": "orders", "label": "Orders", "kind": "number"},
    {"key": "aov", "label": "Average order, $", "kind": "number", "hide_below": 640},
    {"key": "margin", "label": "Margin, %", "kind": "number", "hide_below": 520},
    {"key": "change", "label": "vs month before, %", "kind": "number"},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Month by month")


sheet = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="month", density="compact", label="Months"))


def out(plane):
    read = kit.read("revenue", SHOP.filters.fallback({}))
    draw = lambda v: nu.IfDo(nu.Bool(v), sheet.set_rows(v["months"]))
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(read), draw)))
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
OPTIONS = {
    "range": ["Last 7 days", "Last 30 days", "Last 90 days", "Last 12 months"],
    "source": ["All", "Organic search", "Instagram", "Newsletter", "Paid search", "Referral", "Direct"],
    "device": ["All", "Mobile", "Desktop", "Tablet"],
}
LABELS = {"range": "Range", "source": "Traffic source", "device": "Device"}


class View(nu.Shape):
    filters = nustd.ui.GridRef.slot(max_columns=3, min_cell_width=180, gap=3)


PICKS = {
    k: View.filters[k].to(nustd.ui.FieldRef.slot(label=LABELS[k])).control.to(nustd.ui.SelectRef.slot(options=v))
    for k, v in OPTIONS.items()
}


def out(plane):
    def follow(root):
        shown = lambda f: nu.Sequential(*(PICKS[k].set(f[k]) for k in OPTIONS))
        asked = nu.Dict.of(**{k: nu.Str(PICKS[k]) for k in OPTIONS})
        save = nuspace.atomic(SHOP.traffic.set(asked))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.traffic.on_change()])), nu.let(nuspace.atomic(SHOP.traffic.fallback({})), shown)),
            *(nu.ReactEvery(p.on_change(), save) for p in PICKS.values()),
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


class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot(tone="secondary")
    top = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)
    rates = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)
    trend = nustd.ui.LineChart.slot(title="Purchase rate by day, %", x_type="time", height=240)


funnel = View.top[0, 0].to(nustd.ui.FunnelChart.slot(title="Sessions down the funnel", sort="none", label_format="{b}", height=320,
                                                     option={"series": [{"minSize": "22%"}]}))
steps = View.top[0, 1].to(nustd.ui.CardRef.slot(title="Funnel steps"))[0].to(
    nustd.ui.DataTableRef.slot(columns=STEPS, row_key="stage", density="compact", label="Funnel steps"))
source = View.rates[0, 0].to(nustd.ui.BarChart.slot(title="Purchase rate by source, %", horizontal=True, height=260))
device = View.rates[0, 1].to(nustd.ui.BarChart.slot(title="Purchase rate by device, %", horizontal=True, height=260))


@nu.host
def note(v):
    return f"{v['stages'][0][1]:,} sessions counted from {v['scanned']:,} web events in {v['ms']:.0f} ms, every time the data moves."


def draw(v):
    return nu.IfDo(nu.Bool(v),
        View.note.set(note(v)) >> funnel.set(v["stages"]) >> steps.set_rows(v["steps"])
        >> source.set(v["by_source"]) >> device.set(v["by_device"])
        >> View.trend.set(v["trend"]["Purchase rate"])
    )


def out(plane):
    read = kit.read("funnel", SHOP.traffic.fallback({}), tables=("events",))
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change(), SHOP.traffic.on_change()])), nu.let(nuspace.atomic(read), draw)))
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


class View(nustd.ui.Column):
    metric = nustd.ui.FieldRef.slot(label="Show", max_width=240)
    heat = nustd.ui.HeatmapChart.slot(title="Monthly cohorts", labels=True, height=420, x_label="Months since first order")
    below = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)


metric = View.metric.control.to(nustd.ui.SelectRef.slot(options=METRICS))
curves = View.below[0, 0].to(nustd.ui.LineChart.slot(
    (), title="What a customer has spent, months after their first order", x_type="category",
    y_format="${value}", legend=True, height=300,
))
table = View.below[0, 1].to(nustd.ui.CardRef.slot(title="Cohorts"))[0].to(
    nustd.ui.DataTableRef.slot(columns=ROWS, row_key="cohort", density="compact", label="Cohorts"))


def draw(v):
    return nu.IfDo(nu.Bool(v), View.heat.set(v["cells"]) >> curves.set(v["curves"]) >> table.set_rows(v["rows"]))


def out(plane):
    def build(root):
        save = nuspace.atomic(SHOP.cohort.set(nu.Str(metric)))
        read = kit.read("cohorts", SHOP.cohort.fallback("Retention"))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.cohort.on_change()])), nu.let(nuspace.atomic(SHOP.cohort.fallback("Retention")), metric.set)),
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change(), SHOP.cohort.on_change()])), nu.let(nuspace.atomic(read), draw), every=60.0),
            nu.ReactEvery(metric.on_change(), save),
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
    {"key": "kind", "label": "Type", "width": 120, "cell": nustd.ui.BadgeRef.slot(size="sm"), "hide_below": 560},
    {"key": "city", "label": "City", "hide_below": 720},
    {"key": "orders", "label": "Orders", "kind": "number", "width": 90},
    {"key": "spend", "label": "Spent in range, $", "kind": "number"},
    {"key": "lifetime", "label": "Lifetime, $", "kind": "number", "hide_below": 640},
    {"key": "last", "label": "Last order", "hide_below": 640},
]


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    side = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)
    top = nustd.ui.CardRef.slot(title="Top customers in range")


mix = View.side[0, 0].to(nustd.ui.PieChart.slot(title="Revenue by customer type", donut=True, legend=True, labels=False, height=280))
new = View.side[0, 1].to(nustd.ui.BarChart.slot(("New", "Returning"), title="New against returning, by week", stack=True, x_type="time",
                                                value_format="${value}", height=280))
# A customer's page is made on the first open, so a row is a click, not a link.
table = View.top[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, density="compact", label="Top customers"))


def draw(v):
    return nu.IfDo(nu.Bool(v),
        mix.set(v["mix"]) >> new.set(v["new_returning"]) >> View.top.set_subtitle(views.top_head(v["count"]))
        >> table.set_rows(v["rows"])
    )


def out(plane):
    def build(root):
        def opened(ev):
            cid = nu.Str(ev["key"])
            name = nuspace.atomic(kit.read("who", cid))
            return kit.open_customer(root, cid, name, plane, View.history)

        read = kit.read("customers", SHOP.filters.fallback({}))
        return nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(read), draw)), nu.ReactEvery(table.on_row_click(), opened))

    return kit.on_shop(plane, build)
""")


CUSTOMERS = _page(
    "customers",
    "Customers",
    "lucide:users",
    "The best customers under the shared filters; each opens a page of their own.",
    (("status", BAR), ("filters", FILTERS), ("top", TOP)),
)


PROFILE = cell("""\
KEYS = {"lifetime": "Lifetime spend", "orders": "Orders", "aov": "Average order", "last": "Last order", "rank": "Rank"}


class Who(nustd.ui.Column):
    name = nustd.ui.HeadingRef.slot(level=2)
    line = nustd.ui.TextRef.slot(tone="secondary")


class Head(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="xl")
    who = Who.slot(gap=1)


class View(nustd.ui.Column):
    head = Head.slot(gap=4)
    tiles = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=5, min_cell_width=140, gap=3)
    charts = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)


curve = View.charts[0, 0].to(nustd.ui.AreaChart.slot(title="Spend over time, cumulative", x_type="time", y_format="${value}", height=260))
buys = View.charts[0, 1].to(nustd.ui.BarChart.slot(title="What they buy, $", horizontal=True, height=260))


def draw(v):
    tile = lambda k: View.tiles[k][0].to(nustd.ui.StatRef).set(v["tiles"][k], label=KEYS[k])
    return (
        View.head.face.set_name(v["name"]) >> View.head.who.name.set(v["name"]) >> View.head.who.line.set(v["line"])
        >> nu.Sequential(*(tile(k) for k in KEYS)) >> curve.set(v["curve"]) >> buys.set(v["buys"])
    )


def out(plane):
    def build(root):
        read = kit.read("customer", nu.ToInt(kit.subject(plane)))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change()])), nu.let(nuspace.atomic(read), lambda v: nu.IfDo(nu.Bool(v), draw(v))))

    return kit.on_shop(plane, build)
""")


ORDERS = cell("""\
COLUMNS = [
    {"key": "order", "label": "Order", "width": 110},
    {"key": "date", "label": "Placed"},
    {"key": "channel", "label": "Channel", "width": 130, "cell": nustd.ui.BadgeRef.slot(size="sm"), "hide_below": 560},
    {"key": "items", "label": "Items", "hide_below": 720},
    {"key": "total", "label": "Total, $", "kind": "number", "width": 110},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Every order", subtitle="newest first")


orders = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="order", density="compact", label="Orders"))


def out(plane):
    def build(root):
        read = kit.read("customer", nu.ToInt(kit.subject(plane)))
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change()])), nu.let(nuspace.atomic(read), lambda v: nu.IfDo(nu.Bool(v), orders.set_rows(v["rows"]))))

    return kit.on_shop(plane, build)
""")


CUSTOMER_CELLS = (("profile", PROFILE), ("orders", ORDERS))


# --- products -------------------------------------------------------------------------------


SHEET = cell("""\
# What we set is editable: name, price, cost, stock. The rest is derived from the orders, every time they move.
COLUMNS = [
    {"key": "name", "label": "Product"},
    {"key": "category", "label": "Category", "editable": False, "hide_below": 640},
    {"key": "price", "label": "Price, $", "kind": "number", "width": 100},
    {"key": "cost", "label": "Unit cost, $", "kind": "number", "width": 110},
    {"key": "margin", "label": "Margin, %", "kind": "number", "editable": False, "width": 100},
    {"key": "units", "label": "Units sold", "kind": "number", "editable": False, "width": 100},
    {"key": "revenue", "label": "Revenue, $", "kind": "number", "editable": False},
    {"key": "stock", "label": "In stock", "kind": "number", "width": 100},
    {"key": "cover", "label": "Days of cover", "kind": "number", "editable": False, "width": 120},
]
EDITS = {"name": nu.Str, "price": nu.ToFloat, "cost": nu.ToFloat, "stock": nu.ToInt}
NOTE = "The prices here are what the store sells at: change one and the next orders are sold at it. Stock goes down as they land."


class View(nustd.ui.Column):
    catalog = nustd.ui.CardRef.slot(title="Catalog", subtitle=NOTE)
    revenue = nustd.ui.BarChart.slot(title="Revenue by product, in range", horizontal=True, value_format="${value}", height=380)


sheet = View.catalog[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="sku", editable=True, density="compact", label="Catalog"))


@nu.host
def bars(rows):
    return [[r["name"], r["revenue"]] for r in sorted(rows, key=lambda r: r["revenue"])]


def edit(root, ev):
    row, column = SHOP.products[nu.Str(ev["key"])], nu.Str(ev["column"])
    writes = [nu.IfDo(column == k, getattr(row, k).set(cast(ev["value"]))) for k, cast in EDITS.items()]
    return nuspace.atomic(nu.Sequential(*writes))


def out(plane):
    def build(root):
        read = kit.read("products", SHOP.products.extract(), SHOP.filters.fallback({}))
        draw = lambda rows: nu.IfDo(nu.Bool(rows), sheet.set_rows(rows) >> View.revenue.set(bars(rows)))
        follows = [SHOP.beat.on_change(), SHOP.filters.on_change(), SHOP.products.on_change()]
        return nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*follows)), nu.let(nuspace.atomic(read), draw)), nu.ReactEvery(sheet.on_edit(), lambda ev: edit(root, ev)))

    return kit.on_shop(plane, build)
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
KNOBS = {
    "price": nustd.ui.SliderRef.slot(label="Price change, %", min=-20, max=20, step=1),
    "marketing": nustd.ui.SliderRef.slot(label="Marketing spend, % change", min=-50, max=100, step=5),
    "churn": nustd.ui.SliderRef.slot(label="Subscriber churn, % a month", min=2, max=14, step=0.5),
    "cafes": nustd.ui.SliderRef.slot(label="New wholesale cafes", min=0, max=12, step=1),
}


class View(nu.Shape):
    plan = nustd.ui.CardRef.slot(title="What if", subtitle="Every page below follows the plan.", gap=4)


knobs = View.plan[0].to(nustd.ui.GridRef.slot(max_columns=4, min_cell_width=200, gap=4))
K = {k: knobs[k].to(spec) for k, spec in KNOBS.items()}
reset = View.plan.actions[0].to(nustd.ui.ButtonRef.slot(label="Back to baseline", variant="secondary", icon="rotate-ccw", size="sm"))


def out(plane):
    def build(root):
        shown = lambda p: nu.Sequential(*(K[k].set(p[k]) for k in KNOBS))
        asked = nu.Dict.of(**{k: nu.float(K[k]) for k in KNOBS}, months=12)
        save = nuspace.atomic(SHOP.plan.set(asked))
        back = nuspace.atomic(SHOP.plan.set(kit.PLAN))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.plan.on_change()])), nu.let(nuspace.atomic(SHOP.plan.fallback(kit.PLAN)), shown)),
            *(nu.ReactEvery(K[k].on_change(), save) for k in KNOBS),
            nu.ReactEvery(reset.on_click(), back),
        )

    return reset.init() >> kit.on_shop(plane, build)
""")


OUTLOOK = cell("""\
KEYS = {
    "next": "Next 12 months",
    "vs_base": "Against baseline",
    "growth": "On the last 12 months",
    "gross": "Gross profit",
    "margin": "Gross margin",
}


class View(nustd.ui.Column):
    tiles = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=5, min_cell_width=140, gap=3)
    chart = nustd.ui.LineChart.slot(("Actual", "Baseline", "Plan"), title="Monthly revenue: the last year, the next", x_type="category",
                                    y_format="${value}", height=340)
    fit = nustd.ui.TextRef.slot(tone="secondary", size="sm")


def draw(v):
    tile = lambda k: View.tiles[k][0].to(nustd.ui.StatRef).set(v["tiles"][k], label=KEYS[k])
    return nu.IfDo(nu.Bool(v),
        nu.Sequential(*(tile(k) for k in KEYS)) >> View.chart.set(views.outlook(v))
        >> View.fit.set(views.fit_line(v["tiles"]))
    )


def out(plane):
    read = kit.read("forecast", SHOP.plan.fallback(kit.PLAN), SHOP.products.extract())
    follows = [SHOP.beat.on_change(), SHOP.plan.on_change(), SHOP.products.on_change()]
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*follows)), nu.let(nuspace.atomic(read), draw), every=60.0))
""")


PNL = cell("""\
COLUMNS = [
    {"key": "month", "label": "Month"},
    {"key": "baseline", "label": "Baseline, $", "kind": "number"},
    {"key": "plan", "label": "Plan, $", "kind": "number"},
    {"key": "change", "label": "Change, %", "kind": "number"},
    {"key": "gross", "label": "Gross profit, $", "kind": "number", "hide_below": 640},
    {"key": "low", "label": "Low (80%), $", "kind": "number", "hide_below": 720},
    {"key": "high", "label": "High (80%), $", "kind": "number", "hide_below": 720},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="The plan, month by month")


table = View.card[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="month", density="compact", label="Forecast by month"))


def out(plane):
    read = kit.read("forecast", SHOP.plan.fallback(kit.PLAN), SHOP.products.extract())
    draw = lambda v: nu.IfDo(nu.Bool(v), table.set_rows(v["rows"]))
    follows = [SHOP.beat.on_change(), SHOP.plan.on_change(), SHOP.products.on_change()]
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*follows)), nu.let(nuspace.atomic(read), draw), every=60.0))
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
    """A metric cell: ``value(t, keep)`` in a few lines, drawn as a tile with its last 26 weeks on top."""
    return cell(
        f"""\
import numpy as np


class Tile(nustd.ui.Card):
    media = nustd.ui.Sparkline.slot(area=True, height=48)
    stat = nustd.ui.StatRef.slot(label={label!r})


class View(nu.Shape):
    tile = Tile.slot(size="sm")


{body}

def draw(m):
    return nu.IfDo(nu.Bool(m), View.tile.stat.set(m["value"], delta=m["delta"], trend=m["trend"]) >> View.tile.media.set(m["spark"]))


def out(plane):
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(kit.metric(value, {fmt!r})), draw)))
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


class View(nu.Shape):
    query = nustd.ui.GridRef.slot(max_columns=5, min_cell_width=150, gap=3)


PICKS = {
    k: View.query[k].to(nustd.ui.FieldRef.slot(label=LABELS[k])).control.to(nustd.ui.SelectRef.slot(options=v))
    for k, v in OPTIONS.items()
}


def out(plane):
    def follow(root):
        shown = lambda q: nu.Sequential(*(PICKS[k].set(q[k]) for k in OPTIONS))
        asked = nu.Dict.of(**{k: nu.Str(PICKS[k]) for k in OPTIONS})
        save = nuspace.atomic(SHOP.query.set(asked))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.query.on_change()])), nu.let(nuspace.atomic(SHOP.query.fallback(kit.QUERY)), shown)),
            *(nu.ReactEvery(p.on_change(), save) for p in PICKS.values()),
        )

    return kit.on_shop(plane, follow)
""")


EXPLORE = cell("""\
COLUMNS = [
    {"key": "time", "label": "Time", "width": 150},
    {"key": "session", "label": "Session", "kind": "number", "width": 100, "hide_below": 640},
    {"key": "event", "label": "Event", "width": 140, "cell": nustd.ui.BadgeRef.slot(size="sm")},
    {"key": "source", "label": "Source", "hide_below": 560},
    {"key": "device", "label": "Device", "width": 100, "hide_below": 720},
    {"key": "product", "label": "Product"},
]
HOURS = [f"{h:02d}" for h in range(24)]
DAYS = ["Sun", "Sat", "Fri", "Thu", "Wed", "Tue", "Mon"]
STATS = {"total": "Web events, all of them", "matched": "Matching the query", "sessions": "From sessions", "ms": "Scanned in"}


class View(nustd.ui.Column):
    result = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=4, min_cell_width=160, gap=3)
    charts = nustd.ui.GridRef.slot(cols=2, gap=4, stack_below=900)
    newest = nustd.ui.CardRef.slot(title="The newest 50 that match")


heat = View.charts[0, 0].to(nustd.ui.HeatmapChart.slot(HOURS, DAYS, title="When they happen, local time", legend=False, height=260))
daily = View.charts[0, 1].to(nustd.ui.BarChart.slot(title="Per day", x_type="time", height=260))
rows = View.newest[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, density="compact", label="Events"))


def draw(v):
    said = {"total": views.count(v["total"]), "matched": views.count(v["matched"]), "sessions": views.count(v["sessions"]), "ms": views.took(v["ms"])}
    return nu.IfDo(nu.Bool(v),
        nu.Sequential(*(View.result[k][0].to(nustd.ui.StatRef).set(said[k], label=label) for k, label in STATS.items()))
        >> heat.set(v["heat"]) >> daily.set(v["daily"]) >> rows.set_rows(v["rows"])
    )


def out(plane):
    read = kit.read("events", SHOP.query.fallback(kit.QUERY), tables=("events",))
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change(), SHOP.query.on_change()])), nu.let(nuspace.atomic(read), draw)))
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
        inbox = SHOP.inbox.fallback("")
        status = imports.watch(SHOP.importer.fallback({}), kit.live(root, "importer"), inbox)
        draw = lambda v: View.watch.dot.set(v["tone"], pulse=v["pulse"]) >> View.watch.line.set(v["line"]) >> View.waiting.set(v["waiting"])
        # A file written is all a click does: the importer's own job picks it up.
        drop = lambda kind: nu.let(imports.drop(nuspace.atomic(inbox), kind), lambda _: nu.Noop())
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.importer.on_change(), SHOP.imports.on_change()])), nu.let(nuspace.atomic(status), draw), every=1.0),
            nu.ReactEvery(View.drop.wholesale.on_click(), drop("wholesale")),
            nu.ReactEvery(View.drop.marketplace.on_click(), drop("marketplace")),
            nu.ReactEvery(View.drop.popup.on_click(), drop("popup")),
        )

    buttons = View.drop.wholesale.init() >> View.drop.marketplace.init() >> View.drop.popup.init()
    return View.about.set(ABOUT) >> buttons >> kit.on_shop(plane, build)
""")


LOG = cell("""\
from nudemos.data import imports

COLUMNS = [
    {"key": "when", "label": "Loaded", "width": 100},
    {"key": "file", "label": "File"},
    {"key": "kind", "label": "Export", "width": 130, "cell": nustd.ui.BadgeRef.slot(size="sm")},
    {"key": "loaded", "label": "Rows kept", "kind": "number", "width": 110},
    {"key": "rejected", "label": "Turned down", "kind": "number", "width": 120},
    {"key": "orders", "label": "Orders", "kind": "number", "width": 90, "hide_below": 640},
    {"key": "revenue", "label": "Revenue, $", "kind": "number", "width": 120, "hide_below": 640},
    {"key": "took", "label": "Parsed in", "width": 100, "hide_below": 720},
]


class Loaded(nustd.ui.Card):
    log = nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Imports")
    latest = nustd.ui.MarkdownRef.slot()


class View(nu.Shape):
    card = Loaded.slot(title="Loaded so far")


def out(plane):
    def build(root):
        read = imports.log(SHOP.imports.fallback([]))
        draw = lambda v: View.card.log.set_rows(v["rows"]) >> View.card.latest.set(v["latest"])
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.imports.on_change()])), nu.let(nuspace.atomic(read), draw))

    return kit.on_shop(plane, build)
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


class Controls(nustd.ui.Row):
    pace = nustd.ui.FieldRef.slot(label="Pace of orders", width=200)
    toggle = nustd.ui.ButtonRef.slot(label="Pause stream", icon="pause", variant="secondary")


class View(nustd.ui.Column):
    controls = Controls.slot(gap=3, align="end")
    sold = nustd.ui.BarChart.slot(title="Revenue landing, the last ten minutes", x_type="time", value_format="${value}", height=220)


pace = View.controls.pace.control.to(nustd.ui.SelectRef.slot(options=PACES))


def out(plane):
    def build(root):
        C = View.controls
        running = SHOP.stop.fallback(False).not_()
        button = lambda run: nu.IfDo(nu.Bool(run), C.toggle.set("Pause stream", icon="pause", variant="secondary"),
                                     C.toggle.set("Resume stream", icon="play", variant="primary"))
        toggle = nu.IfDo(nuspace.atomic(running), kit.stop(root), kit.start(root))
        chosen = nuspace.atomic(SHOP.pace.set(nu.Str(pace)))
        sold = views.recent(SHOP.sold.sample(200, begin=views.since(600)))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.pace.on_change()])), nu.let(nuspace.atomic(SHOP.pace.fallback("Busy")), pace.set)),
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.stop.on_change()])), nu.let(nuspace.atomic(running), button)),
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change()])), nu.let(nuspace.atomic(sold), View.sold.set), every=5.0),
            nu.ReactEvery(pace.on_change(), chosen),
            nu.ReactEvery(C.toggle.on_click(), toggle),
        )

    return kit.on_shop(plane, build)
""")


TABLES = cell("""\
COLUMNS = [
    {"key": "table", "label": "Table", "width": 110},
    {"key": "rows", "label": "Rows", "kind": "number"},
    {"key": "shards", "label": "Shards", "kind": "number", "width": 90},
    {"key": "size", "label": "Size", "hide_below": 560},
    {"key": "from", "label": "Where the rows came from", "hide_below": 720},
    {"key": "latest", "label": "Last write", "width": 130, "cell": nustd.ui.RelativeTimeRef},
]
SHARDS = [
    {"key": "id", "label": "Shard", "kind": "number", "width": 90},
    {"key": "table", "label": "Table", "width": 100},
    {"key": "rows", "label": "Rows", "kind": "number", "width": 100},
    {"key": "origin", "label": "Origin", "cell": nustd.ui.BadgeRef.slot(size="sm")},
    {"key": "v", "label": "Version", "kind": "number", "width": 100, "hide_below": 560},
    {"key": "at", "label": "Written", "width": 130, "cell": nustd.ui.RelativeTimeRef},
]


class Tables(nustd.ui.Card):
    table = nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="table", density="compact", label="Tables")
    schema = nustd.ui.MarkdownRef.slot()


class View(nustd.ui.Column):
    tables = Tables.slot(title="Tables")
    shards = nustd.ui.CardRef.slot(title="The newest shards")


shards = View.shards[0].to(nustd.ui.DataTableRef.slot(columns=SHARDS, row_key="id", density="compact", label="Newest shards"))


def draw(v):
    return View.tables.table.set_rows(v["tables"]) >> View.tables.schema.set(views.SCHEMA) >> shards.set_rows(v["shards"])


def out(plane):
    return kit.on_shop(plane, lambda root: nu.Reconcile(nuspace.atomic(nu.OnAny(*[SHOP.beat.on_change()])), nu.let(nuspace.atomic(views.sources(SHOP.index.extract())), draw), every=2.0))
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
