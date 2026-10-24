"""Text: a string any cell keeps, found by the words in it.

What prose, text input and select cells keep, one item each.
"""

from __future__ import annotations

import re

import nu
import nuspace
import nustd.kv
import nustd.ui
from nu.lang.sentinels import UNSET, Unset


__all__ = ["HIT_WIDTH", "Text", "TextContent", "TextHit", "TextView", "WordAt", "matches"]


#: How many characters of the text a hit shows.
HIT_WIDTH = 80


def _word_at(value: object, query: object) -> int:
    q = str(query).strip().lower()
    if not q:
        return -1
    found = re.search(rf"(?<!\w){re.escape(q)}(?!\w)", str(value).lower())
    return found.start() if found else -1


#: Where ``query`` first stands in ``value`` as whole words, ignoring case; ``-1`` when nowhere.
#: Whole means no letter, digit or ``_`` right before or after it: ``stack`` is
#: not in ``Haystack``, ``basil`` is in ``basil's``. An empty query is nowhere.
WordAt = nu.host(_word_at, name="TextWordAt")


def matches(value: nu.StrArg, query: nu.StrArg) -> nu.Bool:
    """Whether ``query`` is in ``value`` as whole words, ignoring case (see :data:`WordAt`)."""
    return nu.Int(WordAt(value, query)) >= 0


class Text(nu.Shape):
    """A text item: the string, markdown or a plain line."""

    value = nustd.kv.StrRef.slot()


class TextView(nustd.ui.Column):
    """A text drawn whole, as markdown."""

    body = nustd.ui.MarkdownRef.slot()


class TextHit(nustd.ui.Row):
    """A text in search results: its start, on one line."""

    text = nustd.ui.TextRef.slot()


class TextContent(nuspace.Content[Text]):
    """The text kind: matched by whole words, drawn as markdown."""

    @classmethod
    def match(cls, item: Text, *, text: nu.StrArg | Unset = UNSET) -> nu.Bool:
        """Whether ``text`` stands in the item as whole words, ignoring case.

        Asked nothing, every item holding a text. A text never written is
        nothing to find.
        """
        held = item.value.exists()
        if text is UNSET:
            return nu.Bool(held)
        return nu.Bool(nu.And(held, matches(nu.str(item.value), text)))

    @classmethod
    def render(cls, item: Text) -> nu.Nu:
        """The text whole, as markdown."""
        return TextView.body.set(nu.str(item.value).fallback(""))

    @classmethod
    def render_hit(cls, item: Text) -> nu.Nu:
        """The text's first :data:`HIT_WIDTH` characters on one line, an ellipsis where cut."""
        body = nu.Str(nu.str(item.value).fallback("")).replace("\n", " ").strip()
        cut = body[:HIT_WIDTH] + nu.If(body.len() > HIT_WIDTH, "…", "")
        return TextHit.text.set(cut)
