"""Larkspur's cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the id of the page it runs on comes in, and
:mod:`.kit` lands the base wherever that page's root is. Pages of one kind
run the same cells: fifty doc pages, a handful of programs, told apart by
their page's meta.

- The root (:data:`ROOT`): welcome and search, the numbers, capture, due this week, activity.
- A doc page (:data:`DOC_CELLS`, by kind): head, page, a cell of its kind, links, edit.
- The folder and tool pages (:data:`VIEW_CELLS`, by name), and an imported folder (:data:`COLLECTION`).
"""

from __future__ import annotations


__all__ = ["COLLECTION", "DOC_CELLS", "IMPORTS", "ROOT", "VIEW_CELLS", "cell"]


#: What every cell imports.
IMPORTS = """\
import nu
import nustd.ui
from nuspace import ops
from nuspace.system.utils import redraws, snap
from nudemos.knowledge import kit, text, views
from nudemos.knowledge.kit import Base
"""


def cell(body: str) -> str:
    """A cell's source: the shared imports, then ``body``."""
    return IMPORTS + "\n\n" + body


#: The pages' and facts' changes, the subscriptions most views follow.
CHANGES = "[Base.docs.on_change(), Base.facts.on_change()]"


# --- the root -------------------------------------------------------------------------------


WELCOME = cell("""\
class Find(nustd.ui.Row):
    q = nustd.ui.InputRef.slot(placeholder="Search pages and facts: battery, price, Ravi, LoRa...")


class View(nustd.ui.Column):
    intro = nustd.ui.MarkdownRef.slot()
    find = Find.slot()
    hits = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(base):
        q = nu.Str(View.find.q)
        hits = views.search(Base.docs.extract(), Base.facts.extract(), q, base)
        intro = views.welcome(Base.facts.extract(), base, kit.now())
        return View.find.q.set("") >> nu.ParallelAsync(
            redraws([Base.facts.on_change()], intro, View.intro.set, every=600.0),
            nu.ReactForever(View.find.q.on_change(), View.hits.set(hits)),
        )

    return kit.on_base(plane, build)
""")


TODAY = cell("""\
KEYS = {
    "pages": "Pages",
    "decisions": "Open decisions",
    "week": "Due this week",
    "late": "Overdue",
    "stale": "Stale pages",
    "health": "Health score",
}

Tiles = type("Tiles", (nustd.ui.Grid,), {k: nustd.ui.StatRef.slot(label=v) for k, v in KEYS.items()})


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=6, min_width=120, gap=3)


def draw(t):
    def tile(k):
        s = t[k]
        return getattr(View.tiles, k).set(s["value"], delta=s["delta"], trend=s["trend"])

    return nu.Sequential(*(tile(k) for k in KEYS))


def out(plane):
    def build(base):
        read = views.tiles(Base.docs.extract(), Base.facts.extract(), Base.health.fallback({}), kit.now())
        return redraws([Base.docs.on_change(), Base.facts.on_change(), Base.health.on_change()], read, draw, every=15.0)

    return kit.on_base(plane, build)
""")


CAPTURE = cell("""\
class Form(nustd.ui.Row):
    title = nustd.ui.InputRef.slot(placeholder="Capture a thought, a link, a question. It becomes a note in My notes.")
    add = nustd.ui.ButtonRef.slot(label="Capture", icon="plus")


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    form = Form.slot(gap=3, align="end")


def out(plane):
    form = View.form

    def build(base):
        typed = nu.Str(form.title).strip()

        def made(c):
            c = nu.Dict(c)
            slug = nu.Str(c["slug"])
            opened = kit.go(View.nav, nu.Str("/") + kit.doc_page(base, slug))
            return kit.add_doc(base, slug, c["doc"], "captured") >> form.title.set("") >> opened

        add = nu.IfDo(typed != "", nu.let(views.capture(typed, Base.docs.extract(), kit.now()), made))
        # The first run brings in the base: the folders, every page, then the checker.
        return kit.seed(base) >> nu.ReactForever(form.add.on_click(), add)

    return form.title.set("") >> form.add.set_label("Capture") >> kit.on_base(plane, build)
""")


TASK_COLUMNS = """\
COLUMNS = [
    {"key": "done", "label": "Done", "kind": "bool", "width": 72},
    {"key": "task", "label": "Task", "editable": False},
    {"key": "owner", "label": "Owner", "editable": False, "width": 96},
    {"key": "due", "label": "Due", "editable": False, "width": 130},
    {"key": "page", "label": "Written in", "editable": False, "width": 240},
]


def tick(ev):
    return nu.IfDo(nu.Str(ev["column"]) == "done", kit.tick(nu.Str(ev["key"]), nu.ToBool(ev["value"])))
"""


