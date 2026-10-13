"""nuverse-demos: the Nu demos as nuspace Planes.

- :mod:`.counter`: a count ticking once a second, in its cell's state.
- :mod:`.sampled`: a kh57 series growing forever, charted from a sample.
- :mod:`.tour`: the two above, nested under one plane.
- :mod:`.movies`: a film base, every film and person its own live page.
- :mod:`.mnist`: a CNN trained on MNIST, steered live, every run tracked. Needs the ``mnist`` extra.
- :mod:`.memes`: a live terminal over a meme market, synced from Solana.

nuspace finds this package through the ``nuspace.extensions`` entry point,
which names :func:`extension`. Nothing is imported here at module scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import Extension


__all__ = ["extension"]


def extension() -> Extension:
    """The tour and the demo planes, as one extension."""
    from nuspace import Extension

    from . import counter, memes, mnist, movies, sampled, tour

    return Extension(planes=(tour.PLANE, counter.PLANE, sampled.PLANE, movies.PLANE, mnist.PLANE, memes.PLANE))
