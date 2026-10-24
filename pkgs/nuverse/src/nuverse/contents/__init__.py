"""The content kinds nuverse ships: the primitives any cell keeps its findable data in.

One module each, a schema Shape and its :class:`nuspace.Content`:

- :mod:`.text`: :class:`~.text.TextContent`, a string, found by its words.
- :mod:`.number`: :class:`~.number.NumberContent`, a float, found within bounds.
- :mod:`.flag`: :class:`~.flag.FlagContent`, an on or off.
- :mod:`.date`: :class:`~.date.DateContent`, a day, found within bounds.
- :mod:`.row`: :class:`~.row.RowContent`, a table row, found by the words in its cells.

A kind's name is its importable name, eg ``nuverse.contents.text.TextContent``.

Nothing here imports a kind up front, as with the Cells: a cell's prog
imports only the kinds its Cell keeps. :data:`CONTENTS` and the names
below import on first read.
"""

from __future__ import annotations

import importlib
from typing import Any


__all__ = [
    "CONTENTS",
    "Date",
    "DateContent",
    "Flag",
    "FlagContent",
    "Number",
    "NumberContent",
    "Row",
    "RowContent",
    "Text",
    "TextContent",
]


#: Each name re-exported here, to the module it lives in. The kinds in registration order.
_NAMES = {
    "Text": "text",
    "TextContent": "text",
    "Number": "number",
    "NumberContent": "number",
    "Flag": "flag",
    "FlagContent": "flag",
    "Date": "date",
    "DateContent": "date",
    "Row": "row",
    "RowContent": "row",
}


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """:data:`CONTENTS`, every kind to register, or one name of a kind module, on first read."""
    if name == "CONTENTS":
        found: Any = tuple(__getattr__(n) for n in _NAMES if n.endswith("Content"))
    elif name in _NAMES:
        found = getattr(importlib.import_module(f"{__name__}.{_NAMES[name]}"), name)
    else:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    globals()[name] = found
    return found
