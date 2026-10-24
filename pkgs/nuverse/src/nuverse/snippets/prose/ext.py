"""The text snippet, registered: the shim as its source."""

from __future__ import annotations

from importlib import resources

from nuspace import Snippet

from .ops import set_text, text_of


__all__ = ["SNIPPET"]


SNIPPET = Snippet(
    "text",
    "Text",
    resources.files(__package__).joinpath("shim.py").read_text("utf-8"),
    description="Text a person reads and edits, markdown kept as the cell's text content.",
    ops=(set_text, text_of),
    group="Content",
    icon="type",
)
