"""nuagent: the model answers in Nu, Nu runs the answer.

- :mod:`.core`: the loop, one turn after another until the model ends the run.
- :mod:`.protocol`: what the model is told about replying in Nu.
- :mod:`.prompt`: the opening prompt, the protocol plus nuskills, the catalogue and the world.
- :mod:`.presets`: what you swap: the store and the backend.
- :mod:`.planes`: a Chat plane for nuspace, found through the ``nuspace.extensions``
  entry point, which names :func:`extension` (``nuagent[space]``).

Nothing here imports nuspace: :func:`extension` imports it when nuspace asks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import Extension


__all__ = ["__version__", "extension"]

__version__ = "0.2.2"


def extension() -> Extension:
    """The Chat plane, as a nuspace extension."""
    from nuspace import Extension

    from .planes import PLANE

    return Extension(planes=(PLANE,))
