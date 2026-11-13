"""The Config plane: which store its Log plane reads, and how.

- ``bar``: the store's state, as on every Log plane.
- ``config`` (:func:`out`): what is at the saved path, then a form: the
  store's path, how often to read it, how many messages a read takes, the
  metrics window a tab starts on. Saved into the root's state on Save,
  never in code. Every Log cell follows the save: a new path opens at once,
  with no restart.
- ``about`` (:func:`about`): how the viewer reads the store, and what it costs.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.ui as ui
from nuspace.specs import PlaneSpec, WebOptions

from . import consts, fmt
from .cells import ABOUT, BAR, CONFIG
from .state import config, root_of, saved


__all__ = ["PLANE", "About", "View", "about", "out"]


HINT = "A save applies to this Log plane at once, with no restart."


# ---- the view ---------------------------------------------------------------
#
#   [ what is at the path                                  ]
#   [ Store                                                ]
#   [ path.............................................    ]
#   [ every ][ count ][ window ]       one per line when narrow
#   [ Save  hint                                           ]


class View(nu.Shape):
    """The ``config`` cell's root."""

    config = ui.ColumnRef.slot(gap=4)


check = View.config[0].to(ui.AlertRef)
form = View.config[1].to(
    ui.CardRef.slot(
        title="Store",
        subtitle="Saved into this Log plane; every cell under it follows a save",
        max_width="prose",
    )
)
path = (
    form[0]
    .to(ui.FieldRef.slot(label="nulog store", help="The directory nulog.store(path) writes"))
    .control.to(ui.InputRef.slot(placeholder="/path/to/logs.db", mono=True))
)
knobs = form[1].to(ui.GridRef.slot(cols=3, gap=4, stack_below=560))
every = (
    knobs[0, 0]
    .to(ui.FieldRef.slot(label="Read every, in seconds"))
    .control.to(ui.NumberInputRef.slot(min=consts.MIN_EVERY, max=consts.MAX_EVERY, step=0.5))
)
count = (
    knobs[0, 1]
    .to(ui.FieldRef.slot(label="Messages a read takes"))
    .control.to(ui.NumberInputRef.slot(min=consts.MIN_COUNT, max=consts.MAX_COUNT, step=50))
)
window = (
    knobs[0, 2]
    .to(ui.FieldRef.slot(label="Metrics window to start on"))
    .control.to(ui.SelectRef.slot(options=list(consts.WINDOW_OPTIONS), value=consts.DEFAULT_WINDOW))
)
save_button = form.footer[0].to(ui.ButtonRef.slot(label="Save", icon="save"))
hint = form.footer[1].to(ui.TextRef.slot(tone="muted", size="sm"))


# ---- the program ------------------------------------------------------------


def checked(at: nu.StrArg) -> nu.Nu:
    def said(v: nu.Nu) -> nu.Nu:
        seen = nu.Dict(v)
        tone = nu.If(seen["state"] == "ok", "ok", nu.If(seen["state"] == "unset", "info", "danger"))
        return check.set(seen["title"], body=seen["note"], variant=tone)

    return nu.let(fmt.look(at), said)


def show(root: nu.Str) -> nu.Nu:
    """The saved config, in every control, and what is at its path."""

    def put(v: nu.Nu) -> nu.Nu:
        s = nu.Dict(v)
        return (
            path.set(s["path"])
            >> every.set(s["every"])
            >> count.set(s["count"])
            >> window.set(s["window"])
            >> checked(s["path"])
        )

    return nu.let(nuspace.atomic(config(root)), put)


def save(root: nu.Str) -> nu.Nu:
    # What the form says now, read from the browser once per click.
    held_every = fmt.bounded(every, consts.DEFAULT_EVERY, consts.MIN_EVERY, consts.MAX_EVERY)
    held_count = nu.int(
        fmt.bounded(count, consts.DEFAULT_COUNT, consts.MIN_COUNT, consts.MAX_COUNT)
    )
    kept = saved(
        root, path=nu.Str(path).strip(), every=held_every, count=held_count, window=nu.Str(window)
    )
    return kept >> show(root) >> hint.set("Saved: this Log plane reads with these now.")


def out(plane: nu.StrArg) -> nu.Nu:
    """The ``config`` cell on ``plane``: the saved config in the form, saved on Save."""

    def follow(root: nu.Str) -> nu.Nu:
        ready = show(root) >> save_button.init() >> hint.set(HINT)
        # Save, or Enter in any of the typed fields.
        asked = nu.OnAny(
            save_button.on_click(), path.on_submit(), every.on_submit(), count.on_submit()
        )
        return ready >> nu.ReactEvery(asked, save(root))

    return nu.let(nuspace.atomic(root_of(plane)), lambda root: follow(nu.Str(root)))


# ---- about ------------------------------------------------------------------

TEXT = """\
### How the viewer reads a store

- The store is opened **read only**, as a RocksDB secondary: it never takes the writer's lock, so the process \
writing the store keeps writing. Each read catches up with the writer's newest commits.
- Each cell opens its own secondary, in a small temp directory removed when the cell stops. A saved path closes \
them all and opens the new one.
- **Messages** reads `count` entries off one end of a stream: a bounded cursor scan, the same cost at a hundred \
entries or a billion. The level and text filters keep rows of that read only; they never search the whole stream.
- **Metrics** charts a kh57 range sample of the window, at most 500 points: about twice that in reads, however \
many points the window holds.
- Nothing is pushed across processes, so the views look again every few seconds: the `Read every` setting. \
Faster is livelier and reads more.
- A path with nothing behind it yet is looked at again every two seconds: start the viewer first and the writer \
after, and it shows up.
"""


class About(nu.Shape):
    """The ``about`` cell's root."""

    about = ui.MarkdownRef.slot()


def about(plane: nu.StrArg) -> nu.Nu:
    """The ``about`` cell: the same text on every Config plane, ``plane`` unread."""
    return About.about.set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))


PLANE = PlaneSpec(
    "nulog_config",
    "Config",
    icon="cog",
    description="Which nulog store this Log plane reads, and how often.",
    web=WebOptions(editable=True, width="board"),
    cells=(("bar", BAR), ("config", CONFIG), ("about", ABOUT)),
    backend="async",
)
