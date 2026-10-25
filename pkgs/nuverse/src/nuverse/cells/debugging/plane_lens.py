"""A plane lens: the lens (:mod:`.lens`) pointed at the plane its cell sits on."""

from __future__ import annotations

from nuspace import CellSpec


__all__ = ["CELL"]


_SOURCE = '''\
"""A lens on this plane. Point the shape and the prefix elsewhere to browse something else."""

import nuspace
from nuspace import ops
from nuverse.cells.debugging.lens import out as lens


# The shape: what the lens expects to find. The prefix: where in the store
# it lives. Here, this plane.
out = lens(nuspace.shapes.Plane, nuspace.Space.planes[ops.Here.plane])
'''


CELL = CellSpec(
    "plane_lens",
    "Plane lens",
    _SOURCE,
    description="Browses the plane the cell sits on as cascading columns.",
    group="Debugging",
    icon="layers",
)
