"""The ``mnist`` Plane: train a CNN on MNIST and track the runs, all inside nuspace.

Nu owns the loop, torch owns the step. A run is a headless job plane whose
one cell provides a :class:`~.trainer.Trainer` and loops in Nu over its
interactions (:mod:`.interactions`), logging into kh57 series in its own
state (:mod:`.state`), reading its learning rate from there each chunk, and
checkpointing as it goes. The planes around it only read and steer that
state.

- :mod:`.trainer`, :mod:`.interactions`: the torch side, and the Nu terms over it.
- :mod:`.job`: the training loop, the cell Launch writes per run.
- :mod:`.launch`, :mod:`.run`, :mod:`.compare`: the planes, as cell sources.
- :mod:`.views`, :mod:`.state`: what the cells read and how they shape it.

Nothing heavy is imported here: torch loads in the job's process, on its
first step. It comes with the ``mnist`` extra: ``pip install "nuverse-demos[mnist]"``.
"""

from __future__ import annotations

from nuspace import Plane

from . import compare, launch


__all__ = ["INTRO", "PLANE"]


INTRO = '''\
import nu
import nustd.ui
from nuspace import ops
from nuspace.system.utils import snap

TEXT = """\\
### MNIST, trained and tracked here

A small CNN learns to read handwritten digits, and every run is tracked live.

- **Launch** starts a run: pick the knobs, press Launch. Each run gets a page, and a headless job under it that trains in its own process.
- A **run page** shows the curves, the weights and gradients of every layer over training, and twelve test digits flipping from wrong to right. Drag the learning rate while it trains, stop it, resume it.
- **Compare** lines the runs up: a table, overlaid curves, the best one in a sentence.

Nu owns the loop, torch owns the step: the job cell is a Nu loop over a trainer resource, the metrics land in kh57 series, and a chart samples them at the same cost however long the run. Close the space mid run and open it again: the run picks up from its last checkpoint.
"""

class Links(nustd.ui.Row):
    launch = nustd.ui.LinkRef.slot()
    compare = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    text = nustd.ui.MarkdownRef.slot()
    links = Links.slot(gap=4)


def links(kids):
    # Launch and Compare, the first two planes under this one.
    def to(i):
        return nu.Str("/") + nu.Str(nu.List(kids)[i])

    return View.links.launch.set(href=to(0), label="Launch a run") >> View.links.compare.set(href=to(1), label="Compare runs")


def out(plane):
    return View.text.set(TEXT) >> nu.let(snap(ops.children(plane)), links) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = Plane(
    "mnist",
    "MNIST",
    icon="network",
    description="Train a CNN on MNIST, steer it live, and track the runs.",
    meta={"editable": True, "full_width": True},
    cells=(("intro", INTRO), ("leader", compare.LEADER)),
    children=(launch.PLANE, compare.PLANE),
    group="Demos",
    backend="async",
)
