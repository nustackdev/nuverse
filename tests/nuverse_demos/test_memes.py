"""nuverse-demos memes: the decoding, the curve math, the book's policy, the views. Offline.

The fixtures are real mainnet blocks, trimmed to the transactions that name
the launchpad (plus a couple that do not) and to the fields the decoder
reads; account keys it does not read are blanked.
"""

from __future__ import annotations

import base64
import json
import os
import struct
from pathlib import Path

import pytest

from nuverse_demos.memes import book as booklib
from nuverse_demos.memes import curve, views
from nuverse_demos.memes.book import Book, clean, endpoint, masked
from nuverse_demos.memes.chain import (
    COMPLETE,
    CREATE,
    LAUNCHPAD_PROGRAM,
    MIGRATE,
    SOL,
    TRADE,
    b58decode,
    b58encode,
    decode_block,
    decode_event,
)


FIXTURES = Path(__file__).parent / "fixtures" / "memes"
SLOT, CREATED = 456413524, 456413622
MINE = "https://rpc.example"


def _block(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


TRADES = _block(f"block_{SLOT}.json")
CREATE_BLOCK = _block(f"block_{CREATED}_create.json")
GRADUATED = 456422143
GRAD_BLOCK = _block(f"block_{GRADUATED}_graduation.json")

#: The coins the fixtures are about, by what happens to them: traded, launched, graduated.
TRADED = decode_block(TRADES, SLOT)["events"][0]["mint"]
LAUNCHED = decode_block(CREATE_BLOCK, CREATED)["events"][0]["mint"]
GRADUATE = decode_block(GRAD_BLOCK, GRADUATED)["events"][0]["mint"]


class Clock:
    """A clock a test moves by hand."""

    def __init__(self, t: float = 1_800_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


# --- base58 and events -----------------------------------------------------------------------


def test_base58_round_trips_keys_and_leading_zeros():
    assert b58encode(b58decode(LAUNCHPAD_PROGRAM)) == LAUNCHPAD_PROGRAM
    assert b58decode(SOL) == bytes(32)
    assert b58encode(b"\0\0\x01") == "112"
    with pytest.raises(ValueError, match="not base58"):
        b58decode("0OIl")


def test_a_block_yields_its_trades_in_order():
    d = decode_block(TRADES, SLOT)
    assert d["slot"] == SLOT
    assert d["time"] == TRADES["blockTime"]
    assert d["txs"] == 9
    assert d["failed"] == 1
    kinds = [e["kind"] for e in d["events"]]
    assert kinds == ["trade"] * 6
    first = d["events"][0]
    assert first["mint"] == TRADED and len(b58decode(TRADED)) == 32
    assert (first["sol"], first["tokens"], first["buy"], first["ix"]) == (
        2810459,
        81964886807890,
        False,
        "sell",
    )
    assert first["quote"] == SOL
    assert first["qamount"] == first["sol"]
    assert first["vquote"] == first["vsol"] == 32261503
    assert first["slot"] == SLOT
    assert first["sig"]


def test_coins_quoted_in_another_token_carry_it():
    # Since 2026 a coin can pair against any whitelisted mint: the legacy SOL fields are 0.
    wif = [e for e in decode_block(TRADES, SLOT)["events"] if e["quote"] != SOL]
    assert wif
    for e in wif:
        assert e["sol"] == 0 and e["vsol"] == 0
        assert e["qamount"] > 0 and e["vquote"] > 0
    assert {e["quote"] for e in wif} <= set(booklib.KNOWN_QUOTES)


def test_a_launch_yields_its_create_then_the_first_buy():
    create, buy = decode_block(CREATE_BLOCK, CREATED)["events"]
    assert create["kind"] == "create"
    assert (create["name"], create["symbol"]) == ("dog wif cap", "cap")
    assert create["mint"] == buy["mint"] == LAUNCHED
    assert create["creator"] == create["user"]
    # The genesis reserves the kb gives.
    assert create["vsol"] == curve.GENESIS_VSOL
    assert create["vtok"] == curve.GENESIS_VTOK
    assert create["rtok"] == curve.GENESIS_RTOK
    assert create["supply"] == curve.SUPPLY
    assert create["quote"] == SOL and create["mayhem"] is True
    assert buy["kind"] == "trade" and buy["buy"]


def test_logs_stand_in_when_there_are_no_inner_instructions():
    tx = json.loads(json.dumps(TRADES["transactions"][1]))
    from_inner = decode_block({"transactions": [tx]}, SLOT)["events"]
    tx["meta"]["innerInstructions"] = None
    from_logs = decode_block({"transactions": [tx]}, SLOT)["events"]
    assert from_logs == from_inner != []


def test_a_graduation_completes_the_curve_then_migrates_it():
    # The last buy empties the real tokens, the complete event follows, and the migration
    # moves ~85 SOL and the reserved tokens into a pool on the AMM, here in the same slot.
    buy, done, moved = decode_block(GRAD_BLOCK, GRADUATED)["events"]
    mint = GRADUATE
    assert (buy["kind"], done["kind"], moved["kind"]) == ("trade", "complete", "migrate")
    assert buy["mint"] == done["mint"] == moved["mint"] == mint
    assert buy["buy"] and buy["rtok"] == 0
    assert buy["rquote"] == pytest.approx(85 * curve.LAMPORTS, rel=0.01)
    assert moved["sol"] == pytest.approx(85.8 * curve.LAMPORTS, rel=0.01)
    assert moved["tokens"] == pytest.approx(205e12, rel=0.01)
    assert moved["pool"] == "GK8GvfLg5uwF5RABmo4TFpQQennsKNn9JR3WZ4ALJ7U6"
    assert done["sig"] != moved["sig"]


def _payload(disc: bytes, *parts: bytes) -> bytes:
    return disc + b"".join(parts)


def test_complete_and_migrate_events_decode():
    user, mint, curve_, pool = (bytes([i]) * 32 for i in (1, 2, 3, 4))
    done = decode_event(_payload(COMPLETE, user, mint, curve_, struct.pack("<q", 7), bytes(32)))
    assert done == {
        "kind": "complete",
        "user": b58encode(user),
        "mint": b58encode(mint),
        "curve": b58encode(curve_),
        "ts": 7,
    }
    moved = decode_event(
        _payload(
            MIGRATE,
            user,
            mint,
            struct.pack("<QQQ", 206, 85, 1),
            curve_,
            struct.pack("<q", 9),
            pool,
            bytes(32),
        )
    )
    assert moved["kind"] == "migrate"
    assert (moved["mint"], moved["pool"], moved["sol"], moved["ts"]) == (
        b58encode(mint),
        b58encode(pool),
        85,
        9,
    )


def test_short_or_unknown_payloads_are_skipped():
    assert decode_event(b"\0" * 300) is None
    assert decode_event(TRADE + b"\0" * 40) is None
    assert decode_event(CREATE + struct.pack("<I", 9999)) is None


def test_an_old_trade_without_the_tail_still_decodes():
    full = base64.b64decode(
        TRADES["transactions"][1]["meta"]["logMessages"][0][len("Program data: ") :]
    )
    e = decode_event(full[:240])
    assert e is not None and e["ix"] == "" and e["quote"] == SOL and e["qamount"] == e["sol"]


# --- the curve, against the kb's own numbers ---------------------------------------------------


def test_a_buy_of_one_sol_at_genesis():
    # 1 SOL in at genesis buys 34,612,903,225,807 raw tokens by the two-step form
    # (k / new vsol), one more than the program's single floor division delivers.
    out = curve.buy_tokens(curve.GENESIS_VSOL, curve.GENESIS_VTOK, curve.LAMPORTS)
    two_step = curve.GENESIS_VTOK - curve.GENESIS_VSOL * curve.GENESIS_VTOK // (
        curve.GENESIS_VSOL + curve.LAMPORTS
    )
    assert out == 34_612_903_225_806 == two_step - 1
    # buy_exact_sol_in shifts the lamports by one, which costs a few ten thousand raw tokens here.
    exact = curve.buy_exact_in(curve.GENESIS_VSOL, curve.GENESIS_VTOK, curve.LAMPORTS)
    assert (
        exact
        == (curve.LAMPORTS - 1) * curve.GENESIS_VTOK // (curve.GENESIS_VSOL + curve.LAMPORTS - 1)
        < out
    )


def test_selling_back_returns_the_sol_less_integer_floor():
    vsol, vtok = curve.GENESIS_VSOL, curve.GENESIS_VTOK
    tokens = curve.buy_tokens(vsol, vtok, curve.LAMPORTS)
    back = curve.sell_tokens(vsol + curve.LAMPORTS, vtok - tokens, tokens)
    assert curve.LAMPORTS - 2 <= back <= curve.LAMPORTS


def test_price_market_cap_and_progress():
    # Genesis: 0.02796 lamports a raw token, about 28 SOL of market cap, nothing bought.
    assert curve.price(curve.GENESIS_VSOL, curve.GENESIS_VTOK) == pytest.approx(2.796e-8, rel=1e-3)
    assert curve.market_cap(curve.GENESIS_VSOL, curve.GENESIS_VTOK) == pytest.approx(
        27.96, rel=1e-3
    )
    assert curve.progress(curve.GENESIS_RTOK) == 0.0
    assert curve.progress(0) == 1.0
    assert curve.progress(curve.GENESIS_RTOK // 2) == pytest.approx(0.5)
    # A WIF-quoted curve: 6 decimals.
    assert curve.market_cap(38_244_457_244, 624_271_720_973_091, quote_decimals=6) == pytest.approx(
        61262, rel=1e-3
    )
    assert curve.price(1, 0) == curve.market_cap(1, 0) == 0.0


# --- the book --------------------------------------------------------------------------------


def _reply_block(b: Book, slot: int, block: dict | None = None, error: dict | None = None) -> None:
    reply = {"error": error} if error else {"result": block}
    b.on_reply({"what": "block", "slot": slot, "sent": b.clock()}, reply)


def test_a_fresh_book_asks_for_the_tip_first():
    b = Book(clock=Clock())
    p = b.plan({"epoch": 0, "rpc": "https://rpc.example/?api-key=x"})
    assert p["do"] == "call"
    assert [c["method"] for c in p["calls"]] == ["getSlot"]
    assert p["calls"][0]["url"] == "https://rpc.example/?api-key=x"


def test_it_starts_two_slots_behind_the_tip_and_reads_up_to_it():
    clock = Clock()
    b = Book(clock=clock)
    b.plan({"epoch": 0})
    b.on_reply({"what": "slot", "sent": clock()}, {"result": 1000})
    clock.t += 0.1
    p = b.plan({"epoch": 0, "rate": 10})
    blocks = [c for c in p["calls"] if c["method"] == "getBlock"]
    assert [c["slot"] for c in blocks] == [998]
    assert blocks[0]["params"][1]["maxSupportedTransactionVersion"] == 1
    # Caught up: it waits rather than asking for blocks that are not out.
    _reply_block(b, 998, {"transactions": []})
    p = b.plan({"epoch": 0, "rate": 10})
    assert p["do"] == "wait" or all(c["method"] != "getBlock" for c in p["calls"])


def test_the_rate_caps_blocks_and_a_burst_reads_several_at_once():
    clock = Clock()
    b = Book(clock=clock)
    b.plan({"epoch": 0})
    b.on_reply({"what": "slot", "sent": clock()}, {"result": 1100})
    b.cursor = 1000
    b.mode = "from"
    clock.t += 10.0  # a full bucket
    p = b.plan({"epoch": 0, "rate": 2, "rpc": MINE})
    slots = [c["slot"] for c in p["calls"] if c["method"] == "getBlock"]
    assert slots == [1000, 1001, 1002, 1003]
    # The bucket is empty: with the tip fresh, the next turn waits half a second, the rate's pace.
    b.on_reply({"what": "slot", "sent": clock()}, {"result": 1100})
    p = b.plan({"epoch": 0, "rate": 2, "rpc": MINE})
    assert p == {"do": "wait", "wait": pytest.approx(0.5)}


def test_the_public_endpoint_gets_one_fresh_block_at_a_time(monkeypatch):
    monkeypatch.delenv(booklib.ENV, raising=False)
    clock = Clock()
    b = Book(clock=clock)
    b.plan({"epoch": 0})
    b.on_reply({"what": "slot", "sent": clock()}, {"result": 1100})
    b.cursor, b.mode = 1000, "from"
    clock.t += 10.0
    p = b.plan({"epoch": 0, "rate": 5})
    assert [c["slot"] for c in p["calls"] if c["method"] == "getBlock"] == [1000]
    b.on_reply({"what": "slot", "sent": clock()}, {"result": 1100})
    assert b.plan({"epoch": 0, "rate": 5}) == {"do": "wait", "wait": 1.0}


def test_replies_out_of_order_move_the_cursor_only_over_what_is_read():
    b = Book(clock=Clock())
    b.cursor, b.tip, b.tip_at, b.epoch = 1000, 1100, b.clock(), 0
    _reply_block(b, 1001, {"transactions": []})
    assert b.cursor == 1000
    _reply_block(b, 1000, None, {"code": -32007, "message": "Slot 1000 was skipped"})
    assert b.cursor == 1002
    assert b.totals["skipped"] == 1 and b.totals["blocks"] == 1
    _reply_block(b, 1001, {"transactions": []})  # asked twice: counted once
    assert b.totals["blocks"] == 1


def test_a_block_not_out_yet_is_asked_again_and_an_error_backs_off():
    clock = Clock()
    b = Book(clock=clock)
    b.cursor, b.tip, b.tip_at, b.epoch = 1000, 1100, clock(), 0
    _reply_block(b, 1000, None, {"code": -32004, "message": "Block not available"})
    assert b.cursor == 1000 and b.until == pytest.approx(clock() + 0.4)
    b.on_error(
        {"what": "block", "slot": 1000},
        "Client error '429 Too Many Requests' for url 'https://x.io/?api-key=SECRET'",
    )
    b.on_error({"what": "block", "slot": 1000}, "again")
    assert b.backoff == 2.0 and b.until == pytest.approx(clock() + 2.0)
    assert b.plan({"epoch": 0})["do"] == "wait"
    (_, older) = list(b.errors)
    assert "SECRET" not in older["message"] and "429" in older["message"]
    assert b.totals["errors"] == 2
    # A block read eases the next backoff.
    clock.t += 3.0
    _reply_block(b, 1000, {"transactions": []})
    assert b.backoff == 0.0 and b.cursor == 1001


def test_a_caught_error_names_its_type_when_its_message_is_empty():
    class Caught(str):
        exception = TimeoutError()

    b = Book(clock=Clock())
    b.on_error({"what": "slot"}, Caught(""))
    assert b.errors[0]["message"] == "TimeoutError"


def test_a_slow_sync_reads_every_block_in_order_and_falls_behind(monkeypatch):
    monkeypatch.delenv(booklib.ENV, raising=False)
    clock = Clock()
    b = Book(clock=clock)
    b.plan({"epoch": 0, "rpc": MINE})
    b.on_reply({"what": "slot", "sent": clock()}, {"result": 1000})
    b.plan({"epoch": 0, "rpc": MINE})
    b.cursor = 900
    clock.t += 1.0
    p = b.plan({"epoch": 0, "rpc": MINE, "rate": 2})
    # Far behind the tip it still asks for the next blocks in order: it never skips.
    slots = [c["slot"] for c in p["calls"] if c["method"] == "getBlock"]
    assert slots == list(range(900, 900 + len(slots))) and slots
    assert b.cursor == 900 and "jumped" not in b.totals
    s = b.stats()
    assert (s["status"], s["lag"], s["limited"]) == ("behind", 100, False)
    assert "Raise the pace on Sync" in s["notice"]
    # A 429 says the endpoint is the reason.
    b.on_error({"what": "block", "slot": 900}, "Client error '429 Too Many Requests'")
    clock.t += 31.0
    s = b.stats()
    assert s["limited"] and "Your RPC is rate limiting" in s["notice"]
    # On the public endpoint the notice points to Sync.
    b.plan({"epoch": 0})
    s = b.stats()
    assert s["public"] and s["notice"] == (
        "The public RPC is rate limited, so this view runs behind the chain. "
        "Set your own RPC on Sync to keep up."
    )
    # Close to the tip it is live, with nothing to say.
    b.cursor = 995
    assert (b.stats()["status"], b.stats()["notice"]) == ("syncing", "")
    b.plan({"epoch": 1, "start": 500})
    assert (b.cursor, b.mode) == (500, "from")
    b.plan({"epoch": 1, "start": 500})
    assert b.cursor == 500


def test_trades_and_launches_fold_into_records_the_board_and_the_tape():
    clock = Clock(1791888300.0)
    b = Book(clock=clock)
    b.cursor, b.tip, b.tip_at, b.epoch = SLOT, SLOT + 100, clock(), 0
    _reply_block(b, SLOT, TRADES)
    b.cursor = CREATED
    _reply_block(b, CREATED, CREATE_BLOCK)
    out = b.flush()
    assert out["moved"]
    tokens = dict(out["tokens"])
    cap = tokens[LAUNCHED]
    assert (cap["name"], cap["symbol"], cap["created"]) == ("dog wif cap", "cap", 1791888256)
    assert cap["trades"] == cap["buys"] == 1 and cap["vol"] > 0
    assert cap["mc"] > cap["mc_open"] * 0.5
    assert 0 < cap["progress"] < 1
    assert b.totals["launches"] == 1 and b.totals["trades"] == 7
    board = out["board"][0]
    assert [r["mint"] for r in board["new"]][:1] == [cap["mint"]]
    # Coins met mid-life are unnamed until a metadata lookup, and have no launch to list as new.
    assert not tokens[TRADED]["name"]
    assert [r["mint"] for r in board["new"]] == [cap["mint"]]
    # Market cap and volume rank SOL coins only: another quote's numbers are not SOL.
    assert {r["quote"] for r in board["mc"]} == {r["quote"] for r in board["volume"]} == {"SOL"}
    sol = [m for m, r in tokens.items() if r["quote"] == SOL]
    assert sorted(r["mint"] for r in board["active"]) == sorted(sol) and len(sol) < len(tokens)
    assert out["tape"][0][0]["mint"] == cap["mint"]
    assert len(out["trades"]) == len(tokens)
    assert dict(out["candles"])[cap["mint"]][0][6] == 1
    # Nothing moved since: the next flush writes nothing.
    assert not b.flush()["moved"]


def test_a_graduation_marks_the_token_and_counts_once():
    b = Book(clock=Clock(1791890200.0))
    b.cursor, b.tip, b.tip_at, b.epoch = GRADUATED, GRADUATED + 100, b.clock(), 0
    _reply_block(b, GRADUATED, GRAD_BLOCK)
    rec = b.tokens[GRADUATE]
    assert rec["complete"] and rec["migrated"] and rec["progress"] == 1.0
    assert rec["pool"] == "GK8GvfLg5uwF5RABmo4TFpQQennsKNn9JR3WZ4ALJ7U6"
    assert rec["mc"] == pytest.approx(410, rel=0.02)  # ~400 SOL at graduation, as published
    assert (b.totals["graduations"], b.totals["migrations"]) == (1, 1)
    # Graduated coins leave the nearest-graduation list to those still on the curve.
    assert all(not r["complete"] for r in b.board()["progress"])


def test_metadata_names_unnamed_coins_in_batches():
    clock = Clock()
    b = Book(clock=clock)
    b.cursor, b.tip, b.tip_at, b.epoch = SLOT, SLOT + 100, clock(), 0
    _reply_block(b, SLOT, TRADES)
    clock.t += 5.0
    p = b.plan({"epoch": 0})
    (meta,) = [c for c in p["calls"] if c["method"] == "getMultipleAccounts"]
    mint = TRADED
    assert mint in meta["mints"]
    values = [None] * len(meta["mints"])
    values[meta["mints"].index(mint)] = {
        "data": {
            "parsed": {
                "info": {
                    "decimals": 6,
                    "supply": "2000000000000000",
                    "extensions": [
                        {
                            "extension": "tokenMetadata",
                            "state": {
                                "name": "Lobotomized Angel Reese",
                                "symbol": "WNBA",
                                "uri": "https://x",
                            },
                        }
                    ],
                }
            }
        }
    }
    b.on_reply(meta, {"result": {"value": values}})
    rec = b.tokens[mint]
    assert (rec["name"], rec["symbol"], rec["supply"]) == (
        "Lobotomized Angel Reese",
        "WNBA",
        2 * curve.SUPPLY,
    )
    # Asked once: the next plan does not ask again.
    clock.t += 5.0
    assert all(mint not in c.get("mints", []) for c in b.plan({"epoch": 0}).get("calls", []))


def test_quiet_tokens_are_evicted_and_the_cap_holds():
    clock = Clock(1791888300.0)
    b = Book(clock=clock, keep_hours=1.0, max_tokens=3)
    b.cursor, b.tip, b.tip_at, b.epoch = SLOT, SLOT + 100, clock(), 0
    _reply_block(b, SLOT, TRADES)
    assert len(b.tokens) == 6
    clock.t += booklib.PRUNE_EVERY + 1
    out = b.flush()
    assert len(b.tokens) == 3 and len(out["gone"]) == 3
    clock.t += 3600 + booklib.PRUNE_EVERY
    out = b.flush()
    assert not b.tokens and len(out["gone"]) == 3


def test_metrics_land_a_point_every_few_seconds():
    clock = Clock()
    b = Book(clock=clock)
    b.load({})
    b.cursor, b.tip, b.tip_at, b.epoch = SLOT, SLOT + 100, clock(), 0
    _reply_block(b, SLOT, TRADES)
    assert b.flush()["point"] == []
    clock.t += booklib.EVERY
    (point,) = b.flush()["point"]
    assert point["t"] == int(clock())
    assert point["blocks"] == pytest.approx(1 / booklib.EVERY)
    assert point["trades"] == pytest.approx(6 / booklib.EVERY)
    assert "coverage" not in point


def test_a_book_picks_up_from_what_it_wrote():
    clock = Clock(1791888300.0)
    b = Book(clock=clock)
    b.cursor, b.tip, b.tip_at, b.epoch = SLOT, SLOT + 100, clock(), 0
    _reply_block(b, SLOT, TRADES)
    out = b.flush()
    saved = {
        "tokens": dict(out["tokens"]),
        "trades": dict(out["trades"]),
        "candles": dict(out["candles"]),
        "tape": out["tape"][0],
        "stats": out["stats"][0],
        "sync": out["sync"][0],
    }
    again = Book(clock=clock)
    again.load(saved)
    assert again.tokens == b.tokens
    assert again.cursor == SLOT + 1 and again.epoch == 0
    assert again.totals["trades"] == 6
    assert [t["n"] for t in again.tape] == [t["n"] for t in b.tape]
    # Same epoch: it carries on from its cursor rather than starting over.
    again.plan({"epoch": 0})
    assert again.cursor == SLOT + 1


def test_the_endpoint_comes_from_the_plane_the_env_or_the_public_one(monkeypatch):
    monkeypatch.delenv(booklib.ENV, raising=False)
    assert endpoint("") == booklib.DEFAULT_RPC
    monkeypatch.setenv(booklib.ENV, " https://env.example ")
    assert endpoint(None) == "https://env.example"
    assert endpoint("https://mine.example") == "https://mine.example"
    assert masked("https://mainnet.helius-rpc.com/?api-key=abc") == "mainnet.helius-rpc.com"
    assert clean("x https://h.io/rpc?api-key=abc&y=1 y") == "x https://h.io/rpc?... y"
    assert "abc" not in clean("api_key=abc")
    assert os.environ[booklib.ENV]


# --- views -----------------------------------------------------------------------------------


def test_numbers_read_short():
    assert views.amount(1234.5) == "1.2K"
    assert views.amount(0.04212) == "0.0421"
    assert views.amount(12.345) == "12.35"
    assert views.amount(0) == "0"
    assert views.ago(100, 112) == "12s"
    assert views.ago(0, 1) == "-"
    assert views.short("3kthZpcqsr1qrsCFQ3FdJYWAwCobqudfin7tnw9Ppx") == "3kth..9Ppx"
    assert views.change(2.5) == "▲ 3.5x"
    assert views.change(-0.25) == "▼ 25%"
    assert views.change(0.001) == "·"


def test_the_status_says_what_the_sync_is_doing():
    shape = views.status_of
    idle = shape({}, False, False, 0.0)
    assert (idle["status"], idle["button"]) == ("idle", "Start")
    stats = {
        "status": "syncing",
        "tip": 10,
        "cursor": 8,
        "lag": 2,
        "rates": {"blocks": 2.0},
        "rpc": "h",
        "beat": 0,
    }
    live = shape(stats, True, False, 1.0)
    assert (live["status"], live["button"], live["tone"]) == ("syncing", "Stop", "ok")
    assert shape(stats, True, True, 1.0)["status"] == "stopping"
    assert shape(stats, False, False, 1.0)["status"] == "down"
    assert shape({**stats, "status": "stopped"}, False, True, 1.0)["button"] == "Start"
    assert shape({**stats, "status": "stopped"}, True, False, 1.0)["status"] == "starting"
    assert live["notice"] == ""
    behind = shape(
        {**stats, "status": "behind", "lag": 300, "notice": "runs behind"}, True, False, 1.0
    )
    assert (behind["status"], behind["tone"], behind["button"]) == ("behind", "warn", "Stop")
    assert behind["notice"] == "runs behind" and "300 behind tip" in behind["line"]
    stopped = {**stats, "status": "stopped", "notice": "runs behind"}
    assert shape(stopped, False, True, 1.0)["notice"] == ""


def test_a_token_page_reads_its_record_trades_and_candles():
    clock = Clock(1791888300.0)
    b = Book(clock=clock)
    b.cursor, b.tip, b.tip_at, b.epoch = CREATED, CREATED + 100, clock(), 0
    _reply_block(b, CREATED, CREATE_BLOCK)
    mint = LAUNCHED
    v = views.token_view_of(b.tokens[mint], b.trades[mint], b.candles[mint], {}, clock())
    assert v["found"] and v["title"] == "dog wif cap" and v["symbol"] == "cap"
    assert v["unit"] == "SOL" and v["mc"].endswith(" SOL")
    assert f"https://solscan.io/token/{mint}" in v["links"]
    assert [r["side"] for r in v["rows"]] == ["▲ BUY"]
    (candle,) = v["candles"]
    assert len(candle) == 5 and candle[3] <= candle[1] <= candle[4]
    assert v["split"]["sells"] == 0 and v["split"]["buys"] > 0
    assert v["chart_title"] == "Market cap, a candle every 5s"
    assert v["volume_title"] == "Volume, a bar every 5s"
    assert views.token_view_of({}, [], [], {}, 0.0) == {"found": False}


def test_an_avatar_is_the_same_picture_for_the_same_mint():
    one = views.avatar(TRADED, "WNBA")
    assert one == views.avatar(TRADED, "WNBA")
    assert one != views.avatar(LAUNCHED, "WNBA")
    assert ">WNBA<" in one and one.startswith("<svg")
    assert views.avatar_url("m", "<b>").startswith("data:image/svg+xml")
    assert "&lt;B&gt;" in views.avatar("m", "<b>")


# --- pictures --------------------------------------------------------------------------------


def test_ipfs_urls_go_through_the_gateway():
    cid = "QmZyiVEccLuYE7H85Vp5oDw1SU3kcXBnKJ7Ln22sne76vy"
    g = booklib.GATEWAY
    assert booklib.gateway_url(f"ipfs://{cid}") == g + cid
    assert booklib.gateway_url(f"ipfs://ipfs/{cid}/0.png") == g + cid + "/0.png"
    assert booklib.gateway_url(f"https://ipfs.io/ipfs/{cid}") == g + cid
    assert booklib.gateway_url(cid) == g + cid
    assert booklib.gateway_url("https://cdn.example/a.png") == "https://cdn.example/a.png"
    assert booklib.gateway_url("http://plain.example/a.png") == ""
    assert booklib.gateway_url("javascript:alert(1)") == booklib.gateway_url(None) == ""


def _launched(clock: Clock) -> Book:
    b = Book(clock=clock)
    b.cursor, b.tip, b.tip_at, b.epoch = CREATED, CREATED + 100, clock(), 0
    _reply_block(b, CREATED, CREATE_BLOCK)
    return b


def test_a_launch_queues_its_picture_and_the_image_lands_in_its_record():
    clock = Clock(1791888300.0)
    b = _launched(clock)
    ask = b.picture()
    assert ask["mint"] == LAUNCHED and ask["url"].startswith(booklib.GATEWAY)
    assert b.picture() == {}  # paced
    b.on_picture(
        ask,
        {"name": "dog wif cap", "image": "ipfs://QmZyiVEccLuYE7H85Vp5oDw1SU3kcXBnKJ7Ln22sne76vy"},
    )
    rec = b.tokens[LAUNCHED]
    assert rec["image"].startswith(booklib.GATEWAY) and rec["picture"] == "ok"
    assert b.launches[0]["image"] == rec["image"]
    # Painted by default: a coin's own image shows only with "Show images" on.
    (card,) = _cards(b)
    assert card["src"].startswith("data:image/svg+xml")
    (card,) = _cards(b, images=True)
    assert card["src"] == rec["image"]
    shown = views.token_view_of(rec, [], [], {}, clock(), images=True)
    assert shown["src"] == rec["image"]
    assert views.token_view_of(rec, [], [], {}, clock())["src"].startswith("data:image/svg+xml")
    clock.t += 1.0
    assert b.picture() == {}  # asked once: nothing more to fetch


def _cards(b: Book, images: bool = False) -> list:
    return [
        {"src": views.picture(x.get("image"), x["mint"], x["symbol"], images)} for x in b.launches
    ]


def test_a_failing_fetch_is_tried_again_once_then_remembered():
    clock = Clock(1791888300.0)
    b = _launched(clock)
    ask = b.picture()
    b.on_no_picture(ask, "ReadTimeout")
    clock.t += 1.0
    again = b.picture()
    assert again == ask
    b.on_no_picture(again, "ReadTimeout")
    clock.t += 1.0
    assert b.picture() == {}
    assert b.tokens[LAUNCHED]["picture"] == "failed" and not b.tokens[LAUNCHED]["image"]
    # Metadata without an image is remembered too, as none.
    c = _launched(clock)
    c.on_picture(c.picture(), {"name": "no picture"})
    assert c.tokens[LAUNCHED]["picture"] == "none"


def test_at_most_a_few_fetches_run_at_once():
    clock = Clock(1791888300.0)
    b = Book(clock=clock)
    for i in range(6):
        rec = booklib.token_record(f"m{i}")
        rec["uri"] = "https://meta.example/" + str(i)
        b.tokens[rec["mint"]] = rec
        b._want(rec)
    asks = []
    for _ in range(6):
        clock.t += booklib.PICTURE_EVERY
        asks.append(b.picture())
    assert len([a for a in asks if a]) == booklib.PICTURES
    b.on_picture(asks[0], {})
    clock.t += booklib.PICTURE_EVERY
    assert b.picture()["mint"] == "m3"


def test_a_young_token_charts_finer_candles_than_a_minute():
    t0 = 1791888300.0
    trades = [[t0 + 7 * i, "buy", 0.1, 1e6, 30.0 + i, "u", "s", 1] for i in range(20)]
    bars, volume, bucket = views.chart_of(
        list(reversed(trades)), [[int(t0 // 60 * 60), 30, 49, 30, 49, 2.0, 20]]
    )
    assert bucket == "every 15s" and len(bars) == len(volume) >= 8
    assert bars[0][1] == 30.0 and bars[-1][2] == 49.0
    assert sum(v for _, v in volume) == pytest.approx(2.0)
    minutes = [[int(t0) + 60 * i, 30, 31, 29, 32, 1.0, 3] for i in range(12)]
    bars, _, bucket = views.chart_of(trades, minutes)
    assert bucket == "a minute" and len(bars) == 12
