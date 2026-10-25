"""The ``data`` Plane: Owlbridge Coffee Roasters, a small shop's numbers as a live space.

Two years of a made up coffee roaster (beans, a subscription, gear, wholesale
to cafes) as three tables in the root's state, a stream selling into them as
you watch, and an importer loading the exports dropped in its inbox. Every
dashboard is a page of small programs over those tables: revenue, funnel,
cohorts, customers with a page each, the catalog as a sheet, a forecast with
what-ifs, a cell per metric, a million web events queried as you type.

- :mod:`.shop`, :mod:`.gen`: the shop and its seeded history, plain data.
- :mod:`.calc`: every view, plain numpy over the tables.
- :mod:`.kit`: the store, the shards and the reads over them, where pages are, the jobs.
- :mod:`.jobs`: the stream and the importer, each a headless job.
- :mod:`.views`, :mod:`.imports`: what the cells show that is not a view of the tables.
- :mod:`.cells`, :mod:`.pages`: every page's cells, as sources.
"""

from __future__ import annotations

from nuspace import PlaneSpec

from . import cells, pages


__all__ = ["PLANE"]


PLANE = PlaneSpec(
    "data",
    "Owlbridge",
    icon="chart-line",
    description="Owlbridge Coffee Roasters: a shop's numbers, live, every chart a cell.",
    meta={"editable": True, "full_width": True},
    cells=cells.ROOT,
    children=pages.PAGES,
    group="Demos",
    backend="async",
)
