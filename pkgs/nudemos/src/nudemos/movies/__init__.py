"""The ``movies`` Plane: the cinematheque, a small film base you run yourself.

A web of pages rather than a list. Opened the first time, its ``add`` cell
brings in twenty films and builds the tree under it, all of it pages it
writes itself:

- a page per film: its poster (painted, nothing fetched), facts linking to
  the people, our rating and notes, the films it connects to, the facts to
  edit;
- People, with a page per director and per actor in two films or more,
  each listing their films and who they worked with;
- Timeline, every film by year and rating, and decade by decade;
- Atlas, directors flowing into genres, and a lens on the one store under
  all of it.

Every page reads and writes one catalog in this plane's state
(:class:`.kit.Catalog`), so a rating changed on a film page moves the
table, the stats, the wall, the timeline and the people at once. Adding a
film from the input is a catalog entry and a page with its own cells; saving
its facts can bring a new person's page into People.

- :mod:`.data`: the opening films, facts only.
- :mod:`.kit`: the catalog, page ids, the ops that make pages, the posters.
- :mod:`.cells`: every cell's source.
"""

from __future__ import annotations

from nuspace import PlaneSpec

from . import cells


__all__ = ["PLANE"]


PLANE = PlaneSpec(
    "movies",
    "Movies",
    icon="film",
    description="The cinematheque: films, people and timelines as a web of live pages.",
    meta={"editable": True, "full_width": True},
    cells=cells.ROOT,
    group="Demos",
    backend="async",
)
