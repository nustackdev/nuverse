"""The bonding curve, as far as watching it needs: price, market cap, progress to graduation.

A launchpad coin trades against a constant-product curve over virtual
reserves, ``vquote * vtok = k``, until its real tokens run out and it
graduates to a pool on the AMM. Every ``TradeEvent`` carries the reserves
after its trade, so a watcher reads the curve off the event and runs no
formula. The trade formulas are here too, integer for integer as the
program runs them, so the published genesis numbers can be checked.

Quote amounts are in the quote's smallest unit (lamports for SOL), tokens in
raw units: every launchpad coin has 6 decimals.
"""

from __future__ import annotations


__all__ = [
    "GENESIS_RTOK",
    "GENESIS_VSOL",
    "GENESIS_VTOK",
    "LAMPORTS",
    "SUPPLY",
    "TOKEN_DECIMALS",
    "buy_exact_in",
    "buy_tokens",
    "market_cap",
    "price",
    "progress",
    "sell_tokens",
]


#: Raw units in one token: every launchpad coin has 6 decimals.
TOKEN_DECIMALS = 6

#: Lamports in one SOL.
LAMPORTS = 10**9

#: What a curve starts with: 30 SOL virtual, 1.073B tokens virtual, 793.1M of them real.
GENESIS_VSOL = 30_000_000_000
GENESIS_VTOK = 1_073_000_000_000_000
GENESIS_RTOK = 793_100_000_000_000

#: A coin's total supply, raw: 1B tokens. Mayhem coins can mint more; the create event says.
SUPPLY = 1_000_000_000_000_000


def price(vquote: int, vtok: int, quote_decimals: int = 9) -> float:
    """The curve's marginal price, in quote per whole token: ``vquote / vtok``, scaled to display units."""
    if vtok <= 0:
        return 0.0
    return vquote / vtok * 10 ** (TOKEN_DECIMALS - quote_decimals)


def market_cap(vquote: int, vtok: int, supply: int = SUPPLY, quote_decimals: int = 9) -> float:
    """The marginal price times the supply, in whole quote units (SOL for a SOL coin)."""
    if vtok <= 0:
        return 0.0
    return vquote * supply / vtok / 10**quote_decimals


def progress(rtok: int, genesis: int = GENESIS_RTOK) -> float:
    """How far to graduation, 0 to 1: the share of the curve's real tokens bought out."""
    if genesis <= 0:
        return 0.0
    return min(1.0, max(0.0, 1.0 - rtok / genesis))


def buy_tokens(vquote: int, vtok: int, quote_in: int) -> int:
    """Tokens out for ``quote_in`` net of fees: ``vtok * q // (vquote + q)``, one integer floor."""
    return vtok * quote_in // (vquote + quote_in)


def buy_exact_in(vquote: int, vtok: int, quote_in: int) -> int:
    """Tokens out of ``buy_exact_sol_in``: the same with the program's one-unit slippage guard."""
    return (quote_in - 1) * vtok // (vquote + quote_in - 1)


def sell_tokens(vquote: int, vtok: int, tokens_in: int) -> int:
    """Quote out, before fees, for ``tokens_in``: ``vquote * t // (vtok + t)``, one integer floor."""
    return vquote * tokens_in // (vtok + tokens_in)
