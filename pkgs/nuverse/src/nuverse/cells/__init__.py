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

Nothing here imports a Cell. A cell's prog imports only its own Cell, and
importing this package pulled in every other one with it, on whichever
thread loaded first: two cells loading on two threads deadlocked.
:func:`nuverse.extension` gathers the specs.
"""

from __future__ import annotations


__all__ = ["source"]


def source(module: str) -> str:
    """A cell's prog for the Cell in ``module``: one line, importing its ``out``."""
    return f"from {module} import out\n"
