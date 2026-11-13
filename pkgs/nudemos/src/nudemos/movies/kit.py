"""What every cinematheque cell shares: the catalog, where pages live, how pages are made.

- :class:`Catalog`: the one store. Every film, keyed by slug, in the
  cinematheque plane's state. Every page reads and writes it there, so a
  rating changed anywhere shows everywhere.
- :func:`on_catalog`: a cell's body given its cinematheque, wherever in the
  tree the cell's page sits; :func:`catalog` is that cinematheque's
  :class:`Catalog`. A page knows its cinematheque from its own plane state,
  written when it was made (:mod:`nudemos.bases`): a removed cinematheque
  raises, never reads another.
- Plane ids are minted. The catalog keeps them (:class:`Planes`), by film key,
  person slug and browsing page, so any cell links any page with one read.
- :func:`add_film` and :func:`ensure_people` are cells writing planes: a film
  added is a catalog entry and a page with its own cells, and a person
  credited enough gets a page of their own.
- :func:`poster`: a film's poster, painted as an SVG from its facts. Nothing
  is fetched, so the whole base works offline.

Cells import this module, so their own sources (:mod:`.cells`) stay short.
"""

from __future__ import annotations

import colorsys
import hashlib
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import nu
import nuspace
import nuspace.specs
import nuspace.web
import nustd.kv
import nustd.ui
from nuspace import Space

from .. import bases
from .data import FILMS, slug


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "ROOT",
    "Catalog",
    "Film",
    "Planes",
    "Tile",
    "add_film",
    "catalog",
    "ensure_people",
    "films_count",
    "has_page",
    "href_of",
    "on_catalog",
    "on_page",
    "page_of",
    "people_of",
    "poster",
    "poster_url",
    "seed",
    "stars",
    "typed_film",
    "wall",
]


#: The root Plane's name. Pages it makes are ``movies_film``, ``movies_person`` and so on.
ROOT = "movies"


class Film(nu.Shape):
    """One film: the facts, then ours (rating out of 10, watched, notes in markdown)."""

    title = nustd.kv.StrRef.slot()
    year = nustd.kv.IntRef.slot()
    director = nustd.kv.StrRef.slot()
    cast = nustd.kv.ListRef.slot(str)
    genres = nustd.kv.ListRef.slot(str)
    runtime = nustd.kv.IntRef.slot()
    rating = nustd.kv.FloatRef.slot()
    watched = nustd.kv.BoolRef.slot()
    notes = nustd.kv.StrRef.slot()


class Planes(nu.Shape):
    """The ids of the planes a cinematheque made: by film key, by person slug, by browsing page."""

    film = nustd.kv.DictRef.slot(str)
    person = nustd.kv.DictRef.slot(str)
    folder = nustd.kv.DictRef.slot(str)


class Catalog(nu.Shape):
    """The cinematheque's store, in its plane's state: films by key, the planes it made, whether the opening films are in."""

    films = nustd.kv.DictRef.slot(Film)
    planes = nustd.kv.ShapeRef.slot(Planes)
    seeded = nustd.kv.BoolRef.slot()


def catalog(base: nu.StrArg) -> Catalog:
    """The catalog of the cinematheque ``base``: its plane's state, typed as :class:`Catalog`."""
    return nuspace.at.plane(id=base).state(Catalog)


# --- where things are -----------------------------------------------------------------------


def base_of(plane: nu.StrArg) -> nu.Str:
    """The cinematheque a plane belongs to: itself at the root, else the one its page recorded.

    Raises:
        Missing: A page that recorded none.
        Removed: The cinematheque it recorded is removed.
    """
    from . import PLANE

    return bases.base_of(plane, PLANE)


def about(plane: nu.StrArg, kind: str) -> nu.Str:
    """What a page is about, from its meta: ``film`` (a key) or ``person`` (a name)."""
    return nu.str(Space.planes[plane].meta[kind].fallback(""))


