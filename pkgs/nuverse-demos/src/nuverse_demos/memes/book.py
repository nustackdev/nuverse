"""The sync's working memory: what it asks the chain next, and what it has seen so far.

The sync job is a Nu loop over a :class:`Book` it provides (:mod:`.job`). On
each turn it asks the book for a plan (:meth:`Book.plan`), makes the call the
plan names over JSON-RPC, hands the reply back (:meth:`Book.on_reply` or
:meth:`Book.on_error`), and commits what the book says changed
(:meth:`Book.flush`) into the space's state. Everything the job decides is
here, in plain Python, so a fake RPC drives it in a test.

What it keeps, bounded so it can run for days:

- a record per token (:func:`token_record`), evicted once quiet for
  ``keep_hours`` or past ``max_tokens``;
- per token its newest trades and one-minute candles of market cap;
- the newest trades across all tokens (the tape), launches and errors;
- running totals, and every few seconds a point per metric for the kh57
  series the Monitor charts.

How it follows the chain: every block in order, from the tip or a given
slot, two slots behind the confirmed tip, at most ``rate`` blocks a second, a
few calls at once. Solana makes a slot about every 220ms, so keeping up takes
4 to 5 blocks a second. A slower sync never skips: it falls behind and says
so (:meth:`Book.stats`), and the numbers stay whole. Skipped slots are passed
over, a block not out yet is asked again shortly, anything else backs off, 1s
doubling to 30s.
"""

from __future__ import annotations

import heapq
import os
import re
import time
from collections import deque
from typing import TYPE_CHECKING, Any

from . import curve
from .chain import SOL, decode_block


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "DEFAULT_RPC",
    "ENV",
    "KNOWN_QUOTES",
    "Book",
    "clean",
    "endpoint",
    "token_record",
]


#: The env var naming an RPC endpoint, read when the Sync plane names none.
ENV = "NUVERSE_MEMES_RPC"

#: The public endpoint, the last fallback. Rate limited: the sync slows to :data:`PUBLIC_RATE` on it.
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"

#: Quote mints known by sight: symbol and decimals. Anything else is looked up once.
KNOWN_QUOTES: dict[str, tuple[str, int]] = {
    SOL: ("SOL", 9),
    "So11111111111111111111111111111111111111112": ("SOL", 9),
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC", 6),
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": ("WIF", 6),
    "DoGEV7LASBkQbibMc5k5vKnTZoMg423GpJ5QtJEGfm7R": ("DOGE", 8),
}

#: JSON-RPC errors that say the slot holds no block, for good.
SKIPPED = {-32007, -32009}

#: JSON-RPC errors that say the block is not out yet: ask again shortly.
NOT_YET = {-32004, -32014}

#: Slots kept between the tip and the block asked for, so it is out.
BEHIND = 2

#: Blocks asked for at once, at most: the rate's burst.
AHEAD = 4

#: The pace on the public endpoint, whatever the rate says: it allows 6 ``getBlock`` calls
#: in 10 seconds, and a block is 3 to 6MB, so one block every two seconds, one at a time.
PUBLIC_RATE = 0.5

#: The pace a sync starts at when the Sync plane sets none: the chain's own, with room to catch up.
RATE = 5.0

#: Slots behind the tip a sync may be and still be live; past it, it is behind.
LIVE = 20

#: Seconds a rate limit answer (a 429) is remembered for: the sync behind is the endpoint's doing.
LIMITED_FOR = 60.0

_LIMITED = re.compile(r"\b429\b|too many requests|rate.?limit", re.IGNORECASE)

#: Seconds between metric points.
EVERY = 5.0

#: Seconds between retention passes.
PRUNE_EVERY = 60.0

#: Rows in each board list, trades kept per token, one-minute candles per token.
BOARD, TRADES, CANDLES = 40, 120, 360

#: Trades on the tape, points on the pulse, launches and errors kept.
TAPE, PULSE, LAUNCHES, ERRORS = 30, 300, 40, 40

#: Mints asked about in one metadata call.
META_BATCH = 50

#: Off-chain metadata fetched at once at most, the least seconds between two, and tries per coin.
PICTURES, PICTURE_EVERY, PICTURE_TRIES = 3, 0.3, 2

#: Where content-addressed metadata and images are read from. ipfs.io answers 429 to most
#: callers; this gateway answered 11 of 12 in a test, in about 5s.
GATEWAY = "https://gateway.pinata.cloud/ipfs/"

_CID = re.compile(r"^(Qm[1-9A-HJ-NP-Za-km-z]{44}|baf[a-z2-7]{20,})(/.*)?$")


