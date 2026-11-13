"""The cinematheque's cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the id of the page it runs on comes in, and
:mod:`.kit` finds that page's cinematheque and its catalog. Pages of one kind
run the same cells: twenty film pages, one program each, told apart by their
page's meta.

- The cinematheque (:data:`ROOT`): welcome, stats, add, films, wall.
- A film page (:data:`FILM`): poster, ours, notes, connected, facts.
- A person page (:data:`PERSON`): profile, circle.
- People (:data:`PEOPLE`), Timeline (:data:`TIMELINE`), Atlas (:data:`ATLAS`):
  the ways to browse the whole base.
"""

from __future__ import annotations


__all__ = ["ATLAS", "FILM", "PEOPLE", "PERSON", "ROOT", "TIMELINE"]


# --- the cinematheque ------------------------------------------------------------------------


WELCOME = '''\
import nu
import nuspace
import nuspace.web
import nustd.ui
from nudemos.movies import kit

TEXT = """\\
Films, the people who made them, and what we made of them.
Every film and every person is a page, and every block on a page is a small program:
open its code, change it, run it again. Browse by the people, by year on the timeline, or the whole map in the atlas.
"""

#: The ways to browse, by the catalog's name for each page, and what each holds.
WAYS = {
    "people": "Every director, and everyone in two films or more",
    "timeline": "Every film by year, and decade by decade",
    "atlas": "Directors into genres, and the store under it all",
}


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=4)


about = View.page["about"].to(nustd.ui.MarkdownRef)
ways = View.page["ways"].to(nustd.ui.GridRef.slot(max_columns=3, min_cell_width=200, gap=3))


def out(plane):
    def build(base):
        folder = kit.catalog(base).planes.folder

        def way(name, what):
            tile = ways[name].to(nustd.ui.PageLinkRef.slot(variant="tile"))
            return nu.IfDo(folder.contains(name), nuspace.web.link(tile, folder[name].fallback(""), description=what))

        draw = nu.Sequential(*(way(name, what) for name, what in WAYS.items()))
        # The browsing pages are made on the first run: the links follow once they are.
        return nu.Reconcile(nuspace.atomic(folder.on_change()), nuspace.atomic(draw))

    return about.set(TEXT) >> kit.on_catalog(plane, build)
'''


STATS = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit

KEYS = {
    "films": "Films",
    "watched": "Watched",
    "rating": "Our average",
    "hours": "Hours of film",
    "people": "People",
    "best": "Our favourite",
}


class View(nu.Shape):
    tiles = nustd.ui.GridRef.slot(max_columns=6, min_cell_width=140, gap=3)


@nu.host
def tally(films):
    rated = [f["rating"] for f in films.values() if f.get("rating")]
    best = max(films.values(), key=lambda f: f.get("rating") or 0, default={})
    return {
        "films": str(len(films)),
        "watched": f"{sum(1 for f in films.values() if f.get('watched'))} of {len(films)}",
        "rating": f"{sum(rated) / len(rated):.1f}" if rated else "-",
        "hours": str(round(sum(f.get("runtime") or 0 for f in films.values()) / 60)),
        "people": str(len(kit.people_of(films))),
        "best": best.get("title", "-"),
    }


def tile(k, label):
    return View.tiles[k].to(nustd.ui.CardRef.slot(size="sm"))[0].to(nustd.ui.StatRef.slot(label=label))


def draw(t):
    return nu.Sequential(*(tile(k, label).set_value(t[k]) for k, label in KEYS.items()))


def out(plane):
    def build(base):
        films = kit.catalog(base).films
        return nu.Reconcile(nuspace.atomic(films.on_change()), nu.let(nuspace.atomic(tally(films.extract())), draw))

    return kit.on_catalog(plane, build)
"""


ADD = """\
import nu
import nustd.ui
from nudemos.movies import kit


class View(nu.Shape):
    form = nustd.ui.FormRef.slot(clear_on_submit=True)


line = View.form["line"].to(nustd.ui.InputGroupRef.slot())
title = line["title"].to(nustd.ui.InputRef.slot(placeholder="A film to add, eg Oppenheimer (2023)", required=True))
add = line["add"].to(nustd.ui.ButtonRef.slot(label="Add film", icon="plus", submit=True))


def out(plane):
    # Enter in the title or a click on Add film: one submit, the title in it, the field cleared.
    def added(base):
        return lambda sub: kit.add_film(base, kit.typed_film(nu.Str(sub["values"]["line"]["title"]).strip()))

    # The first run brings in the opening films, each with its page, then the people.
    return title.init() >> add.init() >> kit.on_catalog(
        plane, lambda base: kit.seed(base) >> nu.ReactEvery(View.form.on_submit(), added(base))
    )
