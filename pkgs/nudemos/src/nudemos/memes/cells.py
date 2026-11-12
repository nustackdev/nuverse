"""The cells every memes plane shares, and the root's own.

Every cell is ``def out(plane)``: the plane it runs on comes in, and
:func:`~.state.root_of` finds the Memes root from there, where the sync
writes. The cells follow ``Memes.beat``, which moves once per commit of the
sync, and redraw on every wake.

- :data:`BAR`: the sync's status, where it is, and Start or Stop, with a notice while it
  runs behind the chain. On every plane.
- :data:`TILES`: the headline numbers.
- :data:`PULSE`: the last few hundred trades as dots, buys over sells.
- :data:`INTRO`, :data:`LAUNCHES`: the root's welcome, and the newest coins as cards.
"""

from __future__ import annotations


__all__ = ["BAR", "IMPORTS", "INTRO", "LAUNCHES", "PULSE", "ROOT", "TILES", "cell"]


#: What every cell imports.
IMPORTS = """\
import nu
import nuspace
import nustd.time
import nustd.ui
from nudemos.memes import control, views
from nudemos.memes.book import RATE
from nudemos.memes.state import control_at, memes_at, root_of
"""


def cell(body: str) -> str:
    """A cell's source: the shared imports, then ``body``."""
    return IMPORTS + "\n\n" + body


BAR = cell("""\
class Bar(nustd.ui.Row):
    dot = nustd.ui.StatusDotRef.slot(tone="neutral")
    pill = nustd.ui.StatusPillRef.slot()
    line = nustd.ui.TextRef.slot()
    toggle = nustd.ui.ButtonRef.slot(label="Start", icon="play")


class View(nustd.ui.Column):
    bar = Bar.slot(gap=3, align="center", grow={"line": 1})
    notice = nustd.ui.TextRef.slot(tone="muted", size="sm")


def read(root):
    stats = memes_at(root).stats.fallback({})
    stop = control_at(root).stop.fallback(False)
    return views.status(stats, control.live(root), stop, nustd.time.time())


def draw(v):
    b = View.bar
    return (
        b.dot.set(v["tone"], pulse=v["pulse"])
        >> b.pill.set(v["status"], tone=v["tone"])
        >> b.line.set(v["line"])
        >> b.toggle.set(v["button"], variant=v["variant"], icon=v["icon"], disabled=v["disabled"])
        >> View.notice.set(v["notice"])
    )


def press(root):
    # What the button says is what it does: Start runs the sync, Stop asks it to end.
    def act(v):
        said = nu.Str(v["button"])
        return nu.IfDo(said == "Stop", control.stop(root), nu.IfDo(said == "Start", control.start(root)))

    return nu.let(nuspace.atomic(read(root)), act)


def out(plane):
    def follow(root):
        moves = [memes_at(root).beat.on_change(), control_at(root).stop.on_change()]
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*moves)), nu.let(nuspace.atomic(read(root)), draw), every=1.0),
            nu.ReactEvery(View.bar.toggle.on_click(), press(root)),
        )

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


TILES = cell("""\
KEYS = {
    "tokens": "Tokens",
    "launches": "Launches",
    "trades": "Trades",
    "volume": "Volume, SOL",
    "buys": "Buys",
    "graduations": "Graduations",
    "blocks": "Blocks read",
    "lag": "Lag",
}


class View(nu.Shape):
    tiles = nustd.ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=3)


def tile(k, label):
    return View.tiles[k].to(nustd.ui.CardRef.slot(size="sm"))[0].to(nustd.ui.StatRef.slot(label=label))


def draw(t):
    def one(k, label):
        s = t[k]
        return tile(k, label).set(s["value"], delta=s["delta"], trend=s["trend"])

    return nu.Sequential(*(one(k, label) for k, label in KEYS.items()))


def out(plane):
    def follow(root):
        read = views.tiles(memes_at(root).stats.fallback({}))
        return nu.Reconcile(nuspace.atomic(memes_at(root).beat.on_change()), nu.let(nuspace.atomic(read), draw))

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