DUE = cell(
    TASK_COLUMNS
    + """

class View(nustd.ui.Column):
    head = nustd.ui.MarkdownRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, dense=True, label="Due this week")
    more = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(base):
        rows = views.task_rows(Base.docs.extract(), kit.now(), "", 7, False)
        draw = lambda r: View.table.set_rows(views.first(r, 10)) >> View.more.set(views.more(r, 10, base))
        return nu.ParallelAsync(
            redraws([Base.docs.on_change()], rows, draw, every=60.0),
            nu.ReactForever(View.table.on_edit(), tick),
        )

    head = "### Due this week\\n\\nEvery task in every page, due in the next seven days or late. Tick one and its page changes."
    return View.head.set(head) >> kit.on_base(plane, build)
"""
)


ACTIVITY = cell("""\
class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=3)
    feed = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(base):
        read = views.activity(Base.log.fallback([]), Base.docs.extract(), base, kit.now(), 12)
        return redraws([Base.log.on_change()], read, View.feed.set, every=30.0)

    return View.head.set_label("What changed") >> kit.on_base(plane, build)
""")


ROOT = (
    ("welcome", WELCOME),
    ("today", TODAY),
    ("capture", CAPTURE),
    ("due", DUE),
    ("activity", ACTIVITY),
)


# --- a doc page -----------------------------------------------------------------------------


HEAD = cell("""\
class Head(nustd.ui.Row):
    kind = nustd.ui.BadgeRef.slot()
    status = nustd.ui.BadgeRef.slot()
    by = nustd.ui.TextRef.slot()
    owner = nustd.ui.LinkRef.slot()
    when = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    head = Head.slot(gap=3, align="center", wrap=True)


def draw(v):
    h = View.head
    second = nu.If(nu.Bool(v["show_status"]), v["status"], v["fresh"])
    tone = nu.If(nu.Bool(v["show_status"]), v["tone"], v["fresh_tone"])
    return (
        h.kind.set(v["kind"], variant="neutral") >> h.status.set(second, variant=tone)
        >> h.by.set("Owner") >> h.owner.set(href=v["owner_href"], label=v["owner"]) >> h.when.set(v["when"])
    )


def out(plane):
    return kit.on_doc(plane, lambda base, slug: redraws(
        [Base.docs.on_change(), Base.health.on_change()],
        views.doc_head(Base.docs.extract(), Base.health.fallback({}), slug, base, kit.now()),
        draw, every=60.0,
    ))
""")


PAGE = cell(f"""\
def out(plane):
    page = nustd.ui.MarkdownRef("page")
    return kit.on_doc(plane, lambda base, slug: redraws(
        {CHANGES},
        views.page(Base.docs.extract(), Base.facts.extract(), slug, base, kit.now()),
        page.set, every=60.0,
    ))
""")


LINKS = cell("""\
def out(plane):
    links = nustd.ui.MarkdownRef("links")
    return kit.on_doc(plane, lambda base, slug: redraws(
        [Base.docs.on_change(), Base.facts.on_change()], views.doc_links(Base.docs.extract(), Base.facts.extract(), slug, base), links.set
    ))
""")


EDIT = cell("""\
class Edit(nustd.ui.Collapsible):
    title = nustd.ui.InputRef.slot(label="Title")
    source = nustd.ui.CodeRef.slot(language="markdown", editable=True, wrap=True, min_height=220, max_height=560)
    tags = nustd.ui.TagInputRef.slot(label="Tags", placeholder="A tag, then Enter")
    save = nustd.ui.ButtonRef.slot(label="Save page", icon="save")
    hint = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    edit = Edit.slot(title="Edit the source", open=False)


HINT = "[[slug]] links a page, {{key}} cites a fact, @name a person, - [ ] a task with @owner due:YYYY-MM-DD, {{query open-decisions}} a live table."


def out(plane):
    def build(base, slug):
        doc, e = Base.docs[slug], View.edit
        show = e.title.set(doc.title.fallback("")) >> e.source.set(doc.body.fallback("")) >> e.tags.set(nu.list(doc.tags))
        title = nu.Str(e.title).strip()
        save = (
            doc.title.set(title) >> doc.body.set(nu.Str(e.source)) >> doc.tags.set(nu.List(e.tags))
            >> kit.touched(doc, slug, "edited") >> ops.rename_plane(plane, title)
        )
        return show >> e.save.set_label("Save page") >> e.hint.set(HINT) >> nu.ParallelAsync(
            nu.ReactForever(e.save.on_click(), nu.IfDo(title != "", save)),
            nu.ReactForever(doc.body.on_change(), e.source.set(doc.body.fallback(""))),
        )

    return kit.on_doc(plane, build)
""")


