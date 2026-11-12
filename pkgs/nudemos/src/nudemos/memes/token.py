"""A token's page: one coin, live. Made on a click (:func:`~.control.open_token`), never ahead.

The page knows its token from its meta (``mint``) and its root from
``base``; every cell reads the token's record, trades and candles from the
root's state, as the sync rewrites them.

- ``head``: its picture, name, facts and links out. The picture is painted
  from the mint; the coin's own, read by the sync from its metadata, shows
  only once the Sync plane's "Show images" is on.
- ``numbers``: market cap, price, volume, trades, buys and sells, traders,
  and how far along the curve it is.
- ``chart``: market cap as candles, and the volume under them, one bar a
  candle: a minute each, or finer for a token only minutes old.
- ``trades``: its newest trades, and how buys and sells split.
"""

from __future__ import annotations

from .cells import cell


__all__ = ["CELLS", "CHART", "HEAD", "NUMBERS", "TRADES"]


#: What every token cell adds to the shared imports: where its token is, and how to read it.
_PAGE = """\
from nuspace import Space


def mint_of(plane):
    return nu.str(Space.planes[plane].meta["mint"].fallback(""))


def view_of(root, mint):
    m = memes_at(root)
    return views.token_view(
        m.tokens[mint].fallback({}), m.trades[mint].fallback([]),
        m.candles[mint].fallback([]), m.quotes.fallback({}), nustd.time.time(),
        control_at(root).images.fallback(False),
    )


def on_token(plane, body):
    # body(root, mint), once the page knows both.
    return nu.let(nuspace.atomic(root_of(plane)), lambda root: nu.let(nuspace.atomic(mint_of(plane)), lambda mint: body(nu.Str(root), nu.Str(mint))))


def following(root, mint, draw, every=2.0):
    moves = [memes_at(root).beat.on_change(), control_at(root).images.on_change()]
    return nu.Reconcile(nuspace.atomic(nu.OnAny(*moves)), nu.let(nuspace.atomic(view_of(root, mint)), draw), every=every)
"""


def _cell(body: str) -> str:
    return cell(_PAGE + "\n\n" + body)


HEAD = _cell("""\
class View(nu.Shape):
    head = nustd.ui.RowRef.slot(gap=5, align="start", grow={"who": 1})


face = View.head["face"].to(nustd.ui.ImageRef.slot(width=96, height=96, radius="md", fit="contain"))
who = View.head["who"].to(nustd.ui.ColumnRef.slot(gap=2))
title = who["title"].to(nustd.ui.HeadingRef.slot(level=2))
facts = who["facts"].to(nustd.ui.MarkdownRef)
links = who["links"].to(nustd.ui.RowRef.slot(gap=3, wrap=True))
state = View.head["state"].to(nustd.ui.StatusPillRef)


def link(l):
    out = links[nu.Str(l["key"])].to(nustd.ui.LinkRef.slot(target="_blank", external=True))
    return out.set(href=l["href"], label=l["label"])


def draw(v):
    # Its own picture with "Show images" on and once the sync has read it, a painted one otherwise.
    keys = nu.List(v["link_keys"])
    found = (
        face.set(v["src"], alt=v["symbol"])
        >> title.set(v["title"]) >> facts.set(v["facts"])
        >> nu.ForEachDo(nu.List(v["links"]), link) >> links.keep(keys) >> links.set_order(keys)
        >> state.set(v["state"], tone=v["tone"])
    )
    gone = title.set("Not followed any more") >> facts.set("The sync let this token go: it went quiet, or the sync never saw it.")
    return nu.IfDo(nu.Bool(v["found"]), found, gone)


def out(plane):
    def build(root, mint):
        # The page named after the coin's ticker, once it is known.
        first = nuspace.atomic(view_of(root, mint))
        named = nu.let(first, lambda v: nu.IfDo(nu.Bool(v["found"]), nuspace.atomic(nuspace.plane.rename(plane, v["symbol"]))))
        return named >> following(root, mint, draw)

    return on_token(plane, build)
""")


