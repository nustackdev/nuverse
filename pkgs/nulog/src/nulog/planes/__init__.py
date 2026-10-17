"""The Log planes: a nulog store read live in a space, as nuspace Planes.

One root and three children, all reading the store the root's config names
(:mod:`.state`)::

    Log           what this is, the store's streams and series at a glance
      Messages    one stream, read off either end, filtered
      Metrics     one series over a window, charted from a sample
      Config    which store, how often, how much

- :mod:`.state`: the config, how a plane finds its root, how a cell
  follows the config and opens the store it names.
- :mod:`.cells`, :mod:`.overview`, :mod:`.messages`, :mod:`.metrics`,
  :mod:`.config`: the planes, as cell sources.
- :mod:`.store`, :mod:`.reads`, :mod:`.fmt`, :mod:`.consts`: what the cells
  open, read and show: the store at the saved path, the bounded reads, the
  rows and tiles shaped from them, the knobs.

Needs nuspace: install ``nulog[space]``. ``import nulog`` never loads this.
"""

from __future__ import annotations

from nuspace import Plane

from . import config, messages, metrics, overview
from .cells import BAR
from .state import ROOT


__all__ = ["PLANE"]


#: The planes under the root, in order.
CHILDREN = (messages.PLANE, metrics.PLANE, config.PLANE)

PLANE = Plane(
    ROOT,
    "Log",
    icon="database",
    description="A nulog store read live: log streams, metric series, and its config.",
    meta={"editable": True, "full_width": True},
    cells=(("intro", overview.INTRO), ("bar", BAR), ("overview", overview.OVERVIEW)),
    children=CHILDREN,
    group="Observe",
    backend="async",
)