PROGRESS = cell("""\
class Numbers(nustd.ui.Grid):
    late = nustd.ui.StatRef.slot(label="Late")
    top = nustd.ui.StatRef.slot(label="Most open")
    meetings = nustd.ui.StatRef.slot(label="Meetings on it")


class View(nustd.ui.Column):
    progress = nustd.ui.ProgressRef.slot()
    numbers = Numbers.slot(columns=3, min_width=150, gap=3)


def draw(v):
    n = View.numbers
    return (
        View.progress.set(v["value"], caption=v["caption"]) >> n.late.set(v["late"], delta=v["late_note"])
        >> n.top.set(v["top"], delta=v["top_note"]) >> n.meetings.set(v["meetings"])
    )


def out(plane):
    return kit.on_doc(plane, lambda base, slug: redraws(
        [Base.docs.on_change()], views.project_view(Base.docs.extract(), slug, kit.now()), draw, every=60.0
    ))
""")


DECIDE = cell("""\
class Decide(nustd.ui.Row):
    status = nustd.ui.SelectRef.slot(options=["open", "decided", "superseded"])
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    decide = Decide.slot(gap=3, align="center")


NOTE = "Open decisions show on Home, in the digest and in every page that asks for them."


def out(plane):
    def build(base, slug):
        doc, d = Base.docs[slug], View.decide
        changed = nu.Str(d.status) != nu.Str(doc.status.fallback("open"))
        return d.note.set(NOTE) >> nu.ParallelAsync(
            redraws([Base.docs.on_change()], doc.status.fallback("open"), d.status.set),
            nu.ReactForever(d.status.on_change(), nu.IfDo(changed, kit.set_status(slug, nu.Str(d.status)))),
        )

    return kit.on_doc(plane, build)
""")


PROFILE = cell("""\
class Who(nustd.ui.Column):
    role = nustd.ui.TextRef.slot()


class Head(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="xl")
    who = Who.slot(gap=1)


class Numbers(nustd.ui.Grid):
    owns = nustd.ui.StatRef.slot(label="Pages owned")
    open = nustd.ui.StatRef.slot(label="Open tasks")
    late = nustd.ui.StatRef.slot(label="Late")
    edits = nustd.ui.StatRef.slot(label="Edits, two weeks")


class View(nustd.ui.Column):
    head = Head.slot(gap=4, align="center")
    numbers = Numbers.slot(columns=4, min_width=130, gap=3)


def draw(v):
    n = View.numbers
    return (
        View.head.who.role.set(v["role"]) >> n.owns.set(v["owns"]) >> n.open.set(v["open"])
        >> n.late.set(v["late"]) >> n.edits.set(v["edits"])
    )


def out(plane):
    def build(base, slug):
        name = Base.docs[slug].title.fallback("")
        return View.head.face.set("", name=name) >> redraws(
            [Base.docs.on_change()], views.person_view(Base.docs.extract(), slug, kit.now()), draw, every=60.0
        )

    return kit.on_doc(plane, build)
""")


_COMMON = (("head", HEAD), ("page", PAGE))
_TAIL = (("links", LINKS), ("edit", EDIT))

#: A doc page's cells, by its kind.
DOC_CELLS = {
    "wiki": _COMMON + _TAIL,
    "note": _COMMON + _TAIL,
    "meeting": _COMMON + _TAIL,
    "project": (("head", HEAD), ("progress", PROGRESS), ("page", PAGE), *_TAIL),
    "decision": (("head", HEAD), ("decide", DECIDE), ("page", PAGE), *_TAIL),
    "person": (("profile", PROFILE), ("head", HEAD), ("page", PAGE), *_TAIL),
}


# --- the folder and tool pages --------------------------------------------------------------


def _opens(name: str, extra: str = "") -> str:
    """A table of pages whose row click opens the page: the shared part of a folder's cell."""
    return f"""\
class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    head = nustd.ui.HeadingRef.slot(level=3)
    note = nustd.ui.TextRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, dense=True, label="{name}")
{extra}

def opens(base):
    return nu.ReactForever(View.table.on_row_click(), lambda ev: kit.go(View.nav, nu.Str("/") + kit.doc_page(base, nu.Str(ev["key"]))))
"""


