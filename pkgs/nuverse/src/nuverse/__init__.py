"""nuverse: the extensions a space offers out of the box.

- :mod:`.planes`: what ``+`` creates beside nuspace's empty plane: ``quickstart``,
  ``jobs``, ``runs``, ``workers``, ``planes``.
- :mod:`.cells`: what ``/`` inserts, one module each, by category:
  views and editors over content items, lenses, examples.
- :mod:`.contents`: the content kinds the Cells keep their findable data
  in, Text, Number, Flag, Date and Row.

nuspace finds this package through the ``nuspace.extensions`` entry point,
which names :func:`extension`. Nothing is imported here at module scope:
workers import cell programs, and a program never needs the registry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import Extension


__all__ = ["extension"]


def extension() -> Extension:
    """Every nuverse Plane, Cell and content kind, as one extension.

    Each spec lives beside its code, ``PLANE``, ``CELL`` or ``CONTENT`` in
    its module, gathered here in order: Planes as the picker lists them,
    Cells as the ``/`` menu does, kinds as the search form does.
    """
    from nuspace import Extension

    from .cells.content import (
        checkbox,
        date_picker,
        item,
        item_picker,
        items,
        number_input,
        select,
        slider,
        switch,
        table,
        text_editor,
        text_input,
    )
    from .cells.debugging import (
        cell_content_lens,
        cell_lens,
        lens,
        plane_content_lens,
        plane_lens,
        space_content_lens,
    )
    from .cells.examples import converter, password, ticker
    from .contents import date, flag, number, row, text
    from .planes import jobs, planes, quickstart, runs, workers

    cells = (
        text_editor,
        table,
        item,
        items,
        item_picker,
        text_input,
        number_input,
        slider,
        switch,
        checkbox,
        select,
        date_picker,
        lens,
        plane_lens,
        cell_lens,
        space_content_lens,
        plane_content_lens,
        cell_content_lens,
        ticker,
        password,
        converter,
    )
    return Extension(
        planes=tuple(m.PLANE for m in (quickstart, jobs, runs, workers, planes)),
        cells=tuple(m.CELL for m in cells),
        contents=tuple(m.CONTENT for m in (text, number, flag, date, row)),
        envs={},
    )
