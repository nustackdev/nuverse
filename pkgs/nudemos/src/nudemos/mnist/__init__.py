"""The ``mnist`` Plane: train a CNN on MNIST and track the runs, all inside nuspace.

Nu owns the loop, torch owns the step. A run is a headless job plane whose
one cell provides a :class:`~.trainer.Trainer` and loops in Nu over its
interactions (:mod:`.interactions`), logging into kh57 series in its own
state (:mod:`.state`), reading its learning rate from there each chunk, and
checkpointing into that state as it goes. The planes around it only read and
steer that state, and Read loads its models to read digits drawn on a pad.

- :mod:`.trainer`, :mod:`.reader`, :mod:`.interactions`: the torch side, and the Nu terms over it.
- :mod:`.ink`: strokes from a pad made into a 28x28 digit the way MNIST made its digits.
- :mod:`.job`: the training loop, the cell Launch writes per run.
- :mod:`.launch`, :mod:`.run`, :mod:`.compare`, :mod:`.read`: the planes, as cell sources.
- :mod:`.views`, :mod:`.state`: what the cells read and how they shape it.

Nothing heavy is imported here: torch loads in the job's process, on its
first step. It comes with the ``mnist`` extra: ``pip install "nudemos[mnist]"``.
"""

from __future__ import annotations

from nuspace.specs import PlaneSpec, WebOptions

from . import compare, launch, read


__all__ = ["INTRO", "PLANE"]


INTRO = '''\
import nu
import nuspace
import nuspace.web
import nustd.ui

TEXT = """\\
### MNIST, trained and tracked here

A small CNN learns to read handwritten digits, and every run is tracked live.

Nu owns the loop, torch owns the step: the job cell is a Nu loop over a trainer resource, the metrics land in kh57 series, and a chart samples them at the same cost however long the run. The models live in the space too, each run's latest checkpoint and its best. Close the space mid run and open it again: the run picks up from its last checkpoint.
"""

#: What the root's first three children hold, in the order the spec makes them.
WAYS = [
    "Pick the knobs and start a run; each gets a page that trains live",
    "Every run side by side: a table, overlaid curves, the best one",
    "Draw a digit and a run's model reads it, checkpoint by checkpoint",
]


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=4)


text = View.page["text"].to(nustd.ui.MarkdownRef)
ways = View.page["ways"].to(nustd.ui.GridRef.slot(max_columns=3, min_cell_width=200, gap=3))


def links(kids):
    def way(i, what):
        pid = nu.Str(nu.List(kids)[i])
        tile = ways[pid].to(nustd.ui.PageLinkRef.slot(variant="tile"))
        return nuspace.web.link(tile, pid, description=what)

    return nu.Sequential(*(way(i, what) for i, what in enumerate(WAYS)))


def out(plane):
    # Launch, Compare and Read, the first three planes under this one.
    first = nuspace.Space.planes[plane].children.keys(limit=3)
    return text.set(TEXT) >> nuspace.atomic(nu.let(first, links)) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = PlaneSpec(
    "mnist",
    "MNIST",
    icon="network",
    description="Train a CNN on MNIST, steer it live, track the runs, and read digits you draw.",
    web=WebOptions(editable=True, width="board"),
    cells=(("intro", INTRO), ("leader", compare.LEADER)),
    children=(launch.PLANE, compare.PLANE, read.PLANE),
    group="Demos",
    backend="async",
)