"""


FILMS = """\
import nu
import nustd.ui
import nuspace
from nudemos import pages
from nudemos.movies import kit

COLUMNS = [
    {"key": "title", "label": "Title", "editable": False, "cell": nustd.ui.PageLinkRef.slot(variant="inline")},
    {"key": "year", "label": "Year", "kind": "number", "editable": False, "width": 80, "align": "end"},
    {"key": "director", "label": "Director", "editable": False, "hide_below": 640},
    {"key": "genres", "label": "Genres", "editable": False, "wrap": "truncate", "hide_below": 800},
    {"key": "rating", "label": "Our rating", "kind": "number", "width": 120, "align": "end"},
    {"key": "watched", "label": "Watched", "kind": "bool", "width": 100},
]


class View(nu.Shape):
    table = nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", editable=True, label="Films", density="compact")


@nu.host
def rows(films, planes):
    ordered = sorted(films.items(), key=lambda kv: kv[1].get("year") or 0)
    return [
        {"key": key, "title": {"page": kit.page_of(planes, "film", key), "label": f["title"]},
         "year": f.get("year"), "director": f.get("director"), "genres": ", ".join(f.get("genres") or []),
         "rating": f.get("rating") or None, "watched": f.get("watched")}
        for key, f in ordered
    ]


def edit(films, ev):
    film = films[nu.Str(ev["key"])]
    column = nu.Str(ev["column"])
    return nu.IfDo(column == "rating", film.rating.set(nu.ToFloat(ev["value"]))) >> nu.IfDo(
        column == "watched", film.watched.set(nu.ToBool(ev["value"]))
    )


def out(plane):
    table = View.table

    def build(base):
        cat = kit.catalog(base)
        read = pages.linked(rows(cat.films.extract(), cat.planes.extract()), "title")
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(read), table.set_rows)),
            nu.ReactEvery(table.on_edit(), lambda ev: edit(cat.films, ev)),
        )

    return kit.on_catalog(plane, build)
"""


WALL = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit


class View(nu.Shape):
    wall = nustd.ui.CardRef.slot(title="The wall", subtitle="our favourites first")


posters = View.wall["posters"].to(nustd.ui.GridRef.slot(kit.Tile, max_columns=6, min_cell_width=150, gap=4))


@nu.host
def tiles(films, planes):
    best = sorted(films.items(), key=lambda kv: (-(kv[1].get("rating") or 0), kv[1]["title"]))
    return [
        {"key": key, "src": kit.poster_url(f), "label": f["title"], "page": kit.page_of(planes, "film", key),
         "note": f"{f.get('year') or ''}  {kit.stars(f.get('rating'))}"}
        for key, f in best
    ]


def out(plane):
    def build(base):
        cat = kit.catalog(base)
        read = tiles(cat.films.extract(), cat.planes.extract())
        return nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(read), lambda t: kit.wall(posters, t)))

    return kit.on_catalog(plane, build)
"""


ROOT = (("welcome", WELCOME), ("stats", STATS), ("add", ADD), ("films", FILMS), ("wall", WALL))


# --- a film page -----------------------------------------------------------------------------


POSTER = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit


class View(nu.Shape):
    front = nustd.ui.GridRef.slot(cols="240px 1fr", stack_below=520, gap=6)


poster = View.front[0, 0].to(nustd.ui.ImageRef.slot(width=240, radius="md"))
facts = View.front[0, 1].to(nustd.ui.ColumnRef.slot(gap=3))
line = facts["line"].to(nustd.ui.TextRef.slot(tone="muted"))
directed = facts["directed"].to(nustd.ui.LineRef)
cast = facts["cast"].to(nustd.ui.RowRef.slot(gap=2, wrap=True))
back = facts["back"].to(nustd.ui.LineRef)


@nu.host
def front(films, key, planes):
    f, people = films.get(key, {}), kit.people_of(films)

    def who(name):
        # A person draws as a link once they have a page, as plain text before.
        shown = kit.has_page(people.get(name, {"directed": [], "films": []}))
        page = kit.page_of(planes, "person", kit.slug(name)) if shown else ""
        return {"key": ("p:" if page else "t:") + kit.slug(name), "label": name, "page": page}

    facts = [str(f.get("year") or ""), f"{f['runtime']} min" if f.get("runtime") else "", " / ".join(f.get("genres") or [])]
    crew = [who(c) for c in f.get("cast") or []]
    return {
        "src": kit.poster_url(f), "title": f.get("title", ""), "line": "  ·  ".join(x for x in facts if x),
        "director": who(f["director"]) if f.get("director") else {"key": "", "label": "unknown", "page": ""},
        "cast": crew, "keys": ["with"] + [c["key"] for c in crew],
    }