HANDBOOK = cell(
    """\
COLUMNS = [
    {"key": "title", "label": "Page"},
    {"key": "owner", "label": "Owner", "width": 160},
    {"key": "edited", "label": "Edited", "width": 140, "sortable": False},
    {"key": "fresh", "label": "Fresh", "width": 100},
    {"key": "links", "label": "Linked from", "kind": "number", "width": 120},
]
"""
    + _opens("Handbook")
    + """

def out(plane):
    def build(base):
        rows = views.pages_rows(Base.docs.extract(), Base.health.fallback({}), "wiki", kit.now())
        return nu.ParallelAsync(redraws([Base.docs.on_change(), Base.health.on_change()], rows, View.table.set_rows, every=60.0), opens(base))

    note = "How Larkspur works, one page per topic. A page untouched for too long is flagged by the checker."
    return View.note.set(note) >> kit.on_base(plane, build)
"""
)


RECENT = cell("""\
def out(plane):
    md = nustd.ui.MarkdownRef("recent")
    read = lambda base: nu.Str("### Recently edited\\n\\n") + views.page_query("recent", "8", Base.docs.extract(), Base.facts.extract(), base, kit.now())
    return kit.on_base(plane, lambda base: redraws([Base.docs.on_change()], read(base), md.set, every=60.0))
""")


PROJECTS = cell(
    """\
COLUMNS = [
    {"key": "title", "label": "Project"},
    {"key": "owner", "label": "Owner", "width": 150},
    {"key": "status", "label": "Status", "width": 100},
    {"key": "progress", "label": "Done", "width": 90},
    {"key": "open", "label": "Open tasks", "kind": "number", "width": 120},
    {"key": "next", "label": "Next due", "width": 140},
]
"""
    + _opens("Projects", "    chart = nustd.ui.Chart.slot(height=240)\n")
    + """


def draw(v):
    return View.table.set_rows(nu.Dict(v)["rows"]) >> View.chart.set(option=views.projects_chart(v))


def out(plane):
    def build(base):
        read = views.projects_view(Base.docs.extract(), kit.now())
        return nu.ParallelAsync(redraws([Base.docs.on_change()], read, draw, every=60.0), opens(base))

    note = "Progress is counted from the tasks in each project page and in every page that links it."
    return View.note.set(note) >> kit.on_base(plane, build)
"""
)


MEETING_NEW = cell("""\
class Line1(nustd.ui.Row):
    title = nustd.ui.InputRef.slot(label="Meeting", placeholder="eg Battery sync")
    project = nustd.ui.SelectRef.slot(placeholder="About a project")


class Form(nustd.ui.Collapsible):
    line = Line1.slot(gap=3, align="end")
    people = nustd.ui.TagInputRef.slot(label="Attendees", placeholder="Theo, Ravi, ... then Enter")
    write = nustd.ui.ButtonRef.slot(label="Write the note", icon="sparkles")
    hint = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    form = Form.slot(title="New meeting note", open=True)


@nu.host
def projects(docs):
    return [{"value": k, "label": d["title"]} for k, d in sorted(docs.items()) if d.get("kind") == "project"]


HINT = "The note writes itself: who is there, what is still open for them on that project, the open decisions, and a link to last time."


def out(plane):
    f = View.form

    def build(base):
        def made(c):
            c = nu.Dict(c)
            slug = nu.Str(c["slug"])
            return kit.add_doc(base, slug, c["doc"], "wrote up") >> f.line.title.set("") >> kit.go(View.nav, nu.Str("/") + kit.doc_page(base, slug))

        new = views.meeting_new(nu.Str(f.line.title), nu.Str(f.line.project), nu.List(f.people), "", Base.docs.extract(), kit.now())
        return f.line.project.set_options(projects(Base.docs.extract())) >> nu.ReactForever(f.write.on_click(), nu.let(new, made))

    return f.line.title.set("") >> f.people.set([]) >> f.write.set_label("Write the note") >> f.hint.set(HINT) >> kit.on_base(plane, build)
""")


MEETINGS = cell(
    """\
COLUMNS = [
    {"key": "date", "label": "Date", "width": 120, "sortable": False},
    {"key": "title", "label": "Meeting"},
    {"key": "people", "label": "People", "kind": "number", "width": 90},
    {"key": "decisions", "label": "Decisions", "kind": "number", "width": 110},
    {"key": "open", "label": "Open items", "kind": "number", "width": 110},
]
"""
    + _opens("Meetings")
    + """

def out(plane):
    def build(base):
        rows = views.meetings_rows(Base.docs.extract(), kit.now())
        return nu.ParallelAsync(redraws([Base.docs.on_change()], rows, View.table.set_rows), opens(base))

    return View.head.set_label("Every meeting, newest first") >> View.note.set("") >> kit.on_base(plane, build)
"""
)


