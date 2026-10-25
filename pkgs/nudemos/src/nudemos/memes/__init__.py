"""The ``memes`` Plane: a live terminal over the meme market, read straight off Solana.

A headless job follows the chain over JSON-RPC, finds the meme launchpad's own events
in every block it reads (a coin created, a trade on its curve, a curve
completed, liquidity migrated), and writes what it makes of them into the
root's state: a record per token, the newest trades, the newest launches,
totals, and kh57 metrics. Every page is a few small programs reading that
state as it moves. It only watches: no wallets, no trading.

- :mod:`.chain`, :mod:`.curve`: the decoding and the curve math, plain Python.
- :mod:`.book`: what the sync asks next and what it keeps, plain Python.
- :mod:`.job`: the sync's Nu loop over the book, the cell the job runs.
- :mod:`.state`, :mod:`.control`: the state every plane shares, and the ops over it.
- :mod:`.views`: what the cells read, shaped for the widgets.
- :mod:`.cells`, :mod:`.overview`, :mod:`.monitor`, :mod:`.sync`, :mod:`.token`: the planes, as cell sources.

The RPC endpoint is set on the Sync plane, or ``$NUVERSE_MEMES_RPC``, or the
public mainnet endpoint. Calls go out through ``nustd.http``: the ``memes``
extra brings it, ``pip install "nudemos[memes]"``.
"""

from __future__ import annotations

from nuspace import PlaneSpec

from . import cells, monitor, overview, sync


__all__ = ["PLANE"]


PLANE = PlaneSpec(
    "memes",
    "Memes",
    icon="flame",
    description="A live terminal over meme launches, synced from Solana.",
    meta={"editable": True, "full_width": True},
    cells=cells.ROOT,
    children=(overview.PLANE, monitor.PLANE, sync.PLANE),
    group="Demos",
    backend="async",
)