def person(at, p):
    page = nu.Str(p["page"])
    key = nu.Str(p["key"])
    linked = at[key].to(nustd.ui.LinkRef).set(href=kit.href_of(page), label=p["label"])
    plain = at[key].to(nustd.ui.TextRef).set(p["label"])
    return nu.IfDo(page != "", linked, plain)


def draw(v, base):
    head = directed[0].to(nustd.ui.TextRef.slot(weight="medium")).set("Directed by")
    with_ = cast["with"].to(nustd.ui.TextRef.slot(weight="medium")).set("With")
    by = nu.Dict(v["director"])
    who = directed[1].to(nustd.ui.LinkRef).set(href=kit.href_of(by["page"]), label=by["label"])
    crew = nu.ForEachDo(nu.List(v["cast"]), lambda p: person(cast, p)) >> cast.keep(nu.List(v["keys"])) >> cast.set_order(nu.List(v["keys"]))
    shelf = back[0].to(nustd.ui.LinkRef).set(href=nuspace.web.href(base), label="Back to the shelf")
    hint = back[1].to(nustd.ui.TextRef.slot(tone="muted")).set(", or Option+click it to keep this film open beside")
    return poster.set(v["src"], alt=v["title"]) >> line.set(v["line"]) >> head >> who >> with_ >> crew >> shelf >> hint


def out(plane):
    def build(base, key):
        cat = kit.catalog(base)
        read = front(cat.films.extract(), key, cat.planes.extract())
        return nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(read), lambda v: draw(v, base)))

    return kit.on_page(plane, "film", build)
"""


OURS = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit


class Ours(nustd.ui.Row):
    rating = nustd.ui.SliderRef.slot(label="Our rating", min=0, max=10, step=0.5)
    watched = nustd.ui.SwitchRef.slot(label="Watched")
    rank = nustd.ui.StatRef.slot(label="On our shelf")


class View(nu.Shape):
    ours = Ours.slot(gap=6, grow={"rating": 1})


@nu.host
def rank(films, key):
    ranked = sorted(films, key=lambda k: -(films[k].get("rating") or 0))
    return f"#{ranked.index(key) + 1} of {len(films)}" if films.get(key, {}).get("rating") else "unrated"


def out(plane):
    def build(base, key):
        films = kit.catalog(base).films
        film, ours = films[key], View.ours
        shown = nu.Dict.of(rating=film.rating.fallback(0.0), watched=film.watched.fallback(False), rank=rank(films.extract(), key))
        draw = lambda v: ours.rating.set(v["rating"]) >> ours.watched.set(v["watched"]) >> ours.rank.set_value(v["rank"])
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(films.on_change()), nu.let(nuspace.atomic(shown), draw)),
            nu.ReactEvery(ours.rating.on_change(), film.rating.set(nu.ToFloat(ours.rating))),
            nu.ReactEvery(ours.watched.on_change(), film.watched.set(nu.ToBool(ours.watched))),
        )

    return kit.on_page(plane, "film", build)
"""


NOTES = """\
import nu
import nustd.ui
from nudemos.movies import kit


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Our notes", subtitle="markdown, kept as you type")


notes = View.card["notes"].to(nustd.ui.MarkdownRef)


def out(plane):
    def build(base, key):
        kept = kit.catalog(base).films[key].notes
        return (
            notes.set(kept.fallback(""))
            >> notes.set_readonly(False)
            >> notes.set_placeholder("What we thought.")
            >> nu.ParallelAsync(
                nu.ReactEvery(notes.on_change(), kept.set(nu.Str(notes))),
                nu.ReactEvery(kept.on_change(), notes.set(nu.str(kept))),
            )
        )

    return kit.on_page(plane, "film", build)
"""


