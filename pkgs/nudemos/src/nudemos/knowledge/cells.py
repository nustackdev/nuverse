"""Larkspur's cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the id of the page it runs on comes in, and
:mod:`.kit` finds that page's root and its base (``B`` in a cell). Pages of one kind
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
import nuspace
import nuspace.web
import nustd.ui
from nudemos import pages
from nudemos.knowledge import kit, text, views
"""


def cell(body: str) -> str:
    """A cell's source: the shared imports, then ``body``."""
    return IMPORTS + "\n\n" + body


#: The pages' and facts' changes, the subscriptions most views follow.
CHANGES = "[B.docs.on_change(), B.facts.on_change()]"


# --- the root -------------------------------------------------------------------------------


WELCOME = cell("""\
class View(nustd.ui.Column):
    intro = nustd.ui.MarkdownRef.slot()
    q = nustd.ui.InputRef.slot(placeholder="Search pages and facts: battery, price, Ravi, LoRa...")
    hits = nustd.ui.ColumnRef.slot(nustd.ui.LineRef, gap=2)
    note = nustd.ui.TextRef.slot(tone="muted")


def hit(h):
    h = nu.Dict(h)
    line, link = View.hits[nu.Int(h["i"])], nu.Dict(h["link"])
    return (
        line[0].to(nustd.ui.LinkRef).set(href=link.get_item("href", ""), label=link["label"])
        >> line[1].to(nustd.ui.BadgeRef.slot(size="sm")).set(h["kind"])
        >> line[2].to(nustd.ui.TextRef.slot(tone="muted", size="sm")).set(h["excerpt"])
    )


def draw(v):
    rows = pages.linked(nu.Dict(v)["hits"], "link", "label")
    return nu.ForEachDo(rows, hit) >> View.hits.truncate(nu.List(rows).len()) >> View.note.set(v["note"])


def out(plane):
    def build(base, B):
        found = views.search(B.docs.extract(), B.facts.extract(), nu.Str(View.q), B.planes.extract())
        intro = views.welcome(B.facts.extract(), B.planes.extract(), kit.now())
        return View.intro.init() >> View.q.init() >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.facts.on_change()])), nu.let(nuspace.atomic(intro), View.intro.set), every=600.0),
            nu.ReactEvery(View.q.on_submit(), nu.let(found, draw)),
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


class View(nu.Shape):
    tiles = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=6, min_cell_width=150, gap=3)


def draw(t):
    def tile(k):
        s = t[k]
        return View.tiles[k][0].to(nustd.ui.StatRef).set(s["value"], label=KEYS[k], delta=s["delta"], trend=s["trend"])

    return nu.Sequential(*(tile(k) for k in KEYS))


def out(plane):
    def build(base, B):
        read = views.tiles(B.docs.extract(), B.facts.extract(), B.health.fallback({}), kit.now())
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change(), B.facts.on_change(), B.health.on_change()])), nu.let(nuspace.atomic(read), draw), every=15.0)

    return kit.on_base(plane, build)
""")


CAPTURE = cell("""\
class Line(nustd.ui.InputGroup):
    title = nustd.ui.InputRef.slot(placeholder="Capture a thought, a link, a question. It becomes a note in My notes.", required=True)
    add = nustd.ui.ButtonRef.slot(label="Capture", icon="plus", submit=True)


class Capture(nustd.ui.Form):
    line = Line.slot()


class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    form = Capture.slot(clear_on_submit=True)


def out(plane):
    form = View.form

    def build(base, B):
        def made(c):
            c = nu.Dict(c)
            slug = nu.Str(c["slug"])
            opened = View.history.push(kit.doc_href(B, slug))
            return kit.add_doc(base, slug, c["doc"], "captured") >> opened

        # Enter or Capture: one submit with the text, the field cleared.
        def add(sub):
            typed = nu.Str(sub["values"]["line"]["title"]).strip()
            return nu.let(views.capture(typed, B.docs.extract(), kit.now()), made)

        # The first run brings in the base: the folders, every page, then the checker.
        return kit.seed(base) >> nu.ReactEvery(form.on_submit(), add)

    return form.init() >> kit.on_base(plane, build)
""")


TASK_COLUMNS = """\
COLUMNS = [
    {"key": "done", "label": "Done", "kind": "bool", "width": 72},
    {"key": "task", "label": "Task", "editable": False},
    {"key": "owner", "label": "Owner", "editable": False, "width": 96, "hide_below": 640},
    {"key": "due", "label": "Due", "editable": False, "width": 130},
    {"key": "page", "label": "Written in", "editable": False, "width": 240, "hide_below": 800, "cell": nustd.ui.PageLinkRef.slot(variant="inline")},
]


def tick(B, ev):
    return nu.IfDo(nu.Str(ev["column"]) == "done", kit.tick(B, nu.Str(ev["key"]), nu.ToBool(ev["value"])))
"""


