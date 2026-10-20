"""What every design cell shares: the system's state, where it lives, and the writes over it.

- :class:`System`: the one store, in the Design plane's state. The spec
  (only what changed from the language), a ``rev`` every drawing follows,
  the history, the teammates' proposals, the releases.
- :func:`on_system`: a cell's body with :class:`System` landed at the
  Design plane, wherever in the tree the cell's page sits.
- :func:`edit`, :func:`undo`, :func:`reset`: the writes. Each is one change
  to the spec and one line in the history, and moves ``rev``, so every page
  drawing from the spec redraws.
- :func:`go`: send the shell to a page.

Cells import this module, so their own sources (:mod:`.cells`) stay short.
"""

from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.kv
import nustd.time
from nuspace import ops
from nuspace.shapes import Space
from nuspace.system.utils import redraws, snap

from . import checks, color
from . import spec as specs


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "System",
    "drawn",
    "edit",
    "go",
    "is_root",
    "on_system",
    "reset",
    "root_of",
    "spec",
    "undo",
]


#: The root Plane's registered names: under nudemos, and on its own.
ROOTS = ("nudemos.design", "design")


class System(nuspace.PlaneState):
    """The design system's store, on the Design plane."""

    # What changed from the language, key -> str. Read through :func:`spec`.
    spec = nustd.kv.PrimitiveDictRef.slot()
    # Moves on every write to the spec: the one thing drawings follow.
    rev = nustd.kv.IntRef.slot()
    # The history, oldest first: ``{at, who, what, changes: {key: [old, new]}}``.
    log = nustd.kv.PrimitiveListRef.slot()
    # Proposals waiting, the ones decided, the one open on Review, and a count that moves with them.
    inbox = nustd.kv.PrimitiveListRef.slot()
    decided = nustd.kv.PrimitiveListRef.slot()
    pick = nustd.kv.StrRef.slot()
    mail = nustd.kv.IntRef.slot()
    # The studio: the next proposal in its pool, seconds between arrivals, whether it is paused.
    cursor = nustd.kv.IntRef.slot()
    pace = nustd.kv.FloatRef.slot()
    paused = nustd.kv.BoolRef.slot()
    # Releases cut, oldest first: ``{version, page, at, files, bytes, spec}``.
    releases = nustd.kv.PrimitiveListRef.slot()
    # The theme drawings are made in: auto, dusk or dawn.
    preview = nustd.kv.StrRef.slot()
    seeded = nustd.kv.BoolRef.slot()


# --- where things are -----------------------------------------------------------------------


def _made_by(plane: nu.StrArg) -> nu.Str:
    return Space.planes[plane].props.made_by.fallback("")


def is_root(plane: nu.StrArg) -> nu.Bool:
    """Whether ``plane`` is a Design plane. Bare read."""
    by = _made_by(plane)
    return nu.Bool((by == ROOTS[0]).or_(by == ROOTS[1]))


def root_of(plane: nu.StrArg) -> nu.Str:
    """The Design plane a page belongs to: itself, its meta's ``base``, or the first Design plane above it. Bare read."""
    up = ops.parent(plane)
    up2 = ops.parent(up)
    walk = nu.If(
        is_root(plane), plane, nu.If(is_root(up), up, nu.If(is_root(up2), up2, ops.parent(up2)))
    )
    return nu.str(Space.planes[plane].meta["base"]).fallback(nu.Str(walk))