DECISIONS = cell("""\
COLUMNS = [
    {"key": "title", "label": "Decision", "editable": False},
    {"key": "status", "label": "Status", "kind": "select", "options": ["open", "decided", "superseded"], "width": 140},
    {"key": "owner", "label": "Owner", "editable": False, "width": 150},
    {"key": "touched", "label": "Last touched", "editable": False, "width": 140, "sortable": False},
    {"key": "cited", "label": "Cited by", "kind": "number", "editable": False, "width": 100},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=3)
    note = nustd.ui.TextRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, dense=True, label="Decisions")


def edit(ev):
    return nu.IfDo(nu.Str(ev["column"]) == "status", kit.set_status(nu.Str(ev["key"]), nu.Str(ev["value"])))


def out(plane):
    def build(base):
        rows = views.decisions(Base.docs.extract(), kit.now())
        return nu.ParallelAsync(redraws([Base.docs.on_change()], rows, View.table.set_rows, every=60.0), nu.ReactForever(View.table.on_edit(), edit))

    note = "Change a status here and the decision's page, Home, the digest and every open-decisions table follow."
    return View.note.set(note) >> kit.on_base(plane, build)
""")


PEOPLE = cell("""\
class Name(nustd.ui.Column):
    link = nustd.ui.LinkRef.slot()
    role = nustd.ui.TextRef.slot()
    note = nustd.ui.TextRef.slot()


class Face(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="lg")
    name = Name.slot(gap=0)


class View(nustd.ui.Column):
    intro = nustd.ui.TextRef.slot()
    faces = nustd.ui.GridRef.slot(Face, min_width=280, gap=3)


def draw(rows):
    def one(r):
        f = View.faces[r["i"]]
        return f.face.set("", name=r["name"]) >> f.name.link.set(href=r["href"], label=r["name"]) >> f.name.role.set(r["role"]) >> f.name.note.set(r["note"])

    return nu.ForEachDo(rows, one)


def out(plane):
    intro = View.intro.set("Seven of us. Each person's page lists what they own and what is on them, live.")
    return intro >> kit.on_base(plane, lambda base: redraws(
        [Base.docs.on_change()], views.people_cards(Base.docs.extract(), kit.now(), base), draw, every=60.0
    ))
""")


NOTES = cell(
    """\
COLUMNS = [
    {"key": "title", "label": "Note"},
    {"key": "from", "label": "From", "width": 170},
    {"key": "tags", "label": "Tags", "width": 200},
    {"key": "edited", "label": "Edited", "width": 140, "sortable": False},
]
"""
    + _opens("My notes")
    + """

def out(plane):
    def build(base):
        return nu.ParallelAsync(redraws([Base.docs.on_change()], views.notes_rows(Base.docs.extract(), kit.now()), View.table.set_rows, every=60.0), opens(base))

    note = "My second brain: reading notes, half thoughts, captures from Home, and notebooks brought in from elsewhere."
    return View.note.set(note) >> kit.on_base(plane, build)
"""
)


TASKS = cell(
    TASK_COLUMNS
    + """

class Filter(nustd.ui.Row):
    who = nustd.ui.SelectRef.slot(placeholder="Everyone")
    done = nustd.ui.SwitchRef.slot(label="Show done")
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    filter = Filter.slot(gap=4, align="center")
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, dense=True, label="Tasks")


PEOPLE = [{"value": "", "label": "Everyone"}] + [{"value": k, "label": v} for k, v in kit.NAMES.items()]


def out(plane):
    f = View.filter

    def build(base):
        rows = views.task_rows(Base.docs.extract(), kit.now(), nu.Str(f.who), -1, nu.Bool(f.done))
        again = nu.let(rows, View.table.set_rows)
        return nu.ParallelAsync(
            redraws([Base.docs.on_change()], rows, View.table.set_rows, every=60.0),
            nu.ReactForever(f.who.on_change(), again),
            nu.ReactForever(f.done.on_change(), again),
            nu.ReactForever(View.table.on_edit(), tick),
        )

    note = "Tasks live in the pages they are written in. This is a query over all of them."
    return f.who.set_options(PEOPLE) >> f.who.set("") >> f.done.set(False) >> f.note.set(note) >> kit.on_base(plane, build)
"""
)


