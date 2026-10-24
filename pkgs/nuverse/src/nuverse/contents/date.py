"""Date: a day any cell keeps, found within bounds.

What date picker cells keep, one item each.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.datetime.kv
import nustd.ui
from nu.lang.sentinels import UNSET, Unset


__all__ = ["Date", "DateContent", "DateHit", "DateView", "iso"]


class Date(nu.Shape):
    """A date item: the day, stored ISO ``YYYY-MM-DD``."""

    value = nustd.datetime.kv.DateRef.slot()


class DateView(nustd.ui.Column):
    """A date drawn whole."""

    text = nustd.ui.TextRef.slot()


class DateHit(nustd.ui.Row):
    """A date in search results."""

    text = nustd.ui.TextRef.slot()


def iso(item: Date) -> nu.Str:
    """The item's date as ISO ``YYYY-MM-DD``, ``""`` before one is set."""
    return nu.Str(nu.If(item.value.exists(), nu.ToStr(item.value), ""))


class DateContent(nuspace.Content[Date]):
    """The date kind: matched within bounds, drawn ISO."""

    @classmethod
    def match(
        cls,
        item: Date,
        *,
        min: nu.StrArg | Unset = UNSET,
        max: nu.StrArg | Unset = UNSET,
    ) -> nu.Bool:
        """Whether the item's date is within ``min`` and ``max``, ISO dates, both included.

        ISO dates sort as they fall, so the bounds compare as strings. Either
        left out is no bound. Asked nothing, every item holding a date. A
        date never set is nothing to find.
        """
        checks: list[nu.Nu] = [item.value.exists()]
        if min is not UNSET:
            checks.append(iso(item) >= nu.Str(min).strip())
        if max is not UNSET:
            checks.append(iso(item) <= nu.Str(max).strip())
        return nu.Bool(nu.And(*checks))

    @classmethod
    def render(cls, item: Date) -> nu.Nu:
        """The date, ISO."""
        return DateView.text.set(iso(item))

    @classmethod
    def render_hit(cls, item: Date) -> nu.Nu:
        """The date, ISO, on one line."""
        return DateHit.text.set(iso(item))
