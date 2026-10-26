"""The cinematheque's cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the id of the page it runs on comes in, and
:mod:`.kit` lands the catalog wherever that page's cinematheque is. Pages of
one kind run the same cells: twenty film pages, one program each, told apart
by their page's meta.

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
import nuspace.ui
import nustd.ui

TEXT = """\\
Films, the people who made them, and what we made of them.
Every film and every person is a page, and every block on a page is a small program:
open its code, change it, run it again.
"""


class Ways(nustd.ui.Line):
    lead = nustd.ui.TextRef.slot()
    people = nustd.ui.LinkRef.slot()
    a = nustd.ui.TextRef.slot()
    timeline = nustd.ui.LinkRef.slot()
    b = nustd.ui.TextRef.slot()
    atlas = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    ways = Ways.slot()


def out(plane):
    ways = View.ways
    return (
        View.about.set(TEXT)
        >> ways.lead.set("Browse by ")
        >> ways.people.set(href=nuspace.ui.href(f"{plane}.people"), label="people")
        >> ways.a.set(",  by year on the ")
        >> ways.timeline.set(href=nuspace.ui.href(f"{plane}.timeline"), label="timeline")
        >> ways.b.set(",  or the whole map in the ")
        >> ways.atlas.set(href=nuspace.ui.href(f"{plane}.atlas"), label="atlas")
        >> nu.ForeverDo(nu.Delay(3600.0))
    )
'''


STATS = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class Tiles(nustd.ui.Grid):
    films = nustd.ui.StatRef.slot(label="Films")
    watched = nustd.ui.StatRef.slot(label="Watched")
    rating = nustd.ui.StatRef.slot(label="Our average")
    hours = nustd.ui.StatRef.slot(label="Hours of film")
    people = nustd.ui.StatRef.slot(label="People")
    best = nustd.ui.StatRef.slot(label="Our favourite")


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=6, min_width=140, gap=3)


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


def draw(t):
    return nu.Sequential(*(getattr(View.tiles, k).set_value(t[k]) for k in ("films", "watched", "rating", "hours", "people", "best")))


def out(plane):
    return kit.on_catalog(plane, lambda base: redraws([Catalog.films.on_change()], tally(Catalog.films.extract()), draw))
"""


ADD = """\
import nu
import nustd.ui
from nudemos.movies import kit


class Form(nustd.ui.Row):
    title = nustd.ui.InputRef.slot(placeholder="A film to add, eg Oppenheimer (2023)")
    add = nustd.ui.ButtonRef.slot(label="Add film", icon="plus")


class View(nustd.ui.Column):
    form = Form.slot(gap=3, align="end")


def out(plane):
    form = View.form

    def add(base):
        typed = nu.Str(form.title).strip()
        film = kit.add_film(base, kit.typed_film(typed))
        return nu.IfDo(typed != "", film >> form.title.set(""))

    # The first run brings in the opening films, each with its page, then the people.
    return form.title.set("") >> form.add.set_label("Add film") >> kit.on_catalog(
        plane, lambda base: kit.seed(base) >> nu.ReactForever(form.add.on_click(), add(base))
    )
"""


FILMS = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog

COLUMNS = [
    {"key": "title", "label": "Title", "editable": False},
    {"key": "year", "label": "Year", "kind": "number", "editable": False, "width": 80},
    {"key": "director", "label": "Director", "editable": False},
    {"key": "genres", "label": "Genres", "editable": False},
    {"key": "rating", "label": "Our rating", "kind": "number", "width": 120},
    {"key": "watched", "label": "Watched", "kind": "bool", "width": 100},
]


class View(nustd.ui.Column):
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, label="Films", dense=True)


@nu.host
def rows(films):
    ordered = sorted(films.items(), key=lambda kv: kv[1].get("year") or 0)
    return [
        {**{k: f.get(k) for k in ("title", "year", "director", "watched")},
         "key": key, "rating": f.get("rating") or None, "genres": ", ".join(f.get("genres") or [])}
        for key, f in ordered
    ]


