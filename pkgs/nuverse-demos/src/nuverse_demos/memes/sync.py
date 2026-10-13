"""The Sync plane: where the sync reads from, how fast, and from where on the chain.

- ``bar``: the sync's state, and Start or Stop, as everywhere.
- ``settings``: the RPC endpoint, the pace, the slot to start from, saved
  into the root's state. The job reads them every turn: a new endpoint or
  rate takes effect at once, a new start slot when "Start over" is pressed.
- ``state``: where the sync is and what it has read, as it says.
- ``about``: how the sync works.

The endpoint is kept in this space's state, never in code. Left empty, the
sync uses ``$NUVERSE_MEMES_RPC``, then the public mainnet endpoint.
"""

from __future__ import annotations

from nuspace import Plane

from .cells import BAR, cell


__all__ = ["ABOUT", "PLANE", "SETTINGS", "STATE"]


SETTINGS = cell("""\
class Knobs(nustd.ui.Grid):
    rpc = nustd.ui.InputRef.slot(label="RPC endpoint", placeholder="https://... (empty: $NUVERSE_MEMES_RPC, then the public one)")
    rate = nustd.ui.NumberInputRef.slot(label="Blocks a second, at most", min=0.2, max=10, step=0.5)
    start = nustd.ui.NumberInputRef.slot(label="Start from slot (0: the tip)", min=0, step=1)


class Go(nustd.ui.Row):
    save = nustd.ui.ButtonRef.slot(label="Save", icon="save", variant="secondary")
    over = nustd.ui.ButtonRef.slot(label="Start over from there", icon="rotate-ccw", variant="secondary")
    hint = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    knobs = Knobs.slot(columns=3, min_width=240, gap=3)
    go = Go.slot(gap=3, align="center")


K = View.knobs


def show(root):
    c = Control
    shown = at_root(root, nu.Dict.of(rpc=c.rpc.fallback(""), rate=c.rate.fallback(2.0), start=c.start.fallback(0)))
    return nu.let(snap(shown), lambda v: (
        K.rpc.set(v["rpc"]) >> K.rate.set_value(v["rate"]) >> K.start.set_value(v["start"])
        >> View.go.hint.set(views.endpoint_hint(v["rpc"]))
    ))


def save(root):
    # What the form says now, read from the browser once per click.
    rate = nu.If(nu.float(K.rate) > 0.0, nu.float(K.rate), 2.0)
    kept = Control.rpc.set(nu.Str(K.rpc).strip()) >> Control.rate.set(rate) >> Control.start.set(nu.int(K.start))
    return ops.atomic_state(at_root(root, kept)) >> show(root)


def placed():
    # A slot shows once it is first written, in the order written: the knobs, the buttons, the hint.
    go = View.go
    return (
        K.rpc.set("") >> K.rate.set_value(2.0) >> K.start.set_value(0)
        >> go.save.set("Save", icon="save", variant="secondary")
        >> go.over.set("Start over from there", icon="rotate-ccw", variant="secondary")
        >> go.hint.set("")
    )


def out(plane):
    def follow(root):
        return placed() >> show(root) >> nu.ParallelAsync(
            nu.ReactForever(View.go.save.on_click(), save(root)),
            nu.ReactForever(View.go.over.on_click(), save(root) >> control.restart(root, nu.int(K.start))),
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
- Solana makes a slot every ~220ms, so reading every block takes 4 to 5 a second. Slower, the sync stays live and skips ahead when it falls 40 slots behind, and the Monitor says what share it reads. Started from a slot it reads every block from there and never skips.
- The public endpoint allows 6 `getBlock` calls in 10 seconds, and a block is 3 to 6MB: there the sync reads the newest block every two seconds, about one block in nine, so what it shows is a live sample of the market.
- Coins it meets mid-life are named from their mint's on-chain metadata, a batch at a time.
- It keeps tokens six hours past their last trade, at most four thousand, the newest trades and a candle a minute for each. Metrics are kh57 series: they grow, and a chart samples them at the same cost however long it ran.
- Errors back it off, 1s doubling to 30s. Give it your own endpoint (Helius, Triton, QuickNode...) to read every block.
- Each coin's picture comes from the metadata its launch names, fetched beside the chain a few at a time, ipfs read through a public gateway. The image's address is kept with the coin; the browser loads the image itself.
"""

out = nustd.ui.MarkdownRef("about").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = Plane(
    "memes_sync",
    "Sync",
    icon="cog",
    description="Where the memes sync reads from, how fast, and from which slot.",
    meta={"editable": True, "full_width": True},
    cells=(("sync", BAR), ("settings", SETTINGS), ("state", STATE), ("about", ABOUT)),
    backend="async",
)
