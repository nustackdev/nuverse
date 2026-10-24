"""nuverse: the extensions a space offers out of the box.

- :mod:`.planes`: what ``+`` creates beside nuspace's empty plane: ``jobs``,
  ``runs``, ``workers``, ``planes``.
- :mod:`.snippets`: what ``/`` inserts, one module each, by category:
  views and editors over content items, lenses, examples.
- :mod:`.contents`: the content kinds the snippets keep their findable data
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
    """Every nuverse Plane, snippet and content kind, as one extension."""
    from nuspace import Extension

    from .contents import CONTENTS
    from .planes import PLANES
    from .snippets import SNIPPETS

    return Extension(planes=PLANES, snippets=SNIPPETS, contents=CONTENTS, envs={})
