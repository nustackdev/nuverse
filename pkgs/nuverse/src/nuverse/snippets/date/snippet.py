"""A date cell: one date, its own date item, picked in place, synced both ways.

The date is the cell's :data:`ITEM`, a
:class:`~nuverse.contents.date.DateContent` item.

Its label is the cell's name, edited under Config. Live: a change from any
tab, or an op, shows everywhere. Cleared, the date is gone.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.ui
from nuspace import ops

from ...contents.date import DateContent, iso


__all__ = ["ITEM", "out"]


#: The id of the cell's date item, missing until one is picked.
ITEM = "value"


class Entry(nustd.ui.Field):
    input = nustd.ui.DatePickerRef.slot()


class Settings(nustd.ui.Column):
    name = nustd.ui.InputRef.slot(label="Name")


class Config(nustd.ui.Accordion):
    settings = Settings.slot(gap=3)


class Box(nustd.ui.Column):
    entry = Entry.slot()
    config = Config.slot(sections=[{"id": "settings", "label": "Config"}])


def _keep(picked: nu.Nu) -> nu.Nu:
    """What the picker holds stored: cleared, the date is gone."""
    day, value = nu.Str(picked), DateContent.cell(ITEM).value
    return nu.IfDo(day == "", value.erase(), value.set(day))


def out() -> nu.Nu:
    """The date and its Config, both ways, for as long as the cell runs."""
    entry, settings = Box.entry, Box.config.settings
    item = DateContent.cell(ITEM)
    name = nuspace.Space.cells[ops.Here.cell].name.fallback("")

    def show_name() -> nu.Nu:
        return entry.set_label(name) >> settings.name.set(name)

    return ops.bracketed(
        entry.input.set(iso(item))
        >> show_name()
        >> nu.ParallelAsync(
            nu.ReactForever(entry.input.on_change(), _keep(entry.input)),
            nu.ReactForever(
                settings.name.on_change(), ops.rename_cell(ops.Here.cell, nu.Str(settings.name))
            ),
            nu.ReactForever(item.value.on_change(), entry.input.set(iso(item))),
            nu.ReactForever(nuspace.Space.cells[ops.Here.cell].name.on_change(), show_name()),
        )
    )