CONNECTED = """\
import nu
import nustd.ui
import nuspace
from nudemos import pages
from nudemos.movies import kit

COLUMNS = [
    {"key": "film", "label": "Film", "cell": nustd.ui.PageLinkRef.slot(variant="inline")},
    {"key": "year", "label": "Year", "kind": "number", "width": 80, "align": "end"},
    {"key": "why", "label": "Shares", "wrap": "truncate"},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Connected", subtitle="films sharing a person, or two genres")


films = View.card["films"].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", label="Connected", density="compact"))
empty = View.card.footer["empty"].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))


@nu.host
def connected(catalog, key, planes):
    me = catalog.get(key, {})
    mine = {me.get("director")} | set(me.get("cast") or [])
    found = []
    for k, f in catalog.items():
        shared = sorted(n for n in mine & ({f.get("director")} | set(f.get("cast") or [])) if n)
        genres = set(me.get("genres") or []) & set(f.get("genres") or [])
        if k != key and (shared or len(genres) >= 2):
            why = ", ".join(shared) if shared else "also " + " / ".join(sorted(genres))
            row = {"key": k, "film": {"page": kit.page_of(planes, "film", k), "label": f["title"]}, "year": f.get("year"), "why": why}
            found.append((-len(shared), f.get("year") or 0, row))
    rows = [row for *_, row in sorted(found, key=lambda x: x[:2])][:8]
    return {"rows": rows, "empty": "" if rows else "Nothing shares a person with this film yet."}


def draw(v):
    return films.set_rows(pages.linked(v["rows"], "film")) >> empty.set(v["empty"])


def out(plane):
    def build(base, key):
        cat = kit.catalog(base)
        read = connected(cat.films.extract(), key, cat.planes.extract())
        return nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(read), draw))

    return kit.on_page(plane, "film", build)
"""


FACTS = """\
import nu
import nuspace
import nustd.ui
from nudemos.movies import kit


class When(nustd.ui.Row):
    year = nustd.ui.NumberInputRef.slot(label="Year", min=1880, max=2100)
    runtime = nustd.ui.NumberInputRef.slot(label="Minutes", min=0, max=600)


class Edit(nustd.ui.Collapsible):
    when = When.slot(gap=3)
    director = nustd.ui.InputRef.slot(label="Director")
    cast = nustd.ui.TagInputRef.slot(label="Cast", placeholder="A name, then Enter")
    genres = nustd.ui.TagInputRef.slot(label="Genres", placeholder="Sci-Fi, Crime, Drama...")
    save = nustd.ui.ButtonRef.slot(label="Save facts", icon="save")


class View(nu.Shape):
    edit = Edit.slot(title="Edit the facts", open=False)


def out(plane):
    def build(base, key):
        film, e = kit.catalog(base).films[key], View.edit
        show = (
            e.when.year.set(film.year.fallback(0)) >> e.when.runtime.set(film.runtime.fallback(0))
            >> e.director.set(film.director.fallback("")) >> e.cast.set(nu.list(film.cast)) >> e.genres.set(nu.list(film.genres))
        )
        save = (
            film.year.set(nu.ToInt(e.when.year)) >> film.runtime.set(nu.ToInt(e.when.runtime))
            >> film.director.set(nu.Str(e.director).strip()) >> film.cast.set(nu.List(e.cast)) >> film.genres.set(nu.List(e.genres))
        )
        # Saved facts can credit someone new, who gets a page under People, and the genre picks the icon.
        icon = nuspace.plane.set_icon(plane, kit.icon_of(nu.List(e.genres)))
        return show >> e.save.init() >> nu.ReactEvery(e.save.on_click(), save >> icon >> kit.ensure_people(base))

    return kit.on_page(plane, "film", build)
"""


FILM = (
    ("poster", POSTER),
    ("ours", OURS),
    ("notes", NOTES),
    ("connected", CONNECTED),
    ("facts", FACTS),
)


# --- a person page ---------------------------------------------------------------------------


PROFILE = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=6)


head = View.page["head"].to(nustd.ui.RowRef.slot(gap=4))
face = head["face"].to(nustd.ui.AvatarRef.slot(size="xl"))
role = head["role"].to(nustd.ui.TextRef)
films = View.page["films"].to(nustd.ui.GridRef.slot(kit.Tile, max_columns=8, min_cell_width=130, gap=4))


