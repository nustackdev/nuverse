"""A lens: a shape in the store, browsed as cascading columns.

Its cell's prog names what to browse, ``SHAPE`` and ``PREFIX``, so a person
points it elsewhere by editing two lines.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nustd.ui.lens
from nuspace import Cell


if TYPE_CHECKING:
    import nu


__all__ = ["CELL", "out"]


def out(shape: type, prefix: nu.Ref | None = None) -> nu.Nu:
    """Browse ``shape`` at ``prefix``, for as long as the cell runs.

    Args:
        shape: A shape class: what the lens expects to find.
        prefix: A ref: where in the store that shape lives. None means the root.
    """
    lens = nustd.ui.lens.LensRef("lens")
    return nustd.ui.lens.browse(lens, shape, prefix=prefix)


_SOURCE = f'''\
"""A lens: browses a shape as cascading columns. Point SHAPE and PREFIX elsewhere to browse something else."""

import nuspace
from {__name__} import out as lens


# SHAPE is a shape class: what the lens expects to find.
# PREFIX is a ref: where in the store that shape lives. None means the root.
#
# One plane, for example:
#   SHAPE = nuspace.shapes.Plane
#   PREFIX = nuspace.Space.planes["home"]
SHAPE = nuspace.Space
PREFIX = None


out = lens(SHAPE, PREFIX)
'''


CELL = Cell(
    "lens",
    "Lens",
    _SOURCE,
    description="Browses the whole space, or any shape in it, as cascading columns.",
    group="Debugging",
    icon="scan-search",
)