DUE = cell(
    TASK_COLUMNS
    + """

class View(nu.Shape):
    due = nustd.ui.CardRef.slot(
        title="Due this week",
        subtitle="Every task in every page, due in the next seven days or late. Tick one and its page changes.",
    )


TABLE = View.due[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", editable=True, density="compact", label="Due this week"))
MORE = View.due.footer[0].to(nustd.ui.LinkRef.slot(variant="muted", arrow=True))


def out(plane):
    def build(base, B):
        rows = views.task_rows(B.docs.extract(), B.planes.extract(), kit.now(), "", 7, False)
        tasks = nuspace.web.href(nuspace.atomic(kit.folder_page(B, "tasks")))

        def draw(r):
            left = views.more(r, 10)
            more = nu.IfDo(nu.Str(left) != "", MORE.set(href=tasks, label=left), MORE.erase())
            return TABLE.set_rows(pages.linked(views.first(r, 10), "page")) >> more

        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(rows), draw), every=60.0),
            nu.ReactEvery(TABLE.on_edit(), lambda ev: tick(B, ev)),
        )

    return kit.on_base(plane, build)
"""
)


ACTIVITY = cell("""\
class View(nu.Shape):
    activity = nustd.ui.CardRef.slot(title="What changed", subtitle="Newest first")


FEED = View.activity[0].to(nustd.ui.ColumnRef.slot(nustd.ui.LineRef, gap=0, max_height=360, scroll="y"))
EMPTY = View.activity[1].to(nustd.ui.TextRef.slot(tone="muted"))


def event(e):
    e = nu.Dict(e)
    line, link = FEED[nu.Int(e["i"])], nu.Dict(e["link"])
    page = line[2].to(nustd.ui.LinkRef)
    href = nu.Str(link.get_item("href", ""))
    return (
        line[0].to(nustd.ui.TextRef.slot(weight="medium")).set(e["who"])
        >> line[1].to(nustd.ui.TextRef).set(e["what"])
        >> nu.IfDo(href != "", page.set(href=href, label=link["label"]), page.erase())
        >> line[3].to(nustd.ui.RelativeTimeRef).set(e["at"])
    )


def draw(rows):
    rows = pages.linked(rows, "link", "label")
    n = nu.List(rows).len()
    return nu.ForEachDo(rows, event) >> FEED.truncate(n) >> EMPTY.set(nu.If(n == 0, "Nothing has happened yet.", ""))


def out(plane):
    def build(base, B):
        read = views.activity(B.log.fallback([]), B.docs.extract(), B.planes.extract(), 12)
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.log.on_change()])), nu.let(nuspace.atomic(read), draw))

    return kit.on_base(plane, build)
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
class Head(nustd.ui.Line):
    kind = nustd.ui.BadgeRef.slot(variant="neutral")
    status = nustd.ui.BadgeRef.slot()
    by = nustd.ui.TextRef.slot(value="Owner", tone="muted")
    owner = nustd.ui.LinkRef.slot()
    edited = nustd.ui.TextRef.slot(value="edited", tone="muted")
    when = nustd.ui.RelativeTimeRef.slot()
    rest = nustd.ui.TextRef.slot(tone="muted")


class View(nu.Shape):
    head = Head.slot(wrap=True)


def draw(v):
    h, owner = View.head, nu.Dict(v["owner"])
    page = nu.Str(owner["page"])
    return (
        h.kind.set(v["kind"]) >> h.status.set(v["second"], variant=v["second_tone"])
        >> h.owner.set(href=nu.If(page != "", nuspace.web.href(page), ""), label=owner["label"])
        >> h.when.set(v["edited"]) >> h.rest.set(v["rest"])
    )


def out(plane):
    read = lambda B, slug: views.doc_head(B.docs.extract(), B.health.fallback({}), slug, B.planes.extract())
    return View.head.init() >> kit.on_doc(plane, lambda base, B, slug: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change(), B.health.on_change()])), nu.let(nuspace.atomic(read(B, slug)), draw)))
""")


PAGE = cell(f"""\
def out(plane):
    page = nustd.ui.MarkdownRef("page")
    return kit.on_doc(plane, lambda base, B, slug: nu.Reconcile(nuspace.atomic(nu.OnAny(*{CHANGES})), nu.let(nuspace.atomic(views.page(B.docs.extract(), B.facts.extract(), slug, B.planes.extract(), kit.now())), page.set), every=60.0))
""")


LINKS = cell("""\
class View(nu.Shape):
    links = nustd.ui.GridRef.slot(cols="3fr 2fr", gap=4, stack_below=800)


BACK = View.links[0, 0].to(nustd.ui.CardRef.slot(title="Linked from", size="sm"))
BACK_LINES = BACK[0].to(nustd.ui.ColumnRef.slot(nustd.ui.LineRef, gap=2))
BACK_NONE = BACK[1].to(nustd.ui.TextRef.slot(tone="muted"))
OUT = View.links[0, 1].to(nustd.ui.CardRef.slot(title="Links to", size="sm"))
OUT_LINKS = OUT[0].to(nustd.ui.RowRef.slot(gap=3, wrap=True))
OUT_NONE = OUT[1].to(nustd.ui.TextRef.slot(tone="muted"))
BROKEN = OUT.footer[0].to(nustd.ui.TextRef.slot(tone="danger", size="sm"))


def back(r):
    r = nu.Dict(r)
    line, link = BACK_LINES[nu.Int(r["i"])], nu.Dict(r["link"])
    return (
        line[0].to(nustd.ui.LinkRef).set(href=link.get_item("href", ""), label=link["label"])
        >> line[1].to(nustd.ui.TextRef.slot(tone="muted", size="sm")).set(r["excerpt"])
    )


def out_link(r):
    r = nu.Dict(r)
    link = nu.Dict(r["link"])
    return OUT_LINKS[nu.Int(r["i"])].to(nustd.ui.LinkRef).set(href=link.get_item("href", ""), label=link["label"])


def draw(v):
    v = nu.Dict(v)
    backs, outs = pages.linked(v["back"], "link", "label"), pages.linked(v["out"], "link", "label")
    nb, no = nu.List(backs).len(), nu.List(outs).len()
    return (
        BACK.set_subtitle(v["back_count"]) >> nu.ForEachDo(backs, back) >> BACK_LINES.truncate(nb)
        >> BACK_NONE.set(nu.If(nb == 0, "Nothing links here yet.", ""))
        >> OUT.set_subtitle(v["out_count"]) >> nu.ForEachDo(outs, out_link) >> OUT_LINKS.truncate(no)
        >> OUT_NONE.set(nu.If(no == 0, "No links out.", "")) >> BROKEN.set(v["broken"])
    )


def out(plane):
    read = lambda B, slug: views.doc_links(B.docs.extract(), B.facts.extract(), slug, B.planes.extract())
    return kit.on_doc(plane, lambda base, B, slug: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change(), B.facts.on_change()])), nu.let(nuspace.atomic(read(B, slug)), draw)))
""")