NUMBERS = _cell("""\
KEYS = {
    "mc": "Market cap",
    "price": "Price",
    "vol": "Volume",
    "trades": "Trades",
    "bs": "Buys / sells",
    "traders": "Traders seen",
}


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=4)


both = View.page["both"].to(nustd.ui.GridRef.slot(cols="2fr 1fr", stack_below=800, gap=4))
progress = View.page["progress"].to(nustd.ui.ProgressRef)
tiles = both[0, 0].to(nustd.ui.GridRef.slot(max_columns=3, min_cell_width=150, gap=3))
curve = both[0, 1].to(nustd.ui.CardRef.slot(title="To graduation", size="sm"))["curve"].to(
    nustd.ui.GaugeChart.slot(name="to graduation", value_format="{value}%", height=200)
)


def tile(k):
    return tiles[k].to(nustd.ui.CardRef.slot(size="sm"))[0].to(nustd.ui.StatRef.slot(label=KEYS[k]))


def draw(v):
    shown = (
        tile("mc").set(v["mc"], delta=v["move"] + " since launch", trend=v["trend"]) >> tile("price").set(v["price"])
        >> tile("vol").set(v["vol"]) >> tile("trades").set(v["trades"], delta=v["last"]) >> tile("bs").set(v["bs"])
        >> tile("traders").set(v["traders"])
        >> curve.set(v["progress"]) >> progress.set(v["progress"] / 100.0, caption=v["progress_caption"])
    )
    return nu.IfDo(nu.Bool(v["found"]), shown)


def out(plane):
    return on_token(plane, lambda root, mint: following(root, mint, draw))
""")


CHART = _cell("""\
#: Seconds between repaints at most.
EVERY = 2.0


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Market cap", subtitle="volume under it")


candles = View.card["candles"].to(nustd.ui.CandlestickChart.slot(height=300, option={"animation": False}))
volume = View.card["volume"].to(nustd.ui.BarChart.slot(height=140, option={"animation": False}))


def paint(root, mint):
    def draw(v):
        drawn = (
            View.card.set_title(v["chart_title"]) >> View.card.set_subtitle(v["volume_title"])
            >> candles.set(v["candles"]) >> volume.set(v["volume"])
        )
        return nu.IfDo(nu.Bool(v["found"]), drawn)

    return nu.let(nuspace.atomic(view_of(root, mint)), draw)


def out(plane):
    def build(root, mint):
        beat = nuspace.atomic(memes_at(root).beat.on_change())
        return nu.Reconcile(beat, paint(root, mint) >> nu.Delay(EVERY), every=10.0)

    return on_token(plane, build)
""")


TRADES = _cell("""\
COLUMNS = [
    {"key": "time", "label": "Time", "width": 96, "sortable": False},
    {"key": "side", "label": "Side", "width": 84, "sortable": False, "cell": nustd.ui.BadgeRef.slot(size="sm")},
    {"key": "amount", "label": "Amount", "kind": "number", "align": "end", "sortable": False},
    {"key": "tokens", "label": "Tokens", "kind": "number", "align": "end", "sortable": False, "hide_below": 640},
    {"key": "mc", "label": "Market cap", "kind": "number", "align": "end", "sortable": False},
    {"key": "trader", "label": "Trader", "width": 116, "sortable": False, "hide_below": 800},
]


class View(nu.Shape):
    both = nustd.ui.GridRef.slot(cols="2fr 1fr", stack_below=800, gap=4)


trades = View.both[0, 0].to(nustd.ui.CardRef.slot(title="Trades", subtitle="newest first"))
table = trades["table"].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Trades"))
split = View.both[0, 1].to(nustd.ui.CardRef.slot(title="Buys and sells", subtitle="by volume"))["split"].to(
    nustd.ui.PieChart.slot(donut=True, height=240, colors=["var(--status-ok)", "var(--status-danger)"])
)


def draw(v):
    rows = table.set_rows(v["rows"]) >> split.set(v["split"])
    return trades.set_title(nu.Str("Trades in ") + nu.Str(nu.Dict(v).get_item("unit", ""))) >> nu.IfDo(nu.Bool(v["found"]), rows)


def out(plane):
    return on_token(plane, lambda root, mint: following(root, mint, draw))
""")


CELLS = (("head", HEAD), ("numbers", NUMBERS), ("chart", CHART), ("trades", TRADES))
