"""Number: a float any cell keeps, found within bounds.

What number input and slider cells keep, one item each.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nu.lang.sentinels import UNSET, Unset


__all__ = ["CONTENT", "Number", "NumberContent", "NumberHit", "NumberView", "Shown"]


def _shown(value: float) -> str:
    return f"{float(value):g}"


#: A number as a person writes it: ``42``, not ``42.0``.
Shown = nu.host(_shown, name="NumberShown")


class Number(nu.Shape):
    """A number item: the value."""

    value = nustd.kv.FloatRef.slot()


class NumberView(nustd.ui.Column):
    """A number drawn whole, as a stat."""

    stat = nustd.ui.StatRef.slot()


class NumberHit(nustd.ui.Row):
    """A number in search results."""

    text = nustd.ui.TextRef.slot()


class NumberContent(nuspace.Content[Number], name="Number"):
    """The number kind: matched within bounds, drawn as a person writes it."""

    @classmethod
    def match(
        cls,
        item: Number,
        *,
        min: nu.FloatArg | Unset = UNSET,
        max: nu.FloatArg | Unset = UNSET,
    ) -> nu.Bool:
        """Whether the item's value is within ``min`` and ``max``, both included.

        Either bound left out is no bound. Asked nothing, every item holding a
        value. A value never set is nothing to find.
        """
        checks: list[nu.Nu] = [item.value.exists()]
        if min is not UNSET:
            checks.append(nu.Float(item.value) >= min)
        if max is not UNSET:
            checks.append(nu.Float(item.value) <= max)
        return nu.Bool(nu.And(*checks))

    @classmethod
    def render(cls, item: Number) -> nu.Nu:
        """The value as a stat, ``0`` before one is set."""
        return NumberView.stat.set_value(Shown(item.value.fallback(0.0)))

    @classmethod
    def render_hit(cls, item: Number) -> nu.Nu:
        """The value on one line."""
        return NumberHit.text.set(Shown(item.value.fallback(0.0)))


#: The spec nuverse registers the kind with, as ``nuverse.Number``.
CONTENT = nuspace.ContentSpec(NumberContent, description="A number, found within bounds.")
