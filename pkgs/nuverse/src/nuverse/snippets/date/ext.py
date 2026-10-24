"""The date snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet

from .ops import set_value, value_of


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "date",
    "Date",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="A date kept as the cell's date content, picked from a calendar.",
    ops=(set_value, value_of),
    group="Inputs",
    icon="calendar",
)