PULSE = cell("""\
#: Seconds between repaints at most: the dots move with every block.
EVERY = 1.0

#: Trades one after another across, SOL up on a log scale: buys green, sells red.
SHAPE = {
    "xAxis": {"min": "dataMin", "max": "dataMax", "splitLine": {"show": False}, "axisLabel": {"show": False}},
    "yAxis": {"type": "log", "min": 0.001, "axisLabel": {"formatter": "{value} SOL"}},
    "series": [
        {"itemStyle": {"color": "var(--status-ok)", "opacity": 0.7}},
        {"itemStyle": {"color": "var(--status-danger)", "opacity": 0.7}},
    ],
    "tooltip": {"formatter": "{b}"},
    "animation": False,
}


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="The last few hundred trades", subtitle="in SOL, one after another")


chart = View.card["chart"].to(
    nustd.ui.ScatterChart.slot(["buys", "sells"], symbol_size=7, height=260, legend=True, option=SHAPE)
)


def paint(root):
    return nu.let(nuspace.atomic(views.pulse(memes_at(root).pulse.fallback([]))), chart.set)


def out(plane):
    def follow(root):
        # One pass at a time: blocks landing while it paints merge into one more.
        beat = nuspace.atomic(memes_at(root).beat.on_change())
        return nu.Reconcile(beat, paint(root) >> nu.Delay(EVERY), every=5.0)

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


INTRO = '''\
import nu
import nuspace
import nuspace.web
import nustd.ui

TEXT = """\\
### The meme market, live

Every meme coin launched, every trade on its curve, every graduation, read straight off Solana as the blocks land.
A headless job follows the chain and writes into this space's state; every page here is a small program reading it.
It only watches: no wallets, no buying, no advice.
"""

#: What the root's first three children hold, in the order the spec makes them.
WAYS = [
    "The terminal: tokens, trades as they print, the newest launches",
    "The sync itself: blocks a second, lag, RPC latency, errors",
    "The RPC endpoint, the pace, and where to start",
]


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=4)


text = View.page["text"].to(nustd.ui.MarkdownRef)
ways = View.page["ways"].to(nustd.ui.GridRef.slot(max_columns=3, min_cell_width=200, gap=3))


def links(kids):
    def way(i, what):
        pid = nu.Str(nu.List(kids)[i])
        tile = ways[pid].to(nustd.ui.PageLinkRef.slot(variant="tile"))
        return nuspace.web.link(tile, pid, description=what)

    return nu.Sequential(*(way(i, what) for i, what in enumerate(WAYS)))


def out(plane):
    # The spec makes Overview, Monitor and Sync as the root's first three children.
    first = nuspace.Space.planes[plane].children.keys(limit=3)
    shown = nu.let(first, lambda kids: links(kids))
    return text.set(TEXT) >> nuspace.atomic(shown) >> nu.ForeverDo(nu.Delay(3600.0))
'''


LAUNCHES = cell("""\
#: Cards shown: the newest launches, newest first.
N = 12


class Shown(nu.Shape):
    # The mints this tab drew, card by card: a click opens what it shows.
    mints = nu.ObjectRef.slot()


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    launches = nustd.ui.CardRef.slot(title="New launches", subtitle="newest first")


cards = View.launches["cards"].to(nustd.ui.GridRef.slot(max_columns=4, min_cell_width=240, gap=3))
OPEN = nustd.ui.ButtonRef.slot(label="Open", icon="arrow-right", variant="soft", size="sm", tooltip="Open its page")


def card(i):
    return cards[i].to(nustd.ui.CardRef.slot(size="sm"))


def draw(shown):
    def one(i):
        c, at = nu.Dict(shown[i]), card(i)
        body = at["body"].to(nustd.ui.RowRef.slot(gap=3, align="center"))
        return (
            at.set_title(c["symbol"]) >> at.set_subtitle(c["name"])
            >> body["face"].to(nustd.ui.ImageRef.slot(width=48, height=48, radius="md", fit="contain")).set(c["src"], alt=c["symbol"])
            >> body["note"].to(nustd.ui.TextRef.slot(tone="muted", size="sm")).set(c["note"])
            >> at.actions["open"].to(OPEN).init()
        )

    mints = shown.iter().map(lambda c: nu.Dict(c)["mint"]).to_list()
    return nu.ForRangeDo(0, shown.len(), one) >> cards.truncate(shown.len()) >> Shown.mints.set(mints)


def opener(root, i):
    # A coin's page is made on its first open, so each card position has its own handler.
    mints = nu.List(Shown.mints)
    go = control.open_token(root, nu.Str(mints[i]), View.history)
    return nu.ReactEvery(card(i).actions["open"].to(OPEN).on_click(), nu.IfDo(mints.len() > i, go))


def out(plane):
    def follow(root):
        # A coin's own image only once the Sync plane's "Show images" is on.
        images = control_at(root).images.fallback(False)
        read = views.launch_cards(memes_at(root).launches.fallback([]), nustd.time.time(), N, images)
        moves = [memes_at(root).beat.on_change(), control_at(root).images.on_change()]
        shown = nu.Reconcile(nuspace.atomic(nu.OnAny(*moves)), nu.let(nuspace.atomic(read), lambda c: draw(nu.List(c))), every=5.0)
        opens = [opener(root, i) for i in range(N)]
        return nu.Frame(Shown, nu.ParallelAsync(shown, *opens), mints=[])

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


ROOT = (("intro", INTRO), ("sync", BAR), ("tiles", TILES), ("pulse", PULSE), ("launches", LAUNCHES))
