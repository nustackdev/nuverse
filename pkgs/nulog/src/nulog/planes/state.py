"""The config each Log plane keeps, how its children find it, and how each follows it.

The config lives in the root Log plane's state (:class:`Config`), written
by the Config plane and read by every cell under the root. Each child
finds the root from its own id (:func:`root_of`): the root made from
:data:`nulog.planes.PLANE` is itself, a child's root is its parent.

The planes hang as the root makes them::

    Log           the root: the store's streams and series at a glance
      Messages    one stream, newest or oldest first, filtered
      Metrics     one series over a window, charted from a sample
      Config    which store, how often, how much

A cell that reads the store runs under :func:`following`: it reads the
config, opens the store it names, and starts over when a save moves
them, so a new path takes effect at once, with no restart.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nuspace
import nustd.kv
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import park, snap

from . import consts, fmt
from .store import Opened


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "MADE_BY",
    "RELOOK",
    "ROOT",
    "Config",
    "at_root",
    "child",
    "config",
    "following",
    "point",
    "root_of",
    "saved",
    "with_store",
]


#: The root Plane's name.
ROOT = "log"

#: What a root records as ``made_by``, the name the space registers it under.
MADE_BY = f"nulog.{ROOT}"

#: Seconds between looks at a path with no store behind it yet.
RELOOK = 2.0


class Config(nuspace.PlaneState):
    """What the Config plane saves, in the root's state. Unset slots read as the defaults.

    ``saved`` counts the saves: the cells follow it, so one save moves them
    once, whatever it changed.
    """

    path = nustd.kv.StrRef.slot()
    every = nustd.kv.FloatRef.slot()
    count = nustd.kv.IntRef.slot()
    window = nustd.kv.StrRef.slot()
    saved = nustd.kv.IntRef.slot()


def root_of(plane: nu.StrArg) -> nu.Str:
    """The Log root ``plane`` belongs to: itself, or its parent. Bare read."""
    made_by = Space.planes[plane].props.made_by.fallback("")
    return nu.Str(nu.If(made_by == MADE_BY, plane, ops.parent(plane)))


def at_root(root: nu.StrArg, term: nu.Nu) -> nu.Nu:
    """``term`` over :class:`Config`, landed on the root's state. Bare."""
    return ops.plane_state(root, term)


def config(root: nu.StrArg) -> nu.Dict:
    """Every setting, the defaults where nothing is saved: ``{path, every, count, window, saved}``. Bare."""
    s = Config
    return nu.Dict(
        at_root(
            root,
            nu.Dict.of(
                path=s.path.fallback(""),
                every=s.every.fallback(consts.DEFAULT_EVERY),
                count=s.count.fallback(consts.DEFAULT_COUNT),
                window=s.window.fallback(consts.DEFAULT_WINDOW),
                saved=s.saved.fallback(0),
            ),
        )
    )


def saved(root: nu.StrArg, **fields: nu.Nu | object) -> nu.Nu:
    """Save ``fields`` into the root's config and move ``saved``, in one commit."""
    writes = [getattr(Config, k).set(v) for k, v in fields.items()]
    moved = Config.saved.set(Config.saved.fallback(0) + 1)
    return ops.atomic_state(at_root(root, nu.Sequential(*writes, moved)))


def point(root: nu.StrArg, path: nu.StrArg) -> nu.Nu:
    """Point the root at the store at ``path``, as a save on its Config does."""
    return saved(root, path=path)


def following(root: nu.StrArg, body: Callable[[nu.Dict], nu.Nu]) -> nu.Nu:
    """``body(config)``, started over each time the config is saved. Never returns.

    The config is read into a frame and the body raced against a save:
    a save cancels the body (closing any store it opened) and the loop comes
    round with what was saved. A body that ends early waits for the save
    parked.
    """

    def turn(held: nu.ObjectRef) -> nu.Nu:
        now = nu.Dict(held)
        moves = snap(at_root(root, Config.saved.on_change()))
        moved = nu.WaitReactive(
            moves, nu.Int(snap(at_root(root, Config.saved.fallback(0)))) != now["saved"]
        )
        return nu.Race(body(now) >> park(), moved)

    return nu.ForeverDo(nu.let(snap(config(root)), turn))


def child(root: nu.StrArg, made_by: str) -> nu.Str:
    """The root's child plane made from the spec named ``made_by``, ``""`` when there is none. Bare read."""
    found = (
        ops.children(root)
        .iter()
        .filter(lambda p: Space.planes[nu.Str(p)].props.made_by.fallback("") == made_by)
    )
    return nu.Str(nu.str(nu.First(found)).fallback(""))


class _Said(nu.Shape):
    """What :func:`with_store` last told ``off``, so it tells it again only on a change."""

    look = nu.ObjectRef.slot()


def with_store(
    s: nu.Dict,
    body: Callable[[], nu.Nu],
    off: Callable[[nu.Dict], nu.Nu],
    *,
    again: float = RELOOK,
) -> nu.Nu:
    """``body()`` with the store the config ``s`` names open; ``off(look)`` while it cannot be. Never returns.

    ``off`` gets what :func:`~nulog.planes.fmt.look` says (no path, nothing
    there, not a store) or, when opening or reading the store fails, the
    same shape with the error as its ``note``. Either way the path is looked
    at again every ``again`` seconds, so a store made after the viewer
    opened shows up on its own. ``off`` runs only when what it says changed.
    """

    def tell(said: nu.Nu) -> nu.Nu:
        return nu.IfDo(_Said.look != said, off(nu.Dict(said)) >> _Said.look.set(said))

    def failed(err: nu.Nu, seen: nu.Dict) -> nu.Nu:
        title = "Reading the store failed"
        return tell(nu.Dict.of(state="failed", path=seen["path"], title=title, note=nu.Str(err)))

    def turn(held: nu.ObjectRef) -> nu.Nu:
        seen = nu.Dict(held)
        caught = nu.TryCatch(
            Opened(seen["path"], body()), catch=lambda err: failed(err, seen), errors=Exception
        )
        # Open: forget what off was told, so the next trouble is told even if it is the last one.
        return nu.IfDo(seen["state"] == "ok", _Said.look.set(None) >> caught, tell(seen))

    step = nu.let(fmt.look(s["path"]), turn) >> nu.Delay(again)
    return nu.Frame(_Said, nu.ForeverDo(step), look=None)