def on_catalog(plane: str, build: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``build(base)``, given the page's cinematheque, bracketed step by step. It reads :func:`catalog`."""

    def landed(base: nu.ObjectRef) -> nu.Nu:
        return nuspace.bracketed(build(nu.Str(base)))

    return nu.let(nuspace.atomic(base_of(plane)), landed)


def on_page(plane: str, kind: str, build: Callable[[nu.Str, nu.Str], nu.Nu]) -> nu.Nu:
    """``build(base, subject)`` on a film or person page, as :func:`on_catalog`.

    ``subject`` is what the page is about, read from its meta: a film's key
    for ``kind="film"``, a person's name for ``kind="person"``.
    """
    return nu.let(
        nuspace.atomic(about(plane, kind)),
        lambda s: on_catalog(plane, lambda b: build(b, nu.Str(s))),
    )


class Caption(nustd.ui.Line):
    """Under a poster: the title linking to its page, then a short note."""

    link = nustd.ui.LinkRef.slot()
    note = nustd.ui.TextRef.slot()


class Tile(nustd.ui.Column):
    """One poster on a wall: the picture, and its caption."""

    poster = nustd.ui.ImageRef.slot(radius="md", fit="cover")
    caption = Caption.slot()


def href_of(page: nu.StrArg) -> nu.Str:
    """A link to the plane ``page``, ``""`` while the catalog has made none."""
    pid = nu.Str(page)
    return nu.Str(nu.If(pid == "", "", nuspace.web.href(pid)))


def wall(grid: nu.Nu, tiles: nu.Nu) -> nu.Nu:
    """Draw ``tiles`` (``{key, src, label, page, note}`` each) into ``grid``, keyed by film.

    A film keeps its tile across redraws; a wall sorted anew moves the tiles
    into the new order, and a film gone takes its tile with it.
    """
    shown = nu.List(tiles)
    keys = shown.iter().map(lambda t: nu.Dict(t)["key"]).to_list()

    def draw(t: nu.Attr) -> nu.Nu:
        tile = grid[nu.Str(t["key"])]
        return (
            tile.poster.set(t["src"], alt=t["label"])
            >> tile.caption.link.set(href=href_of(t["page"]), label=t["label"])
            >> tile.caption.note.set("  " + nu.Str(t["note"]))
        )

    return nu.ForEachDo(shown, draw) >> grid.keep(keys) >> grid.set_order(keys)


slug_of = nu.host(slug, name="Slug")


# --- reading the catalog --------------------------------------------------------------------


def page_of(planes: dict, kind: str, key: str) -> str:
    """The id of a plane the catalog made, ``""`` while it has none.

    Args:
        planes: :class:`Planes` as read, ``{film, person, folder}``.
        kind: ``film`` (by key), ``person`` (by slug) or ``folder`` (by name).
        key: The film's key, the person's slug or the browsing page's name.
    """
    return ((planes or {}).get(kind) or {}).get(key) or ""


def people_of(films: dict[str, dict]) -> dict[str, dict[str, list[str]]]:
    """Everyone credited, by name: ``{films, directed, acted}``, each a list of film keys."""
    people: dict[str, dict[str, list[str]]] = {}
    for key, f in sorted(films.items(), key=lambda kv: kv[1].get("year") or 0):
        credits = [(f.get("director") or "", "directed")] + [
            (c, "acted") for c in f.get("cast") or []
        ]
        for name, role in credits:
            if not name:
                continue
            p = people.setdefault(name, {"films": [], "directed": [], "acted": []})
            if key not in p["films"]:
                p["films"].append(key)
            p[role].append(key)
    return people


def has_page(person: dict[str, list[str]]) -> bool:
    """Who gets a page: every director, and anyone in two films or more."""
    return bool(person["directed"]) or len(person["films"]) >= 2


def films_count(n: int) -> str:
    """``1 film``, ``3 films``."""
    return f"{n} film" if n == 1 else f"{n} films"


def stars(rating: float | None) -> str:
    """``8.5`` as ``★ 8.5``, unrated as ``unrated``."""
    return f"★ {rating:g}" if rating else "unrated"


# --- making pages ---------------------------------------------------------------------------


#: An emoji for a film's page, by its first genre.
GENRE_ICONS = {
    "Sci-Fi": "🚀",
    "Crime": "🕵️",
    "Drama": "🎭",
    "Horror": "👻",
    "Thriller": "🗝️",
    "Western": "🤠",
    "Animation": "✨",
    "Fantasy": "🪄",
    "Action": "💥",
    "Adventure": "🧭",
    "Comedy": "😄",
    "Romance": "💌",
}


@nu.host
def icon_of(genres: list[str]) -> str:
    """The page icon for a film with these genres."""
    first = next(iter(genres or []), "")
    return "emoji:" + GENRE_ICONS.get(first, "🎬")


def _page(
    held: nu.Nu,
    base: nu.Nu,
    parent: nu.Nu,
    name: nu.Nu,
    kind: str,
    subject: nu.Nu,
    icon: nu.StrArg,
    cells: tuple[tuple[str, str], ...],
    wide: bool = False,
) -> nu.Nu:
    """A page under ``parent`` with its cells, made once: a page the catalog holds already is left alone.

    ``held`` is the catalog's slot for the page's id (eg
    ``catalog(base).planes.film[key]``). Made in a row of commits: the plane
    with every cell and its web row (``nuspace.specs.add_plane``), then its
    meta and icon (what it is about), then its id into ``held`` with its
    cinematheque recorded in its own state (:func:`nudemos.bases.belongs`).
    """
    spec = nuspace.specs.PlaneSpec(
        f"{ROOT}_{kind}",
        kind.title(),
        cells=tuple(cells),
        web=nuspace.specs.WebOptions(editable=True, width="board" if wide else "page"),
        backend="async",
    )
    meta = nu.Dict.of(**{kind: subject})

    def make(made: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(made)
        return (
            nuspace.specs.add_plane(spec, parent=parent, name=name, into=made)
            >> nuspace.atomic(
                nuspace.plane.set_meta(pid, meta) >> nuspace.plane.set_icon(pid, icon)
            )
            >> nuspace.atomic(held.set(pid) >> bases.belongs(pid, base))
        )

    return nu.IfDo(nu.Bool(nuspace.atomic(held.exists())).not_(), nu.let("", make))


def add_film(base: nu.Str, film: nu.Nu) -> nu.Nu:
    """``film`` (a dict, ``title`` at least) into the catalog, and its page under the cinematheque.

    A title already there keeps what it has, and its page.
    """
    from .cells import FILM

    cat = catalog(base)

    def add(f: nu.ObjectRef, key: nu.ObjectRef) -> nu.Nu:
        k, film = nu.Str(key), nu.Dict(f)
        keep = nuspace.atomic(nu.IfDo(cat.films.contains(k).not_(), cat.films[k].set(film)))
        page = _page(
            cat.planes.film[k], base, base, film["title"], "film", k, icon_of(film["genres"]), FILM
        )
        return keep >> page

    return nu.let(film, lambda f: nu.let(slug_of(nu.Dict(f)["title"]), lambda key: add(f, key)))


def ensure_people(base: nu.Str) -> nu.Nu:
    """A page for everyone who should have one (see :func:`has_page`), under People."""
    from .cells import PERSON

    @nu.host
    def due(films: dict) -> list[str]:
        people = people_of(films)
        directors = sorted(n for n, p in people.items() if p["directed"])
        actors = sorted(n for n, p in people.items() if has_page(p) and not p["directed"])
        return directors + actors

    cat = catalog(base)

    def make(name: nu.Attr, people: nu.ObjectRef) -> nu.Nu:
        n = nu.Str(name)
        held = cat.planes.person[slug_of(n)]
        return _page(held, base, nu.Str(people), n, "person", n, "lucide:user", PERSON)

    def under(people: nu.ObjectRef) -> nu.Nu:
        films = nuspace.atomic(cat.films.extract())
        return nu.let(
            due(films), lambda names: nu.ForEachDo(nu.List(names), lambda n: make(n, people))
        )

    return nu.let(nuspace.atomic(cat.planes.folder["people"].fallback(base)), under)


def seed(base: nu.Str) -> nu.Nu:
    """The first run: the browsing pages, the opening films with their pages, then the people.

    Once per cinematheque, whichever tab gets there first: the flag is taken
    in the same commit that reads it.
    """
    from .cells import ATLAS, PEOPLE, TIMELINE

    cat = catalog(base)

    def browsing(name: str, label: str, icon: str, cells: tuple[tuple[str, str], ...]) -> nu.Nu:
        held = cat.planes.folder[name]
        return _page(held, base, base, label, "view", name, icon, cells, wide=True)

    def films() -> nu.Nu:
        # One body, run per film: the term stays the size of one film however many there are.
        return nu.ForEachDo(nu.List.of(*FILMS), lambda film: add_film(base, film))

    def first(mine: nu.ObjectRef) -> nu.Nu:
        take = nu.IfDo(cat.seeded.is_null(), cat.seeded.set(True) >> mine.set(True))
        build = (
            browsing("people", "People", "lucide:users", PEOPLE)
            >> browsing("timeline", "Timeline", "lucide:calendar", TIMELINE)
            >> browsing("atlas", "Atlas", "lucide:compass", ATLAS)
            >> films()
            >> ensure_people(base)
        )
        planes = cat.planes
        made = (
            cat.films.init(nu.Dict.create())
            >> planes.film.init(nu.Dict.create())
            >> planes.person.init(nu.Dict.create())
            >> planes.folder.init(nu.Dict.create())
            >> take
        )
        return nuspace.atomic(made) >> nu.IfDo(nu.Bool(mine), build)

    return nu.let(False, first)


@nu.host
def typed_film(text: str) -> dict[str, Any]:
    """What was typed, as a new film: ``"Oppenheimer (2023)"`` is a title and a year."""
    m = re.match(r"^(.*?)\s*\((\d{4})\)\s*$", text.strip())
    title, year = (m.group(1), int(m.group(2))) if m else (text.strip(), 0)
    return {
        "title": title,
        "year": year,
        "director": "",
        "cast": [],
        "genres": [],
        "runtime": 0,
        "rating": 0.0,
        "watched": False,
        "notes": "",
    }


# --- posters --------------------------------------------------------------------------------


#: A base hue and a motif per genre: the poster's look before the title's own jitter.
LOOKS = {
    "Sci-Fi": (212, "planet"),
    "Crime": (8, "blinds"),
    "Drama": (276, "faces"),
    "Horror": (350, "corridor"),
    "Thriller": (38, "rings"),
    "Western": (24, "sun"),
    "Animation": (158, "stars"),
    "Fantasy": (172, "stars"),
    "Action": (16, "bolt"),
    "Adventure": (32, "peaks"),
}


def _hex(h: float, s: float, light: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, light, s)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def _motif(kind: str, ink: str, rnd: int) -> str:
    """The shapes behind the title, in ``ink``, varied by ``rnd``."""
    if kind == "planet":
        cx, cy, r, tilt = (
            50 + rnd % 110,
            70 + (rnd >> 4) % 60,
            30 + (rnd >> 8) % 46,
            (rnd >> 12) % 50 - 25,
        )
        ring = (
            f'<ellipse cx="{cx}" cy="{cy}" rx="{r * 1.6:.0f}" ry="{r * 0.26:.0f}" fill="none" stroke="{ink}" stroke-width="3" opacity=".7" transform="rotate({tilt} {cx} {cy})"/>'
            if rnd % 3
            else f'<circle cx="{cx + r}" cy="{cy - r}" r="{r // 4}" fill="{ink}" opacity=".8"/>'
        )
        return (
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{ink}" opacity=".55"/>'
            + ring
            + "".join(
                f'<circle cx="{(rnd * (i + 3) * 37) % 200}" cy="{(rnd * (i + 7) * 53) % 170}" r="1.2" fill="#fff" opacity=".7"/>'
                for i in range(14)
            )
        )
    if kind == "blinds":
        step, angle = 16 + rnd % 14, (rnd >> 5) % 40 - 28
        return "".join(
            f'<rect x="-80" y="{i * step}" width="360" height="{step * 0.4:.0f}" fill="{ink}" opacity=".45" transform="rotate({angle} 100 100)"/>'
            for i in range(-2, 200 // step + 2)
        )
    if kind == "faces":
        return (
            f'<circle cx="78" cy="104" r="58" fill="{ink}" opacity=".5"/>'
            f'<circle cx="124" cy="104" r="58" fill="none" stroke="{ink}" stroke-width="4" opacity=".75"/>'
        )
    if kind == "corridor":
        lines = "".join(
            f'<line x1="100" y1="96" x2="{x}" y2="{y}" stroke="{ink}" stroke-width="2" opacity=".6"/>'
            for x, y in ((0, 0), (200, 0), (0, 200), (200, 200), (0, 96), (200, 96))
        )
        return lines + f'<rect x="84" y="74" width="32" height="46" fill="{ink}" opacity=".85"/>'
    if kind == "rings":
        return "".join(
            f'<circle cx="100" cy="98" r="{14 + i * 18}" fill="none" stroke="{ink}" stroke-width="{5 - i * 0.7:.1f}" opacity="{0.85 - i * 0.13:.2f}"/>'
            for i in range(5)
        )
    if kind == "sun":
        return (
            f'<circle cx="100" cy="128" r="54" fill="{ink}" opacity=".7"/>'
            '<rect x="0" y="128" width="200" height="80" fill="#000" opacity=".45"/>'
        )
    if kind == "bolt":
        return f'<polygon points="112,10 58,118 98,118 82,196 148,78 106,78" fill="{ink}" opacity=".6"/>'
    if kind == "peaks":
        return (
            f'<polygon points="-10,170 62,60 130,170" fill="{ink}" opacity=".55"/>'
            f'<polygon points="70,170 140,40 214,170" fill="{ink}" opacity=".8"/>'
        )
    return "".join(
        f'<circle cx="{(rnd * (i + 2) * 41) % 200}" cy="{(rnd * (i + 5) * 29) % 180}" r="{2 + (rnd >> i) % 5}" fill="{ink}" opacity=".7"/>'
        for i in range(22)
    )


def _lines(title: str, width: int = 11) -> list[str]:
    """The title in lines of about ``width`` characters, word by word."""
    out: list[str] = []
    for word in title.upper().split():
        if out and len(out[-1]) + 1 + len(word) <= width:
            out[-1] += " " + word
        else:
            out.append(word)
    return out[:4]


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def paint(title: str, year: int, director: str, genres: list[str]) -> str:
    """A 2:3 poster as SVG text: a genre motif, the title set large, year and director small."""
    rnd = int(hashlib.blake2b(title.encode()).hexdigest()[:6], 16)
    hue, kind = LOOKS.get(next(iter(genres or []), ""), (rnd % 360, "stars"))
    hue += rnd % 24 - 12
    top, bottom, ink = _hex(hue, 0.55, 0.32), _hex(hue + 18, 0.6, 0.08), _hex(hue - 10, 0.85, 0.62)
    lines = _lines(title)
    size = min(30, int(176 / max(len(line) for line in lines) / 0.62))
    y0 = 262 - (len(lines) - 1) * size * 1.02 - 18
    text = "".join(
        f'<text x="14" y="{y0 + i * size * 1.02:.0f}" font-size="{size}" font-weight="800" fill="#fff" letter-spacing="-0.5">{_esc(line)}</text>'
        for i, line in enumerate(lines)
    )
    by = f"A FILM BY {director.upper()}" if director else "A FILM"
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 300" font-family="Inter, Helvetica, Arial, sans-serif">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient></defs>'
        '<rect width="200" height="300" fill="url(#g)"/>'
        f"{_motif(kind, ink, rnd)}"
        '<rect y="180" width="200" height="120" fill="#000" opacity=".25"/>'
        f'<text x="14" y="24" font-size="11" font-weight="600" fill="#fff" opacity=".8" letter-spacing="3">{year or ""}</text>'
        f"{text}"
        f'<text x="14" y="284" font-size="7.5" font-weight="600" fill="#fff" opacity=".7" letter-spacing="1.4">{_esc(by[:42])}</text>'
        "</svg>"
    )


def poster_url(film: dict) -> str:
    """A film's poster as a ``data:`` url, for an ``ImageRef``."""
    svg = paint(
        film.get("title") or "",
        film.get("year") or 0,
        film.get("director") or "",
        film.get("genres") or [],
    )
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


#: :func:`poster_url` as a term, for a cell drawing one film.
poster = nu.host(poster_url, name="Poster")