EDIT = cell("""\
class Edit(nustd.ui.Collapsible):
    title = nustd.ui.InputRef.slot(label="Title")
    source = nustd.ui.CodeRef.slot(language="markdown", readonly=False, wrap=True, min_height=220, max_height=560)
    tags = nustd.ui.TagInputRef.slot(label="Tags", placeholder="A tag, then Enter")
    save = nustd.ui.ButtonRef.slot(label="Save page", icon="save")
    hint = nustd.ui.TextRef.slot()


class View(nu.Shape):
    edit = Edit.slot(title="Edit the source", open=False)


HINT = "[[slug]] links a page, {{key}} cites a fact, @name a person, - [ ] a task with @owner due:YYYY-MM-DD, {{query open-decisions}} a live table."


def out(plane):
    def build(base, B, slug):
        doc, e = B.docs[slug], View.edit
        show = e.title.set(doc.title.fallback("")) >> e.source.set(doc.body.fallback("")) >> e.tags.set(nu.list(doc.tags))
        title = nu.Str(e.title).strip()
        kept = (
            doc.title.set(title) >> doc.body.set(nu.Str(e.source)) >> doc.tags.set(nu.List(e.tags))
            >> kit.touched(B, doc, slug, "edited")
        )
        # Two commits: the page in the base, then the plane's name.
        save = nuspace.atomic(kept) >> nuspace.atomic(nuspace.plane.rename(plane, title))
        return show >> e.save.init() >> e.hint.set(HINT) >> nu.ParallelAsync(
            nu.ReactEvery(e.save.on_click(), nu.IfDo(title != "", save)),
            nu.ReactEvery(doc.body.on_change(), e.source.set(doc.body.fallback(""))),
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
    numbers = Numbers.slot(max_columns=3, min_cell_width=150, gap=3)


def draw(v):
    n = View.numbers
    return (
        View.progress.set(v["value"], caption=v["caption"]) >> n.late.set(v["late"], delta=v["late_note"])
        >> n.top.set(v["top"], delta=v["top_note"]) >> n.meetings.set(v["meetings"])
    )


def out(plane):
    return kit.on_doc(plane, lambda base, B, slug: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(views.project_view(B.docs.extract(), slug, kit.now())), draw), every=60.0))
""")


DECIDE = cell("""\
class Decide(nustd.ui.Row):
    status = nustd.ui.SelectRef.slot(options=["open", "decided", "superseded"])
    note = nustd.ui.TextRef.slot()


class View(nu.Shape):
    decide = Decide.slot(gap=3, align="center")


NOTE = "Open decisions show on Home, in the digest and in every page that asks for them."


def out(plane):
    def build(base, B, slug):
        doc, d = B.docs[slug], View.decide
        changed = nu.Str(d.status) != nu.Str(doc.status.fallback("open"))
        return d.note.set(NOTE) >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(doc.status.fallback("open")), d.status.set)),
            nu.ReactEvery(d.status.on_change(), nu.IfDo(changed, kit.set_status(B, slug, nu.Str(d.status)))),
        )

    return kit.on_doc(plane, build)
""")


