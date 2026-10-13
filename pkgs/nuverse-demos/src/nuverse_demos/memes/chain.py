"""What a Solana block says about meme launches: the launchpad's events, decoded, in the order they ran.

Pure Python over the JSON ``getBlock`` returns (``encoding: "json"``,
``transactionDetails: "full"``). Nothing here reaches the network.

Every launchpad event is emitted the Anchor ``event_cpi`` way: the
program calls itself with the event as the instruction data, behind an
8-byte tag, then the event's own 8-byte discriminator, then the borsh body.
So a block's events are the launchpad's self-calls among each transaction's
inner instructions. When a transaction carries no inner instructions, its
``Program data:`` log lines say the same.

- :func:`decode_block`: a block's launchpad events, as plain dicts.
- :func:`decode_event`: one event's bytes, as a dict, or None.
- :func:`b58encode`, :func:`b58decode`: Solana's base58, enough of it.

Layouts follow the launchpad's published IDL, checked against mainnet
payloads: a ``TradeEvent`` is 380 to 400 bytes today, its tail grown past
what the IDL lists, and ``ix_name`` sits at offset 258.
"""

from __future__ import annotations

import base64
import struct
from typing import Any


__all__ = [
    "AMM_PROGRAM",
    "LAUNCHPAD_PROGRAM",
    "SOL",
    "b58decode",
    "b58encode",
    "decode_block",
    "decode_event",
]


#: The meme launchpad program: coin creation, the bonding curve, migration.
LAUNCHPAD_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

#: The AMM graduated coins migrate into. Named for reference: its trades are not read here.
AMM_PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

#: The quote mint a SOL-paired coin reports: the default pubkey, all zero bytes.
SOL = "11111111111111111111111111111111"

#: What precedes an event in an ``event_cpi`` self-call: Anchor's ``EVENT_IX_TAG``.
EVENT_TAG = bytes.fromhex("e445a52e51cb9a1d")

#: The launchpad events read here, by discriminator.
TRADE = bytes([189, 219, 127, 211, 78, 230, 97, 238])
CREATE = bytes([27, 114, 169, 77, 222, 235, 99, 118])
COMPLETE = bytes([95, 114, 97, 156, 212, 46, 152, 8])
MIGRATE = bytes([189, 233, 93, 185, 92, 148, 234, 148])

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {c: i for i, c in enumerate(_ALPHABET)}
_LOG = "Program data: "


# --- base58 ------------------------------------------------------------------------------------


def b58encode(raw: bytes) -> str:
    """``raw`` in base58, leading zero bytes as leading ``1``s."""
    n = int.from_bytes(raw, "big")
    out = []
    while n:
        n, r = divmod(n, 58)
        out.append(_ALPHABET[r])
    pad = len(raw) - len(raw.lstrip(b"\0"))
    return "1" * pad + "".join(reversed(out))


def b58decode(text: str) -> bytes:
    """The bytes base58 ``text`` spells. Raises ``ValueError`` on a character outside the alphabet."""
    n = 0
    for c in text:
        try:
            n = n * 58 + _INDEX[c]
        except KeyError:
            raise ValueError(f"not base58: {c!r}") from None
    body = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(text) - len(text.lstrip("1"))
    return b"\0" * pad + body


# --- events ------------------------------------------------------------------------------------


class _Reader:
    """Borsh reads off a payload, front to back. Running past the end raises ``struct.error``."""

    def __init__(self, data: bytes, at: int = 8) -> None:
        self.data, self.at = data, at

    def key(self) -> str:
        raw = self.data[self.at : self.at + 32]
        if len(raw) < 32:
            raise struct.error("short pubkey")
        self.at += 32
        return b58encode(raw)

    def u64(self) -> int:
        (v,) = struct.unpack_from("<Q", self.data, self.at)
        self.at += 8
        return v

    def i64(self) -> int:
        (v,) = struct.unpack_from("<q", self.data, self.at)
        self.at += 8
        return v

    def flag(self) -> bool:
        if self.at >= len(self.data):
            raise struct.error("short bool")
        v = self.data[self.at] == 1
        self.at += 1
        return v

    def text(self, limit: int = 512) -> str:
        (n,) = struct.unpack_from("<I", self.data, self.at)
        if n > limit or self.at + 4 + n > len(self.data):
            raise struct.error("bad string")
        v = self.data[self.at + 4 : self.at + 4 + n].decode("utf-8", "replace")
        self.at += 4 + n
        return v

    def left(self) -> int:
        return len(self.data) - self.at


def _trade(r: _Reader) -> dict[str, Any]:
    """A ``TradeEvent``. Reserves are the curve's after the trade."""
    e: dict[str, Any] = {"kind": "trade", "mint": r.key()}
    e["sol"], e["tokens"], e["buy"] = r.u64(), r.u64(), r.flag()
    e["user"], e["ts"] = r.key(), r.i64()
    e["vsol"], e["vtok"], e["rsol"], e["rtok"] = r.u64(), r.u64(), r.u64(), r.u64()
    r.key()  # fee_recipient
    r.u64()  # fee_basis_points
    e["fee"] = r.u64()
    e["creator"] = r.key()
    r.u64()  # creator_fee_basis_points
    e["creator_fee"] = r.u64()
    # The tail came later and grows: read what is there, default the rest.
    e.update(ix="", mayhem=False, quote=SOL, qamount=e["sol"], vquote=e["vsol"], rquote=e["rsol"])
    try:
        r.flag()  # track_volume
        r.u64(), r.u64(), r.u64(), r.i64()  # the volume accumulator
        e["ix"] = r.text(64)
        e["mayhem"] = r.flag()
        r.u64(), r.u64(), r.u64(), r.u64()  # cashback and buyback, bps and amount
        (holders,) = struct.unpack_from("<I", r.data, r.at)
        r.at += 4 + holders * 34  # shareholders: (pubkey, u16) each
        e["quote"], e["qamount"] = r.key(), r.u64()
        e["vquote"], e["rquote"] = r.u64(), r.u64()
    except struct.error:
        pass
    return e