def edit(ev):
    film = Catalog.films[nu.Str(ev["key"])]
    column = nu.Str(ev["column"])
    return nu.IfDo(column == "rating", film.rating.set(nu.ToFloat(ev["value"]))) >> nu.IfDo(
        column == "watched", film.watched.set(nu.ToBool(ev["value"]))
    )


def out(plane):
    table = View.table
    return kit.on_catalog(plane, lambda base: nu.ParallelAsync(
        redraws([Catalog.films.on_change()], rows(Catalog.films.extract()), table.set_rows),
        nu.ReactForever(table.on_edit(), edit),
    ))
"""


WALL = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class View(nustd.ui.Column):
    heading = nustd.ui.HeadingRef.slot(level=3)
    wall = nustd.ui.GridRef.slot(kit.Tile, min_width=150, gap=4)


@nu.host
def tiles(films, base):
    best = sorted(films.items(), key=lambda kv: (-(kv[1].get("rating") or 0), kv[1]["title"]))
    return [
        {"i": i, "src": kit.poster_url(f), "label": f["title"], "href": f"/{base}.film.{key}",
         "note": f"{f.get('year') or ''}  {kit.stars(f.get('rating'))}"}
        for i, (key, f) in enumerate(best)
    ]


def out(plane):
    def build(base):
        draw = lambda t: kit.wall(View.wall, t)
        return View.heading.set_label("The wall, our favourites first") >> redraws(
            [Catalog.films.on_change()], tiles(Catalog.films.extract(), base), draw
        )

    return kit.on_catalog(plane, build)
"""


ROOT = (("welcome", WELCOME), ("stats", STATS), ("add", ADD), ("films", FILMS), ("wall", WALL))


# --- a film page -----------------------------------------------------------------------------


POSTER = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class Facts(nustd.ui.Column):
    line = nustd.ui.TextRef.slot()
    credits = nustd.ui.MarkdownRef.slot()


class Front(nustd.ui.Row):
    poster = nustd.ui.ImageRef.slot(width=240, rounded=True)
    facts = Facts.slot(gap=3)


class View(nustd.ui.Column):
    front = Front.slot(gap=6, align="start")


@nu.host
def front(films, key, base):
    f, people = films.get(key, {}), kit.people_of(films)

    def who(name):
        return f"[{name}](/{base}.person.{kit.slug(name)})" if kit.has_page(people.get(name, {"directed": [], "films": []})) else name

    facts = [str(f.get("year") or ""), f"{f['runtime']} min" if f.get("runtime") else "", " / ".join(f.get("genres") or [])]
    credits = [f"**Directed by** {who(f['director'])}" if f.get("director") else "",
               "**With** " + ", ".join(who(c) for c in f.get("cast") or []) if f.get("cast") else "",
               f"[Back to the shelf](/{base}), or Option+click it to keep this film open beside"]
    return {"src": kit.poster_url(f), "title": f.get("title", ""), "line": "  ·  ".join(x for x in facts if x),
            "credits": "\\n\\n".join(c for c in credits if c)}


def draw(v):
    front = View.front
    return front.poster.set(v["src"], alt=v["title"]) >> front.facts.line.set(v["line"]) >> front.facts.credits.set(v["credits"])


def out(plane):
    return kit.on_page(plane, "film", lambda base, key: redraws(
        [Catalog.films.on_change()], front(Catalog.films.extract(), key, base), draw
    ))
"""


OURS = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class Ours(nustd.ui.Row):
    rating = nustd.ui.SliderRef.slot(label="Our rating", min=0, max=10, step=0.5)
    watched = nustd.ui.SwitchRef.slot(label="Watched")
    rank = nustd.ui.StatRef.slot(label="On our shelf")


class View(nustd.ui.Column):
    ours = Ours.slot(gap=6)


@nu.host
def rank(films, key):
    ranked = sorted(films, key=lambda k: -(films[k].get("rating") or 0))
    return f"#{ranked.index(key) + 1} of {len(films)}" if films.get(key, {}).get("rating") else "unrated"


def out(plane):
    def build(base, key):
        film, ours = Catalog.films[key], View.ours
        shown = nu.Dict.of(rating=film.rating.fallback(0.0), watched=film.watched.fallback(False), rank=rank(Catalog.films.extract(), key))
        draw = lambda v: ours.rating.set_value(v["rating"]) >> ours.watched.set(v["watched"]) >> ours.rank.set_value(v["rank"])
        return nu.ParallelAsync(
            redraws([Catalog.films.on_change()], shown, draw),
            nu.ReactForever(ours.rating.on_change(), film.rating.set(nu.ToFloat(ours.rating))),
            nu.ReactForever(ours.watched.on_change(), film.watched.set(nu.ToBool(ours.watched))),
        )

    return kit.on_page(plane, "film", build)
"""


