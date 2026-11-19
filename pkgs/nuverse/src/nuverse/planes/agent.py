"""The agent Plane: one coding agent's conversation, run by one engine cell.

Headless (``web=None``): nav never runs it, so two tabs on one chat never
mean two Agent processes, and closing a tab never ends a turn. A run is
added by :func:`nuverse.agents.ask` when the engine has no live owner, and
ends after the idle timeout. Made by :func:`nuverse.agents.add` only, so it
is not offered by ``+``.

The engine cell is a shim (:func:`~nuverse.planes.shim`): its code is
:func:`nuverse.agents.engine.engine`, imported on the worker only, so a
space without the ``agents`` extra still loads this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nuspace.specs import PlaneSpec
from nuverse.planes import shim


if TYPE_CHECKING:
    import nu


__all__ = ["ENGINE", "PLANE", "engine"]


def engine(plane: str) -> nu.Nu:
    """The engine cell: :func:`nuverse.agents.engine.engine` for ``plane``."""
    from nuverse.agents.engine import engine as run

    return run(plane)


ENGINE = shim("agent", "engine")


#: What an agent plane is made from. Named with the package in front, as it
#: records on the planes it makes.
PLANE = PlaneSpec(
    "nuverse.agent",
    "Agent",
    icon="bot",
    description="A coding agent's conversation, run headless over ACP.",
    cells=(("engine", ENGINE),),
    backend="async",
)
