"""The ``movies`` Plane: rows are data, cells are programs.

A shelf where every movie is its own cell, not a row in a table:

- ``shelf``: stat tiles, movies, watched and average rating, following the
  cards live. Counts only cards still on the plane, so a deleted card
  leaves no ghost.
- ``add``: a title and a button. Each click writes a new card cell at the
  bottom, :data:`CARD` with the title baked in.
- a card per movie: a rating slider and a watched switch, kept in the
  card's own state and reported into the plane's (``Shelf.cards``) for the
  shelf.

A spec cannot seed state, so the seeded cards carry theirs in their source:
:func:`card` bakes a title, rating and watched into :data:`CARD`, and a card
falls back to them until its own state says otherwise.
"""

from __future__ import annotations

import json

from nuspace import Plane


__all__ = ["ADD", "CARD", "PLANE", "SEEDS", "SHELF", "card"]


SHELF = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops
from nuspace.system.utils import redraws


class Shelf(nuspace.PlaneState):
    # Every card reports here, by its cell id.
    cards = nustd.kv.DictRef.slot(object)


class Tiles(nustd.ui.Row):
    movies = nustd.ui.StatRef.slot(label="Movies")
    watched = nustd.ui.StatRef.slot(label="Watched")
    rating = nustd.ui.StatRef.slot(label="Average rating")


class View(nustd.ui.Column):
    tiles = Tiles.slot(gap=8)


@nu.host
def tally(cards, cells):
    # Only cards still on the plane: a removed card leaves no ghost.
    live = [v for k, v in cards.items() if k in cells]
    rated = [v["rating"] for v in live if v.get("rating")]
    seen = sum(1 for v in live if v.get("watched"))
    avg = f"{sum(rated) / len(rated):.1f}" if rated else "-"
    return [str(len(live)), f"{seen} of {len(live)}", avg]


tiles = View.tiles
cells = nuspace.Space.planes[ops.Here.plane].cells


def draw(t):
    return tiles.movies.set_value(t[0]) >> tiles.watched.set_value(t[1]) >> tiles.rating.set_value(t[2])


# Read again after subscribing and on every report or card coming and going.
out = redraws(
    [Shelf.cards.on_change(), cells.on_change()], tally(nu.dict(Shelf.cards), nu.list(cells)), draw
)
"""


CARD = """\
import nu
import nustd.kv
import nustd.ui
import nuspace
from nuspace import ops

# What this card starts as, until its own state says otherwise.
TITLE = "Dune"
RATING = 0.0
WATCHED = False


class Movie(nuspace.CellState):
    # This card's own state.
    rating = nustd.kv.FloatRef.slot()
    watched = nustd.kv.BoolRef.slot()


class Shelf(nuspace.PlaneState):
    # The plane's, the shelf reads it.
    cards = nustd.kv.DictRef.slot(object)


class Card(nustd.ui.Card):
    rating = nustd.ui.SliderRef.slot(label="Rating", max=10)
    watched = nustd.ui.SwitchRef.slot(label="Watched")


class View(nustd.ui.Column):
    card = Card.slot(title=TITLE)


mine = nu.Dict.of(
    rating=Movie.rating.fallback(RATING),
    watched=Movie.watched.fallback(WATCHED),
)
report = Shelf.cards[ops.Here.cell].set(mine)


def keep(field, value, cast, default):
    # The control and the value, kept in step both ways.
    changed = value.set(cast(field)) >> report
    return field.set(value.fallback(default)) >> nu.ParallelAsync(
        nu.ReactForever(field.on_change(), changed),
        nu.ReactForever(value.on_change(), field.set(value)),
    )


card = View.card
out = ops.bracketed(
    report
    >> nu.ParallelAsync(
        keep(card.rating, Movie.rating, nu.ToFloat, RATING),
        keep(card.watched, Movie.watched, nu.ToBool, WATCHED),
    )
)
"""


ADD = (
    """\
import json

import nu
import nustd.ui
from nuspace import ops

#: A new card's program, its title swapped in by card().
CARD = """
    + repr(CARD)
    + """


class Form(nustd.ui.Row):
    title = nustd.ui.InputRef.slot(placeholder="Movie title")
    add = nustd.ui.ButtonRef.slot(label="Add")


class View(nustd.ui.Column):
    form = Form.slot(gap=2)


@nu.host
def card(title):
    # The card's program, its title baked in as a constant.
    return CARD.replace('TITLE = "Dune"', "TITLE = " + json.dumps(title, ensure_ascii=False))


form = View.form


def add(title):
    return ops.add_cell(ops.Here.plane, card(title), name=title) >> form.title.set("")


typed = nu.Str(form.title).strip()
added = nu.let(typed, lambda t: nu.IfDo(nu.Str(t) != "", add(nu.Str(t))))
out = form.title.set("") >> form.add.set("Add") >> nu.ReactForever(form.add.on_click(), added)
"""
)


#: The cards a new plane starts with: title, rating, watched.
SEEDS = (("Dune", 8.0, True), ("Arrival", 9.0, True), ("Heat", 0.0, False))


def card(title: str, rating: float = 0.0, watched: bool = False) -> str:
    """:data:`CARD` with ``title``, ``rating`` and ``watched`` baked in as its defaults."""
    return (
        CARD.replace('TITLE = "Dune"', "TITLE = " + json.dumps(title, ensure_ascii=False))
        .replace("RATING = 0.0", f"RATING = {float(rating)!r}")
        .replace("WATCHED = False", f"WATCHED = {bool(watched)!r}")
    )


PLANE = Plane(
    "movies",
    "Movies",
    icon="film",
    description="A shelf where every movie is a cell, and a cell that adds them.",
    meta={"editable": True, "full_width": False},
    cells=(
        ("shelf", SHELF),
        ("add", ADD),
        *((title, card(title, rating, watched)) for title, rating, watched in SEEDS),
    ),
    group="Demos",
    backend="async",
)