def endpoint(setting: str | None) -> str:
    """The RPC endpoint to call: the Sync plane's, else ``$NUVERSE_MEMES_RPC``, else the public one."""
    return (setting or "").strip() or os.environ.get(ENV, "").strip() or DEFAULT_RPC


_QUERY = re.compile(r"(https?://[^\s'\"?]+)\?[^\s'\"]*")
_KEYS = re.compile(r"(api[-_]?key=)[^&\s'\"]+", re.IGNORECASE)


def clean(text: str, limit: int = 240) -> str:
    """An error message fit to keep and show: query strings and keys out, one line, capped."""
    text = _KEYS.sub(r"\1...", _QUERY.sub(r"\1?...", str(text)))
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def gateway_url(url: str | None) -> str:
    """A metadata or image url the sync and the browser can read: ipfs moved to :data:`GATEWAY`.

    ``ipfs://<cid>``, ``https://<any host>/ipfs/<cid>`` and a bare cid all
    become the gateway's url for the cid. Other https urls pass as they are;
    anything else is ``""``.
    """
    url = (url or "").strip()
    if url.startswith("ipfs://"):
        url = url[len("ipfs://") :].removeprefix("ipfs/")
    elif "/ipfs/" in url and url.startswith("https://"):
        url = url.split("/ipfs/", 1)[1]
    elif url.startswith("https://"):
        return url
    return GATEWAY + url if _CID.match(url) else ""


def masked(url: str) -> str:
    """An endpoint as shown: its host, never its path or query."""
    m = re.match(r"^(https?://)?([^/?#]+)", url.strip())
    return m.group(2) if m else url


def token_record(mint: str, *, quote: str = SOL, now: float = 0.0) -> dict[str, Any]:
    """A token as first seen: everything the tables and its page read, zeroed."""
    return {
        "mint": mint,
        "name": "",
        "symbol": "",
        "uri": "",
        "image": "",
        "picture": "",
        "creator": "",
        "created": 0,
        "seen": now,
        "slot": 0,
        "sig": "",
        "quote": quote,
        "supply": curve.SUPPLY,
        "mayhem": False,
        "cashback": False,
        "vq": 0,
        "vt": 0,
        "rq": 0,
        "rt": curve.GENESIS_RTOK,
        "price": 0.0,
        "mc": 0.0,
        "mc_open": 0.0,
        "progress": 0.0,
        "trades": 0,
        "buys": 0,
        "sells": 0,
        "vol": 0.0,
        "buy_vol": 0.0,
        "sell_vol": 0.0,
        "traders": 0,
        "last": 0.0,
        "last_side": "",
        "complete": False,
        "migrated": False,
        "pool": "",
        "graduated": 0.0,
    }