def _create(r: _Reader) -> dict[str, Any]:
    """A ``CreateEvent``: what was launched, by whom, on what curve."""
    e: dict[str, Any] = {
        "kind": "create",
        "name": r.text(),
        "symbol": r.text(),
        "uri": r.text(1024),
    }
    e["mint"], e["curve"], e["user"], e["creator"] = r.key(), r.key(), r.key(), r.key()
    e["ts"], e["vtok"], e["vsol"], e["rtok"], e["supply"] = (
        r.i64(),
        r.u64(),
        r.u64(),
        r.u64(),
        r.u64(),
    )
    e.update(mayhem=False, cashback=False, quote=SOL, vquote=e["vsol"])
    try:
        r.key()  # token_program
        e["mayhem"], e["cashback"] = r.flag(), r.flag()
        e["quote"], e["vquote"] = r.key(), r.u64()
    except struct.error:
        pass
    return e


def _complete(r: _Reader) -> dict[str, Any]:
    """A ``CompleteEvent``: the buy that emptied the curve's real tokens."""
    return {"kind": "complete", "user": r.key(), "mint": r.key(), "curve": r.key(), "ts": r.i64()}


def _migrate(r: _Reader) -> dict[str, Any]:
    """The migration event: the curve's reserves moved into a pool on the AMM."""
    e: dict[str, Any] = {"kind": "migrate", "user": r.key(), "mint": r.key()}
    e["tokens"], e["sol"], e["fee"] = r.u64(), r.u64(), r.u64()
    e["curve"], e["ts"], e["pool"] = r.key(), r.i64(), r.key()
    return e


_DECODERS = {TRADE: _trade, CREATE: _create, COMPLETE: _complete, MIGRATE: _migrate}


def decode_event(data: bytes) -> dict[str, Any] | None:
    """One launchpad event from its bytes, discriminator first: a dict with ``kind``, or None.

    None for an event not read here, or one too short to be what its
    discriminator says.
    """
    decode = _DECODERS.get(data[:8])
    if decode is None:
        return None
    try:
        return decode(_Reader(data))
    except struct.error:
        return None


# --- blocks ------------------------------------------------------------------------------------


def _keys(tx: dict) -> list[str]:
    """Every account a transaction names, in index order: its own, then those its lookup tables load."""
    keys = list(tx["transaction"]["message"]["accountKeys"])
    loaded = (tx.get("meta") or {}).get("loadedAddresses") or {}
    return keys + list(loaded.get("writable") or []) + list(loaded.get("readonly") or [])


def _from_inner(tx: dict, keys: list[str]) -> list[bytes] | None:
    """The event payloads among the launchpad's self-calls, in order. None when there are no inner instructions."""
    inner = (tx.get("meta") or {}).get("innerInstructions")
    if inner is None:
        return None
    out = []
    for group in inner:
        for ix in group.get("instructions") or []:
            i = ix.get("programIdIndex", -1)
            if not (0 <= i < len(keys)) or keys[i] != LAUNCHPAD_PROGRAM:
                continue
            try:
                data = b58decode(ix.get("data") or "")
            except ValueError:
                continue
            if data[:8] == EVENT_TAG:
                out.append(data[8:])
    return out


def _from_logs(tx: dict) -> list[bytes]:
    """The event payloads in a transaction's ``Program data:`` log lines, in order."""
    out = []
    for line in (tx.get("meta") or {}).get("logMessages") or []:
        if line.startswith(_LOG):
            try:
                out.append(base64.b64decode(line[len(_LOG) :]))
            except ValueError:
                continue
    return out


def decode_block(block: dict, slot: int) -> dict[str, Any]:
    """The launchpad events of the block at ``slot``: ``{slot, time, txs, failed, events}``.

    ``slot`` is passed in: ``getBlock`` does not say which slot it answered for.

    ``events`` holds every launchpad event of every transaction that
    succeeded and names the launchpad, in block order, each a dict from
    :func:`decode_event` with the transaction's ``sig`` and ``slot`` added.
    ``txs`` counts the block's transactions, ``failed`` the launchpad ones
    that failed.
    """
    txs = block.get("transactions") or []
    events: list[dict[str, Any]] = []
    failed = 0
    for tx in txs:
        try:
            keys = _keys(tx)
        except (KeyError, TypeError):
            continue
        if LAUNCHPAD_PROGRAM not in keys:
            continue
        if (tx.get("meta") or {}).get("err") is not None:
            failed += 1
            continue
        payloads = _from_inner(tx, keys)
        if payloads is None:
            payloads = _from_logs(tx)
        sig = (tx["transaction"].get("signatures") or [""])[0]
        for data in payloads:
            e = decode_event(data)
            if e is not None:
                e["sig"], e["slot"] = sig, slot
                events.append(e)
    return {
        "slot": slot,
        "time": block.get("blockTime"),
        "txs": len(txs),
        "failed": failed,
        "events": events,
    }
