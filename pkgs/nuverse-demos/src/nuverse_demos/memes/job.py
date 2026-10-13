"""The sync job: a Nu loop that follows the chain, and the terms it is made of.

Nu owns the loop and the calls, the :class:`~.book.Book` owns the decisions.
:data:`SYNC` is the job's one cell: it provides a Book and the JSON-RPC
transport, loads what the last run left, then turns until the Sync plane's
``stop`` is set. A turn asks the book for a plan, makes the calls the plan
names (``getSlot``, a few ``getBlock``, ``getMultipleAccounts``) at once
through ``nustd.http``, hands each reply back, and commits what changed in one short
write to the root's state. Every commit moves ``Memes.beat``, which is what
the planes reading it follow.

A call that raises (a refused connection, a 429, a timeout) is the book's
to log and back off from: the loop keeps turning. A crash ends the run, and
the supervisor brings it back; the book picks up from the cursor it saved.

Beside that loop, three fetchers read coins' off-chain metadata (the url a
launch names) for their pictures: the image's url lands in the token's
record, and the browser loads the image itself.

- :class:`Rpc`: JSON-RPC as a ``nustd.http`` Service, the endpoint read per call.
- :class:`Plan`, :class:`Reply`, :class:`Failed`, :class:`Flush`,
  :class:`Load`, :class:`Stopped`: the book's methods as Nu terms.
- :func:`saved`, :func:`written`: what a run reads at start and writes per turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import nu
import nustd.http
from nu.engine.structure import Declared
from nu.lang import ScalarAction

from .book import Book
from .state import Control, Memes


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = [
    "SYNC",
    "Failed",
    "Flush",
    "Load",
    "Offchain",
    "Picture",
    "Pictured",
    "Plan",
    "Reply",
    "Rpc",
    "Stopped",
    "Unpictured",
    "saved",
    "written",
]


class Rpc(nu.Service):
    """Solana JSON-RPC: one POST per call, to whichever endpoint the call names.

    The endpoint is a path placeholder rather than the binding's base url,
    so the Sync plane can change it between two calls.
    """

    call = nustd.http.POSTRef.method("{url}", jsonrpc="2.0", id=1)


class Offchain(nu.Service):
    """A coin's off-chain metadata: JSON at whatever url its launch names, read through the gateway."""

    read = nustd.http.GETRef.method("{url}")


class _Call(ScalarAction):
    """Calls :attr:`method` on the provided :class:`Book` with the other children's values.

    The book is child 0, read through a ``FabricRef``: it is what the call
    changes, so it sits in the mutation slot.
    """

    method: ClassVar[str] = ""
    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, *args: object) -> None:
        super().__init__(nu.FabricRef(Book), *args)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self.method

        def thunk(rt: Runtime) -> object:
            book, *args = (c(rt) for c in children)
            return getattr(book, method)(*args)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self.method

        async def athunk(rt: Runtime) -> object:
            book, *args = [await c(rt) for c in children]
            return getattr(book, method)(*args)

        return athunk


class Plan(_Call):
    """What to do next, given the Sync plane's knobs: see :meth:`.Book.plan`."""

    method = "plan"

    def __init__(self, control: nu.Nu) -> None:
        super().__init__(control)


class Reply(_Call):
    """A call's JSON-RPC response, handed to the book."""

    method = "on_reply"

    def __init__(self, plan: nu.Nu, reply: nu.Nu) -> None:
        super().__init__(plan, reply)


class Failed(_Call):
    """A call that raised, the caught error handed to the book."""

    method = "on_error"

    def __init__(self, plan: nu.Nu, message: nu.Nu) -> None:
        super().__init__(plan, message)


class Flush(_Call):
    """What changed since the last flush: see :meth:`.Book.flush`."""

    method = "flush"


class Load(_Call):
    """What the last run left, read back into the book."""

    method = "load"

    def __init__(self, saved: nu.Nu) -> None:
        super().__init__(saved)


class Picture(_Call):
    """The next coin whose metadata to fetch for its picture, ``{mint, url}``, or ``{}``."""

    method = "picture"


class Pictured(_Call):
    """A coin's metadata, handed to the book."""

    method = "on_picture"

    def __init__(self, ask: nu.Nu, meta: nu.Nu) -> None:
        super().__init__(ask, meta)


class Unpictured(_Call):
    """A metadata fetch that failed, handed to the book."""

    method = "on_no_picture"

    def __init__(self, ask: nu.Nu, error: nu.Nu) -> None:
        super().__init__(ask, error)


class Stopped(_Call):
    """The stop asked for, noted for the last flush."""

    method = "on_stop"


def saved() -> nu.Nu:
    """Everything :meth:`.Book.load` reads, as one dict, over :class:`Memes`. Bare."""
    m = Memes
    return nu.Dict.of(
        tokens=nu.Dict(m.tokens.extract()).fallback({}),
        trades=nu.Dict(m.trades.extract()).fallback({}),
        candles=nu.Dict(m.candles.extract()).fallback({}),
        tape=m.tape.fallback([]),
        pulse=m.pulse.fallback([]),
        launches=m.launches.fallback([]),
        errors=m.errors.fallback([]),
        quotes=m.quotes.fallback({}),
        stats=m.stats.fallback({}),
        sync=m.sync.fallback({}),
    )