def on_system(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(base)`` with :class:`System` landed at the Design plane, bracketed step by step."""

    def landed(base: nu.ObjectRef) -> nu.Nu:
        b = nu.Str(base)
        return ops.bracketed(ops.plane_state(b, build(b)))

    return nu.let(snap(root_of(plane)), landed)


def go(nav: nu.Nu, uri: nu.StrArg) -> nu.Nu:
    """Send the shell to ``uri``. The shell follows back and forward only: push it, one past, step back."""
    return nu.let(uri, lambda u: nav.set(u) >> nav.set(nu.Str(u) + "?open") >> nav.back())


# --- reading -------------------------------------------------------------------------------------


merged = nu.host(specs.merged, name="Merged")


def spec() -> nu.Nu:
    """The spec in effect, as a plain dict. Bare: read inside :func:`on_system`."""
    return merged(System.spec.fallback({}))


def drawn(plane: str, view_ref: nu.Nu, doc: Callable[[nu.Nu], nu.Nu]) -> nu.Nu:
    """A frame drawing the spec: ``view_ref`` gets ``doc(view)``, again whenever the spec or the preview theme moves."""
    return on_system(
        plane, lambda base: redraws(follows(), seen(), lambda v: view_ref.set_html(doc(v)))
    )


def follows() -> list[nu.Nu]:
    """What a drawing of the spec follows: the spec and the preview theme."""
    return [System.rev.on_change(), System.preview.on_change()]


@nu.host
def view(stored: dict, mode: str) -> dict[str, Any]:
    """The spec in effect and the theme to draw it in, as one value to redraw from."""
    return {
        "spec": specs.merged(stored),
        "mode": mode or "auto",
        "changed": sorted(specs.changed(stored)),
    }


def seen() -> nu.Nu:
    """:func:`view` of the store now. Bare."""
    return view(System.spec.fallback({}), System.preview.fallback("auto"))


# --- writing -------------------------------------------------------------------------------------


#: Edits by the same hand to the same thing this close together are one line in the history.
MERGE_S = 6.0
#: Lines kept.
KEEP = 80


def _logged(log: list, stored: dict, changes: dict, who: str, what: str, now: float) -> list:
    cur = specs.merged(stored)
    diff = {
        k: [cur[k], str(v)]
        for k, v in dict(changes).items()
        if k in cur and cur[k] != str(v) and (not cur[k].startswith("#") or color.is_hex(str(v)))
    }
    log = list(log or [])
    if not diff:
        return log
    last = log[-1] if log else None
    if last and last["who"] == who and last["what"] == what and now - last["at"] < MERGE_S:
        merged_diff = dict(last["changes"])
        for k, (old, new) in diff.items():
            merged_diff[k] = [merged_diff[k][0] if k in merged_diff else old, new]
        log[-1] = {**last, "at": now, "changes": merged_diff}
    else:
        log.append({"at": now, "who": who, "what": what, "changes": diff})
    return log[-KEEP:]


def _applied(stored: dict, changes: dict) -> dict:
    out = {k: v for k, v in dict(stored or {}).items() if k in specs.DEFAULTS}
    for k, v in dict(changes).items():
        if k not in specs.DEFAULTS or (
            specs.DEFAULTS[k].startswith("#") and not color.is_hex(str(v))
        ):
            continue
        if str(v) == specs.DEFAULTS[k]:
            out.pop(k, None)
        else:
            out[k] = str(v)
    return out


logged = nu.host(_logged, name="Logged")
applied = nu.host(_applied, name="Applied")


def edit(changes: nu.Nu, who: nu.StrArg, what: nu.StrArg) -> nu.Nu:
    """Write ``changes`` (``{key: value}``) into the spec, with a line in the history. Bare: inside :func:`on_system`.

    ``changes`` is read once, so a value read off a slider is the one written.
    """

    def write(ch: nu.ObjectRef) -> nu.Nu:
        line = logged(
            System.log.fallback([]), System.spec.fallback({}), ch, who, what, nustd.time.time()
        )
        return (
            System.log.set(line)
            >> System.spec.set(applied(System.spec.fallback({}), ch))
            >> System.rev.set(System.rev.fallback(0) + 1)
        )

    return nu.let(changes, write)


@nu.host
def _undone(stored: dict, log: list) -> dict:
    if not log:
        return dict(stored or {})
    olds = {k: old for k, (old, _new) in log[-1]["changes"].items()}
    return _applied(stored, olds)


@nu.host
def _popped(log: list) -> list:
    return list(log or [])[:-1]


def undo() -> nu.Nu:
    """Take the last line of the history back. Bare: inside :func:`on_system`."""
    return (
        System.spec.set(_undone(System.spec.fallback({}), System.log.fallback([])))
        >> System.log.set(_popped(System.log.fallback([])))
        >> System.rev.set(System.rev.fallback(0) + 1)
    )


@nu.host
def _back(stored: dict) -> dict:
    return {k: specs.DEFAULTS[k] for k in specs.changed(stored)}


def reset(who: nu.StrArg = "you") -> nu.Nu:
    """Every token back to the language, as one line in the history. Bare."""
    return edit(_back(System.spec.fallback({})), who, "Back to the language")


# --- small shapes ----------------------------------------------------------------------------------


def ago(at: float, now: float | None = None) -> str:
    """``just now``, ``40s ago``, ``3 min ago``, ``2 h ago``."""
    s = max(0.0, (now or _time.time()) - at)
    if s < 10:
        return "just now"
    if s < 60:
        return f"{s:.0f}s ago"
    if s < 3600:
        return f"{s / 60:.0f} min ago"
    if s < 86400:
        return f"{s / 3600:.0f} h ago"
    days = round(s / 86400)
    return "yesterday" if days <= 1 else f"{days} days ago"


def describe_change(changes: dict) -> str:
    """``afterglow (dusk) #8946db to #9a4fe0, and 5 more``."""
    items = list(changes.items())
    if not items:
        return ""
    k, (old, new) = items[0]
    name = k.split(":", 1)[-1] + (f" ({k.split(':')[0]})" if ":" in k else "")
    more = f", and {len(items) - 1} more" if len(items) > 1 else ""
    return f"`{name}` {old} to {new}{more}"


@nu.host
def tally(stored: dict, inbox: list, releases: list) -> dict[str, str]:
    """The numbers the Design plane leads with."""
    sp = specs.merged(stored)
    s = checks.summary(sp)
    last = releases[-1]["version"] if releases else "none yet"
    return {
        "tokens": str(len(specs.COLORS) * 2 + len(specs.SCALARS)),
        "changed": str(len(specs.changed(stored))),
        "checks": f"{s['pass'] + s['under']} of {s['total']}",
        "failing": str(s["fail"]),
        "inbox": str(len(inbox or [])),
        "release": last,
    }
