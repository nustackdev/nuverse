"""What the memes cells read and draw: plain Python that turns the sync's state into widgets.

The job writes numbers; these functions make the strings, rows and chart
series the planes show, and they are ``@nu.host`` so a cell calls them on
what it read. Times are relative to the reader's clock (``ago``), amounts are
short (``1.2K``), addresses are cut (``3kth..9Ppx``). Nothing here touches
the store.

- :func:`status`: the sync's state as a pill, a line, a notice and a button.
- :func:`tiles`: the headline numbers.
- :func:`token_rows`, :func:`tape_rows`, :func:`launch_cards`, :func:`error_rows`: the tables and feeds.
- :func:`pulse`: recent trades as a scatter, buys and sells apart.
- :func:`token_view`: everything a token page shows.
- :func:`health`: the Monitor's charts from kh57 samples.
- :func:`avatar_url`: a token's picture, painted from its mint.
"""

from __future__ import annotations

import colorsys
import hashlib
import importlib.util
import math
import time
from typing import Any
from urllib.parse import quote

import nu

from .book import DEFAULT_RPC, ENV, KNOWN_QUOTES, masked


__all__ = [
    "SORTS",
    "TONES",
    "ago",
    "amount",
    "avatar",
    "avatar_url",
    "error_rows",
    "health",
    "launch_cards",
    "picture",
    "pulse",
    "short",
    "status",
    "status_of",
    "tape_rows",
    "tiles",
    "token_rows",
    "token_view",
    "token_view_of",
]


#: The pill tone for each status.
TONES = {
    "syncing": "ok",
    "behind": "warn",
    "starting": "info",
    "backing off": "warn",
    "stopping": "warn",
    "stopped": "neutral",
    "idle": "neutral",
    "down": "danger",
}

#: The token table's orders, by board list: key, and what the picker says.
SORTS = {
    "new": "Newest",
    "mc": "Market cap",
    "volume": "Volume",
    "progress": "Nearest graduation",
    "active": "Last trade",
}

#: Which board list a click on a column header sorts by.
COLUMN_SORTS = {
    "age": "new",
    "mc": "mc",
    "vol": "volume",
    "curve": "progress",
    "last": "active",
}


# --- small things ------------------------------------------------------------------------------


def amount(x: float | None, digits: int = 2) -> str:
    """``x`` short: ``0.042``, ``12.3``, ``4.5K``, ``1.2M``."""
    if x is None or not math.isfinite(x):
        return "-"
    a = abs(x)
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if a >= size:
            return f"{x / size:.1f}{unit}"
    if a >= 100:
        return f"{x:.0f}"
    if a >= 1:
        return f"{x:.{digits}f}"
    if a == 0:
        return "0"
    return f"{x:.3g}"


def price(x: float | None) -> str:
    """A token's price, tiny as it is: ``2.8e-8``."""
    if not x:
        return "-"
    return f"{x:.2e}".replace("e-0", "e-")


def ago(t: float | None, now: float | None = None) -> str:
    """How long ago ``t`` was: ``4s``, ``12m``, ``3h``, ``2d``."""
    if not t:
        return "-"
    s = max(0.0, (now or time.time()) - float(t))
    if s < 60:
        return f"{s:.0f}s"
    if s < 3600:
        return f"{s // 60:.0f}m"
    if s < 86400:
        return f"{s // 3600:.0f}h"
    return f"{s // 86400:.0f}d"


def clock(t: float | None) -> str:
    """``t`` as a wall clock time, ``14:03:22`` in the reader's local time."""
    return time.strftime("%H:%M:%S", time.localtime(t)) if t else "-"


def short(address: str | None, n: int = 4) -> str:
    """An address cut to its ends: ``3kth..9Ppx``."""
    if not address:
        return "-"
    return address if len(address) <= 2 * n + 2 else f"{address[:n]}..{address[-n:]}"


def label(rec: dict[str, Any]) -> str:
    """A token's ticker, or its mint's first characters while it has none yet."""
    return (rec.get("symbol") or "").strip() or (rec.get("mint") or "-")[:6] + "…"


def pct(x: float | None, sign: bool = False) -> str:
    """``x`` as a percent: ``42%``, or ``+12%`` with ``sign``."""
    if x is None or not math.isfinite(x):
        return "-"
    v = 100 * x
    body = f"{v:.0f}%" if abs(v) >= 10 or v == 0 else f"{v:.1f}%"
    return ("+" if sign and v > 0 else "") + body


