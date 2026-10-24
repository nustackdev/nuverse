"""Flag: an on or off any cell keeps, found by which.

What switch and checkbox cells keep, one item each.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nu.lang.sentinels import UNSET, Unset


__all__ = ["Flag", "FlagContent", "FlagHit", "FlagView"]


class Flag(nu.Shape):
    """A flag item: whether it is on."""

    value = nustd.kv.BoolRef.slot()


class FlagView(nustd.ui.Row):
    """A flag drawn whole, as a badge."""

    badge = nustd.ui.BadgeRef.slot()


class FlagHit(nustd.ui.Row):
    """A flag in search results, as a badge."""

    badge = nustd.ui.BadgeRef.slot()


def _badge(item: Flag) -> tuple[nu.Nu, nu.Nu]:
    """The item's label and badge variant: ``on`` and ok, ``off`` and neutral."""
    on = item.value.fallback(False)
    return nu.If(on, "on", "off"), nu.If(on, "ok", "neutral")


class FlagContent(nuspace.Content[Flag]):
    """The flag kind: matched by on or off, drawn as a badge."""

    @classmethod
    def match(cls, item: Flag, *, on: nu.BoolArg | Unset = UNSET) -> nu.Bool:
        """Whether the item is ``on``, or off for ``on=False``.

        Asked nothing, every item holding a value. A value never set is
        nothing to find.
        """
        held = item.value.exists()
        if on is UNSET:
            return nu.Bool(held)
        return nu.Bool(nu.And(held, nu.Bool(item.value) == on))

    @classmethod
    def render(cls, item: Flag) -> nu.Nu:
        """``on`` or ``off``, as a badge. Off before one is set."""
        label, variant = _badge(item)
        return FlagView.badge.set(label, variant=variant)

    @classmethod
    def render_hit(cls, item: Flag) -> nu.Nu:
        """``on`` or ``off``, as a badge."""
        label, variant = _badge(item)
        return FlagHit.badge.set(label, variant=variant)