TASKS_CHART = cell("""\
class View(nustd.ui.Column):
    chart = nustd.ui.Chart.slot(height=260)


def draw(v):
    return View.chart.set(option=views.tasks_option(v))


def out(plane):
    return kit.on_base(plane, lambda base: redraws([Base.docs.on_change()], views.tasks_chart(Base.docs.extract(), kit.now()), draw, every=60.0))
""")


FACTS = cell(
    """\
COLUMNS = [
    {"key": "label", "label": "Fact", "editable": False},
    {"key": "value", "label": "Value", "width": 240},
    {"key": "cite", "label": "Cite as", "editable": False, "width": 170},
    {"key": "owner", "label": "Owner", "editable": False, "width": 100},
    {"key": "cited", "label": "Cited on", "kind": "number", "editable": False, "width": 100},
    {"key": "changed", "label": "Changed", "editable": False, "width": 130, "sortable": False},
]


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=3)
    note = nustd.ui.TextRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, dense=True, label="Facts")


def edit(ev):
    value = nu.Str(ev["value"]).strip()
    return nu.IfDo((nu.Str(ev["column"]) == "value").and_(value != ""), kit.set_fact(nu.Str(ev["key"]), value))


def out(plane):
    def build(base):
        rows = views.facts_rows(Base.docs.extract(), Base.facts.extract(), kit.now())
        return nu.ParallelAsync(redraws(CHANGES, rows, View.table.set_rows, every=60.0), nu.ReactForever(View.table.on_edit(), edit))

    note = "Each fact is written once and cited on pages as {{key}}. Change a value here and every page citing it follows."
    return View.note.set(note) >> kit.on_base(plane, build)
""".replace("CHANGES", CHANGES)
)


FACT_USES = cell(f"""\
def out(plane):
    md = nustd.ui.MarkdownRef("uses")
    read = lambda base: nu.Str("### Where each fact is cited\\n\\n") + views.fact_uses(Base.docs.extract(), Base.facts.extract(), base)
    return kit.on_base(plane, lambda base: redraws({CHANGES}, read(base), md.set))
""")


GLOSSARY = cell("""\
COLUMNS = [
    {"key": "term", "label": "Term", "width": 220},
    {"key": "meaning", "label": "What it means"},
    {"key": "used", "label": "Used on", "kind": "number", "width": 100},
]


class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", dense=True, label="Glossary")


def out(plane):
    note = "The words we use. How many pages use each is counted from the pages as they are now."
    return View.note.set(note) >> kit.on_base(plane, lambda base: redraws([Base.docs.on_change()], views.glossary_rows(Base.docs.extract()), View.table.set_rows))
""")


GRAPH = cell("""\
class Both(nustd.ui.Column):
    chart = nustd.ui.Chart.slot(height=560)
    side = nustd.ui.MarkdownRef.slot()


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    note = nustd.ui.TextRef.slot()
    both = Both.slot(gap=4)


def out(plane):
    def build(base):
        docs = Base.docs.extract()
        draw = lambda v: View.both.chart.set(option=v)
        side = redraws([Base.docs.on_change()], views.graph_side(docs, base), View.both.side.set)
        # A node opens its page; an edge or the legend names no page, and does nothing.
        go = lambda s: nu.IfDo(nu.Str(s) != "", kit.go(View.nav, nu.Str("/") + kit.doc_page(base, nu.Str(s))))
        opened = nu.ReactForever(View.both.chart.on_click(), lambda ev: nu.let(views.slug_named(nu.str(nu.Dict(ev)["name"]).fallback(""), Base.docs.extract()), go))
        return nu.ParallelAsync(redraws([Base.docs.on_change()], views.graph_option(docs, base), draw), side, opened)

    note = "Every page and every link, drawn from the pages as they are. Hover to see a page's neighbours, click to open it."
    return View.note.set(note) >> kit.on_base(plane, build)
""")


DIGEST = cell(f"""\
class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot()
    digest = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(base):
        read = views.digest(Base.docs.extract(), Base.facts.extract(), Base.log.fallback([]), base, kit.now())
        return redraws({CHANGES} + [Base.log.on_change(), Base.health.on_change()], read, View.digest.set, every=60.0)

    note = "Nobody writes this page. It is written from the base, and rewrites itself as the week moves."
    return View.note.set(note) >> kit.on_base(plane, build)
""")