class Book:
    """The sync's memory and its policy. One per job run, provided with ``nu.Provide``.

    Args:
        keep_hours: How long a token stays after its last trade.
        max_tokens: The most tokens kept; the quietest go first.
        clock: Seconds now, ``time.time`` unless a test drives it.
    """

    def __init__(
        self,
        keep_hours: float = 6.0,
        max_tokens: int = 4000,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.keep = keep_hours * 3600.0
        self.max_tokens = max_tokens
        self.clock = clock or time.time
        self.tokens: dict[str, dict[str, Any]] = {}
        self.trades: dict[str, list[list]] = {}
        self.candles: dict[str, list[list]] = {}
        self.traders: dict[str, set[str]] = {}
        self.tape: deque[dict[str, Any]] = deque(maxlen=TAPE)
        self.pulse: deque[list] = deque(maxlen=PULSE)
        self.launches: deque[dict[str, Any]] = deque(maxlen=LAUNCHES)
        self.errors: deque[dict[str, Any]] = deque(maxlen=ERRORS)
        self.quotes: dict[str, list] = {}
        self.totals: dict[str, float] = dict.fromkeys(
            (
                "blocks",
                "skipped",
                "txs",
                "failed",
                "trades",
                "buys",
                "sells",
                "volume",
                "launches",
                "graduations",
                "migrations",
                "errors",
                "calls",
            ),
            0,
        )
        # Where it is on the chain.
        self.cursor = 0
        self.tip = 0
        self.tip_at = 0.0
        self.epoch = -1
        self.mode = "tip"
        self.started = 0.0
        self.status = "starting"
        # Pacing and backoff.
        self.allow = 1.0
        self.allow_at = 0.0
        self.done: set[int] = set()
        self.meta_at = 0.0
        self.backoff = 0.0
        self.until = 0.0
        self.limited_at = 0.0
        self.not_yet = 0
        self.url = DEFAULT_RPC
        # Metadata to look up, and what was already asked.
        self.unnamed: deque[str] = deque()
        self.asked: set[str] = set()
        # Coins whose off-chain picture is still to fetch, newest first, and those being fetched.
        self.wanted: deque[str] = deque()
        self.fetching: set[str] = set()
        self.picture_at = 0.0
        self.tries: dict[str, int] = {}
        # The window the next metric point covers.
        self.window: dict[str, float] = {}
        self.window_at = 0.0
        self.latency: list[float] = []
        self.rates: dict[str, float] = {}
        self.pruned_at = 0.0
        # What changed since the last flush.
        self.dirty: set[str] = set()
        self.dirty_trades: set[str] = set()
        self.dirty_candles: set[str] = set()
        self.gone: list[str] = []
        self.moved = False
        self.point: dict[str, Any] | None = None

    # --- lifecycle ----------------------------------------------------------------------------

    def load(self, saved: dict | None) -> None:
        """Pick up where the last run left off: what :meth:`flush` wrote, read back from the store."""
        saved = saved or {}
        for mint, rec in (saved.get("tokens") or {}).items():
            self.tokens[mint] = {**token_record(mint), **dict(rec)}
        self.trades = {m: [list(t) for t in v] for m, v in (saved.get("trades") or {}).items()}
        self.candles = {m: [list(c) for c in v] for m, v in (saved.get("candles") or {}).items()}
        for mint, rows in self.trades.items():
            self.traders[mint] = {r[5] for r in rows if len(r) > 5}
        self.tape.extend(saved.get("tape") or [])
        self.pulse.extend(saved.get("pulse") or [])
        self.launches.extend(saved.get("launches") or [])
        self.errors.extend(saved.get("errors") or [])
        self.quotes.update(saved.get("quotes") or {})
        stats = saved.get("stats") or {}
        for k in self.totals:
            self.totals[k] = (stats.get("totals") or {}).get(k, 0)
        sync = saved.get("sync") or {}
        self.cursor = int(sync.get("cursor") or 0)
        self.epoch = int(sync.get("epoch", -1))
        self.mode = sync.get("mode") or "tip"
        self.unnamed.extend(m for m, r in self.tokens.items() if not r["name"])
        for m, r in sorted(
            self.tokens.items(), key=lambda kv: -(kv[1]["created"] or kv[1]["seen"])
        ):
            if r.get("picture") in ("", "asked") and r.get("uri"):
                r["picture"] = ""
                self.wanted.append(m)
        self.started = self.clock()
        self.window_at = self.started
        self.pruned_at = self.started
        self.status = "starting"
        self.moved = True

    # --- planning ------------------------------------------------------------------------------

    def plan(self, control: dict | None) -> dict[str, Any]:
        """What to do next: ``{do: "wait", wait}``, or ``{do: "call", calls}`` to make at once.

        Each call is ``{what, url, method, params, sent}``: ``getSlot`` when
        the tip is stale, up to :data:`AHEAD` ``getBlock`` as the rate
        allows, and ``getMultipleAccounts`` for names still missing.
        ``control`` is what the Sync plane holds: ``rpc``, ``rate``,
        ``epoch`` and ``start`` (a slot, 0 for the tip).
        """
        control = control or {}
        now = self.clock()
        self.url = endpoint(control.get("rpc"))
        rate = max(0.1, float(control.get("rate") or RATE))
        public = self.url == DEFAULT_RPC
        burst = 1 if public else AHEAD
        if public:
            rate = min(rate, PUBLIC_RATE)
        epoch = int(control.get("epoch") or 0)
        if epoch != self.epoch:
            # Asked to start over: from a slot, or from the tip.
            self.epoch = epoch
            start = int(control.get("start") or 0)
            self.cursor, self.mode = (start, "from") if start > 0 else (0, "tip")
            self.done.clear()
            self.moved = True
        if now < self.until:
            return {"do": "wait", "wait": min(1.0, self.until - now)}
        # The rate as a bucket: it fills at ``rate`` a second, up to a burst of AHEAD.
        self.allow = min(float(burst), self.allow + (now - self.allow_at) * rate)
        self.allow_at = now
        calls = []
        stale = now - self.tip_at > 2.0 or (
            self.cursor >= self.tip - BEHIND and now - self.tip_at > 0.4
        )
        if not self.tip or stale:
            calls.append(self._call("slot", "getSlot", [{"commitment": "confirmed"}]))
        if self.tip:
            if self.cursor == 0:
                self.cursor = self.tip - BEHIND
                self.moved = True
            # Every block in order: a sync slower than the chain falls behind, it never skips.
            slot = self.cursor
            while self.allow >= 1.0 and slot <= self.tip - BEHIND and len(calls) < burst + 1:
                if slot not in self.done:
                    calls.append(self._block(slot))
                    self.allow -= 1.0
                slot += 1
        if self.unnamed and now - self.meta_at > 3.0:
            calls += self._meta()
        if calls:
            return {"do": "call", "calls": calls}
        wait = (1.0 - self.allow) / rate if self.allow < 1.0 else 0.25
        return {"do": "wait", "wait": min(1.0, max(0.05, wait))}

    def _call(self, what: str, method: str, params: list) -> dict[str, Any]:
        self.totals["calls"] += 1
        return {
            "what": what,
            "url": self.url,
            "method": method,
            "params": params,
            "sent": self.clock(),
            "slot": 0,
        }

    def _block(self, slot: int) -> dict[str, Any]:
        options = {
            "commitment": "confirmed",
            "encoding": "json",
            "transactionDetails": "full",
            "rewards": False,
            "maxSupportedTransactionVersion": 1,
        }
        return {**self._call("block", "getBlock", [slot, options]), "slot": slot}

    def _meta(self) -> list[dict[str, Any]]:
        self.meta_at = self.clock()
        mints = []
        while self.unnamed and len(mints) < META_BATCH:
            m = self.unnamed.popleft()
            if m not in self.asked and (m in self.tokens or m in self.quotes):
                self.asked.add(m)
                mints.append(m)
        if not mints:
            return []
        return [
            {
                **self._call("meta", "getMultipleAccounts", [mints, {"encoding": "jsonParsed"}]),
                "mints": mints,
            }
        ]

    # --- replies -------------------------------------------------------------------------------

    def on_reply(self, plan: dict, reply: object) -> None:
        """What a call came back with: a JSON-RPC response, ``result`` or ``error``."""
        now = self.clock()
        self.latency.append(max(0.0, now - float(plan.get("sent") or now)) * 1000.0)
        if not isinstance(reply, dict):
            self.on_error(plan, f"unexpected reply: {type(reply).__name__}")
            return
        error = reply.get("error")
        what = plan.get("what")
        if what == "block":
            self._on_block(plan, reply.get("result"), error)
        elif error is not None:
            self.on_error(plan, f"{error.get('code')} {error.get('message')}")
        elif what == "slot":
            self.tip, self.tip_at = int(reply["result"]), now
            self.moved = True
            self._ok()
        elif what == "meta":
            self._on_meta(plan.get("mints") or [], reply.get("result") or {})
            self._ok()

    def on_error(self, plan: dict, message: object) -> None:
        """A call that failed, or a reply that made no sense: logged, and the sync backs off.

        ``message`` is a string, or the caught error itself: a string carrying
        its exception, whose type says more than an empty message does.
        """
        exc = getattr(message, "exception", None)
        if isinstance(exc, BaseException):
            message = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        now = self.clock()
        if _LIMITED.search(str(message)):
            self.limited_at = now
        self.backoff = min(30.0, self.backoff * 2 if self.backoff else 1.0)
        self.until = now + self.backoff
        self.totals["errors"] += 1
        self._bump("errors")
        self.errors.appendleft(
            {
                "t": now,
                "what": plan.get("what") or "",
                "slot": plan.get("slot") or 0,
                "message": clean(message),
            }
        )
        if plan.get("what") == "meta":
            # Asked again later, unless it keeps failing: the names are a nicety.
            self.unnamed.extend(m for m in plan.get("mints") or [] if m in self.tokens)
            self.asked.difference_update(plan.get("mints") or [])
        self.moved = True

    def on_stop(self) -> None:
        """The sync was asked to stop: the status says so on the next flush."""
        self.status = "stopped"
        self.rates = {}  # a stopped sync reads nothing a second
        self.moved = True

    def _ok(self) -> None:
        # A success eases the next backoff; a wait already set by a failure still runs out.
        self.backoff = 0.0

    def _on_block(self, plan: dict, block: object, error: dict | None) -> None:
        slot = int(plan.get("slot") or self.cursor)
        code = (error or {}).get("code")
        if error is not None and code in NOT_YET:
            # Not out yet: ask again shortly, unless it never comes.
            self.not_yet += 1
            if self.not_yet < 20:
                self.until = self.clock() + 0.4
                return
        elif error is not None and code not in SKIPPED:
            self.on_error(plan, f"{code} {error.get('message')}")
            return
        if slot < self.cursor or slot in self.done:
            return  # asked twice: once is enough
        self.not_yet = 0
        self._ok()
        self.done.add(slot)
        while self.cursor in self.done:
            self.done.discard(self.cursor)
            self.cursor += 1
        self.moved = True
        if error is not None or not isinstance(block, dict):
            self.totals["skipped"] += 1
            return
        decoded = decode_block(block, slot)
        self.totals["blocks"] += 1
        self.totals["txs"] += decoded["txs"]
        self.totals["failed"] += decoded["failed"]
        self._bump("blocks")
        for e in decoded["events"]:
            {
                "create": self._create,
                "trade": self._trade,
                "complete": self._complete,
                "migrate": self._migrate,
            }[e["kind"]](e, decoded["time"] or int(self.clock()))

    def _on_meta(self, mints: list[str], result: dict) -> None:
        values = result.get("value") if isinstance(result, dict) else None
        for mint, acc in zip(mints, values or [], strict=False):
            info = (((acc or {}).get("data") or {}).get("parsed") or {}).get("info") or {}
            found = next(
                (
                    x.get("state") or {}
                    for x in info.get("extensions") or []
                    if x.get("extension") == "tokenMetadata"
                ),
                {},
            )
            if mint in self.quotes:
                symbol = (found.get("symbol") or "").strip() or self.quotes[mint][0]
                self.quotes[mint] = [symbol[:10], int(info.get("decimals", self.quotes[mint][1]))]
                for rec in self.tokens.values():
                    if rec["quote"] == mint:
                        self._price(rec)
                        self.dirty.add(rec["mint"])
            rec = self.tokens.get(mint)
            if rec is None:
                continue
            if found:
                rec["name"] = (found.get("name") or "").strip()[:64]
                rec["symbol"] = (found.get("symbol") or "").strip()[:16]
                rec["uri"] = (found.get("uri") or "").strip()[:300]
                self._want(rec)
            if str(info.get("supply") or "").isdigit():
                rec["supply"] = int(info["supply"])
                self._price(rec)
            self.dirty.add(mint)

    # --- events --------------------------------------------------------------------------------

    def _quote(self, mint: str) -> tuple[str, int]:
        """A quote's symbol and decimals: known, looked up, or a guess until the lookup lands."""
        if mint in KNOWN_QUOTES:
            return KNOWN_QUOTES[mint]
        if mint not in self.quotes:
            self.quotes[mint] = [mint[:4], 6]
            self.unnamed.append(mint)
        symbol, decimals = self.quotes[mint]
        return symbol, int(decimals)

    def _token(self, mint: str, quote: str, ts: float) -> dict[str, Any]:
        rec = self.tokens.get(mint)
        if rec is None:
            rec = self.tokens[mint] = token_record(mint, quote=quote, now=ts)
            self.unnamed.append(mint)
        return rec

    def _price(self, rec: dict[str, Any]) -> None:
        _, decimals = self._quote(rec["quote"])
        rec["price"] = curve.price(rec["vq"], rec["vt"], decimals)
        rec["mc"] = curve.market_cap(rec["vq"], rec["vt"], rec["supply"], decimals)
        rec["progress"] = 1.0 if rec["complete"] else curve.progress(rec["rt"])

    def _create(self, e: dict, ts: float) -> None:
        rec = self._token(e["mint"], e["quote"], ts)
        if e["mint"] in self.unnamed:
            self.unnamed.remove(e["mint"])
        rec.update(
            name=e["name"][:64],
            symbol=e["symbol"][:16],
            uri=e["uri"][:300],
            creator=e["creator"],
            created=e["ts"],
            slot=e["slot"],
            sig=e["sig"],
            quote=e["quote"],
            supply=e["supply"] or curve.SUPPLY,
            mayhem=e["mayhem"],
            cashback=e["cashback"],
            vq=e["vquote"],
            vt=e["vtok"],
            rt=e["rtok"],
        )
        self._price(rec)
        rec["mc_open"] = rec["mc"]
        self._want(rec, first=True)
        self.totals["launches"] += 1
        self._bump("launches")
        self.launches.appendleft(
            {
                "mint": rec["mint"],
                "name": rec["name"],
                "symbol": rec["symbol"],
                "creator": rec["creator"],
                "t": e["ts"],
                "quote": self._quote(rec["quote"])[0],
                "mayhem": rec["mayhem"],
                "image": rec["image"],
            }
        )
        self.dirty.add(rec["mint"])

    def _trade(self, e: dict, ts: float) -> None:
        mint = e["mint"]
        rec = self._token(mint, e["quote"], e["ts"] or ts)
        symbol, decimals = self._quote(e["quote"])
        amount = e["qamount"] / 10**decimals
        side = "buy" if e["buy"] else "sell"
        rec.update(vq=e["vquote"], vt=e["vtok"], rq=e["rquote"], rt=e["rtok"], quote=e["quote"])
        if not rec["creator"]:
            rec["creator"] = e["creator"]
        rec["mayhem"] = rec["mayhem"] or e["mayhem"]
        self._price(rec)
        if not rec["mc_open"]:
            rec["mc_open"] = rec["mc"]
        rec["trades"] += 1
        rec["buys" if e["buy"] else "sells"] += 1
        rec["vol"] += amount
        rec["buy_vol" if e["buy"] else "sell_vol"] += amount
        rec["last"], rec["last_side"] = e["ts"] or ts, side
        seen = self.traders.setdefault(mint, set())
        if len(seen) < 5000:
            seen.add(e["user"])
        rec["traders"] = max(rec["traders"], len(seen))
        is_sol = e["quote"] in (SOL, "So11111111111111111111111111111111111111112")
        sol = amount if is_sol else 0.0
        self.totals["trades"] += 1
        self.totals["buys" if e["buy"] else "sells"] += 1
        self.totals["volume"] += sol
        self._bump("trades")
        self._bump("volume", sol)
        t = e["ts"] or ts
        row = [
            t,
            side,
            round(amount, 9),
            e["tokens"] / 10**curve.TOKEN_DECIMALS,
            rec["mc"],
            e["user"],
            e["sig"],
            e["slot"],
        ]
        trades = self.trades.setdefault(mint, [])
        trades.insert(0, row)
        del trades[TRADES:]
        self.dirty_trades.add(mint)
        self._candle(mint, t, rec["mc"], amount)
        if is_sol:
            self.tape.appendleft(self._tape_row(mint, rec, t, side, amount, symbol, e["user"]))
        self.pulse.append(
            [self.totals["trades"], side, round(sol or 0.0, 6), rec["symbol"] or mint[:4]]
        )
        self.dirty.add(mint)

    def _tape_row(
        self, mint: str, rec: dict, t: float, side: str, amount: float, symbol: str, user: str
    ) -> dict[str, Any]:
        return {
            "mint": mint,
            "symbol": rec["symbol"],
            "name": rec["name"],
            "t": t,
            "side": side,
            "amount": amount,
            "quote": symbol,
            "mc": rec["mc"],
            "user": user,
            "n": self.totals["trades"],
        }

    def _candle(self, mint: str, t: float, mc: float, amount: float) -> None:
        minute = int(t // 60 * 60)
        rows = self.candles.setdefault(mint, [])
        if rows and rows[-1][0] == minute:
            c = rows[-1]
            c[2], c[3], c[4] = mc, min(c[3], mc), max(c[4], mc)
            c[5] += amount
            c[6] += 1
        else:
            opened = rows[-1][2] if rows else mc
            rows.append([minute, opened, mc, min(opened, mc), max(opened, mc), amount, 1])
            del rows[:-CANDLES]
        self.dirty_candles.add(mint)

    def _complete(self, e: dict, ts: float) -> None:
        rec = self._token(e["mint"], SOL, e["ts"] or ts)
        if not rec["complete"]:
            rec["complete"], rec["graduated"] = True, e["ts"] or ts
            rec["progress"] = 1.0
            self.totals["graduations"] += 1
            self._bump("graduations")
        self.dirty.add(e["mint"])

    def _migrate(self, e: dict, ts: float) -> None:
        rec = self._token(e["mint"], SOL, e["ts"] or ts)
        if not rec["migrated"]:
            rec["migrated"], rec["pool"] = True, e["pool"]
            rec["complete"], rec["progress"] = True, 1.0
            rec["graduated"] = rec["graduated"] or e["ts"] or ts
            self.totals["migrations"] += 1
        self.dirty.add(e["mint"])

    # --- pictures ---------------------------------------------------------------------------

    def _want(self, rec: dict[str, Any], first: bool = False) -> None:
        """Queue a coin's off-chain picture, once, when it names metadata to read it from."""
        m = rec["mint"]
        if rec["picture"] or not gateway_url(rec["uri"]) or m in self.fetching or m in self.wanted:
            return
        self.wanted.appendleft(m) if first else self.wanted.append(m)

    def picture(self) -> dict[str, Any]:
        """The next coin's metadata to fetch, ``{mint, url}``, or ``{}`` while none is due.

        At most :data:`PICTURES` at once and one every :data:`PICTURE_EVERY`
        seconds, the newest launches first.
        """
        now = self.clock()
        if len(self.fetching) >= PICTURES or now - self.picture_at < PICTURE_EVERY:
            return {}
        while self.wanted:
            m = self.wanted.popleft()
            rec = self.tokens.get(m)
            if rec is None or rec["picture"] not in ("",):
                continue
            self.picture_at = now
            self.fetching.add(m)
            rec["picture"] = "asked"
            return {"mint": m, "url": gateway_url(rec["uri"])}
        return {}

    def on_picture(self, ask: dict, meta: object) -> None:
        """A coin's metadata came back: its ``image``, read through the gateway, or none."""
        m = ask.get("mint", "")
        self.fetching.discard(m)
        rec = self.tokens.get(m)
        if rec is None:
            return
        src = gateway_url(meta.get("image") if isinstance(meta, dict) else None)
        rec["image"], rec["picture"] = src, ("ok" if src else "none")
        self.dirty.add(m)
        for x in self.launches:
            if x["mint"] == m:
                x["image"] = src

    def on_no_picture(self, ask: dict, message: object = "") -> None:
        """A metadata fetch that failed: tried again later, then given up on and remembered."""
        m = ask.get("mint", "")
        self.fetching.discard(m)
        rec = self.tokens.get(m)
        if rec is None:
            return
        self.tries[m] = self.tries.get(m, 0) + 1
        if self.tries[m] < PICTURE_TRIES:
            rec["picture"] = ""
            self.wanted.append(m)
        else:
            rec["picture"] = "failed"
            self.tries.pop(m, None)
            self.dirty.add(m)

    # --- metrics and retention ------------------------------------------------------------------

    def _bump(self, key: str, by: float = 1.0) -> None:
        self.window[key] = self.window.get(key, 0.0) + by

    def _metrics(self, now: float) -> None:
        span = now - self.window_at
        if span < EVERY:
            return
        w, lat = self.window, self.latency
        self.rates = {
            "blocks": w.get("blocks", 0.0) / span,
            "trades": w.get("trades", 0.0) / span,
            # Launches are rare: a minute's rate over the last five, from the launches kept.
            "launches": sum(1 for x in self.launches if now - (x["t"] or 0) <= 300) / 5.0,
            "volume": w.get("volume", 0.0) * 60.0 / span,
            "errors": w.get("errors", 0.0),
            "latency": sum(lat) / len(lat) if lat else 0.0,
            "lag": float(max(0, self.tip - self.cursor)) if self.tip and self.cursor else 0.0,
        }
        self.point = {"t": int(now), **{k: round(v, 3) for k, v in self.rates.items()}}
        self.window, self.latency, self.window_at = {}, [], now
        self.moved = True

    def _prune(self, now: float) -> None:
        if now - self.pruned_at < PRUNE_EVERY:
            return
        self.pruned_at = now
        quiet = [
            m
            for m, r in self.tokens.items()
            if now - max(r["last"], r["created"], r["seen"]) > self.keep
        ]
        over = len(self.tokens) - len(quiet) - self.max_tokens
        if over > 0:
            alive = (m for m in self.tokens if m not in set(quiet))
            quiet += heapq.nsmallest(
                over, alive, key=lambda m: self.tokens[m]["last"] or self.tokens[m]["seen"]
            )
        for m in quiet:
            self.tokens.pop(m, None)
            self.trades.pop(m, None)
            self.candles.pop(m, None)
            self.traders.pop(m, None)
            self.tries.pop(m, None)
            self.dirty.discard(m)
            self.dirty_trades.discard(m)
            self.dirty_candles.discard(m)
        self.gone.extend(quiet)

    # --- what changed ------------------------------------------------------------------------

    def board(self) -> dict[str, list[dict[str, Any]]]:
        """The overview's token lists, top :data:`BOARD` each: newest, biggest, busiest, nearest graduation, latest."""
        # SOL-paired coins only: another quote's market cap and volume are not in SOL.
        sol = [r for r in self.tokens.values() if r["quote"] == SOL]
        ranks = {
            "new": (lambda r: r["created"], [r for r in sol if r["created"]]),
            "mc": (lambda r: r["mc"], sol),
            "volume": (lambda r: r["vol"], sol),
            "progress": (lambda r: r["progress"], [r for r in sol if not r["complete"]]),
            "active": (lambda r: r["last"], sol),
        }
        rows = {k: heapq.nlargest(BOARD, pool, key=f) for k, (f, pool) in ranks.items()}
        return {k: [self.row(r) for r in v] for k, v in rows.items()}

    def row(self, r: dict[str, Any]) -> dict[str, Any]:
        """A token as a board row: what a table line shows, no more."""
        symbol, _ = self._quote(r["quote"])
        return {
            "mint": r["mint"],
            "name": r["name"],
            "symbol": r["symbol"],
            "created": r["created"] or r["seen"],
            "known": bool(r["created"]),
            "quote": symbol,
            "mc": r["mc"],
            "change": (r["mc"] / r["mc_open"] - 1.0) if r["mc_open"] else 0.0,
            "progress": r["progress"],
            "vol": r["vol"],
            "trades": r["trades"],
            "buys": r["buys"],
            "sells": r["sells"],
            "last": r["last"],
            "side": r["last_side"],
            "complete": r["complete"],
            "migrated": r["migrated"],
            "mayhem": r["mayhem"],
        }

    def _tape(self) -> list[dict[str, Any]]:
        """The tape, each trade under its token's name as known now: names land after trades."""
        out = []
        for t in self.tape:
            rec = self.tokens.get(t["mint"])
            out.append({**t, "symbol": rec["symbol"], "name": rec["name"]} if rec else t)
        return out

    def stats(self) -> dict[str, Any]:
        """The sync's status and totals, as the Sync, Monitor and Overview planes show them."""
        now = self.clock()
        lag = max(0, self.tip - self.cursor) if self.tip and self.cursor else 0
        public = self.url == DEFAULT_RPC
        status = self.status
        if status not in ("stopped",):
            if self.until > now and self.backoff:
                status = "backing off"
            elif not self.tip:
                status = "starting"
            else:
                status = "syncing" if lag <= LIVE else "behind"
        self.status = status
        return {
            "status": status,
            "cursor": self.cursor,
            "tip": self.tip,
            "lag": lag,
            "mode": self.mode,
            "rpc": masked(self.url),
            "public": public,
            "limited": public or now - self.limited_at < LIMITED_FOR,
            "notice": self.notice(lag, public, now),
            "backoff": self.backoff,
            "started": self.started,
            "beat": self.clock(),
            "tokens": len(self.tokens),
            "totals": dict(self.totals),
            "rates": dict(self.rates),
        }

    def notice(self, lag: int, public: bool, now: float) -> str:
        """Why the view runs behind the chain, when it does: empty while it keeps up."""
        if self.status == "stopped" or lag <= LIVE:
            return ""
        if public:
            return (
                "The public RPC is rate limited, so this view runs behind the chain. "
                "Set your own RPC on Sync to keep up."
            )
        if now - self.limited_at < LIMITED_FOR:
            return (
                "Your RPC is rate limiting the sync, so this view runs behind the chain. "
                "Lower the pace on Sync, or use an endpoint with a higher limit."
            )
        return (
            "The sync reads every block in order and is behind the chain. "
            "Raise the pace on Sync to catch up."
        )

    def flush(self) -> dict[str, Any]:
        """Everything that changed since the last flush, as the job writes it: a dict of lists.

        Every key is always there, so the job writes with one loop per key:
        ``tokens``, ``trades`` and ``candles`` are ``[[mint, value], ...]``,
        ``gone`` the mints evicted, ``board``, ``tape``, ``pulse``,
        ``launches``, ``errors``, ``quotes``, ``stats``, ``sync`` and
        ``point`` each a list of zero or one value. ``moved`` says whether
        there is anything to write at all.
        """
        now = self.clock()
        self._metrics(now)
        self._prune(now)
        changed = bool(self.dirty or self.gone)
        out = {
            "tokens": [[m, self.tokens[m]] for m in sorted(self.dirty) if m in self.tokens],
            "trades": [[m, self.trades[m]] for m in sorted(self.dirty_trades) if m in self.trades],
            "candles": [
                [m, self.candles[m]] for m in sorted(self.dirty_candles) if m in self.candles
            ],
            "gone": list(self.gone),
            "board": [self.board()] if changed else [],
            "tape": [self._tape()] if self.dirty_trades else [],
            "pulse": [list(self.pulse)] if self.dirty_trades else [],
            "launches": [list(self.launches)] if changed else [],
            "errors": [list(self.errors)] if self.moved else [],
            "quotes": [dict(self.quotes)] if changed else [],
            "stats": [self.stats()] if (self.moved or changed) else [],
            "sync": [{"cursor": self.cursor, "epoch": self.epoch, "mode": self.mode}]
            if self.moved
            else [],
            "point": [self.point] if self.point else [],
        }
        out["moved"] = bool(self.moved or changed or self.point)
        self.dirty, self.dirty_trades, self.dirty_candles = set(), set(), set()
        self.gone, self.point, self.moved = [], None, False
        return out