NOTES = """\
import nu
import nustd.ui
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class View(nustd.ui.Column):
    heading = nustd.ui.HeadingRef.slot(level=3)
    notes = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(base, key):
        notes, kept = View.notes, Catalog.films[key].notes
        return (
            View.heading.set_label("Our notes")
            >> notes.set(kept.fallback(""))
            >> notes.set_editable(True)
            >> notes.set_placeholder("What we thought. Markdown, kept as you type.")
            >> nu.ParallelAsync(
                nu.ReactForever(notes.on_change(), kept.set(nu.Str(notes))),
                nu.ReactForever(kept.on_change(), notes.set(nu.str(kept))),
            )
        )

    return kit.on_page(plane, "film", build)
"""


CONNECTED = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


@nu.host
def connected(films, key, base):
    me = films.get(key, {})
    mine = {me.get("director")} | set(me.get("cast") or [])
    links = []
    for k, f in films.items():
        shared = sorted(n for n in mine & ({f.get("director")} | set(f.get("cast") or [])) if n)
        genres = set(me.get("genres") or []) & set(f.get("genres") or [])
        if k != key and (shared or len(genres) >= 2):
            why = ", ".join(shared) if shared else "also " + " / ".join(sorted(genres))
            links.append((-len(shared), f.get("year") or 0, f"- [{f['title']}](/{base}.film.{k}) {f.get('year') or ''}  ·  {why}"))
    lines = [line for *_, line in sorted(links)][:8]
    return "### Connected\\n\\n" + ("\\n".join(lines) if lines else "Nothing shares a person with this film yet.")


def out(plane):
    web = nustd.ui.MarkdownRef("connected")
    return kit.on_page(plane, "film", lambda base, key: redraws(
        [Catalog.films.on_change()], connected(Catalog.films.extract(), key, base), web.set
    ))
"""


FACTS = """\
import nu
import nustd.ui
from nuspace import ops
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class When(nustd.ui.Row):
    year = nustd.ui.NumberInputRef.slot(label="Year", min=1880, max=2100)
    runtime = nustd.ui.NumberInputRef.slot(label="Minutes", min=0, max=600)


class Edit(nustd.ui.Collapsible):
    when = When.slot(gap=3)
    director = nustd.ui.InputRef.slot(label="Director")
    cast = nustd.ui.TagInputRef.slot(label="Cast", placeholder="A name, then Enter")
    genres = nustd.ui.TagInputRef.slot(label="Genres", placeholder="Sci-Fi, Crime, Drama...")
    save = nustd.ui.ButtonRef.slot(label="Save facts", icon="save")


class View(nustd.ui.Column):
    edit = Edit.slot(title="Edit the facts", open=False)


def out(plane):
    def build(base, key):
        film, e = Catalog.films[key], View.edit
        show = (
            e.when.year.set_value(film.year.fallback(0)) >> e.when.runtime.set_value(film.runtime.fallback(0))
            >> e.director.set(film.director.fallback("")) >> e.cast.set(nu.list(film.cast)) >> e.genres.set(nu.list(film.genres))
        )
        save = (
            film.year.set(nu.ToInt(e.when.year)) >> film.runtime.set(nu.ToInt(e.when.runtime))
            >> film.director.set(nu.Str(e.director).strip()) >> film.cast.set(nu.List(e.cast)) >> film.genres.set(nu.List(e.genres))
        )
        # Saved facts can credit someone new, who gets a page under People, and the genre picks the icon.
        icon = ops.set_plane_meta(plane, nu.Dict.of(icon=kit.icon_of(nu.List(e.genres))))
        return show >> e.save.set_label("Save facts") >> nu.ReactForever(e.save.on_click(), save >> icon >> kit.ensure_people(base))

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
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class Who(nustd.ui.Column):
    role = nustd.ui.TextRef.slot()


