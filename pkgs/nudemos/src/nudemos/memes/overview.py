"""The Overview plane: the terminal. Every token the sync follows, and the trades as they print.

- ``bar``, ``tiles``: the sync's state and the headline numbers, as on the root.
- ``tokens``: the tokens, by newest, market cap, volume, nearest graduation
  or last trade, picked above the table or by a column header. A click opens
  the token's page.
- ``tape``: the newest trades across every token. A click opens the token.
- ``launches``: the newest coins, as cards.

The order is each tab's own: two tabs sort two ways.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions

from .cells import BAR, LAUNCHES, TILES, cell


__all__ = ["PLANE", "TAPE", "TOKENS"]


TOKENS = cell("""\
def column(key, label, width=0, number=True, sortable=True, **more):
    c = {"key": key, "label": label, "sortable": sortable, **more}
    if number:
        c["kind"] = "number"
        c["align"] = "end"
    if width:
        c["width"] = width
    return c


COLUMNS = [
    column("token", "Token", 120, number=False, sortable=False),
    column("name", "Name", number=False, sortable=False, wrap="truncate", hide_below=900),
    column("age", "Age", 96, number=False, cell=nustd.ui.RelativeTimeRef),
    column("mc", "Market cap", 116),
    column("move", "Since launch", 116, sortable=False),
    column("curve", "Curve", 110, number=False, cell=nustd.ui.ProgressRef),
    column("vol", "Volume", 104),
    column("trades", "Trades", 84, sortable=False, hide_below=1100),
    column("bs", "Buys / sells", 110, sortable=False, hide_below=1100),
    column("last", "Last trade", 104, number=False),
]

ORDERS = [{"value": k, "label": v} for k, v in views.SORTS.items()]


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    tokens = nustd.ui.PageSectionRef.slot(title="Tokens", description="every coin the sync follows; a click opens its page")


sort = View.tokens.actions["sort"].to(nustd.ui.SelectRef.slot(options=ORDERS, selected="new"))
table = View.tokens["table"].to(nustd.ui.DataTableRef.slot(
    columns=COLUMNS, row_key="mint", clickable_rows=True, density="compact", label="Tokens",
    sort_column="age", sort_direction="desc",
))


class Pick(nu.Shape):
    # This tab's order: a board list.
    sort = nu.StrRef.slot()


@nu.host
def by_column(column):
    return views.COLUMN_SORTS.get(column, "")


@nu.host
def column_of(order):
    return {v: k for k, v in views.COLUMN_SORTS.items()}.get(order, "")


def out(plane):
    def follow(root):
        read = views.token_rows(memes_at(root).board.fallback({}), Pick.sort, nustd.time.time())
        draw = nu.let(nuspace.atomic(read), table.set_rows)
        shown = nu.Reconcile(nuspace.atomic(memes_at(root).beat.on_change()), draw, every=2.0)

        def order(picked):
            # A new order: the picker, the header's arrows and the rows, at once.
            s = nu.Str(picked)
            return Pick.sort.set(s) >> sort.set(s) >> table.set_sort(column_of(s), "desc") >> draw

        picked = nu.ReactEvery(sort.on_change(), order(nu.Str(sort)))
        clicked = nu.ReactEvery(table.on_sort(), lambda ev: nu.let(by_column(ev["sort_column"]), lambda s: nu.IfDo(nu.Str(s) != "", order(s))))
        # A token's page is made on its first open, so a row click opens it.
        opened = nu.ReactEvery(table.on_row_click(), lambda ev: control.open_token(root, nu.Str(ev["key"]), View.history))
        return sort.set("new") >> nu.Frame(Pick, nu.ParallelAsync(shown, picked, clicked, opened), sort="new")

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


TAPE = cell("""\
COLUMNS = [
    {"key": "age", "label": "Age", "width": 96, "sortable": False, "cell": nustd.ui.RelativeTimeRef},
    {"key": "side", "label": "Side", "width": 84, "sortable": False, "cell": nustd.ui.BadgeRef.slot(size="sm")},
    {"key": "token", "label": "Token", "width": 120, "sortable": False},
    {"key": "amount", "label": "Amount", "kind": "number", "align": "end", "sortable": False},
    {"key": "mc", "label": "Market cap", "kind": "number", "align": "end", "width": 110, "sortable": False},
    {"key": "trader", "label": "Trader", "width": 116, "sortable": False, "hide_below": 800},
]


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    card = nustd.ui.CardRef.slot(title="Trades, as they print", subtitle="every token, newest first; a click opens it")


tape = View.card["tape"].to(nustd.ui.DataTableRef.slot(
    columns=COLUMNS, row_key="key", clickable_rows=True, density="compact", label="Trades",
))


@nu.host
def mint_of(key):
    return str(key).rsplit(":", 1)[0]


def out(plane):
    def follow(root):
        read = views.tape_rows(memes_at(root).tape.fallback([]))
        rows = nu.Reconcile(nuspace.atomic(memes_at(root).beat.on_change()), nu.let(nuspace.atomic(read), tape.set_rows), every=2.0)
        opened = nu.ReactEvery(tape.on_row_click(), lambda ev: control.open_token(root, mint_of(ev["key"]), View.history))
        return nu.ParallelAsync(rows, opened)

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


PLANE = PlaneSpec(
    "memes_overview",
    "Overview",
    icon="square-terminal",
    description="The memes terminal: tokens, trades and launches, live.",
    web=WebOptions(editable=True, width="board"),
    cells=(
        ("sync", BAR),
        ("tiles", TILES),
        ("tokens", TOKENS),
        ("tape", TAPE),
        ("launches", LAUNCHES),
    ),
    backend="async",
)
