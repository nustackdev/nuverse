"""What every Log cell imports, and the bar every Log plane opens with.

Every cell is ``def out(plane)``: the plane it runs on comes in, and
:func:`~.state.root_of` finds the Log root from there, where the config
live. A cell that reads the store runs under :func:`~.state.following` and
:func:`~.state.with_store`: it starts over on a save, opens the store the
config names, and says why when it cannot.

- :data:`BAR`: the store's state in one line: live or not, how many streams
  and series, from where, how often; and a link to Config.
"""

from __future__ import annotations


__all__ = ["BAR", "IMPORTS", "cell"]


#: What every cell imports.
IMPORTS = """\
import nu
import nustd.time
import nustd.ui
from nuspace import ops
from nuspace.system.utils import drawing, redraw, snap
from nulog.planes.state import Config, at_root, child, following, root_of, saved, config, with_store
from nulog.planes import consts, fmt, reads
"""


def cell(body: str) -> str:
    """A cell's source: the shared imports, then ``body``."""
    return IMPORTS + "\n\n" + body


BAR = cell("""\
class Bar(nustd.ui.Row):
    dot = nustd.ui.StatusDotRef.slot(tone="neutral")
    pill = nustd.ui.StatusPillRef.slot()
    line = nustd.ui.TextRef.slot()
    config = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    bar = Bar.slot(gap=3, align="center")


B = View.bar


def draw(said):
    v = nu.Dict(said)
    return B.dot.set(v["tone"], pulse=v["pulse"]) >> B.pill.set(v["pill"], tone=v["tone"]) >> B.line.set(v["line"])


def off(seen):
    return draw(fmt.status(seen, 0, 0, 0.0))


def live(s):
    def read():
        counts = nu.List(reads.streams()).len(), nu.List(reads.series()).len()
        return fmt.status(fmt.look(s["path"]), *counts, s["every"])

    return drawing(nu.ForeverDo(redraw(read(), draw) >> nu.Delay(s["every"])))


def link(plane, root):
    # To Config, from every plane but Config itself.
    def to(p):
        go = B.config.set(href=nu.Str("/") + nu.Str(p), label="Config")
        return nu.IfDo((nu.Str(p) != "").and_(nu.Str(p) != plane), go)

    return nu.let(snap(child(root, "nulog_config")), to)


def out(plane):
    def follow(root):
        placed = draw(fmt.status(fmt.look(""), 0, 0, 0.0))
        return placed >> link(plane, root) >> following(root, lambda s: with_store(s, lambda: live(s), off))

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")
