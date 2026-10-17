"""The ``text`` snippet: a text editor cell, its text kept in the cell's state.

Registered as ``nuverse.text``, the snippet nuspace's document editing works on:
typing into an empty line starts one, and its cells are the plane's text
cells.
"""

from __future__ import annotations

from .ext import SNIPPET
from .ops import search, set_text, text_of


__all__ = ["SNIPPET", "search", "set_text", "text_of"]