def change(x: float) -> str:
    """A move since launch with an arrow: ``▲ 3.2x`` for big ones, ``▼ 12%`` for falls."""
    if not x or not math.isfinite(x) or abs(x) < 0.005:
        return "·"
    if x >= 1.0:
        return f"▲ {x + 1:.1f}x"
    return f"▲ {100 * x:.0f}%" if x > 0 else f"▼ {100 * -x:.0f}%"


# --- the sync ----------------------------------------------------------------------------------


def _idle(said: str, parts: list[str]) -> dict[str, Any]:
    return {
        "status": said,
        "tone": TONES.get(said, "neutral"),
        "line": "  ·  ".join(parts),
        "button": "Start",
        "variant": "primary",
        "icon": "play",
        "disabled": False,
        "pulse": False,
        "beat": "",
        "notice": "",
    }


def status_of(stats: dict | None, live: bool, stop: bool, now: float) -> dict[str, Any]:
    """The sync's state for the bar: ``{status, tone, line, notice, button, variant, icon, pulse}``.

    ``notice`` says why the view runs behind the chain while it does, empty otherwise.

    ``live`` says the job has a run, ``stop`` that a stop was asked for. A job
    that says it syncs but has no run is ``down``; one never started is ``idle``.
    """
    s = stats or {}
    said = s.get("status") or ""
    if not s:
        said = "starting" if live else "idle"
    elif stop and live:
        said = "stopping"
    elif live and said == "stopped":
        said = "starting"
    elif not live and said != "stopped":
        said = "stopped" if stop else ("down" if said else "idle")
    rates = s.get("rates") or {}
    totals = s.get("totals") or {}
    parts = []
    if s.get("tip"):
        parts.append(f"slot {s.get('cursor', 0):,}")
        parts.append(f"{s.get('lag', 0)} behind tip")
    if rates and said in ("syncing", "behind"):
        parts.append(f"{rates.get('blocks', 0):.1f} blocks/s")
    if s.get("rpc"):
        parts.append(s["rpc"] + (" (public)" if s.get("public") else ""))
    if not s:
        parts.append("Press Start: the sync follows the chain from its tip.")
    elif said == "backing off" and s.get("backoff"):
        parts.append(f"retrying in {s['backoff']:.0f}s")
    if said in ("stopped", "idle") and totals.get("blocks"):
        parts.append(f"{totals['blocks']:,.0f} blocks read")
    running = said in ("syncing", "behind", "starting", "backing off")
    if not running and importlib.util.find_spec("httpx") is None:
        # The calls go through nustd.http, which the memes extra brings.
        parts = [
            'Syncing needs nustd.http: pip install "nuverse-demos[memes]", then restart the space.'
        ]
        return {**_idle(said, parts), "disabled": True}
    return {
        "status": said,
        "tone": TONES.get(said, "neutral"),
        "line": "  ·  ".join(parts),
        "button": "Stop" if running else ("Stopping" if said == "stopping" else "Start"),
        "variant": "secondary" if running or said == "stopping" else "primary",
        "icon": "square" if running else "play",
        "disabled": said == "stopping",
        "pulse": said in ("syncing", "behind"),
        "beat": ago(s.get("beat"), now) if s else "",
        "notice": (s.get("notice") or "") if running else "",
    }


#: :func:`status_of` as a term, for the bar every plane shows.
status = nu.host(status_of, name="Status")