class Head(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="xl")
    who = Who.slot(gap=1)


class View(nustd.ui.Column):
    head = Head.slot(gap=4)
    films = nustd.ui.GridRef.slot(kit.Tile, min_width=130, gap=4)


@nu.host
def profile(films, name, base):
    me = kit.people_of(films).get(name, {"films": [], "directed": [], "acted": []})
    years = [films[k].get("year") or 0 for k in me["films"]]
    roles = [r for r, ks in (("Director", me["directed"]), ("Actor", me["acted"])) if ks]
    rated = [films[k]["rating"] for k in me["films"] if films[k].get("rating")]
    role = f"{' and '.join(roles)}  ·  {kit.films_count(len(years))}, {min(years)} to {max(years)}" if years else "No films here yet"
    if rated:
        role += f"  ·  we give them {sum(rated) / len(rated):.1f} on average"
    tiles = [{"i": i, "src": kit.poster_url(films[k]), "label": films[k]["title"], "href": f"/{base}.film.{k}",
              "note": f"{films[k].get('year') or ''}  {'directed' if k in me['directed'] else 'acted'}"}
             for i, k in enumerate(me["films"])]
    return {"role": role, "tiles": tiles}


def out(plane):
    def build(base, name):
        head = View.head
        draw = lambda v: head.who.role.set(v["role"]) >> kit.wall(View.films, v["tiles"])
        return head.face.set_name(name) >> redraws(
            [Catalog.films.on_change()], profile(Catalog.films.extract(), name, base), draw
        )

    return kit.on_page(plane, "person", build)
"""


CIRCLE = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class Both(nustd.ui.Row):
    circle = nustd.ui.MarkdownRef.slot()
    ratings = nustd.ui.BarChart.slot(title="Our ratings of their films", horizontal=True, y_max=10, height=220)


class View(nustd.ui.Column):
    both = Both.slot(gap=6, align="start", wrap=True, min_width=320)


@nu.host
def circle(films, name, base):
    people = kit.people_of(films)
    mine = set(people.get(name, {}).get("films", []))
    shared = {n: [films[k]["title"] for k in p["films"] if k in mine] for n, p in people.items() if n != name}
    close = sorted(((n, ts) for n, ts in shared.items() if ts), key=lambda x: (-len(x[1]), x[0]))[:10]
    link = lambda n: f"[{n}](/{base}.person.{kit.slug(n)})" if kit.has_page(people[n]) else n
    lines = [f"- {link(n)}  ·  {', '.join(ts)}" for n, ts in close]
    bars = [[films[k]["title"], films[k].get("rating") or 0] for k in sorted(mine, key=lambda k: films[k].get("year") or 0)]
    return {"md": "### Worked with\\n\\n" + "\\n".join(lines), "bars": bars}


def out(plane):
    draw = lambda v: View.both.circle.set(v["md"]) >> View.both.ratings.set(v["bars"])
    return kit.on_page(plane, "person", lambda base, name: redraws(
        [Catalog.films.on_change()], circle(Catalog.films.extract(), name, base), draw
    ))
"""


PERSON = (("profile", PROFILE), ("circle", CIRCLE))


# --- the ways to browse ----------------------------------------------------------------------


PEOPLE_GRID = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class Name(nustd.ui.Column):
    link = nustd.ui.LinkRef.slot()
    note = nustd.ui.TextRef.slot()


class Face(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="lg")
    name = Name.slot(gap=0)


class View(nustd.ui.Column):
    intro = nustd.ui.TextRef.slot()
    faces = nustd.ui.GridRef.slot(Face, min_width=260, gap=3)