PROFILE = cell("""\
class Head(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="xl")
    role = nustd.ui.TextRef.slot(tone="secondary")


class Numbers(nustd.ui.Grid):
    owns = nustd.ui.StatRef.slot(label="Pages owned")
    open = nustd.ui.StatRef.slot(label="Open tasks")
    late = nustd.ui.StatRef.slot(label="Late")
    edits = nustd.ui.StatRef.slot(label="Edits, two weeks")


class View(nustd.ui.Column):
    head = Head.slot(gap=4, align="center")
    numbers = Numbers.slot(max_columns=4, min_cell_width=130, gap=3)


def draw(v):
    n = View.numbers
    return (
        View.head.role.set(v["role"]) >> n.owns.set(v["owns"]) >> n.open.set(v["open"])
        >> n.late.set(v["late"]) >> n.edits.set(v["edits"])
    )


def out(plane):
    def build(base, B, slug):
        name = B.docs[slug].title.fallback("")
        return View.head.face.set("", name=name) >> nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(views.person_view(B.docs.extract(), slug, kit.now())), draw), every=60.0)

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


def _folder(name: str, title: str, subtitle: str = "", extra: str = "") -> str:
    """The shared part of a folder's cell: a card holding a table of its pages, each title a link."""
    return f"""\
class View(nustd.ui.Column):
    pages = nustd.ui.CardRef.slot(title="{title}", subtitle="{subtitle}")
{extra}

TABLE = View.pages[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="{name}"))


def shown(rows):
    return TABLE.set_rows(pages.linked(rows, "title"))
"""


#: A folder's page column: the title, a link to the page.
TITLE = '{"key": "title", "label": "%s", "cell": nustd.ui.PageLinkRef.slot(variant="inline")}'

#: A column of when something was last edited, drawn as time from now.
EDITED = (
    '{"key": "%s", "label": "%s", "width": 130, "align": "end", "cell": nustd.ui.RelativeTimeRef}'
)


HANDBOOK = cell(
    f"""\
COLUMNS = [
    {TITLE % "Page"},
    {{"key": "owner", "label": "Owner", "width": 160, "hide_below": 640}},
    {EDITED % ("edited", "Edited")},
    {{"key": "fresh", "label": "Fresh", "width": 100, "cell": nustd.ui.BadgeRef.slot(size="sm")}},
    {{"key": "links", "label": "Linked from", "kind": "number", "width": 120, "align": "end", "hide_below": 640}},
]
"""
    + _folder(
        "Handbook",
        "Every topic",
        "How Larkspur works, one page per topic. A page untouched for too long is flagged by the checker.",
    )
    + """

def out(plane):
    def build(base, B):
        rows = views.pages_rows(B.docs.extract(), B.health.fallback({}), "wiki", B.planes.extract())
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change(), B.health.on_change()])), nu.let(nuspace.atomic(rows), shown))

    return kit.on_base(plane, build)
"""
)


RECENT = cell("""\
def out(plane):
    md = nustd.ui.MarkdownRef("recent")
    read = lambda B: nu.Str("### Recently edited\\n\\n") + views.page_query("recent", "8", B.docs.extract(), B.facts.extract(), B.planes.extract(), kit.now())
    return kit.on_base(plane, lambda base, B: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(read(B)), md.set), every=60.0))
""")


PROJECTS = cell(
    f"""\
COLUMNS = [
    {TITLE % "Project"},
    {{"key": "owner", "label": "Owner", "width": 150, "hide_below": 640}},
    {{"key": "status", "label": "Status", "width": 110, "cell": nustd.ui.StatusPillRef}},
    {{"key": "progress", "label": "Done", "width": 140, "cell": nustd.ui.ProgressRef}},
    {{"key": "open", "label": "Open tasks", "kind": "number", "width": 110, "align": "end"}},
    {{"key": "next", "label": "Next due", "width": 140, "hide_below": 800}},
]
"""
    + _folder(
        "Projects",
        "Every project",
        "Progress is counted from the tasks in each project page and in every page that links it.",
        '    tasks = nustd.ui.CardRef.slot(title="Tasks by project", subtitle="Done and open")\n',
    )
    + """

CHART = View.tasks[0].to(nustd.ui.Chart.slot(height=240))


def draw(v):
    return shown(nu.Dict(v)["rows"]) >> CHART.set(option=views.projects_chart(v))


def out(plane):
    def build(base, B):
        read = views.projects_view(B.docs.extract(), B.planes.extract(), kit.now())
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(read), draw), every=60.0)

    return kit.on_base(plane, build)
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
    history = nustd.ui.HistoryRef.slot()
    form = Form.slot(title="New meeting note", open=True)


@nu.host
def projects(docs):
    return [{"value": k, "label": d["title"]} for k, d in sorted(docs.items()) if d.get("kind") == "project"]


HINT = "The note writes itself: who is there, what is still open for them on that project, the open decisions, and a link to last time."


def out(plane):
    f = View.form

    def build(base, B):
        def made(c):
            c = nu.Dict(c)
            slug = nu.Str(c["slug"])
            return kit.add_doc(base, slug, c["doc"], "wrote up") >> f.line.title.set("") >> View.history.push(kit.doc_href(B, slug))

        new = views.meeting_new(nu.Str(f.line.title), nu.Str(f.line.project).fallback(""), nu.List(f.people), "", B.docs.extract(), kit.now())
        return f.line.project.set_options(projects(B.docs.extract())) >> nu.ReactEvery(f.write.on_click(), nu.let(new, made))

    return f.line.title.init() >> f.people.init() >> f.write.init() >> f.hint.set(HINT) >> kit.on_base(plane, build)
""")


MEETINGS = cell(
    f"""\
COLUMNS = [
    {{"key": "date", "label": "Date", "width": 120, "sortable": False}},
    {TITLE % "Meeting"},
    {{"key": "people", "label": "People", "kind": "number", "width": 90, "align": "end", "hide_below": 640}},
    {{"key": "decisions", "label": "Decisions", "kind": "number", "width": 110, "align": "end"}},
    {{"key": "open", "label": "Open items", "kind": "number", "width": 110, "align": "end"}},
]
"""
    + _folder("Meetings", "Every meeting", "Newest first.")
    + """

def out(plane):
    return kit.on_base(plane, lambda base, B: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(views.meetings_rows(B.docs.extract(), B.planes.extract())), shown)))
"""
)


DECISIONS = cell(
    f"""\
COLUMNS = [
    {{"key": "title", "label": "Decision", "editable": False, "cell": nustd.ui.PageLinkRef.slot(variant="inline")}},
    {{"key": "status", "label": "Status", "kind": "select", "options": ["open", "decided", "superseded"], "width": 140}},
    {{"key": "owner", "label": "Owner", "editable": False, "width": 150, "hide_below": 640}},
    {EDITED[:-1] % ("touched", "Last touched")}, "editable": False}},
    {{"key": "cited", "label": "Cited by", "kind": "number", "editable": False, "width": 100, "align": "end"}},
]


class View(nu.Shape):
    decisions = nustd.ui.CardRef.slot(
        title="Decisions",
        subtitle="Change a status here and the decision's page, Home, the digest and every open-decisions table follow.",
    )


TABLE = View.decisions[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", editable=True, density="compact", label="Decisions"))


def edit(B, ev):
    return nu.IfDo(nu.Str(ev["column"]) == "status", kit.set_status(B, nu.Str(ev["key"]), nu.Str(ev["value"])))


def out(plane):
    def build(base, B):
        rows = pages.linked(views.decisions(B.docs.extract(), B.planes.extract()), "title")
        return nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(rows), TABLE.set_rows)), nu.ReactEvery(TABLE.on_edit(), lambda ev: edit(B, ev)))

    return kit.on_base(plane, build)
"""
)


PEOPLE = cell("""\
class Name(nustd.ui.Column):
    link = nustd.ui.LinkRef.slot()
    role = nustd.ui.TextRef.slot(tone="secondary", size="sm")
    note = nustd.ui.TextRef.slot(tone="muted", size="sm")


class Face(nustd.ui.Row):
    face = nustd.ui.AvatarRef.slot(size="lg")
    name = Name.slot(gap=0)


class View(nustd.ui.Column):
    intro = nustd.ui.TextRef.slot(value="Seven of us. Each person's page lists what they own and what is on them, live.", tone="muted")
    faces = nustd.ui.GridRef.slot(nustd.ui.CardRef.slot(size="sm"), max_columns=3, min_cell_width=260, gap=3)


def one(r):
    r = nu.Dict(r)
    f, link = View.faces[nu.Str(r["slug"])][0].to(Face.slot(gap=3)), nu.Dict(r["link"])
    return (
        f.face.set("", name=r["name"]) >> f.name.link.set(href=link.get_item("href", ""), label=link["label"])
        >> f.name.role.set(r["role"]) >> f.name.note.set(r["note"])
    )


def draw(rows):
    return nu.ForEachDo(pages.linked(rows, "link", "label"), one)


def out(plane):
    return View.intro.init() >> kit.on_base(plane, lambda base, B: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(views.people_cards(B.docs.extract(), B.planes.extract())), draw)))
""")


NOTES = cell(
    f"""\
COLUMNS = [
    {TITLE % "Note"},
    {{"key": "from", "label": "From", "width": 170, "hide_below": 640}},
    {{"key": "tags", "label": "Tags", "width": 200, "hide_below": 800}},
    {EDITED % ("edited", "Edited")},
]
"""
    + _folder(
        "My notes",
        "Every note",
        "My second brain: reading notes, half thoughts, captures from Home, and notebooks brought in from elsewhere.",
    )
    + """

def out(plane):
    return kit.on_base(plane, lambda base, B: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(views.notes_rows(B.docs.extract(), B.planes.extract())), shown)))
"""
)


TASKS = cell(
    TASK_COLUMNS
    + """

class View(nu.Shape):
    tasks = nustd.ui.CardRef.slot(title="Tasks", subtitle="Tasks live in the pages they are written in. This is a query over all of them.")


WHO = View.tasks.actions[0].to(nustd.ui.SelectRef.slot(placeholder="Everyone"))
DONE = View.tasks.actions[1].to(nustd.ui.SwitchRef.slot(label="Show done"))
TABLE = View.tasks[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", editable=True, density="compact", label="Tasks"))

PEOPLE = [{"value": "", "label": "Everyone"}] + [{"value": k, "label": v} for k, v in kit.NAMES.items()]


def out(plane):
    def build(base, B):
        rows = pages.linked(views.task_rows(B.docs.extract(), B.planes.extract(), kit.now(), nu.Str(WHO).fallback(""), -1, nu.Bool(DONE)), "page")
        again = nu.let(rows, TABLE.set_rows)
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(rows), TABLE.set_rows), every=60.0),
            nu.ReactEvery(WHO.on_change(), again),
            nu.ReactEvery(DONE.on_change(), again),
            nu.ReactEvery(TABLE.on_edit(), lambda ev: tick(B, ev)),
        )

    return WHO.set_options(PEOPLE) >> WHO.init() >> DONE.init() >> kit.on_base(plane, build)
"""
)


TASKS_CHART = cell("""\
class View(nu.Shape):
    chart = nustd.ui.CardRef.slot(title="Open tasks by person", subtitle="Late, due this week, and later")


CHART = View.chart[0].to(nustd.ui.Chart.slot(height=260))


def draw(v):
    return CHART.set(option=views.tasks_option(v))


def out(plane):
    return kit.on_base(plane, lambda base, B: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(views.tasks_chart(B.docs.extract(), kit.now())), draw), every=60.0))
""")


FACTS = cell(
    f"""\
COLUMNS = [
    {{"key": "label", "label": "Fact", "editable": False}},
    {{"key": "value", "label": "Value", "width": 240}},
    {{"key": "cite", "label": "Cite as", "editable": False, "width": 170, "hide_below": 800}},
    {{"key": "owner", "label": "Owner", "editable": False, "width": 100, "hide_below": 640}},
    {{"key": "cited", "label": "Cited on", "kind": "number", "editable": False, "width": 100, "align": "end"}},
    {EDITED[:-1] % ("changed", "Changed")}, "editable": False}},
]


class View(nu.Shape):
    facts = nustd.ui.CardRef.slot(
        title="Facts",
        subtitle="Each fact is written once and cited on pages as {{{{key}}}}. Change a value here and every page citing it follows.",
    )


TABLE = View.facts[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", editable=True, density="compact", label="Facts"))


def edit(B, ev):
    value = nu.Str(ev["value"]).strip()
    return nu.IfDo((nu.Str(ev["column"]) == "value").and_(value != ""), kit.set_fact(B, nu.Str(ev["key"]), value))


def out(plane):
    def build(base, B):
        rows = views.facts_rows(B.docs.extract(), B.facts.extract())
        return nu.ParallelAsync(nu.Reconcile(nuspace.atomic(nu.OnAny(*{CHANGES})), nu.let(nuspace.atomic(rows), TABLE.set_rows)), nu.ReactEvery(TABLE.on_edit(), lambda ev: edit(B, ev)))

    return kit.on_base(plane, build)
"""
)


FACT_USES = cell(f"""\
class Use(nustd.ui.Column):
    head = nustd.ui.LineRef.slot()
    where = nustd.ui.RowRef.slot(gap=3, wrap=True)


class View(nu.Shape):
    uses = nustd.ui.CardRef.slot(title="Where each fact is cited")


USES = View.uses[0].to(nustd.ui.ColumnRef.slot(Use.slot(gap=1), gap=3, divided=True))
EMPTY = View.uses[1].to(nustd.ui.TextRef.slot(tone="muted"))


def head(h):
    h = nu.Dict(h)
    use = USES[nu.Int(h["i"])]
    return (
        use.head[0].to(nustd.ui.TextRef.slot(weight="medium")).set(h["label"])
        >> use.head[1].to(nustd.ui.BadgeRef.slot(variant="neutral", size="sm")).set(h["value"])
        >> use.where.truncate(h["n"])
    )


def link(r):
    r = nu.Dict(r)
    to = nu.Dict(r["link"])
    return USES[nu.Int(r["i"])].where[nu.Int(r["j"])].to(nustd.ui.LinkRef).set(href=to.get_item("href", ""), label=to["label"])


def draw(v):
    v = nu.Dict(v)
    n = nu.List(v["heads"]).len()
    return (
        nu.ForEachDo(pages.linked(v["links"], "link", "label"), link) >> nu.ForEachDo(v["heads"], head)
        >> USES.truncate(n) >> EMPTY.set(nu.If(n == 0, "No page cites a fact yet.", ""))
    )


def out(plane):
    read = lambda B: views.fact_uses(B.docs.extract(), B.facts.extract(), B.planes.extract())
    return kit.on_base(plane, lambda base, B: nu.Reconcile(nuspace.atomic(nu.OnAny(*{CHANGES})), nu.let(nuspace.atomic(read(B)), draw)))
""")


GLOSSARY = cell("""\
COLUMNS = [
    {"key": "term", "label": "Term", "width": 220},
    {"key": "meaning", "label": "What it means", "wrap": "wrap"},
    {"key": "used", "label": "Used on", "kind": "number", "width": 100, "align": "end"},
]


class View(nu.Shape):
    glossary = nustd.ui.CardRef.slot(
        title="Glossary",
        subtitle="The words we use. How many pages use each is counted from the pages as they are now.",
    )


TABLE = View.glossary[0].to(nustd.ui.DataTableRef.slot(columns=COLUMNS, row_key="key", density="compact", label="Glossary"))


def out(plane):
    return kit.on_base(plane, lambda base, B: nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(views.glossary_rows(B.docs.extract())), TABLE.set_rows)))
""")


GRAPH = cell("""\
class View(nu.Shape):
    history = nustd.ui.HistoryRef.slot()
    board = nustd.ui.GridRef.slot(cols="2fr 1fr", gap=4, stack_below=900)


MAP = View.board[0, 0].to(nustd.ui.CardRef.slot(title="Every page and every link"))
CHART = MAP[0].to(nustd.ui.Chart.slot(height=560))
NOTE = MAP.footer[0].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))
SIDE = View.board[0, 1].to(nustd.ui.ColumnRef.slot(gap=4))
HUBS = SIDE[0].to(nustd.ui.CardRef.slot(title="Most connected", size="sm"))
HUB_LINES = HUBS[0].to(nustd.ui.ColumnRef.slot(nustd.ui.LineRef, gap=2))
ALONE = SIDE[1].to(nustd.ui.CardRef.slot(title="Islands", size="sm"))
ALONE_LINES = ALONE[0].to(nustd.ui.ColumnRef.slot(nustd.ui.LineRef, gap=2))


def hub(r):
    r = nu.Dict(r)
    line, link = HUB_LINES[nu.Int(r["i"])], nu.Dict(r["link"])
    return (
        line[0].to(nustd.ui.LinkRef).set(href=link.get_item("href", ""), label=link["label"])
        >> line[1].to(nustd.ui.TextRef.slot(tone="muted", size="sm")).set(r["count"])
    )


def alone(r):
    r = nu.Dict(r)
    link = nu.Dict(r["link"])
    return ALONE_LINES[nu.Int(r["i"])][0].to(nustd.ui.LinkRef).set(href=link.get_item("href", ""), label=link["label"])


def side(v):
    v = nu.Dict(v)
    hubs, lone = pages.linked(v["hubs"], "link", "label"), pages.linked(v["alone"], "link", "label")
    return (
        MAP.set_subtitle(v["size"]) >> nu.ForEachDo(hubs, hub) >> HUB_LINES.truncate(nu.List(hubs).len())
        >> ALONE.set_subtitle(v["alone_count"]) >> nu.ForEachDo(lone, alone) >> ALONE_LINES.truncate(nu.List(lone).len())
    )


def out(plane):
    def build(base, B):
        docs = B.docs.extract()
        changed = nu.OnAny(*[B.docs.on_change()])
        drawn = nu.Reconcile(nuspace.atomic(changed), nu.let(nuspace.atomic(views.graph_option(docs, B.planes.extract())), lambda v: CHART.set(option=v)))
        sided = nu.Reconcile(nuspace.atomic(changed), nu.let(nuspace.atomic(views.graph_side(docs, B.planes.extract())), side))
        # A page's dot opens its page; an edge or the legend names no page, and does nothing.
        go = lambda s: nu.IfDo(nu.Str(s) != "", View.history.push(kit.doc_href(B, nu.Str(s))))
        opened = nu.ReactEvery(CHART.on_click(), lambda ev: nu.let(views.slug_named(nu.str(nu.Dict(ev).get_item("name", "")), B.docs.extract()), go))
        return nu.ParallelAsync(drawn, sided, opened)

    note = "Drawn from the pages as they are. Hover a page to see its neighbours, click it to open it."
    return NOTE.set(note) >> kit.on_base(plane, build)
""")


DIGEST = cell(f"""\
class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot()
    digest = nustd.ui.MarkdownRef.slot()


def out(plane):
    def build(base, B):
        read = views.digest(B.docs.extract(), B.facts.extract(), B.log.fallback([]), B.planes.extract(), kit.now())
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*{CHANGES} + [B.log.on_change(), B.health.on_change()])), nu.let(nuspace.atomic(read), View.digest.set), every=60.0)

    note = "Nobody writes this page. It is written from the base, and rewrites itself as the week moves."
    return View.note.set(note) >> kit.on_base(plane, build)
""")


HEALTH = cell("""\
class Bar(nustd.ui.Row):
    dot = nustd.ui.StatusDotRef.slot(tone="neutral")
    pill = nustd.ui.StatusPillRef.slot()
    line = nustd.ui.TextRef.slot()
    when = nustd.ui.RelativeTimeRef.slot()


class Top(nustd.ui.Row):
    score = nustd.ui.GaugeRef.slot()
    trend = nustd.ui.Sparkline.slot(area=True, height=64, max_points=60, option={"yAxis": {"min": 0, "max": 100}})


class Act(nustd.ui.Row):
    reviewed = nustd.ui.ButtonRef.slot(label="Mark stale pages reviewed", icon="square-check-big", variant="secondary")
    hint = nustd.ui.TextRef.slot(tone="muted")


class View(nustd.ui.Column):
    bar = Bar.slot(gap=3, wrap=True)
    top = Top.slot(gap=6, grow={"trend": 1})
    act = Act.slot(gap=3, wrap=True)
    issues = nustd.ui.CardRef.slot(title="Issues")


TABLE = View.issues[0].to(
    nustd.ui.DataTableRef.slot(
        columns=[
            {"key": "issue", "label": "Issue", "width": 140, "cell": nustd.ui.BadgeRef.slot(size="sm")},
            {"key": "page", "label": "Page", "width": 260, "cell": nustd.ui.PageLinkRef.slot(variant="inline")},
            {"key": "owner", "label": "Owner", "width": 100, "hide_below": 640},
            {"key": "detail", "label": "Detail", "hide_below": 800},
        ],
        row_key="key", density="compact", label="Issues",
    )
)


def draw(v):
    b, t = View.bar, View.top
    return (
        b.dot.set(v["tone"], pulse=v["pulse"]) >> b.pill.set(v["status"], tone=v["tone"]) >> b.line.set(v["line"])
        >> nu.IfDo(nu.Float(v["checked"]) > 0, b.when.set(v["checked"]), b.when.erase())
        >> t.score.set(v["gauge"], caption=v["caption"]) >> t.trend.set(v["history"])
        >> TABLE.set_rows(pages.linked(v["rows"], "page"))
    )


@nu.host
def stale(health):
    return [s["doc"] for s in (health or {}).get("stale", [])]


def out(plane):
    def build(base, B):
        read = views.health_view(B.health.fallback({}), kit.live(base, "checker"), B.docs.extract(), B.planes.extract())
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.health.on_change()])), nu.let(nuspace.atomic(read), draw), every=5.0),
            nu.ReactEvery(View.act.reviewed.on_click(), kit.reviewed(B, stale(B.health.fallback({})))),
        )

    hint = "The checker runs in its own process: on every change, and every 20 seconds. Each issue links its page."
    # The bar and the gauge first, so they draw above the button whatever lands first.
    drawn = View.bar.init() >> View.top.init() >> View.act.hint.set(hint) >> View.act.reviewed.init()
    return drawn >> View.issues.init() >> kit.on_base(plane, build)
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

    def build(base, B):
        read = views.imports_view(B.imports.fallback({}), kit.live(base, "importer"), kit.now())
        start = kit.start_import(base, nu.Str(p.source))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.imports.on_change()])), nu.let(nuspace.atomic(read), draw), every=10.0),
            nu.ReactEvery(p.go.on_click(), start),
        )

    return View.note.set(NOTE) >> p.source.set_options(sources()) >> p.source.set("lab-notebook") >> p.go.init() >> kit.on_base(plane, build)
""")


ASK = cell("""\
import nustd.cc
from nudemos.knowledge.ask import OPTIONS, Asker, answered, asked, shown

TRIES = ("What is still blocking the launch?", "Why did we pick LoRa?", "What is Theo working on this week?")


class Asking(nustd.ui.InputGroup):
    q = nustd.ui.InputRef.slot(placeholder="Ask anything the base knows: dates, owners, why we decided something...", required=True)
    go = nustd.ui.ButtonRef.slot(label="Ask", icon="sparkles", submit=True)


class Ask(nustd.ui.Form):
    line = Asking.slot()


class View(nustd.ui.Column):
    note = nustd.ui.TextRef.slot(tone="muted")
    box = Ask.slot(busy_on_submit=True)
    tries = nustd.ui.RowRef.slot(gap=2, wrap=True)
    status = nustd.ui.TextRef.slot()
    answer = nustd.ui.MarkdownRef.slot()
    line = nustd.ui.TextRef.slot()
    before = nustd.ui.MarkdownRef.slot()


NOTE = "Claude reads the whole base as it is right now, every page with its facts filled in, and answers with links to the pages it used."
LEAD = View.tries[0].to(nustd.ui.TextRef.slot(tone="muted", size="sm"))
TRY = [View.tries[i + 1].to(nustd.ui.ButtonRef.slot(variant="secondary", size="sm")) for i in range(len(TRIES))]


def out(plane):
    b = View.box

    def build(base, B):
        def ask(question):
            def call(started):
                prompt = asked(B.docs.extract(), B.facts.extract(), question)
                reply = Asker.answer(prompt=prompt)
                return nu.let(reply, lambda r: B.asks.set(answered(B.asks.fallback([]), r, question, started)))

            reading = nu.Str("Reading ") + nu.ToStr(nu.Dict(B.docs.extract()).len()) + " pages..."
            failed = lambda err: View.status.set(nu.Str("Could not ask: ") + nu.ToStr(err))
            # Busy while Claude reads: the form takes no other ask, Ask spins.
            return (
                View.status.set(reading) >> b.set_busy(True)
                >> nu.TryCatch(nu.let(kit.now(), call) >> View.status.set(""), catch=failed)
                >> b.set_busy(False)
            )

        def tried(ref, question):
            return nu.ReactEvery(ref.on_click(), b.line.q.set(question) >> ask(question))

        draw = lambda v: View.answer.set(v["answer"]) >> View.line.set(v["line"]) >> View.before.set(v["before"])
        read = shown(B.asks.fallback([]), B.docs.extract(), B.facts.extract(), B.planes.extract(), kit.now())
        body = nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.asks.on_change(), B.docs.on_change()])), nu.let(nuspace.atomic(read), draw), every=30.0),
            nu.ReactEvery(b.on_submit(), lambda sub: ask(nu.Str(sub["values"]["line"]["q"]).strip())),
            *(tried(ref, q) for ref, q in zip(TRY, TRIES, strict=True)),
        )
        return nu.With(nustd.cc.bind(Asker, **OPTIONS), body=body)

    shown_first = (
        View.note.set(NOTE) >> b.init() >> LEAD.set("Try")
        >> nu.Sequential(*(ref.set(q) for ref, q in zip(TRY, TRIES, strict=True)))
    )
    return shown_first >> kit.on_base(plane, build)
""")


COLLECTION = (
    (
        "pages",
        cell(
            f"""\
COLUMNS = [
    {TITLE % "Note"},
    {{"key": "tags", "label": "Tags", "width": 200, "hide_below": 640}},
    {EDITED % ("edited", "Edited")},
]
"""
            + _folder("Notes", "In this notebook")
            + """

@nu.host
def rows(docs, folder, planes):
    mine = sorted(((k, d) for k, d in docs.items() if d.get("folder") == folder), key=lambda kv: kv[1]["title"])
    return [
        {"key": k, "title": {"page": text.page_of(planes, k), "label": d["title"]}, "tags": ", ".join(d.get("tags") or []), "edited": (d.get("updated") or 0) * 1000}
        for k, d in mine
    ]


def out(plane):
    def build(base, B, folder):
        return nu.Reconcile(nuspace.atomic(nu.OnAny(*[B.docs.on_change()])), nu.let(nuspace.atomic(rows(B.docs.extract(), folder, B.planes.extract())), shown))

    return kit.on_doc(plane, build)
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
