"""The ``knowledge`` Plane: Larkspur's wiki and handbook, and one person's notes, where every page is live.

A small company's knowledge base, the kind kept in Notion, Obsidian or
Confluence: a handbook, projects, meetings, decisions, people, a glossary,
tasks, and a second brain of notes. Opened the first time, its ``capture``
cell brings the base in and builds the tree under it, fifty pages and the
folders and tools around them, all pages it writes itself.

Every page reads and writes one base in this plane's state
(:class:`.kit.Base`), and its body is a small program over it:

- ``{{key}}`` cites a fact defined once on Facts: change the price there and
  every page quoting it follows;
- ``{{query ...}}`` is a live table (open decisions, tasks due, what a person
  owns), drawn from the whole base as it is now;
- ``[[slug]]`` links run both ways: every page lists what links to it, and
  the Graph draws all of them;
- tasks live in the pages they are written in, so ticking one on Home or on
  Tasks rewrites its line in its page.

Two jobs run beside the pages, each a headless plane in its own process: a
checker that flags stale pages, broken links and missing facts on every
change and every twenty seconds, and an importer that brings an exported
notebook in as pages. The weekly digest and a new meeting note write
themselves from the base.

- :mod:`.data`, ``exports/``: the opening content, and a notebook to import.
- :mod:`.text`, :mod:`.seed`: reading, rendering and querying pages, plain Python.
- :mod:`.kit`: the base, page ids, the ops that make pages and start the jobs.
- :mod:`.views`, :mod:`.cells`, :mod:`.jobs`: what cells read, their sources, the jobs.
"""

from __future__ import annotations

from nuspace import Plane

from . import cells


__all__ = ["PLANE"]


PLANE = Plane(
    "knowledge",
    "Knowledge",
    icon="sprout",
    description="Larkspur's wiki, handbook and notes: every page live, every fact cited once.",
    meta={"editable": True, "full_width": True, "compact": True},
    cells=cells.ROOT,
    group="Demos",
    backend="async",
)