@nu.host
def tiles(stats: dict | None) -> dict[str, dict[str, str]]:
    """The headline tiles: ``{key: {value, delta, trend}}``."""
    s = stats or {}
    t, r = s.get("totals") or {}, s.get("rates") or {}
    buys, sells = t.get("buys", 0), t.get("sells", 0)
    ratio = buys / (buys + sells) if buys + sells else 0.0

    def tile(value: str, delta: str = "", trend: str = "flat") -> dict[str, str]:
        return {"value": value, "delta": delta, "trend": trend}

    return {
        "tokens": tile(f"{s.get('tokens', 0):,}", "tracked now"),
        "launches": tile(
            f"{t.get('launches', 0):,.0f}",
            f"{r.get('launches', 0):.1f} a minute",
            "up" if r.get("launches") else "flat",
        ),
        "trades": tile(
            f"{t.get('trades', 0):,.0f}",
            f"{r.get('trades', 0):.1f} a second",
            "up" if r.get("trades") else "flat",
        ),
        "volume": tile(
            amount(t.get("volume", 0.0)),
            f"{amount(r.get('volume', 0.0))} SOL a minute",
            "up" if r.get("volume") else "flat",
        ),
        "buys": tile(
            pct(ratio), f"{buys:,.0f} buys, {sells:,.0f} sells", "up" if ratio >= 0.5 else "down"
        ),
        "graduations": tile(
            f"{t.get('graduations', 0):,.0f}", f"{t.get('migrations', 0):,.0f} migrated"
        ),
        "blocks": tile(f"{t.get('blocks', 0):,.0f}", f"{r.get('blocks', 0):.1f} a second"),
        "lag": tile(
            f"{s.get('lag', 0):,}", "slots behind tip", "down" if s.get("lag", 0) > 20 else "flat"
        ),
    }


# --- the tables ------------------------------------------------------------------------------


@nu.host
def token_rows(board: dict | None, sort: str, now: float) -> list[dict[str, Any]]:
    """One board list as table rows, keyed by mint."""
    rows = []
    for r in (board or {}).get(sort) or []:
        q = "" if r["quote"] == "SOL" else f" {r['quote']}"
        state = (
            "migrated" if r["migrated"] else ("graduated" if r["complete"] else pct(r["progress"]))
        )
        rows.append(
            {
                "mint": r["mint"],
                "token": label(r),
                "name": (r["name"] or "")[:28],
                "age": ago(r["created"], now) if r["known"] else "-",
                "mc": amount(r["mc"]) + q,
                "move": change(r["change"]),
                "curve": state,
                "vol": amount(r["vol"]) + q,
                "trades": r["trades"],
                "bs": f"{r['buys']}/{r['sells']}",
                "last": (("▲ " if r["side"] == "buy" else "▼ ") if r["side"] else "")
                + ago(r["last"], now),
            }
        )
    return rows


@nu.host
def tape_rows(tape: list | None, now: float) -> list[dict[str, Any]]:
    """The newest trades, newest first, keyed ``<mint>:<n>`` so a click finds the token."""
    return [
        {
            "key": f"{t['mint']}:{t['n']}",
            "age": ago(t["t"], now),
            "side": "▲ BUY" if t["side"] == "buy" else "▼ SELL",
            "token": label(t),
            "amount": f"{amount(t['amount'], 3)} {t['quote']}",
            "mc": amount(t["mc"]),
            "trader": short(t["user"]),
        }
        for t in tape or []
    ]


@nu.host
def launch_cards(
    launches: list | None, now: float, n: int = 12, images: bool = False
) -> list[dict[str, Any]]:
    """The newest launches as cards: picture, ticker, name, how long ago, a link to its page.

    A coin's own image only with ``images`` on (the Sync plane's "Show images"): launches
    are anyone's, some images are explicit, so a painted avatar stands in by default.
    """
    return [
        {
            "i": str(i),
            "mint": x["mint"],
            "src": picture(x.get("image"), x["mint"], x["symbol"], images),
            "symbol": label(x),
            "name": (x["name"] or "")[:24] or "unnamed",
            "note": f"{ago(x['t'], now)} ago  ·  by {short(x['creator'])}",
        }
        for i, x in enumerate((launches or [])[:n])
    ]


@nu.host
def error_rows(errors: list | None, now: float) -> list[dict[str, Any]]:
    """The newest errors, newest first."""
    return [
        {
            "key": str(i),
            "when": f"{clock(e['t'])}  ({ago(e['t'], now)} ago)",
            "call": e["what"] or "-",
            "slot": f"{e['slot']:,}" if e.get("slot") else "",
            "message": e["message"],
        }
        for i, e in enumerate(errors or [])
    ]


@nu.host
def pulse(points: list | None) -> dict[str, list]:
    """Recent trades as dots: one after another across, SOL up (log), buys and sells as two series."""
    out: dict[str, list] = {"buys": [], "sells": []}
    for n, side, sol, symbol in points or []:
        if sol > 0:
            out["buys" if side == "buy" else "sells"].append(
                {"value": [n, round(sol, 4)], "name": f"{symbol}  {amount(sol, 3)} SOL"}
            )
    return out


# --- a token's page ----------------------------------------------------------------------------


