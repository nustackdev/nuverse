"""The Sync plane: where the sync reads from, how fast, and from where on the chain.

- ``bar``: the sync's state, and Start or Stop, as everywhere.
- ``settings``: the RPC endpoint, the pace, the slot to start from, saved
  into the root's state. The job reads them every turn: a new endpoint or
  rate takes effect at once, a new start slot when "Start over" is pressed.
  "Show images" turns coins' own images on, off by default: some are explicit.
- ``state``: where the sync is and what it has read, as it says.
- ``about``: how the sync works.

The endpoint is kept in this space's state, never in code. Left empty, the
sync uses ``$NUVERSE_MEMES_RPC``, then the public mainnet endpoint.
"""

from __future__ import annotations

from nuspace import PlaneSpec

from .cells import BAR, cell


__all__ = ["ABOUT", "PLANE", "SETTINGS", "STATE"]


SETTINGS = cell("""\
class Knobs(nustd.ui.Grid):
    rpc = nustd.ui.InputRef.slot(label="RPC endpoint", placeholder="https://... (empty: $NUVERSE_MEMES_RPC, then the public one)")
    rate = nustd.ui.NumberInputRef.slot(label="Blocks a second, at most", min=0.2, max=10, step=0.5)
    start = nustd.ui.NumberInputRef.slot(label="Start from slot (0: the tip)", min=0, step=1)


class Images(nustd.ui.Row):
    show = nustd.ui.SwitchRef.slot(label="Show images")
    note = nustd.ui.TextRef.slot()


class Go(nustd.ui.Row):
    save = nustd.ui.ButtonRef.slot(label="Save", icon="save", variant="secondary")
    over = nustd.ui.ButtonRef.slot(label="Start over from there", icon="rotate-ccw", variant="secondary")
    hint = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    knobs = Knobs.slot(columns=3, min_width=240, gap=3)
    go = Go.slot(gap=3, align="center")
    images = Images.slot(gap=3, align="center")


K = View.knobs


def show(root):
    c = Control
    shown = at_root(root, nu.Dict.of(
        rpc=c.rpc.fallback(""), rate=c.rate.fallback(RATE), start=c.start.fallback(0), images=c.images.fallback(False),
    ))
    return nu.let(snap(shown), lambda v: (
        K.rpc.set(v["rpc"]) >> K.rate.set_value(v["rate"]) >> K.start.set_value(v["start"])
        >> View.go.hint.set(views.endpoint_hint(v["rpc"])) >> View.images.show.set(v["images"])
    ))


def save(root):
    # What the form says now, read from the browser once per click.
    rate = nu.If(nu.float(K.rate) > 0.0, nu.float(K.rate), RATE)
    kept = Control.rpc.set(nu.Str(K.rpc).strip()) >> Control.rate.set(rate) >> Control.start.set(nu.int(K.start))
    return ops.atomic_state(at_root(root, kept)) >> show(root)


def images(root):
    # The switch saves on its own: what it says now, read from the browser once per flip.
    return ops.atomic_state(at_root(root, Control.images.set(nu.Bool(View.images.show))))


def placed():
    # A slot shows once it is first written, in the order written: the knobs, the buttons, the hint.
    go = View.go
    return (
        K.rpc.set("") >> K.rate.set_value(RATE) >> K.start.set_value(0)
        >> go.save.set("Save", icon="save", variant="secondary")
        >> go.over.set("Start over from there", icon="rotate-ccw", variant="secondary")
        >> go.hint.set("")
        >> View.images.show.set(False)
        >> View.images.note.set("Coins' own images, off by default: anyone can launch a coin, and some images are explicit.")
    )


def out(plane):
    def follow(root):
        return placed() >> show(root) >> nu.ParallelAsync(
            nu.ReactForever(View.go.save.on_click(), save(root)),
            nu.ReactForever(View.go.over.on_click(), save(root) >> control.restart(root, nu.int(K.start))),
            nu.ReactForever(View.images.show.on_change(), images(root)),
        )

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


STATE = cell("""\
class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    state = nustd.ui.JsonViewerRef.slot(expand_depth=2, max_height=420)


@nu.host
def said(stats, sync):
    s = dict(stats or {})
    return {
        "status": s.get("status", "never started"),
        "notice": s.get("notice", ""),
        "mode": s.get("mode", "tip"),
        "slot": s.get("cursor", 0),
        "tip": s.get("tip", 0),
        "endpoint": s.get("rpc", ""),
        "totals": s.get("totals", {}),
        "rates": {k: round(v, 3) for k, v in (s.get("rates") or {}).items()},
        "saved": dict(sync or {}),
    }


def out(plane):
    def follow(root):
        read = said(at_root(root, Memes.stats.fallback({})), at_root(root, Memes.sync.fallback({})))
        return redraws([at_root(root, Memes.beat.on_change())], read, View.state.set_value, every=5.0)

    return View.head.set("What the sync says") >> nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


ABOUT = '''\
import nu
import nustd.ui

TEXT = """\\
### How the sync works

- A **headless job** under the Memes plane runs one Nu loop in its own process, kept up by the supervisor: it comes back after a crash, and when the space opens again.
- Each turn it asks for the chain's tip and a few blocks at once over JSON-RPC (`getSlot`, `getBlock`), as fast as the rate allows.
- In each block it finds the meme launchpad's own events, the ones the program writes as it runs: a coin **created**, a **trade** on its curve with the curve's reserves after it, a curve **completed**, its liquidity **migrated** to an AMM pool. Price, market cap and progress to graduation come straight off those reserves.
- It reads every block in order and never skips one, so the numbers stay whole. Solana makes a slot every ~220ms, so keeping up takes 4 to 5 blocks a second; slower, the sync falls behind the chain and the bar says so.
- The public endpoint allows 6 `getBlock` calls in 10 seconds, and a block is 3 to 6MB: there the sync reads a block every two seconds and runs further behind the chain as it goes.
- Coins it meets mid-life are named from their mint's on-chain metadata, a batch at a time.
- It keeps tokens six hours past their last trade, at most four thousand, the newest trades and a candle a minute for each. Metrics are kh57 series: they grow, and a chart samples them at the same cost however long it ran.
- Errors back it off, 1s doubling to 30s. Give it your own endpoint (Helius, Triton, QuickNode...) to keep up with the chain.
- Each coin's picture comes from the metadata its launch names, fetched beside the chain a few at a time, ipfs read through a public gateway. The image's address is kept with the coin; the browser loads the image itself, and only with "Show images" on: till then a picture painted from the coin's address stands in.
"""

out = nustd.ui.MarkdownRef("about").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = PlaneSpec(
    "memes_sync",
    "Sync",
    icon="cog",
    description="Where the memes sync reads from, how fast, and from which slot.",
    meta={"editable": True, "full_width": True},
    cells=(("sync", BAR), ("settings", SETTINGS), ("state", STATE), ("about", ABOUT)),
    backend="async",
)