HEALTH = cell("""\
class Bar(nustd.ui.Row):
    dot = nustd.ui.StatusDotRef.slot(tone="neutral")
    pill = nustd.ui.StatusPillRef.slot()
    line = nustd.ui.TextRef.slot()


class Top(nustd.ui.Row):
    score = nustd.ui.GaugeRef.slot()
    trend = nustd.ui.Sparkline.slot(area=True, height=64, max_points=60, option={"yAxis": {"min": 0, "max": 100}})


class Act(nustd.ui.Row):
    reviewed = nustd.ui.ButtonRef.slot(label="Mark stale pages reviewed", icon="square-check-big", variant="secondary")
    hint = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    bar = Bar.slot(gap=3, align="center")
    top = Top.slot(gap=6, align="center")
    act = Act.slot(gap=3, align="center")
    table = nustd.ui.TableRef.slot(
        columns=[
            {"key": "issue", "label": "Issue", "width": 130},
            {"key": "page", "label": "Page", "width": 260},
            {"key": "owner", "label": "Owner", "width": 100},
            {"key": "detail", "label": "Detail"},
        ],
        row_key="key", clickable_rows=True, dense=True, label="Issues",
    )


def draw(v):
    b, t = View.bar, View.top
    return (
        b.dot.set(v["tone"], pulse=v["pulse"]) >> b.pill.set(v["status"], tone=v["tone"]) >> b.line.set(v["line"])
        >> t.score.set(v["gauge"], caption=v["caption"]) >> t.trend.set(v["history"]) >> View.table.set_rows(v["rows"])
    )


@nu.host
def doc_of(key):
    return str(key).split(":")[1]


@nu.host
def stale(health):
    return [s["doc"] for s in (health or {}).get("stale", [])]


def out(plane):
    def build(base):
        read = views.health_view(Base.health.fallback({}), kit.live(base, "checker"), Base.docs.extract(), kit.now())
        opened = lambda ev: kit.go(View.nav, nu.Str("/") + kit.doc_page(base, doc_of(ev["key"])))
        return nu.ParallelAsync(
            redraws([Base.health.on_change()], read, draw, every=5.0),
            nu.ReactForever(View.act.reviewed.on_click(), kit.reviewed(stale(Base.health.fallback({})))),
            nu.ReactForever(View.table.on_row_click(), opened),
        )

    hint = "The checker runs in its own process: on every change, and every 20 seconds. Click an issue to open its page."
    return View.act.hint.set(hint) >> View.act.reviewed.set_label("Mark stale pages reviewed") >> kit.on_base(plane, build)
""")


IMPORT = cell("""\
class Pick(nustd.ui.Row):
    source = nustd.ui.SelectRef.slot()
    go = nustd.ui.ButtonRef.slot(label="Import", icon="inbox")
    pill = nustd.ui.StatusPillRef.slot()


class View(nustd.ui.Column):
    note = nustd.ui.MarkdownRef.slot()
    pick = Pick.slot(gap=3, align="center")
    progress = nustd.ui.ProgressRef.slot()
    log = nustd.ui.MarkdownRef.slot()


NOTE = "Bring notes in from elsewhere. The importer runs as a job in its own process: it reads each markdown file, keeps its frontmatter, tags, tasks and wikilinks, and writes it in as a page of its own, linked into what is already here."


@nu.host
def sources():
    from nudemos.knowledge import seed
    return [{"value": e["key"], "label": f"{e['label']}, {e['files']} notes"} for e in seed.exports()]


def draw(v):
    p = View.pick
    return (
        View.progress.set(v["value"], caption=v["caption"]) >> p.pill.set(v["status"], tone=v["tone"])
        >> p.go.set_disabled(v["busy"]) >> View.log.set(v["log"])
    )


def out(plane):
    p = View.pick

    def build(base):
        read = views.imports_view(Base.imports.fallback({}), kit.live(base, "importer"), kit.now())
        start = kit.start_import(base, nu.Str(p.source))
        return nu.ParallelAsync(
            redraws([Base.imports.on_change()], read, draw, every=10.0),
            nu.ReactForever(p.go.on_click(), start),
        )

    return View.note.set(NOTE) >> p.source.set_options(sources()) >> p.source.set("lab-notebook") >> p.go.set_label("Import") >> kit.on_base(plane, build)
""")