def token_view_of(
    rec: dict | None,
    trades: list | None,
    candles: list | None,
    quotes: dict | None,
    now: float,
    images: bool = False,
) -> dict[str, Any]:
    """Everything a token page shows, from its record, its trades and its candles.

    Its own image only with ``images`` on, as in :func:`launch_cards`.
    """
    r = rec or {}
    if not r:
        return {"found": False}
    q = r.get("quote") or ""
    known = KNOWN_QUOTES.get(q) or (quotes or {}).get(q) or (short(q), 6)
    unit, decimals = str(known[0]), int(known[1])
    state = (
        "migrated to the AMM"
        if r.get("migrated")
        else ("graduated" if r.get("complete") else "on the curve")
    )
    tone = "ok" if r.get("complete") else "info"
    buys, sells = r.get("buys", 0), r.get("sells", 0)
    mint, creator = r["mint"], r.get("creator") or ""
    facts = [
        f"`{mint[:10]}…`",
        f"launched {ago(r.get('created'), now)} ago"
        if r.get("created")
        else f"first seen {ago(r.get('seen'), now)} ago",
        f"paired with {unit}",
    ]
    links = [
        f"[Solscan](https://solscan.io/token/{mint})",
    ]
    if creator:
        links.append(f"[creator {short(creator)}](https://solscan.io/account/{creator})")
    if r.get("pool"):
        links.append(f"[pool](https://solscan.io/account/{r['pool']})")
    if r.get("sig"):
        links.append(f"[launch tx](https://solscan.io/tx/{r['sig']})")
    rows = [
        {
            "key": f"{i}",
            "time": clock(t[0]),
            "side": "▲ BUY" if t[1] == "buy" else "▼ SELL",
            "amount": amount(t[2], 4),
            "tokens": amount(t[3]),
            "mc": amount(t[4]),
            "trader": short(t[5]),
        }
        for i, t in enumerate(trades or [])
    ]

    bars, volume, bucket = chart_of(trades or [], candles or [])
    return {
        "found": True,
        "title": r.get("name") or label(r),
        "symbol": label(r),
        "src": picture(r.get("image"), mint, r.get("symbol") or "", images),
        "state": state,
        "tone": tone,
        "facts": "  ·  ".join(facts),
        "links": "  ·  ".join(links),
        "mc": f"{amount(r.get('mc'))} {unit}",
        "move": change((r["mc"] / r["mc_open"] - 1.0) if r.get("mc_open") else 0.0),
        "trend": "up" if r.get("mc", 0) >= r.get("mc_open", 0) else "down",
        "price": f"{price(r.get('price'))} {unit}",
        "vol": f"{amount(r.get('vol'))} {unit}",
        "trades": f"{r.get('trades', 0):,}",
        "bs": f"{buys:,} / {sells:,}",
        "traders": f"{r.get('traders', 0):,}",
        "progress": round(100 * float(r.get("progress") or 0.0), 1),
        "progress_caption": "graduated"
        if r.get("complete")
        else f"{amount(r.get('rq', 0) / 10**decimals)} {unit} in the curve",
        "rows": rows,
        "candles": bars,
        "chart_title": f"Market cap, a candle {bucket}",
        "volume_title": f"Volume, a bar {bucket}",
        "volume": volume,
        "unit": unit,
        "split": {
            "buys": round(r.get("buy_vol", 0.0), 4),
            "sells": round(r.get("sell_vol", 0.0), 4),
        },
        "last": f"last trade {ago(r.get('last'), now)} ago" if r.get("last") else "no trades yet",
    }


#: :func:`token_view_of` as a term, for a token page's cells.
token_view = nu.host(token_view_of, name="TokenView")


#: Candle sizes a young token's chart picks from, in seconds, finest first.
BUCKETS = (5, 10, 15, 30, 60)


def _bucket_name(seconds: int) -> str:
    return "a minute" if seconds == 60 else f"every {seconds}s"


