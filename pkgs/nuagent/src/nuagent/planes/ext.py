"""The Chat plane, registered: one cell, the composer, and the shim a message's cell runs.

Every cell's prog is a shim: the code lives in the package, and the prog only
names it, so a fix ships with the package and reaches every chat already made.
The engine's and the settings cell's progs are shims the same way
(:data:`.engine.SOURCE`, :data:`.settings.SOURCE`). A said cell's shim carries
one argument, its message's place in the inbox (:func:`said_prog`). The
cells the agent adds are its own source, not shims.
"""

from __future__ import annotations

import nu
from nuspace import Plane


__all__ = ["COMPOSER", "PLANE", "said_prog"]


def _shim(cell: str) -> str:
    """A cell's prog: :mod:`.chat`'s term of the same name, on the running page."""
    return f"from nuagent.planes import chat\n\n\ndef out(plane):\n    return chat.{cell}(plane)\n"


COMPOSER = _shim("composer")


def said_prog(at: nu.IntArg) -> nu.Str:
    """A said cell's prog: :func:`.chat.said` on the running page, for message ``at``."""
    head = "from nuagent.planes import chat\n\n\ndef out(plane):\n    return chat.said(plane, "
    return nu.Str(head) + nu.str(at) + ")\n"


PLANE = Plane(
    "nuagent_chat",
    "Chat",
    icon="messages-square",
    description="A conversation with an agent that answers in Nu and acts on the space.",
    meta={"editable": True, "full_width": False},
    cells=(("composer", COMPOSER),),
    group="Agents",
    backend="async",
)
