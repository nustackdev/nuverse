"""The state the memes planes share, and how each plane finds it.

Everything lives in the root Memes plane's state: the sync job writes the
chain's side (:class:`Memes`), the Sync plane writes the knobs
(:class:`Control`), the root keeps the ids of what it made (:class:`Made`),
and every other plane reads them from the root, through :func:`memes_at`,
:func:`control_at` and :func:`made_at`. One class each, imported by every
cell, so the slots are declared once.

Values the job rewrites whole each turn (a token, the board, the tape) are
primitive blobs: one row each in the store, whatever they hold. Metrics are
kh57 series keyed by unix second, so a chart samples them at the same cost
however long the sync has run.

The planes hang as the root makes them::

    Memes                 the root, made from :data:`nudemos.memes.PLANE`
      Overview            the terminal: tokens, tape, launches
        <token>           a token's page, made on a click, spec ``memes_token``
      Monitor, Sync
      sync                the job (headless, mp), spec ``memes_job``
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import Space

from .. import bases


__all__ = [
    "CHILDREN",
    "JOB",
    "OVERVIEW",
    "ROOT",
    "TOKEN",
    "Control",
    "Made",
    "Memes",
    "control_at",
    "job_of",
    "made_at",
    "memes_at",
    "overview_of",
    "root_of",
]


#: The spec names of the root, of the job, of a token page, of the Overview.
ROOT, JOB, TOKEN, OVERVIEW = "memes", "memes_job", "memes_token", "memes_overview"

#: How many of the root's first children are looked at for its Overview.
_FIRST = 8


class Memes(nu.Shape):
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


class Control(nu.Shape):
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


class Made(nu.Shape):
    """The ids of what the root made after it was made itself: the job, the token planes by mint."""

    job = nustd.kv.StrRef.slot()
    token_planes = nustd.kv.DictRef.slot(str)


def memes_at(root: nu.StrArg) -> Memes:
    """The root's :class:`Memes`, in its plane's state."""
    return nuspace.at.plane(id=root).state(Memes)


def control_at(root: nu.StrArg) -> Control:
    """The root's :class:`Control`, in its plane's state."""
    return nuspace.at.plane(id=root).state(Control)


def made_at(root: nu.StrArg) -> Made:
    """The root's :class:`Made`, in its plane's state."""
    return nuspace.at.plane(id=root).state(Made)


#: The specs of the planes the root spec makes under it: their root is their parent.
CHILDREN = ("memes_overview", "memes_monitor", "memes_sync")


def root_of(plane: nu.StrArg) -> nu.Str:
    """The Memes root a plane belongs to: the one it recorded, its parent, or itself. Bare read.

    A plane the root made later (a token page, the job) records it in its
    own state (:mod:`nudemos.bases`), checked here; one its spec made under
    it (:data:`CHILDREN`) hangs right under it; the root itself has neither.

    Raises:
        Removed: The root a plane recorded is removed.
    """
    row = Space.planes[plane]
    under = nu.List.of(*CHILDREN).contains(row.spec.fallback(""))
    here = nu.str(nu.If(under, row.parent.fallback(""), plane))
    held = nuspace.at.plane(id=plane).state(bases.Belongs).base
    return nu.Str(nu.If(held.exists(), bases.recorded(plane), here))


def overview_of(root: nu.StrArg) -> nu.Str:
    """The root's Overview plane, where token pages hang; the root itself when it has none. Bare read.

    One page of the root's first children: the spec puts the Overview first.
    """
    first = nu.List(Space.planes[root].children.keys(limit=_FIRST))
    found = first.iter().filter(lambda p: Space.planes[nu.Str(p)].spec.fallback("") == OVERVIEW)
    return nu.str(found.first(default=root))


def job_of(root: nu.StrArg) -> nu.Str:
    """The sync job's plane id, ``""`` before the first start. Bare read."""
    return nu.Str(made_at(root).job.fallback(""))