def chart_of(trades: list, candles: list) -> tuple[list, list, str]:
    """A token's market cap candles and volume bars, ``(candles, volume, bucket name)``.

    A token with a few minutes of history gets candles built from its trades,
    as fine as they need to be for a dozen of them, so a young token's chart
    is not one lone candle; an older one gets the sync's minute candles.
    """
    if len(candles) >= 12 or not trades:
        rows = [[c[0], c[1], c[2], c[3], c[4], c[5]] for c in candles]
        size = 60
    else:
        ts = sorted(trades, key=lambda t: t[0])
        span = max(1.0, ts[-1][0] - ts[0][0])
        size = next((b for b in BUCKETS if span / b <= 12), 60)
        rows = []
        for t, _side, amount, _tokens, mc, *_ in ts:
            start = int(t // size * size)
            if rows and rows[-1][0] == start:
                c = rows[-1]
                c[2], c[3], c[4], c[5] = mc, min(c[3], mc), max(c[4], mc), c[5] + amount
            else:
                opened = rows[-1][2] if rows else mc
                rows.append([start, opened, mc, min(opened, mc), max(opened, mc), amount])
    fmt = "%H:%M" if size == 60 else "%H:%M:%S"

    def at(t: float) -> str:
        return time.strftime(fmt, time.localtime(t))

    bars = [
        [at(c[0]), round(c[1], 4), round(c[2], 4), round(c[3], 4), round(c[4], 4)] for c in rows
    ]
    volume = [[at(c[0]), round(c[5], 4)] for c in rows]
    return bars, volume, _bucket_name(size)


# --- the monitor ---------------------------------------------------------------------------


def _series(points: list | None) -> list[list]:
    return [[int(k) * 1000, round(v, 3)] for k, v in sorted(points or [])]


@nu.host
def health(
    blocks: list,
    trades: list,
    launches: list,
    volume: list,
    lag: list,
    latency: list,
    errors: list,
) -> dict[str, Any]:
    """The Monitor's charts, each a series by time from a kh57 sample."""
    return {
        "throughput": {"blocks/s": _series(blocks), "trades/s": _series(trades)},
        "flow": {"launches/min": _series(launches), "SOL/min": _series(volume)},
        "lag": _series(lag),
        "latency": _series(latency),
        "errors": _series(errors),
    }


@nu.host
def endpoint_hint(setting: str) -> str:
    """What the Sync form says about the endpoint in use when its own field is empty."""
    import os

    if (setting or "").strip():
        return f"Using {masked(setting)}."
    env = os.environ.get(ENV, "").strip()
    if env:
        return f"Using ${ENV} ({masked(env)})."
    return f"Using the public {masked(DEFAULT_RPC)}: 6 blocks in 10 seconds at most, so the sync reads every block but falls behind the chain there."


# --- pictures ------------------------------------------------------------------------------------


def _hex(h: float, s: float, light: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, light, s)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def avatar(mint: str, symbol: str = "") -> str:
    """A token's picture as SVG text: a gradient, a few blobs and its ticker, all from its mint.

    The same mint paints the same picture everywhere, so a token is
    recognisable at a glance across the tape, the launches and its page.
    """
    h = hashlib.blake2b(mint.encode(), digest_size=16).digest()
    hue = h[0] * 360 / 256
    top, bottom = _hex(hue, 0.7, 0.55), _hex(hue + 40 + h[1] % 80, 0.65, 0.32)
    blobs = []
    for i in range(3):
        cx, cy, r = 10 + h[2 + i] % 80, 10 + h[5 + i] % 80, 14 + h[8 + i] % 22
        ink = _hex(hue + 120 + 60 * i + h[11 + i] % 40, 0.8, 0.62)
        blobs.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{ink}" opacity=".55"/>')
    raw = (symbol or mint[:4]).strip().upper()[:5]
    text = _esc(raw)
    size = 34 if len(raw) <= 3 else (26 if len(raw) == 4 else 20)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" font-family="Inter, Helvetica, Arial, sans-serif">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bottom}"/></linearGradient></defs>'
        '<rect width="100" height="100" rx="22" fill="url(#g)"/>'
        f"{''.join(blobs)}"
        f'<text x="50" y="50" dy=".35em" text-anchor="middle" font-size="{size}" font-weight="800" '
        f'fill="#fff" letter-spacing="-0.5">{text}</text>'
        "</svg>"
    )


def picture(image: str | None, mint: str, symbol: str, images: bool) -> str:
    """A coin's picture: its own image when ``images`` is on and it has one, else its avatar."""
    return image if images and image else avatar_url(mint, symbol)


def avatar_url(mint: str, symbol: str = "") -> str:
    """:func:`avatar` as a ``data:`` url, for an ``ImageRef``."""
    return "data:image/svg+xml;charset=utf-8," + quote(avatar(mint, symbol))