def control() -> nu.Nu:
    """The Sync plane's knobs, as one dict, over :class:`Control`. Bare."""
    c = Control
    return nu.Dict.of(
        rpc=c.rpc.fallback(""),
        rate=c.rate.fallback(2.0),
        epoch=c.epoch.fallback(0),
        start=c.start.fallback(0),
    )


def written(d: nu.Nu) -> nu.Nu:
    """The writes of one :meth:`.Book.flush`, over :class:`Memes`. Bare: the job brackets it.

    Each key of the flush is a list, so each is one loop, empty when nothing changed.
    """
    m, f = Memes, nu.Dict(d)

    def each(key: str, write: Callable[[nu.List], nu.Nu]) -> nu.Nu:
        return nu.ForEachDo(nu.List(f[key]), lambda v: write(nu.List(v)))

    def one(key: str, ref: nu.Nu) -> nu.Nu:
        return nu.ForEachDo(nu.List(f[key]), lambda v: ref.set(v))

    def gone(mint: nu.Nu) -> nu.Nu:
        return nu.Sequential(
            *(
                nu.IfDo(ref.contains(mint), ref.del_item(mint))
                for ref in (m.tokens, m.trades, m.candles)
            )
        )

    def point(p: nu.Nu) -> nu.Nu:
        p, t = nu.Dict(p), nu.Int(nu.Dict(p)["t"])
        series = {
            "blocks": m.blocks_s,
            "trades": m.trades_s,
            "launches": m.launches_m,
            "volume": m.volume_m,
            "lag": m.lag,
            "latency": m.latency,
            "errors": m.errors_n,
            "coverage": m.coverage,
        }
        return nu.Sequential(*(ref.set_item(t, nu.Float(p[k])) for k, ref in series.items()))

    return (
        each("tokens", lambda kv: m.tokens[nu.Str(kv[0])].set(kv[1]))
        >> each("trades", lambda kv: m.trades[nu.Str(kv[0])].set(kv[1]))
        >> each("candles", lambda kv: m.candles[nu.Str(kv[0])].set(kv[1]))
        >> nu.ForEachDo(nu.List(f["gone"]), lambda mint: gone(nu.Str(mint)))
        >> one("board", m.board)
        >> one("tape", m.tape)
        >> one("pulse", m.pulse)
        >> one("launches", m.launches)
        >> one("errors", m.errors)
        >> one("quotes", m.quotes)
        >> one("stats", m.stats)
        >> one("sync", m.sync)
        >> nu.ForEachDo(nu.List(f["point"]), point)
        >> m.beat.set(m.beat.fallback(0) + 1)
    )


SYNC = """\
import nu
import nustd.http
from nuspace import ops
from nuspace.system.utils import snap
from nuverse_demos.memes.book import Book
from nuverse_demos.memes.job import (
    Failed, Flush, Load, Offchain, Picture, Pictured, Plan, Reply, Rpc, Stopped, Unpictured, control, saved, written,
)
from nuverse_demos.memes.state import Control, at_root, root_of

#: Seconds one call may take, one metadata fetch, and what the book is told about the chain and its memory.
TIMEOUT, OFFCHAIN = 10.0, 8.0
BOOK = {"keep_hours": 6.0, "max_tokens": 4000, "max_lag": 40}


def commit(root):
    # One short write per turn, only when something moved.
    return nu.let(Flush(), lambda d: nu.IfDo(nu.Bool(d["moved"]), ops.atomic_state(at_root(root, written(d)))))


def call(p):
    rpc = Rpc.call(url=p["url"], method=p["method"], params=p["params"])
    return nu.TryCatch(nu.let(rpc, lambda r: Reply(p, r)), catch=lambda err: Failed(p, err))


def turn(root):
    def act(p):
        # The calls of one turn go out together: a few blocks, the tip, some names.
        calls = nu.ForEachParAsync(nu.List(p["calls"]), call)
        return nu.IfDo(nu.Str(p["do"]) == "wait", nu.Delay(nu.Float(p["wait"])), calls)

    return nu.let(Plan(snap(at_root(root, control()))), act) >> commit(root)


def pictures():
    # Beside the chain, a few fetchers read coins' metadata for their pictures, one coin each at a time.
    def fetch(ask):
        meta = Offchain.read(url=ask["url"])
        got = nu.TryCatch(nu.let(meta, lambda m: Pictured(ask, m)), catch=lambda err: Unpictured(ask, err))
        return nu.IfDo(nu.Dict(ask).contains("url"), got, nu.Delay(1.0))

    fetcher = nu.ForeverDo(nu.let(Picture(), fetch))
    return nu.ForEachParAsync(nu.List.of(1, 2, 3), lambda _: fetcher)


def out(plane):
    def run(root):
        going = snap(at_root(root, Control.stop.fallback(False)).not_())
        chain = nu.WhileDo(going, turn(root))
        # The chain's loop ends the run: the fetchers go with it.
        loop = Load(snap(at_root(root, saved()))) >> nu.Race(chain, pictures()) >> Stopped() >> commit(root)
        transport = (nustd.http.bind(Rpc, timeout=TIMEOUT), nustd.http.bind(Offchain, timeout=OFFCHAIN))
        return nu.With(*transport, nu.Provide(Book, BOOK), body=loop)

    return nu.let(snap(root_of(plane)), lambda root: run(nu.Str(root)))
"""
