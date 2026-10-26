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

from nuspace import PlaneSpec

from .cells import BAR, LAUNCHES, TILES, cell


__all__ = ["PLANE", "TAPE", "TOKENS"]


TOKENS = cell("""\
def column(key, label, width=0, number=True, sortable=True):
    c = {"key": key, "label": label, "sortable": sortable}
    if number:
        c["kind"] = "number"
    if width:
        c["width"] = width
    return c


COLUMNS = [
    column("token", "Token", 120, number=False, sortable=False),
    column("name", "Name", number=False, sortable=False),
    column("age", "Age", 72),
    column("mc", "Market cap", 116),
    column("move", "Since launch", 116, sortable=False),
    column("curve", "Curve", 92),
    column("vol", "Volume", 104),
    column("trades", "Trades", 84, sortable=False),
    column("bs", "Buys / sells", 110, sortable=False),
    column("last", "Last trade", 104),
]

ORDERS = [{"value": k, "label": v} for k, v in views.SORTS.items()]


class Head(nustd.ui.Row):
    title = nustd.ui.HeadingRef.slot(level=4)
    sort = nustd.ui.SelectRef.slot(options=ORDERS, selected="new")


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    head = Head.slot(gap=3, align="center", justify="between")
    table = nustd.ui.TableRef.slot(
        columns=COLUMNS, row_key="mint", clickable_rows=True, dense=True, label="Tokens",
        sort_column="age", sort_direction="desc",
    )


class Pick(nu.Shape):
    # This tab's order: a board list.
    sort = nu.StrRef.slot()


@nu.host
def by_column(column):
    return views.COLUMN_SORTS.get(column, "")


@nu.host
def column_of(sort):
    return {v: k for k, v in views.COLUMN_SORTS.items()}.get(sort, "")


def out(plane):
    t = View.table

    def follow(root):
        read = views.token_rows(at_root(root, Memes.board.fallback({})), Pick.sort, nustd.time.time())
        draw = redraw(read, t.set_rows)
        shown = nu.ReconcileReactive(snap(at_root(root, Memes.beat.on_change())), draw, every=2.0)

        def order(sort):
            # A new order: the picker, the header's arrows and the rows, at once.
            s = nu.Str(sort)
            return Pick.sort.set(s) >> View.head.sort.set(s) >> t.set_sort(column_of(s), "desc") >> draw

        picked = nu.ReactForever(View.head.sort.on_change(), order(nu.Str(View.head.sort)))
        clicked = nu.ReactForever(t.on_sort(), lambda ev: nu.let(by_column(ev["sort_column"]), lambda s: nu.IfDo(nu.Str(s) != "", order(s))))
        opened = nu.ReactForever(t.on_row_click(), lambda ev: control.open_token(root, nu.Str(ev["key"]), View.history))
        body = nu.ParallelAsync(shown, picked, clicked, opened)
        # A slot shows once it is first written: the title, then the picker.
        head = View.head.title.set("Tokens") >> View.head.sort.set_options(ORDERS) >> View.head.sort.set("new")
        return head >> nu.Frame(Pick, drawing(body), sort="new")

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


TAPE = cell("""\
COLUMNS = [
    {"key": "age", "label": "Age", "kind": "number", "width": 64, "sortable": False},
    {"key": "side", "label": "Side", "width": 84, "sortable": False},
    {"key": "token", "label": "Token", "width": 120, "sortable": False},
    {"key": "amount", "label": "Amount", "kind": "number", "sortable": False},
    {"key": "mc", "label": "Market cap", "kind": "number", "width": 110, "sortable": False},
    {"key": "trader", "label": "Trader", "width": 116, "sortable": False},
]


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    head = nustd.ui.HeadingRef.slot(level=4)
    tape = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, dense=True, label="Trades")


@nu.host
def mint_of(key):
    return str(key).rsplit(":", 1)[0]


def out(plane):
    def follow(root):
        read = views.tape_rows(at_root(root, Memes.tape.fallback([])), nustd.time.time())
        rows = redraws([at_root(root, Memes.beat.on_change())], read, View.tape.set_rows, every=2.0)
        opened = nu.ReactForever(
            View.tape.on_row_click(),
            lambda ev: control.open_token(root, mint_of(ev["key"]), View.history),
        )
        return View.head.set("Trades, as they print") >> nu.ParallelAsync(rows, opened)

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


PLANE = PlaneSpec(
    "memes_overview",
    "Overview",
    icon="square-terminal",
    description="The memes terminal: tokens, trades and launches, live.",
    meta={"editable": True, "full_width": True},
    cells=(
        ("sync", BAR),
        ("tiles", TILES),
        ("tokens", TOKENS),
        ("tape", TAPE),
        ("launches", LAUNCHES),
    ),
    backend="async",
)
