"""nuverse-log: nulog as a nuspace extension.

- :mod:`.plane`: the ``log`` Plane ``+`` creates.

nuspace finds this package through the ``nuspace.extensions`` entry point,
which names :func:`extension`. Nothing is imported here at module scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import Extension


__all__ = ["extension"]


def extension() -> Extension:
    """The Log plane, as one extension."""
    from nuspace import Extension

    from .plane import PLANE

    return Extension(planes=(PLANE,))
