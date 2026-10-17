"""The state the memes planes share, and how each plane finds it.

Everything lives in the root Memes plane's state: the sync job writes the
chain's side (:class:`Memes`), the Sync plane writes the knobs
(:class:`Control`), and every other plane reads both from the root. One class
each, imported by every cell, so the slots are declared once.

Values the job rewrites whole each turn (a token, the board, the tape) are
primitive blobs: one row each in the store, whatever they hold. Metrics are
kh57 series keyed by unix second, so a chart samples them at the same cost
however long the sync has run.

The planes hang as the root makes them::

    Memes                 the root, made from :data:`nudemos.memes.PLANE`
      Overview            the terminal: tokens, tape, launches
        <token>           a token's page, made on a click, made_by ``memes_token``
      Monitor, Sync
      sync                the job (headless, mp), made_by ``memes_job``
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space


__all__ = [
    "JOB",
    "MADE_BY",
    "OVERVIEW",
    "ROOT",
    "TOKEN",
    "Control",
    "Memes",
    "at_root",
    "job_cell",
    "job_of",
    "overview_of",
    "root_of",
    "token_page",
]


#: ``made_by`` of the root, of the job, of a token page, of the Overview.
ROOT, JOB, TOKEN, OVERVIEW = "memes", "memes_job", "memes_token", "memes_overview"

#: What a root records as ``made_by``, the name the space registers it under.
MADE_BY = f"nudemos.{ROOT}"


class Memes(nuspace.PlaneState):
    """What the sync job writes: the tokens it follows, the feeds, the totals, the metrics."""

    # One record per token, its newest trades, its one-minute market cap candles.
    tokens = nustd.kv.DictRef.slot(nustd.kv.PrimitiveDictRef)
    trades = nustd.kv.DictRef.slot(nustd.kv.PrimitiveListRef)
    candles = nustd.kv.DictRef.slot(nustd.kv.PrimitiveListRef)
    # The overview's token lists, the tape, the pulse, the launches, the errors.
    board = nustd.kv.PrimitiveDictRef.slot()
    tape = nustd.kv.PrimitiveListRef.slot()
    pulse = nustd.kv.PrimitiveListRef.slot()
    launches = nustd.kv.PrimitiveListRef.slot()
    errors = nustd.kv.PrimitiveListRef.slot()
    quotes = nustd.kv.PrimitiveDictRef.slot()
    # Status, totals and rates; where the sync is; a count of its commits, to follow.
    stats = nustd.kv.PrimitiveDictRef.slot()
    sync = nustd.kv.PrimitiveDictRef.slot()
    beat = nustd.kv.IntRef.slot()
    # Metrics, a point every few seconds, keyed by unix second.
    blocks_s = nustd.kv.Kh57Ref.slot(float)
    trades_s = nustd.kv.Kh57Ref.slot(float)
    launches_m = nustd.kv.Kh57Ref.slot(float)
    volume_m = nustd.kv.Kh57Ref.slot(float)
    lag = nustd.kv.Kh57Ref.slot(float)
    latency = nustd.kv.Kh57Ref.slot(float)
    errors_n = nustd.kv.Kh57Ref.slot(float)


class Control(nuspace.PlaneState):
    """What the Sync plane sets: the endpoint, the pace, where to start, whether to run.

    ``epoch`` moves when a start over is asked for: from ``start``, a slot,
    or from the tip when it is 0. The job reads all of it every turn.
    """

    rpc = nustd.kv.StrRef.slot()
    rate = nustd.kv.FloatRef.slot()
    start = nustd.kv.IntRef.slot()
    epoch = nustd.kv.IntRef.slot()
    stop = nustd.kv.BoolRef.slot()
    # Coins' own images, off by default: launches are anyone's, and some images are explicit.
    images = nustd.kv.BoolRef.slot()


def _made_by(plane: nu.StrArg) -> nu.Str:
    return Space.planes[plane].props.made_by.fallback("")


def root_of(plane: nu.StrArg) -> nu.Str:
    """The Memes root a plane belongs to: itself, its meta's ``base``, or its parent. Bare read."""
    base = nu.str(Space.planes[plane].meta["base"]).fallback(ops.parent(plane))
    return nu.Str(nu.If(_made_by(plane) == MADE_BY, plane, base))


def at_root(root: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`Memes` and :class:`Control`, landed on the root's state. Bare."""
    return ops.plane_state(root, term)


def overview_of(root: nu.StrArg) -> nu.Str:
    """The root's Overview plane, where token pages hang; the root itself when it has none. Bare read."""
    found = ops.children(root).iter().filter(lambda p: _made_by(nu.Str(p)) == OVERVIEW)
    return nu.str(nu.First(found)).fallback(root)


def job_of(root: nu.StrArg) -> nu.Str:
    """The sync job's plane id: fixed under the root, so every cell finds it without a look."""
    return nu.Str(root) + ".sync"


def job_cell(job: nu.StrArg) -> nu.Str:
    """The job's one cell: its id with ``_main`` after it."""
    return nu.Str(job) + "_main"


def token_page(root: nu.StrArg, mint: nu.StrArg) -> nu.Str:
    """A token page's plane id: the root's, then the mint."""
    return nu.Str(root) + ".token." + nu.Str(mint)
