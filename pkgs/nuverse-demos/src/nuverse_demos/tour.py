"""The ``demos`` Plane: a short intro, and the three demos nested under it.

One plane for all of them at once. Its children are the same Planes ``+``
creates one by one, each on its own backend, with its own cells and state.
"""

from __future__ import annotations

from nuspace import Plane

from . import counter, movies, sampled


__all__ = ["INTRO", "PLANE"]


INTRO = '''\
import nu
import nustd.ui

TEXT = """\\
### Nu demos

Three small Nu programs, each a plane nested under this one.

- **Counter**: a count kept in its cell's state, ticking once a second.
- **Sampled**: a series that grows forever, charted from a reservoir sample.
- **Movies**: a shelf where every movie is its own cell, and a cell that writes cells.

Every cell is a Nu program. Open its code to read it, change it, and run it again with Cmd+Enter.
"""

out = nustd.ui.MarkdownRef("intro").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = Plane(
    "demos",
    "Nu demos",
    icon="compass",
    description="A counter, a sampled series and a movie shelf, nested under one plane.",
    meta={"editable": True, "full_width": False},
    cells=(("intro", INTRO),),
    children=(counter.PLANE, sampled.PLANE, movies.PLANE),
    group="Demos",
    backend="async",
)
