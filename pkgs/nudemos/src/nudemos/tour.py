"""The ``demos`` Plane: a short intro, and the demos nested under it.

One plane for all of them at once. Its children are the same Planes ``+``
creates one by one, each on its own backend, with its own cells and state.
"""

from __future__ import annotations

from nuspace import Plane

from . import counter, sampled


__all__ = ["INTRO", "PLANE"]


INTRO = '''\
import nu
import nustd.ui

TEXT = """\\
### Nu demos

Two small Nu programs, each a plane nested under this one.

- **Counter**: a count kept in its cell's state, ticking once a second.
- **Sampled**: a series that grows forever, charted from a reservoir sample.

Every cell is a Nu program. Open its code to read it, change it, and run it again with Cmd+Enter.
"""

out = nustd.ui.MarkdownRef("intro").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = Plane(
    "tour",
    "Nu demos",
    icon="compass",
    description="A counter and a sampled series, nested under one plane.",
    meta={"editable": True, "full_width": False},
    cells=(("intro", INTRO),),
    children=(counter.PLANE, sampled.PLANE),
    group="Demos",
    backend="async",
)
