"""Every Log cell's stored prog: a shim that names package code.

The code lives in the package (:mod:`.bar`, :mod:`.overview`,
:mod:`.messages`, :mod:`.metrics`, :mod:`.config`) and a prog only names
it, so a fix ships with the package and reaches every Log plane already
made. This module imports none of them, so each can import its shims.

Each prog is ``def out(plane)``: the plane it runs on comes in, and
:func:`~.state.root_of` finds the Log root from there, where the config
lives.
"""

from __future__ import annotations


__all__ = ["ABOUT", "BAR", "CONFIG", "INTRO", "MESSAGES", "METRICS", "OVERVIEW", "shim"]


def shim(module: str, fn: str = "out") -> str:
    """A cell's prog: ``nulog.planes.<module>.<fn>(plane)`` on the running page."""
    return (
        f"from nulog.planes import {module}\n\n\ndef out(plane):\n    return {module}.{fn}(plane)\n"
    )


#: The store's state in one line, on every Log plane.
BAR = shim("bar")
#: The root's what this is, with a tile per child plane.
INTRO = shim("overview", "intro")
#: The root's streams and series at a glance.
OVERVIEW = shim("overview")
MESSAGES = shim("messages")
METRICS = shim("metrics")
CONFIG = shim("config")
#: How the viewer reads a store, under the Config form.
ABOUT = shim("config", "about")
