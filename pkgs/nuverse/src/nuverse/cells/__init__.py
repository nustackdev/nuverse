"""The Cells ``/`` inserts, one module each, by category.

- :mod:`.content`: views and editors over content items
  (:mod:`nuverse.contents`): text, inputs, items and the table.
- :mod:`.debugging`: lenses on the store and on content items.
- :mod:`.examples`: small programs showing what a cell can do.

A Cell is a view over content items: it reads and writes them by
address and exposes no data ops of its own. A Cell module is the cell's
real code, ``out()`` and the shapes it keeps its own state in, and its
``CELL``, registered with :func:`source` of the module as the cell's
prog: one import line, so a change to the code reaches every cell already
made from it.

Nothing here imports a Cell up front. A cell's prog imports only its own
Cell, and importing this package pulled in every other one with it, on
whichever thread loaded first. :data:`CELLS` imports them all on first
read instead.
"""

from __future__ import annotations

import importlib
from typing import Any


__all__ = ["CELLS", "source"]


#: The Cell modules, by category, in menu order.
_ORDER = (
    "content.text_editor",
    "content.table",
    "content.item",
    "content.items",
    "content.item_picker",
    "content.text_input",
    "content.number_input",
    "content.slider",
    "content.switch",
    "content.checkbox",
    "content.select",
    "content.date_picker",
    "debugging.lens",
    "debugging.plane_lens",
    "debugging.cell_lens",
    "debugging.space_content_lens",
    "debugging.plane_content_lens",
    "debugging.cell_content_lens",
    "examples.ticker",
    "examples.password",
    "examples.converter",
)


def source(module: str) -> str:
    """A cell's prog for the Cell in ``module``: one line, importing its ``out``."""
    return f"from {module} import out\n"


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """:data:`CELLS`, every Cell ready to register, built on first read."""
    if name != "CELLS":
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    modules = (importlib.import_module(f"{__name__}.{mod}") for mod in _ORDER)
    cells = tuple(module.CELL for module in modules)
    globals()["CELLS"] = cells
    return cells
