"""The ``counter`` Plane: a count ticking once a second, kept, shown live.

Two cells. ``count`` keeps the count in its own state and ticks it once a
second, each tick one short commit, and its tile follows the count. Every
open tab runs the plane, so every tab runs the cell: the last tick's time,
kept beside the count, holds them to one tick a second between them.
``about`` says how it works.
"""

from __future__ import annotations

from nuspace import PlaneSpec


__all__ = ["ABOUT", "COUNT", "PLANE"]


COUNT = """\
import nu
import nustd.kv
import nustd.time
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws

#: Seconds between ticks.
EVERY = 1.0


class Counter(nuspace.CellState):
    value = nustd.kv.IntRef.slot()
    at = nustd.kv.FloatRef.slot()


tile = nustd.ui.StatRef("count")


def tick(now):
    # Due only when no tab ticked in the last second, so two tabs still count one.
    due = nu.Float(now) - Counter.at.fallback(0.0) >= EVERY * 0.9
    step = Counter.value.set(Counter.value.fallback(0) + 1) >> Counter.at.set(nu.Float(now))
    return nu.IfDo(due, step)


def show(n):
    return tile.set_value(nu.str(n))


ticks = nu.ForeverDo(nu.DelayedDo(EVERY, ops.atomic_state(nu.let(nustd.time.time(), tick))))
shows = redraws([Counter.value.on_change()], Counter.value.fallback(0), show)
out = tile.set_label("Count") >> nu.ParallelAsync(ticks, shows)
"""


ABOUT = '''\
import nu
import nustd.ui

TEXT = """\\
### How it works

- The count lives in the Count cell's own state. Close the plane, restart the space: it carries on.
- The cell ticks once a second, each tick one short commit to the state store.
- Every open tab runs the plane. The last tick's time, kept beside the count, holds them to one tick a second.
- The tile follows the count through `on_change`, so every tab shows the same number.
- One Ref system for the state and the tile, one set of Interactions wiring them.
- Open the Count cell's code to change it: Cmd+Enter runs the new version on the same count.
"""

out = nustd.ui.MarkdownRef("about").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = PlaneSpec(
    "counter",
    "Counter",
    icon="hash",
    description="A count ticking once a second, kept in its cell's state.",
    meta={"editable": True, "full_width": False},
    cells=(("count", COUNT), ("about", ABOUT)),
    group="Demos",
    backend="async",
)