@nu.host
def faces(films, base):
    people = [(n, p) for n, p in kit.people_of(films).items() if kit.has_page(p)]
    people.sort(key=lambda np: (not np[1]["directed"], -len(np[1]["films"]), np[0]))
    return [{"i": str(i), "name": n, "href": f"/{base}.person.{kit.slug(n)}",
             "note": f"{'Director' if p['directed'] else 'Actor'}, {kit.films_count(len(p['films']))}"}
            for i, (n, p) in enumerate(people)]


def draw(rows):
    def one(r):
        face = View.faces[r["i"]]
        return face.face.set_name(r["name"]) >> face.name.link.set(href=r["href"], label=r["name"]) >> face.name.note.set(r["note"])
    return nu.ForEachDo(rows, one)


def out(plane):
    intro = View.intro.set("Every director, and everyone who appears in two films or more. The web grows as films are added.")
    return intro >> kit.on_catalog(plane, lambda base: redraws(
        [Catalog.films.on_change()], faces(Catalog.films.extract(), base), draw
    ))
"""


PEOPLE = (("people", PEOPLE_GRID),)


CHART = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class View(nustd.ui.Column):
    chart = nustd.ui.ScatterChart.slot(
        title="Every film by year and our rating", symbol_size=14, x_label="Year", y_label="Our rating",
        x_format="{value}", tooltip_format="{b}", legend=True, height=360,
    )


@nu.host
def points(films):
    by = {}
    for f in films.values():
        if not f.get("rating") or not f.get("year"):
            continue  # unrated or undated: on the list below, not on the chart
        genre = next(iter(f.get("genres") or []), "Other")
        by.setdefault(genre, []).append({"name": f"{f['title']} ({f.get('year')})  {kit.stars(f.get('rating'))}",
                                         "value": [f.get("year") or 0, f.get("rating") or 0]})
    return by


def out(plane):
    return kit.on_catalog(plane, lambda base: redraws(
        [Catalog.films.on_change()], points(Catalog.films.extract()), View.chart.set
    ))
"""


DECADES = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


@nu.host
def decades(films, base):
    by = {}
    for key, f in sorted(films.items(), key=lambda kv: kv[1].get("year") or 0):
        by.setdefault((f.get("year") or 0) // 10 * 10, []).append(
            f"- **{f.get('year') or '?'}**  [{f['title']}](/{base}.film.{key})  ·  {f.get('director') or 'unknown'}  ·  {kit.stars(f.get('rating'))}"
        )
    return "\\n\\n".join(f"### The {d}s\\n\\n" + "\\n".join(lines) for d, lines in by.items())


def out(plane):
    text = nustd.ui.MarkdownRef("decades")
    return kit.on_catalog(plane, lambda base: redraws(
        [Catalog.films.on_change()], decades(Catalog.films.extract(), base), text.set
    ))
"""


TIMELINE = (("chart", CHART), ("decades", DECADES))


FLOWS = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.movies import kit
from nudemos.movies.kit import Catalog


class View(nustd.ui.Column):
    flows = nustd.ui.SankeyChart.slot(title="Who makes what: directors into genres", height=520)


@nu.host
def flows(films):
    weights = {}
    for f in films.values():
        for g in f.get("genres") or []:
            if f.get("director"):
                weights[(f["director"], g)] = weights.get((f["director"], g), 0) + 1
    return [[d, g, n] for (d, g), n in sorted(weights.items())]


def out(plane):
    return kit.on_catalog(plane, lambda base: redraws(
        [Catalog.films.on_change()], flows(Catalog.films.extract()), View.flows.set
    ))
"""


LENS = """\
import nu
import nustd.ui.lens
from nuspace.shapes import States
from nuspace.system.utils import snap
from nudemos.movies import kit


def out(plane):
    # The whole cinematheque is this one store: browse it as it lies, and watch it change.
    lens = nustd.ui.lens.LensRef("store")
    store = lambda base: nustd.ui.lens.browse(lens, kit.Catalog, prefix=States.planes[nu.Str(base)].state)
    return nu.let(snap(kit.base_of(plane)), store)
"""


ATLAS = (("flows", FLOWS), ("store", LENS))