ASK = cell("""\
import nustd.cc
from nudemos.knowledge.ask import OPTIONS, Asker, answered, asked, shown

TRIES = ("What is still blocking the launch?", "Why did we pick LoRa?", "What is Theo working on this week?")


class Box(nustd.ui.Row):
    q = nustd.ui.InputRef.slot(placeholder="Ask anything the base knows: dates, owners, why we decided something...")
    go = nustd.ui.ButtonRef.slot(label="Ask", icon="sparkles")


class Tries(nustd.ui.Row):
    lead = nustd.ui.TextRef.slot()
    a = nustd.ui.ButtonRef.slot(variant="secondary")
    b = nustd.ui.ButtonRef.slot(variant="secondary")
    c = nustd.ui.ButtonRef.slot(variant="secondary")


class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot()
    box = Box.slot(gap=3, align="end")
    tries = Tries.slot(gap=2, align="center", wrap=True)
    status = nustd.ui.TextRef.slot()
    answer = nustd.ui.MarkdownRef.slot()
    line = nustd.ui.TextRef.slot()
    before = nustd.ui.MarkdownRef.slot()


NOTE = "Claude reads the whole base as it is right now, every page with its facts filled in, and answers with links to the pages it used."


def out(plane):
    b, t = View.box, View.tries

    def build(base):
        def ask(question):
            def call(started):
                prompt = asked(Base.docs.extract(), Base.facts.extract(), question)
                reply = Asker.answer(prompt=prompt)
                return nu.let(reply, lambda r: Base.asks.set(answered(Base.asks.fallback([]), r, question, started)))

            reading = nu.Str("Reading ") + nu.ToStr(nu.Dict(Base.docs.extract()).len()) + " pages..."
            failed = lambda err: View.status.set(nu.Str("Could not ask: ") + nu.ToStr(err))
            return (
                View.status.set(reading) >> b.go.set_disabled(True)
                >> nu.TryCatch(nu.let(kit.now(), call) >> View.status.set(""), catch=failed)
                >> b.go.set_disabled(False)
            )

        def tried(ref, question):
            return nu.ReactForever(ref.on_click(), b.q.set(question) >> ask(question))

        typed = nu.Str(b.q).strip()
        draw = lambda v: View.answer.set(v["answer"]) >> View.line.set(v["line"]) >> View.before.set(v["before"])
        read = shown(Base.asks.fallback([]), Base.docs.extract(), Base.facts.extract(), base, kit.now())
        body = nu.ParallelAsync(
            redraws([Base.asks.on_change(), Base.docs.on_change()], read, draw, every=30.0),
            nu.ReactForever(b.go.on_click(), nu.IfDo(typed != "", ask(typed))),
            tried(t.a, TRIES[0]), tried(t.b, TRIES[1]), tried(t.c, TRIES[2]),
        )
        return nu.With(nustd.cc.bind(Asker, **OPTIONS), body=body)

    shown_first = (
        View.note.set(NOTE) >> b.q.set("") >> b.go.set_label("Ask") >> t.lead.set("Try")
        >> t.a.set_label(TRIES[0]) >> t.b.set_label(TRIES[1]) >> t.c.set_label(TRIES[2])
    )
    return shown_first >> kit.on_base(plane, build)
""")


COLLECTION = (
    (
        "pages",
        cell(
            """\
COLUMNS = [
    {"key": "title", "label": "Note"},
    {"key": "tags", "label": "Tags", "width": 200},
    {"key": "edited", "label": "Edited", "width": 140, "sortable": False},
]
"""
            + _opens("Notes")
            + """

@nu.host
def rows(docs, folder, now):
    mine = sorted(((k, d) for k, d in docs.items() if d.get("folder") == folder), key=lambda kv: kv[1]["title"])
    return [{"key": k, "title": d["title"], "tags": ", ".join(d.get("tags") or []), "edited": text.ago(d.get("updated") or 0, now)} for k, d in mine]


def out(plane):
    def build(base, folder):
        return nu.ParallelAsync(redraws([Base.docs.on_change()], rows(Base.docs.extract(), folder, kit.now()), View.table.set_rows), opens(base))

    return View.head.set_label("In this notebook") >> View.note.set("") >> kit.on_doc(plane, build)
"""
        ),
    ),
)


#: The folder and tool pages' cells, by name.
VIEW_CELLS = {
    "handbook": (("pages", HANDBOOK), ("recent", RECENT)),
    "projects": (("projects", PROJECTS),),
    "meetings": (("new", MEETING_NEW), ("meetings", MEETINGS)),
    "decisions": (("decisions", DECISIONS),),
    "people": (("people", PEOPLE),),
    "notes": (("notes", NOTES),),
    "ask": (("ask", ASK),),
    "tasks": (("chart", TASKS_CHART), ("tasks", TASKS)),
    "facts": (("facts", FACTS), ("uses", FACT_USES)),
    "glossary": (("glossary", GLOSSARY),),
    "graph": (("graph", GRAPH),),
    "digest": (("digest", DIGEST),),
    "health": (("health", HEALTH),),
    "import": (("import", IMPORT),),
}
