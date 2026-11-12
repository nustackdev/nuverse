"""The bar every Log plane opens with: the store's state in one line, and a link to Config.

Live or not, how many streams and series, from where, how often. The line
takes the room the row has; the Config link sits at its right end, on every
plane but Config itself.
"""

from __future__ import annotations

import nu
import nuspace
import nuspace.web as web
import nustd.ui as ui

from . import fmt, reads
from .state import child, following, root_of, with_store


__all__ = ["View", "out"]


class View(nu.Shape):
    """The ``bar`` cell's root."""

    bar = ui.RowRef.slot(gap=3, align="center", grow={2: 1})


dot = View.bar[0].to(ui.StatusDotRef.slot(tone="neutral"))
pill = View.bar[1].to(ui.StatusPillRef)
line = View.bar[2].to(ui.TextRef.slot(tone="muted", size="sm"))
to_config = View.bar[3].to(ui.LinkRef.slot(icon="cog"))


def draw(said: nu.Nu) -> nu.Nu:
    v = nu.Dict(said)
    return (
        dot.set(v["tone"], pulse=v["pulse"])
        >> pill.set(v["pill"], tone=v["tone"])
        >> line.set(v["line"])
    )


def off(seen: nu.Dict) -> nu.Nu:
    return draw(fmt.status(seen, 0, 0, 0.0))


def live(s: nu.Dict) -> nu.Nu:
    def read() -> nu.Nu:
        counts = nu.List(reads.streams()).len(), nu.List(reads.series()).len()
        return fmt.status(fmt.look(s["path"]), *counts, s["every"])

    return nu.ForeverDo(nu.let(read(), draw) >> nu.Delay(s["every"]))


def link(plane: nu.StrArg, root: nu.Str) -> nu.Nu:
    """The link to Config, from every plane but Config itself."""

    def to(p: nu.Nu) -> nu.Nu:
        there = nu.Str(p)
        go = nuspace.atomic(web.link(to_config, there, label="Config"))
        return nu.IfDo((there != "").and_(there != plane), go)

    return nu.let(nuspace.atomic(child(root, "nulog_config")), to)


def out(plane: nu.StrArg) -> nu.Nu:
    """The ``bar`` cell on ``plane``: the store's state, following the root's config."""

    def follow(root: nu.Str) -> nu.Nu:
        first = draw(fmt.status(fmt.look(""), 0, 0, 0.0))
        body = following(root, lambda s: with_store(s, lambda: live(s), off))
        return first >> link(plane, root) >> body

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))
