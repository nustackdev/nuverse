"""The cells every memes plane shares, and the root's own.

Every cell is ``def out(plane)``: the plane it runs on comes in, and
:func:`~.state.root_of` finds the Memes root from there, where the sync
writes. The cells follow ``Memes.beat``, which moves once per commit of the
sync, and redraw only what reads differently.

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
import nustd.time
import nustd.ui
from nuspace import ops
from nuspace.system.utils import drawing, redraw, redraws, snap
from nudemos.memes import control, views
from nudemos.memes.book import RATE
from nudemos.memes.state import Control, Memes, at_root, root_of
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
    bar = Bar.slot(gap=3, align="center")
    notice = nustd.ui.TextRef.slot()


def read(root):
    stats = at_root(root, Memes.stats.fallback({}))
    stop = at_root(root, Control.stop.fallback(False))
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

    return nu.let(snap(read(root)), act)


def out(plane):
    def follow(root):
        moves = [at_root(root, Memes.beat.on_change()), at_root(root, Control.stop.on_change())]
        return nu.ParallelAsync(
            redraws(moves, read(root), draw, every=1.0),
            nu.ReactForever(View.bar.toggle.on_click(), press(root)),
        )

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
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

Tiles = type("Tiles", (nustd.ui.Grid,), {k: nustd.ui.StatRef.slot(label=v) for k, v in KEYS.items()})


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=8, min_width=128, gap=3)


def draw(t):
    def tile(k):
        s = t[k]
        return getattr(View.tiles, k).set(s["value"], delta=s["delta"], trend=s["trend"])

    return nu.Sequential(*(tile(k) for k in KEYS))


def out(plane):
    def follow(root):
        read = views.tiles(at_root(root, Memes.stats.fallback({})))
        return redraws([at_root(root, Memes.beat.on_change())], read, draw)

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
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


class View(nustd.ui.Column):
    chart = nustd.ui.ScatterChart.slot(
        ["buys", "sells"], title="The last few hundred trades, in SOL", symbol_size=7,
        height=260, legend=True, option=SHAPE,
    )


def paint(root):
    return nu.let(snap(views.pulse(at_root(root, Memes.pulse.fallback([])))), View.chart.set)


def out(plane):
    def follow(root):
        # One pass at a time: blocks landing while it paints merge into one more.
        beat = snap(at_root(root, Memes.beat.on_change()))
        return nu.ReconcileReactive(beat, paint(root) >> nu.Delay(EVERY), every=5.0)

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


INTRO = '''\
import nu
import nuspace.ui
import nustd.ui
from nuspace import ops
from nuspace.system.utils import snap

TEXT = """\\
### The meme market, live

Every meme coin launched, every trade on its curve, every graduation, read straight off Solana as the blocks land.
A headless job follows the chain and writes into this space's state; every page here is a small program reading it.

- **Overview** is the terminal: the tokens, the trades as they print, the newest launches. Click a token to open its page.
- **Monitor** watches the sync itself: blocks a second, lag behind the tip, the RPC's latency, errors.
- **Sync** sets the RPC endpoint and the pace, and where to start.

It only watches: no wallets, no buying, no advice.
"""


class Links(nustd.ui.Row):
    overview = nustd.ui.LinkRef.slot()
    monitor = nustd.ui.LinkRef.slot()
    sync = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    links = Links.slot(gap=4)


def links(kids):
    def to(i):
        return nuspace.ui.href(nu.List(kids)[i])

    l = View.links
    return l.overview.set(href=to(0), label="Open the terminal") >> l.monitor.set(href=to(1), label="Monitor") >> l.sync.set(href=to(2), label="Sync settings")


def out(plane):
    return View.text.set(TEXT) >> nu.let(snap(ops.children(plane)), links) >> nu.ForeverDo(nu.Delay(3600.0))
'''


LAUNCHES = cell("""\
#: Cards shown: the newest launches, newest first.
N = 12


class Body(nustd.ui.Row):
    face = nustd.ui.ImageRef.slot(width=48, height=48, rounded=True, fit="contain")
    note = nustd.ui.TextRef.slot()
    open = nustd.ui.ButtonRef.slot(label="Open", icon="arrow-right", variant="soft", tooltip="Open its page")


class Launch(nustd.ui.Card):
    body = Body.slot(gap=3, align="center")


Cards = type("Cards", (nustd.ui.Grid,), {f"c{i}": Launch.slot() for i in range(N)})


class Shown(nu.Shape):
    # The mints this tab drew, card by card: a click opens what it shows.
    mints = nu.ObjectRef.slot()


class View(nustd.ui.Column):
    history = nustd.ui.HistoryRef.slot()
    head = nustd.ui.HeadingRef.slot(level=4)
    cards = Cards.slot(min_width=240, gap=3)


def draw(cards):
    def one(i, c):
        card = getattr(View.cards, f"c{i}")
        return (
            card.set_title(c["symbol"]) >> card.set_subtitle(c["name"])
            >> card.body.face.set(c["src"], alt=c["symbol"]) >> card.body.note.set(c["note"])
            >> card.body.open.set("Open", icon="arrow-right", variant="soft")
        )

    shown = nu.List(cards)
    each = [nu.IfDo(shown.len() > i, nu.let(shown[i], lambda c, i=i: one(i, c))) for i in range(N)]
    mints = shown.iter().map(lambda c: nu.Dict(c)["mint"]).to_list()
    return nu.Sequential(*each) >> Shown.mints.set(mints)


def opener(root, i):
    mints = nu.List(Shown.mints)
    go = control.open_token(root, nu.Str(mints[i]), View.history)
    return nu.ReactForever(getattr(View.cards, f"c{i}").body.open.on_click(), nu.IfDo(mints.len() > i, go))


def out(plane):
    def follow(root):
        # A coin's own image only once the Sync plane's "Show images" is on.
        images = at_root(root, Control.images.fallback(False))
        read = views.launch_cards(at_root(root, Memes.launches.fallback([])), nustd.time.time(), N, images)
        moves = [at_root(root, Memes.beat.on_change()), at_root(root, Control.images.on_change())]
        shown = redraws(moves, read, draw, every=5.0)
        opens = [opener(root, i) for i in range(N)]
        return View.head.set("New launches") >> nu.Frame(Shown, nu.ParallelAsync(shown, *opens), mints=[])

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


ROOT = (("intro", INTRO), ("sync", BAR), ("tiles", TILES), ("pulse", PULSE), ("launches", LAUNCHES))