@nu.host
def profile(films, name, planes):
    me = kit.people_of(films).get(name, {"films": [], "directed": [], "acted": []})
    years = [films[k].get("year") or 0 for k in me["films"]]
    roles = [r for r, ks in (("Director", me["directed"]), ("Actor", me["acted"])) if ks]
    rated = [films[k]["rating"] for k in me["films"] if films[k].get("rating")]
    said = f"{' and '.join(roles)}  ·  {kit.films_count(len(years))}, {min(years)} to {max(years)}" if years else "No films here yet"
    if rated:
        said += f"  ·  we give them {sum(rated) / len(rated):.1f} on average"
    tiles = [{"key": k, "src": kit.poster_url(films[k]), "label": films[k]["title"], "page": kit.page_of(planes, "film", k),
              "note": f"{films[k].get('year') or ''}  {'directed' if k in me['directed'] else 'acted'}"}
             for k in me["films"]]
    return {"role": said, "tiles": tiles}


def out(plane):
    def build(base, name):
        draw = lambda v: role.set(v["role"]) >> kit.wall(films, v["tiles"])
        cat = kit.catalog(base)
        read = profile(cat.films.extract(), name, cat.planes.extract())
        return face.set_name(name) >> nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(read), draw))

    return kit.on_page(plane, "person", build)
"""


CIRCLE = """\
import nu
import nustd.ui
import nuspace
from nudemos import pages
from nudemos.movies import kit

COLUMNS = [
    {"key": "person", "label": "Person", "cell": nustd.ui.PageLinkRef.slot(variant="inline"), "width": 200},
    {"key": "films", "label": "Films together", "wrap": "truncate"},
]


class View(nu.Shape):
    both = nustd.ui.GridRef.slot(cols=2, stack_below=800, gap=4)


people = View.both[0, 0].to(nustd.ui.CardRef.slot(title="Worked with", subtitle="most films together first"))
table = people["people"].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", label="Worked with", density="compact"))
ratings = View.both[0, 1].to(nustd.ui.CardRef.slot(title="Our ratings", subtitle="their films, by year"))
bars = ratings["ratings"].to(nustd.ui.BarChart.slot(horizontal=True, y_max=10, height=220))


@nu.host
def circle(films, name, planes):
    folks = kit.people_of(films)
    mine = set(folks.get(name, {}).get("films", []))
    shared = {n: [films[k]["title"] for k in p["films"] if k in mine] for n, p in folks.items() if n != name}
    close = sorted(((n, ts) for n, ts in shared.items() if ts), key=lambda x: (-len(x[1]), x[0]))[:10]

    def page(n):
        return kit.page_of(planes, "person", kit.slug(n)) if kit.has_page(folks[n]) else ""

    rows = [{"key": kit.slug(n), "person": {"page": page(n), "label": n}, "films": ", ".join(ts)} for n, ts in close]
    bars = [[films[k]["title"], films[k].get("rating") or 0] for k in sorted(mine, key=lambda k: films[k].get("year") or 0)]
    return {"rows": rows, "bars": bars}


def out(plane):
    draw = lambda v: table.set_rows(pages.linked(v["rows"], "person")) >> bars.set(v["bars"])

    def build(base, name):
        cat = kit.catalog(base)
        read = circle(cat.films.extract(), name, cat.planes.extract())
        return nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(read), draw))

    return kit.on_page(plane, "person", build)
"""


PERSON = (("profile", PROFILE), ("circle", CIRCLE))


# --- the ways to browse ----------------------------------------------------------------------


PEOPLE_GRID = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit


class Name(nustd.ui.Column):
    link = nustd.ui.LinkRef.slot()
    note = nustd.ui.TextRef.slot(tone="muted", size="sm")


class Face(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="lg")
    name = Name.slot(gap=0)


class View(nu.Shape):
    page = nustd.ui.ColumnRef.slot(gap=4)


intro = View.page["intro"].to(nustd.ui.TextRef.slot(tone="muted"))
grid = View.page["faces"].to(nustd.ui.GridRef.slot(Face, max_columns=4, min_cell_width=260, gap=3))


@nu.host
def faces(films, planes):
    people = [(n, p) for n, p in kit.people_of(films).items() if kit.has_page(p)]
    people.sort(key=lambda np: (not np[1]["directed"], -len(np[1]["films"]), np[0]))
    return [{"key": kit.slug(n), "name": n, "page": kit.page_of(planes, "person", kit.slug(n)),
             "note": f"{'Director' if p['directed'] else 'Actor'}, {kit.films_count(len(p['films']))}"}
            for n, p in people]


def draw(rows):
    shown = nu.List(rows)
    keys = shown.iter().map(lambda r: nu.Dict(r)["key"]).to_list()

    def one(r):
        face = grid[nu.Str(r["key"])]
        link = face.name.link.set(href=kit.href_of(r["page"]), label=r["name"])
        return face.face.set_name(r["name"]) >> link >> face.name.note.set(r["note"])

    return nu.ForEachDo(shown, one) >> grid.keep(keys) >> grid.set_order(keys)


def out(plane):
    said = intro.set("Every director, and everyone who appears in two films or more. The web grows as films are added.")

    def build(base):
        cat = kit.catalog(base)
        return nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(faces(cat.films.extract(), cat.planes.extract())), draw))

    return said >> kit.on_catalog(plane, build)
"""


