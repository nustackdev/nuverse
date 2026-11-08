"""Where a demo plane finds the base plane it belongs to: an id in its own plane state, checked when read.

A demo a space may hold more than once (movies, knowledge, design, memes)
keeps its store in its base plane's state. Each plane it makes under the
base records the base's id in its own plane state (:class:`Belongs`), in
the commit that keeps the new plane's id. The base itself records nothing:
a plane made from the demo's own spec is a base.

:func:`base_of` reads it and refuses what is not there, never falling back
to another plane: a plane with no record raises ``Missing``, a base removed
since raises ``Removed``.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
from nuspace import Space
from nuspace.errors import Missing, Removed
from nuspace.specs import PlaneSpec, registered_name
from nuspace.utils import Require


__all__ = ["Belongs", "base_of", "belongs", "recorded"]


class Belongs(nu.Shape):
    """A plane's, in its plane state: the base plane it was made under."""

    base = nustd.kv.StrRef.slot()


def belongs(plane: nu.StrArg, base: nu.StrArg) -> nu.Nu:
    """``plane`` recorded as one of ``base``'s. A bare State write: the caller brackets it."""
    return nuspace.at.plane(id=plane).state(Belongs).base.set(base)


def recorded(plane: nu.StrArg) -> nu.Str:
    """The base ``plane`` recorded (:func:`belongs`). A bare read, a few point reads.

    Raises:
        Missing: ``plane`` recorded none.
        Removed: The base it recorded is removed.
    """
    p = nu.Str(plane)
    held = nuspace.at.plane(id=p).state(Belongs).base
    known = nu.Str(
        Require(held.exists(), held, "plane " + p + " belongs to no base", exc_cls=Missing)
    )
    return nu.Str(
        Require(
            nuspace.plane.exists(known),
            known,
            "the base of plane " + p + " is removed",
            exc_cls=Removed,
        )
    )


def base_of(plane: nu.StrArg, spec: PlaneSpec) -> nu.Str:
    """The base ``plane`` belongs to: ``plane`` itself when made from ``spec``, else the one it recorded.

    A bare read over Space and State, a few point reads: the caller brackets it.

    Raises:
        Missing: ``plane`` is no base and recorded none.
        Removed: The base it recorded is removed.
    """
    p = nu.Str(plane)
    itself = Space.planes[p].spec.fallback("") == registered_name(spec)
    return nu.Str(nu.If(itself, p, recorded(p)))
