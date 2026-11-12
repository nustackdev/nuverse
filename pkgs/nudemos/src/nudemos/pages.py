"""Plane links in demo tables: one helper every demo uses.

A demo's row helper names a plane by id, ``{"page": pid, "label": text}``, and
never spells a url. :func:`linked` turns that column into a link cell value at
draw time::

    from nudemos import pages

    table.set_rows(pages.linked(views.activity(desk), "what"))
    # column: {"key": "what", "cell": ui.PageLinkRef.slot(variant="inline")}

Call it once per link column. ``prop="label"`` suits a ``LinkRef`` cell.
Rows drawn in a term, titled off the store, take ``nuspace.web.page(pid)``
instead; this is for rows a host helper built, which carry their own label.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import nu
from nuspace import web


__all__ = ["linked"]


def _cell(value: object, prop: str) -> object:
    if not isinstance(value, Mapping):
        return value
    text = str(value.get("label") or "")
    page = value.get("page")
    return {"href": web.url(str(page)), prop: text} if page else {prop: text}


def _linked(rows: object, col: str, prop: str = "title") -> list:
    """``rows`` with each row's ``col`` turned into a link cell value.

    A row's ``col`` is ``{"page": pid, "label": text}``. It becomes
    ``{"href": web.url(pid), prop: text}``, ``prop`` ``"title"`` for a
    ``PageLinkRef`` cell, ``"label"`` for a ``LinkRef`` cell. A row with an
    empty page keeps ``{prop: text}`` and draws unlinked; a row whose ``col``
    is not a ``{page, label}`` record keeps it as it is.
    """
    held = rows if isinstance(rows, Sequence) and not isinstance(rows, str) else []
    return [
        {**row, col: _cell(row.get(col), prop)} if isinstance(row, Mapping) and col in row else row
        for row in held
    ]


#: ``linked(rows, col, prop="title")``: :func:`_linked` as a term, for a cell's table rows.
linked = nu.host(_linked, name="PageLinked")
