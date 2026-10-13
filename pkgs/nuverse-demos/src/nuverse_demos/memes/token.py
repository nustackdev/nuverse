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
from nuspace.shapes import Space


def mint_of(plane):
    return nu.str(Space.planes[plane].meta["mint"]).fallback("")


def view_of(root, mint):
    m = Memes
    return views.token_view(
        at_root(root, m.tokens[mint].fallback({})), at_root(root, m.trades[mint].fallback([])),
        at_root(root, m.candles[mint].fallback([])), at_root(root, m.quotes.fallback({})), nustd.time.time(),
        at_root(root, Control.images.fallback(False)),
    )


def on_token(plane, body):
    # body(root, mint), once the page knows both.
    return nu.let(snap(root_of(plane)), lambda root: nu.let(snap(mint_of(plane)), lambda mint: body(nu.Str(root), nu.Str(mint))))


def following(root, mint, draw, every=2.0):
    moves = [at_root(root, Memes.beat.on_change()), at_root(root, Control.images.on_change())]
    return redraws(moves, view_of(root, mint), draw, every=every)
"""


def _cell(body: str) -> str:
    return cell(_PAGE + "\n\n" + body)


HEAD = _cell("""\
class Who(nustd.ui.Column):
    title = nustd.ui.HeadingRef.slot(level=2)
    facts = nustd.ui.MarkdownRef.slot()
    links = nustd.ui.MarkdownRef.slot()


class Head(nustd.ui.Row):
    face = nustd.ui.ImageRef.slot(width=96, height=96, rounded=True, fit="contain")
    who = Who.slot(gap=1)
    state = nustd.ui.StatusPillRef.slot()


class View(nustd.ui.Column):
    head = Head.slot(gap=5, align="start")


def draw(v):
    # Its own picture with "Show images" on and once the sync has read it, a painted one otherwise.
    h = View.head
    found = (
        h.face.set(v["src"], alt=v["symbol"], width=96, height=96, fit="contain", rounded=True)
        >> h.who.title.set(v["title"]) >> h.who.facts.set(v["facts"]) >> h.who.links.set(v["links"])
        >> h.state.set(v["state"], tone=v["tone"])
    )
    gone = h.who.title.set("Not followed any more") >> h.who.facts.set("The sync let this token go: it went quiet, or the sync never saw it.")
    return nu.IfDo(nu.Bool(v["found"]), found, gone)


def out(plane):
    def build(root, mint):
        # The page named after the coin's ticker, once it is known.
        first = snap(view_of(root, mint))
        named = nu.let(first, lambda v: nu.IfDo(nu.Bool(v["found"]), ops.rename_plane(plane, v["symbol"])))
        return named >> following(root, mint, draw)

    return on_token(plane, build)
""")


NUMBERS = _cell("""\
class Tiles(nustd.ui.Grid):
    mc = nustd.ui.StatRef.slot(label="Market cap")
    price = nustd.ui.StatRef.slot(label="Price")
    vol = nustd.ui.StatRef.slot(label="Volume")
    trades = nustd.ui.StatRef.slot(label="Trades")
    bs = nustd.ui.StatRef.slot(label="Buys / sells")
    traders = nustd.ui.StatRef.slot(label="Traders seen")


class Both(nustd.ui.Row):
    tiles = Tiles.slot(columns=3, min_width=150, gap=3)
    curve = nustd.ui.GaugeChart.slot(name="to graduation", value_format="{value}%", height=200)


class View(nustd.ui.Column):
    both = Both.slot(gap=5, align="center", wrap=True, min_width=320)
    progress = nustd.ui.ProgressRef.slot()


def draw(v):
    t = View.both.tiles
    tiles = (
        t.mc.set(v["mc"], delta=v["move"] + " since launch", trend=v["trend"]) >> t.price.set(v["price"])
        >> t.vol.set(v["vol"]) >> t.trades.set(v["trades"], delta=v["last"]) >> t.bs.set(v["bs"])
        >> t.traders.set(v["traders"])
    )
    curve = View.both.curve.set(v["progress"]) >> View.progress.set(v["progress"] / 100.0, caption=v["progress_caption"])
    return nu.IfDo(nu.Bool(v["found"]), tiles >> curve)


def out(plane):
    return on_token(plane, lambda root, mint: following(root, mint, draw))
""")


CHART = _cell("""\
#: Seconds between repaints at most.
EVERY = 2.0


class Charts(nustd.ui.Column):
    candles = nustd.ui.CandlestickChart.slot(
        title="Market cap, a candle a minute", height=300, option={"animation": False},
    )
    volume = nustd.ui.BarChart.slot(title="Volume, a bar a minute", height=140, option={"animation": False})


class View(nustd.ui.Column):
    charts = Charts.slot(gap=2)


def paint(root, mint):
    def draw(v):
        c = View.charts
        def titled(text):
            return nu.Dict.of(title=nu.List.of(nu.Dict.of(id="title", text=text)))

        drawn = (
            c.candles.set(v["candles"]) >> c.candles.merge(titled(v["chart_title"]))
            >> c.volume.set(v["volume"]) >> c.volume.merge(titled(v["volume_title"]))
        )
        return nu.IfDo(nu.Bool(v["found"]), drawn)

    return nu.let(snap(view_of(root, mint)), draw)


def out(plane):
    def build(root, mint):
        beat = snap(at_root(root, Memes.beat.on_change()))
        return nu.ReconcileReactive(beat, paint(root, mint) >> nu.Delay(EVERY), every=10.0)

    return on_token(plane, build)
""")


TRADES = _cell("""\
COLUMNS = [
    {"key": "time", "label": "Time", "width": 96, "sortable": False},
    {"key": "side", "label": "Side", "width": 84, "sortable": False},
    {"key": "amount", "label": "Amount", "kind": "number", "sortable": False},
    {"key": "tokens", "label": "Tokens", "kind": "number", "sortable": False},
    {"key": "mc", "label": "Market cap", "kind": "number", "sortable": False},
    {"key": "trader", "label": "Trader", "width": 116, "sortable": False},
]


class Both(nustd.ui.Row):
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Trades")
    split = nustd.ui.PieChart.slot(
        title="Buys and sells, by volume", donut=True, height=240,
        colors=["var(--status-ok)", "var(--status-danger)"],
    )


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    both = Both.slot(gap=5, align="start", wrap=True, min_width=320)


def draw(v):
    rows = View.both.table.set_rows(v["rows"]) >> View.both.split.set(v["split"])
    return View.head.set(nu.Str("Trades in ") + nu.Str(nu.Dict(v).get_item("unit", ""))) >> nu.IfDo(nu.Bool(v["found"]), rows)


def out(plane):
    return on_token(plane, lambda root, mint: following(root, mint, draw))
""")


CELLS = (("head", HEAD), ("numbers", NUMBERS), ("chart", CHART), ("trades", TRADES))
