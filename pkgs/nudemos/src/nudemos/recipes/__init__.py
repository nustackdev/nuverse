"""The ``recipes`` Plane: whole pages built from the kit, each a live page of its own.

Each recipe is one module with one entry, ``page(links=None)``, that builds a
full page from the kit's Refs and returns the term that draws it. Pages, all
of Meridian, a made-up network of small observatories (:mod:`.meridian`):

- :mod:`.dashboard`: stat cards with sparklines, a bento of charts.
- :mod:`.detail`: one instrument, a hero with its picture, key facts and actions.
- :mod:`.catalog`: the instruments as cards with actions, link cards, page links, an empty state.
- :mod:`.settings`: a sidebar of nav items beside sections of form fields.
- :mod:`.landing`: the product page, a display heading, features and calls to action.

A recipe is plain ``nustd.ui``: no host, no server, no store. A page links
to the others by href only, through ``links``, which maps a page's name to
the href that opens it (:data:`.meridian.LINKS` by default), so a host that
serves the pages under its own routes passes those. Every recipe is
deterministic, and its module source runs as is as a program of its own
once a line calls ``page``: :func:`source` hands it over for that.

Here each one is a plane whose one cell is the recipe's whole source, so it
runs live and Cmd+Enter runs an edit of it. The pages link to each other,
so their ids have to be known when a page draws, as plain strings: a recipe
takes its links before it builds a single Ref. A child declared on a
``PlaneSpec`` mints its id when it is created, so the pages are made the
way the research desk makes its own: the group's index cell makes each one
once, under itself, at ``<index id>.<recipe>``, and a page's cell works its
siblings' ids out of its own (``out(plane)`` gets it as a string). The
index draws a tile per page, titled and marked off the store with
``nuspace.ui.page_link``.
"""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING

import nu
from nuspace import PlaneSpec, ops
from nuspace.system.utils import snap


if TYPE_CHECKING:
    from types import ModuleType


__all__ = ["INDEX", "PAGES", "PLANE", "RECIPES", "make_pages", "module", "page_id", "source"]


#: Every recipe by name, in the order they are listed.
RECIPES = ("dashboard", "detail", "catalog", "settings", "landing")


def module(name: str) -> ModuleType:
    """The recipe module ``name``."""
    if name not in RECIPES:
        msg = f"no recipe {name!r}; there are {', '.join(RECIPES)}"
        raise KeyError(msg)
    return importlib.import_module(f"{__name__}.{name}")


def source(name: str) -> str:
    """The recipe's module source: a program once something calls its ``page``."""
    return inspect.getsource(module(name))


# --- the pages as planes -----------------------------------------------------------------------


#: Every page as (recipe, label, icon), in sidebar order. The icons are in
#: both sets, the sidebar's and the kit's page links', since a tile draws
#: the plane's own.
_PAGES = (
    ("dashboard", "Dashboard", "gauge"),
    ("detail", "Detail", "star"),
    ("catalog", "Catalog", "layers"),
    ("settings", "Settings", "wrench"),
    ("landing", "Landing", "rocket"),
)

_META = {"editable": True, "full_width": True}


def page_id(base: str, recipe: str) -> str:
    """The plane id of ``recipe``'s page under the index ``base``."""
    return f"{base}.{recipe}"


def _source(recipe: str) -> str:
    """A page cell's source: the recipe as it ships, then an entry that links it to its siblings."""
    return (
        source(recipe)
        + f"""

# --- in a space ------------------------------------------------------------------------------
# The pages are siblings under one index, at ``<index id>.<recipe>``, each
# opened at its pane URL, ``/<plane id>``: this page's own id says where the
# others are. A recipe takes its links as plain strings, before it builds a
# Ref, so they are spelled here rather than by ``nuspace.ui.href``; a plane id
# of letters and dots reads the same either way.

RECIPES = {RECIPES!r}


def out(plane):
    base = plane.rsplit(".", 1)[0]
    links = {{name: f"/{{base}}.{{name}}" for name in RECIPES}}
    return page(links=links) >> nu.ForeverDo(nu.Delay(3600.0))
"""
    )


def _summary(recipe: str) -> str:
    doc = module(recipe).__doc__ or ""
    line = doc.strip().splitlines()[0].split(": ", 1)[-1]
    return line[:1].upper() + line[1:]


#: Each page's spec, by recipe. Made by :func:`make_pages`, not declared as
#: children, so each one's id is its index's id and its name.
PAGES = {
    recipe: PlaneSpec(
        f"recipes_{recipe}",
        label,
        icon=icon,
        description=_summary(recipe),
        meta=_META,
        cells=((recipe, _source(recipe)),),
        backend="async",
    )
    for recipe, label, icon in _PAGES
}


def make_pages(base: nu.StrArg) -> nu.Nu:
    """Every page under the index ``base``, each made only when it is missing.

    Made on every run of the index, so a first run cut short is finished by
    the next, and a page someone deleted comes back.
    """
    made = []
    for recipe, spec in PAGES.items():
        pid = nu.Str(base) + "." + recipe
        create = ops.create_plane(spec, parent=base, plane_id=pid)
        made.append(nu.IfDo(nu.Bool(snap(ops.plane_exists(pid))).not_(), create))
    return nu.Sequential(*made)


INDEX = f'''\
import nu
import nustd.ui
import nuspace.ui
from nudemos import recipes

RECIPES = {RECIPES!r}

TEXT = """\\
Whole pages built from the kit in plain Python, one plane each, all of Meridian, a made-up \\
network of small observatories. Each page's cell is the recipe's own source: open it, change it, \\
and Cmd+Enter draws the new page. The pages link to each other.
"""

intro = nustd.ui.TextRef("intro", props={{"tone": "secondary"}})
tiles = nustd.ui.GridRef("pages", props={{"columns": 3, "min_width": 220, "gap": 3}})


def out(plane):
    def tile(name):
        ref = nustd.ui.PageLinkRef(name, parent_ref=tiles, props={{"variant": "tile"}})
        about = recipes.PAGES[name].description
        return nuspace.ui.page_link(ref, recipes.page_id(plane, name), description=about)

    drawn = intro.set(TEXT) >> nu.Sequential(*(tile(name) for name in RECIPES))
    return recipes.make_pages(plane) >> drawn >> nu.ForeverDo(nu.Delay(3600.0))
'''


PLANE = PlaneSpec(
    "recipes",
    "Recipes",
    icon="compass",
    description="Whole pages from the kit in plain Python: a dashboard, a detail page, a catalog, settings, a landing.",
    meta=_META,
    cells=(("index", INDEX),),
    group="Recipes",
    backend="async",
)
