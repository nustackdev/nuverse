"""The ``number`` snippet: a number input cell, its value an item of the cell."""

from __future__ import annotations

from .ext import SNIPPET
from .ops import set_value, value_of


__all__ = ["SNIPPET", "set_value", "value_of"]