PEOPLE = (("people", PEOPLE_GRID),)


CHART = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Every film by year and our rating", subtitle="unrated and undated films are in the table below")


chart = View.card["chart"].to(nustd.ui.ScatterChart.slot(
    symbol_size=14, x_label="Year", y_label="Our rating", x_format="{value}", tooltip_format="{b}", legend=True, height=360,
))


@nu.host
def points(films):
    by = {}
    for f in films.values():
        if not f.get("rating") or not f.get("year"):
            continue  # unrated or undated: in the table below, not on the chart
        genre = next(iter(f.get("genres") or []), "Other")
        by.setdefault(genre, []).append({"name": f"{f['title']} ({f.get('year')})  {kit.stars(f.get('rating'))}",
                                         "value": [f.get("year") or 0, f.get("rating") or 0]})
    return by


def out(plane):
    def build(base):
        films = kit.catalog(base).films
        return nu.Reconcile(nuspace.atomic(films.on_change()), nu.let(nuspace.atomic(points(films.extract())), chart.set))

    return kit.on_catalog(plane, build)
"""


DECADES = """\
import nu
import nustd.ui
import nuspace
from nudemos import pages
from nudemos.movies import kit

COLUMNS = [
    {"key": "decade", "label": "Decade", "width": 100},
    {"key": "year", "label": "Year", "kind": "number", "width": 80, "align": "end"},
    {"key": "film", "label": "Film", "cell": nustd.ui.PageLinkRef.slot(variant="inline")},
    {"key": "director", "label": "Director", "hide_below": 640},
    {"key": "rating", "label": "Our rating", "width": 110, "align": "end"},
]


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Decade by decade", subtitle="every film, oldest first")


table = View.card["decades"].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", label="Decades", density="compact"))


@nu.host
def decades(films, planes):
    ordered = sorted(films.items(), key=lambda kv: kv[1].get("year") or 0)
    return [
        {"key": key, "decade": f"{(f.get('year') or 0) // 10 * 10}s" if f.get("year") else "undated", "year": f.get("year"),
         "film": {"page": kit.page_of(planes, "film", key), "label": f["title"]},
         "director": f.get("director") or "unknown", "rating": kit.stars(f.get("rating"))}
        for key, f in ordered
    ]


def out(plane):
    def build(base):
        cat = kit.catalog(base)
        read = pages.linked(decades(cat.films.extract(), cat.planes.extract()), "film")
        return nu.Reconcile(nuspace.atomic(cat.on_change()), nu.let(nuspace.atomic(read), table.set_rows))

    return kit.on_catalog(plane, build)
"""


TIMELINE = (("chart", CHART), ("decades", DECADES))


FLOWS = """\
import nu
import nustd.ui
import nuspace
from nudemos.movies import kit


class View(nu.Shape):
    card = nustd.ui.CardRef.slot(title="Who makes what", subtitle="directors into genres")


sankey = View.card["flows"].to(nustd.ui.SankeyChart.slot(height=520))


@nu.host
def flows(films):
    weights = {}
    for f in films.values():
        for g in f.get("genres") or []:
            if f.get("director"):
                weights[(f["director"], g)] = weights.get((f["director"], g), 0) + 1
    return [[d, g, n] for (d, g), n in sorted(weights.items())]


def out(plane):
    def build(base):
        films = kit.catalog(base).films
        return nu.Reconcile(nuspace.atomic(films.on_change()), nu.let(nuspace.atomic(flows(films.extract())), sankey.set))

    return kit.on_catalog(plane, build)
"""


LENS = """\
import nu
import nuspace
import nustd.ui.lens
from nudemos.movies import kit


def out(plane):
    # The whole cinematheque is this one store: browse it as it lies, and watch it change.
    lens = nustd.ui.lens.LensRef("store")
    store = lambda base: nustd.ui.lens.browse(lens, kit.Catalog, prefix=nuspace.State.planes[nu.Str(base)])
    return nu.let(nuspace.atomic(kit.base_of(plane)), store)
"""


ATLAS = (("flows", FLOWS), ("store", LENS))
