"""The Config plane: which store its Log plane reads, and how.

- ``bar``: the store's state, as on every Log plane.
- ``config``: the store's path, how often to read it, how many messages a
  read takes, the metrics window a tab starts on. Saved into the root's
  state on Save, never in code. Every Log cell follows the save: a new path
  opens at once, with no restart.
- ``about``: how the viewer reads the store, and what it costs.
"""

from __future__ import annotations

from nuspace import PlaneSpec

from .cells import BAR, cell


__all__ = ["ABOUT", "CONFIG", "PLANE"]


CONFIG = cell("""\
class WindowField(nustd.ui.Field):
    choice = nustd.ui.SelectRef.slot(options=list(consts.WINDOW_OPTIONS), selected=consts.DEFAULT_WINDOW)


class Knobs(nustd.ui.Grid):
    every = nustd.ui.NumberInputRef.slot(label="Read every, in seconds", min=consts.MIN_EVERY, max=consts.MAX_EVERY, step=0.5)
    count = nustd.ui.NumberInputRef.slot(label="Messages a read takes", min=consts.MIN_COUNT, max=consts.MAX_COUNT, step=50)
    window = WindowField.slot(label="Metrics window to start on")


class Go(nustd.ui.Row):
    save = nustd.ui.ButtonRef.slot(label="Save", icon="save")
    hint = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    path = nustd.ui.InputRef.slot(label="nulog store", placeholder="/path/to/logs.db, the directory nulog.store(path) writes", mono=True)
    knobs = Knobs.slot(columns=3, min_width=200, gap=3)
    go = Go.slot(gap=3, align="center")
    check = nustd.ui.AlertRef.slot()


K = View.knobs

HINT = "A save applies to this Log plane at once, with no restart."


def check(path):
    def said(v):
        seen = nu.Dict(v)
        tone = nu.If(seen["state"] == "ok", "ok", nu.If(seen["state"] == "unset", "info", "danger"))
        return View.check.set(seen["title"], body=seen["note"], variant=tone)

    return nu.let(fmt.look(path), said)


def show(root):
    def put(v):
        s = nu.Dict(v)
        return (
            View.path.set(s["path"]) >> K.every.set_value(s["every"]) >> K.count.set_value(s["count"])
            >> K.window.choice.set(s["window"]) >> check(s["path"])
        )

    return nu.let(snap(config(root)), put)


def save(root):
    # What the form says now, read from the browser once per click.
    every = fmt.bounded(K.every, consts.DEFAULT_EVERY, consts.MIN_EVERY, consts.MAX_EVERY)
    count = nu.int(fmt.bounded(K.count, consts.DEFAULT_COUNT, consts.MIN_COUNT, consts.MAX_COUNT))
    kept = saved(root, path=nu.Str(View.path).strip(), every=every, count=count, window=nu.Str(K.window.choice))
    return kept >> show(root) >> View.go.hint.set("Saved: this Log plane reads with these now.")


def placed():
    # A slot shows once it is first written, in the order written: the path, the knobs, the button, the hint.
    return (
        View.path.set("") >> K.every.set_value(consts.DEFAULT_EVERY) >> K.count.set_value(consts.DEFAULT_COUNT)
        >> K.window.choice.set(consts.DEFAULT_WINDOW)
        >> View.go.save.set("Save", icon="save") >> View.go.hint.set(HINT)
    )


def out(plane):
    def follow(root):
        return placed() >> show(root) >> nu.ReactForever(View.go.save.on_click(), save(root))

    return nu.let(snap(root_of(plane)), lambda root: follow(nu.Str(root)))
""")


ABOUT = '''\
import nu
import nustd.ui

TEXT = """\\
### How the viewer reads a store

- The store is opened **read only**, as a RocksDB secondary: it never takes the writer's lock, so the process writing the store keeps writing. Each read catches up with the writer's newest commits.
- Each cell opens its own secondary, in a small temp directory removed when the cell stops. A saved path closes them all and opens the new one.
- **Messages** reads `count` entries off one end of a stream: a bounded cursor scan, the same cost at a hundred entries or a billion. The level and text filters keep rows of that read only; they never search the whole stream.
- **Metrics** charts a kh57 range sample of the window, at most 500 points: about twice that in reads, however many points the window holds.
- Nothing is pushed across processes, so the views look again every few seconds: the `Read every` setting. Faster is livelier and reads more.
- A path with nothing behind it yet is looked at again every two seconds: start the viewer first and the writer after, and it shows up.
"""

out = nustd.ui.MarkdownRef("about").set(TEXT) >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = PlaneSpec(
    "nulog_config",
    "Config",
    icon="cog",
    description="Which nulog store this Log plane reads, and how often.",
    meta={"editable": True, "full_width": True},
    cells=(("bar", BAR), ("config", CONFIG), ("about", ABOUT)),
    backend="async",
)
