"""The desk's cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the id of the page it runs on comes in, and
:mod:`.kit` brackets it over the desk (:data:`~.kit.DESK`), found by its
key wherever the page sits. Pages of one kind
run the same cells: twenty-odd source pages, one program each, told apart by
their page's meta.

- The desk (:data:`ROOT`): welcome, pulse, the week, the board, what happened lately.
- Reading list (:data:`READING`) and a source page (:data:`SOURCE`).
- Claims (:data:`CLAIMS`) and a claim page (:data:`CLAIM`): standing, history, evidence, our take.
- Models (:data:`MODELS`).
- Evals (:data:`EVALS`) and a run page (:data:`RUN`).
- Watch (:data:`WATCH`), the probe's page.
- Notebook (:data:`NOTEBOOK`).

Rows that name a page carry ``{"page": id, "label": text}``; :func:`nudemos.pages.linked`
turns them into link cells as they are drawn.
"""

from __future__ import annotations


__all__ = [
    "CLAIM",
    "CLAIMS",
    "EVALS",
    "MODELS",
    "NOTEBOOK",
    "READING",
    "ROOT",
    "RUN",
    "SOURCE",
    "WATCH",
]


# --- the desk ------------------------------------------------------------------------------------


WELCOME = r'''
import nu
import nuspace
import nuspace.web as web
from nustd import ui
from nudemos.research import kit

TEXT = """\
A three-person desk on what is new in large language models, and what of it holds up.
Papers come in and get read, their claims go on the board, and our own eval runs on Claude weigh in next to them.
Every source, claim and run is a page, and every block on a page is a small program: open its code, change it, run it again.
"""

SECTIONS = {
    "reading": "The papers, a page each with our notes",
    "claims": "Every claim, scored live from its evidence",
    "models": "The models as their reports give them",
    "evals": "Our own suite, run on Claude",
    "watch": "A probe that asks Claude every few minutes",
    "notebook": "Dated entries, some written from live numbers",
}


class View(ui.Column):
    about = ui.MarkdownRef.slot()
    sections = ui.GridRef.slot(max_columns=3, min_cell_width=200, gap=3)


def links():
    tile = lambda name: View.sections[name].to(ui.PageLinkRef.slot(variant="tile"))
    return nuspace.atomic(nu.Sequential(*(
        web.link(tile(name), kit.section_plane(name), description=about) for name, about in SECTIONS.items()
    )))


def out(plane):
    # The first open brings in the sections, the sources, the claims and the runs, each a page, and starts the probe.
    return View.about.set(TEXT) >> kit.on_desk(plane, lambda base: kit.seed(base) >> links() >> nu.ForeverDo(nu.Delay(3600.0)))
'''


PULSE = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit, views


KEYS = {"sources": "Sources", "claims": "Claims", "evidence": "Evidence", "runs": "Eval runs", "probe": "Probe", "spend": "Spent on Claude"}


class View(nu.Shape):
    tiles = ui.GridRef.slot(max_columns=6, min_cell_width=140, gap=3)


@nu.host
def pulse(d):
    sources, runs, probes = d["sources"], d["runs"], d["probes"] or []
    sc = views.scores(d["claims"], d["evidence"], runs, d["models"], probes)
    done = [r for r in runs.values() if r.get("status") == "done"]
    live = [r for r in runs.values() if r.get("status") in ("queued", "running")]
    best = max((views.accuracy(r)[0] / max(1, views.accuracy(r)[1]) for r in done), default=0)
    ours = sum(s["ours"] for s in sc.values())
    cost = sum(a.get("cost") or 0 for r in runs.values() for a in (r.get("answers") or {}).values())
    cost += sum(p.get("cost") or 0 for p in probes)
    last = probes[-1] if probes else None
    return {
        "sources": [str(len(sources)), f"{sum(1 for s in sources.values() if s.get('status') == 'read')} read"],
        "claims": [str(len(sc)), f"{sum(1 for s in sc.values() if s['status'] == 'Supported')} supported"],
        "evidence": [str(len(d["evidence"]) + ours), f"{ours} from our runs"],
        "runs": [str(len(done)), f"{len(live)} running now" if live else f"best {best:.0%}"],
        "probe": [("right" if last["correct"] else "wrong") + f", {last['seconds']:.1f} s" if last else "waiting",
                  views.ago(last["at"]) if last else "first question soon"],
        "spend": [f"${cost:.2f}", f"{len(probes)} probes, {sum(len(r.get('answers') or {}) for r in runs.values())} run answers"],
    }


def draw(t):
    stat = lambda k: View.tiles[k].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=KEYS[k]))
    return nu.Sequential(*(stat(k).set(nu.List(t[k])[0], delta=nu.List(t[k])[1]) for k in KEYS))


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(pulse(kit.whole())), draw), every=20.0))
"""


WEEK = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit, views


class View(nu.Shape):
    week = ui.CardRef.slot(title="This week on the desk", subtitle="the last seven days")


def out(plane):
    # Reads the whole desk: sources, evidence, runs, the probe. Anything that lands there shows here.
    digest, text = nu.host(views.digest), View.week[0].to(ui.MarkdownRef)
    return kit.on_desk(
        plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(digest(kit.whole())), text.set), every=30.0)
    )
"""


BOARD = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit, views


class View(nu.Shape):
    board = ui.CardRef.slot(title="Where the claims stand", subtitle="evidence for and against, by weight")


chart = View.board[0].to(ui.BarChart.slot(
    ("For", "Against"), stack=True, horizontal=True, height=380,
    option={"grid": {"left": 300, "outerBoundsMode": "none", "bottom": 24}},
))


@nu.host
def bars(d):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"])
    order = sorted(sc, key=lambda k: -sc[k]["score"])
    label = lambda k: f"{d['claims'][k]['label']}  {sc[k]['score']:+.2f}"
    return {
        "bars": {"For": [[label(k), sc[k]["for"]] for k in order], "Against": [[label(k), -sc[k]["against"]] for k in order]},
        # Each claim's page wears its standing in the sidebar.
        "icons": [[k, kit.CLAIM_ICONS[sc[k]["tone"]]] for k in order],
    }


def draw(v):
    icons = nu.ForEachDo(v["icons"], lambda i: kit.wear(kit.DESK.planes.claims[nu.Str(nu.List(i)[0])], nu.List(i)[1]))
    return chart.set(v["bars"]) >> icons


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("claims", "evidence", "runs", "models", "probes"))), nu.let(nuspace.atomic(bars(kit.whole())), draw)))
"""


ACTIVITY = r"""
import nu
import nuspace
from nustd import ui
from nudemos import pages
from nudemos.research import kit, views


class View(nu.Shape):
    lately = ui.CardRef.slot(title="Lately", subtitle="who did what on the desk, newest first")


feed = View.lately[0].to(ui.DataTableRef.slot(
    columns=[
        {"key": "at", "label": "When", "cell": ui.RelativeTimeRef, "width": 110},
        {"key": "who", "label": "Who", "width": 110},
        {"key": "did", "label": "Did", "wrap": "truncate"},
        {"key": "what", "label": "What", "cell": ui.PageLinkRef.slot(variant="inline")},
        {"key": "on", "label": "On", "cell": ui.PageLinkRef.slot(variant="inline"), "hide_below": 720},
    ],
    row_key="key", label="Lately", density="compact", variant="borderless",
))


@nu.host
def lately(d):
    return views.activity(d, 12)


def out(plane):
    # Every row links to the pages it happened on.
    rows = lambda d: pages.linked(pages.linked(lately(d), "what"), "on")
    return kit.on_desk(
        plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(rows(kit.whole())), feed.set_rows), every=30.0)
    )
"""


ROOT = (
    ("welcome", WELCOME),
    ("pulse", PULSE),
    ("week", WEEK),
    ("board", BOARD),
    ("activity", ACTIVITY),
)


# --- reading list ----------------------------------------------------------------------------------


ADD_SOURCE = r"""
import nu
from nustd import ui
from nudemos.research import data, kit


class View(nu.Shape):
    add = ui.CollapsibleRef.slot(title="Add a source", open=False, gap=3)


form = View.add[0].to(ui.GridRef.slot(cols=3, stack_below=640, gap=3))
INPUTS = {
    "title": ("Title", "Scaling Laws for Neural Language Models"),
    "authors": ("Authors", "Kaplan et al."),
    "year": ("Year", "2020"),
    "venue": ("Venue", "arXiv, NeurIPS, ICLR..."),
    "arxiv": ("arXiv id", "2001.08361"),
}
typed = {k: form[i // 3, i % 3].to(ui.InputRef.slot(label=label, placeholder=hint)) for i, (k, (label, hint)) in enumerate(INPUTS.items())}
by = form[1, 2].to(ui.FieldRef.slot(label="Added by")).control.to(ui.SelectRef.slot(options=list(data.TEAM), selected=data.TEAM[0]))
go = View.add[1].to(ui.RowRef.slot(justify="end"))[0].to(ui.ButtonRef.slot(label="Add to the list", icon="plus"))


def out(plane):
    def add(base):
        source = kit.typed_source(*(nu.Str(typed[k]) for k in INPUTS), nu.Str(by))
        cleared = nu.Sequential(*(i.set("") for i in typed.values()))
        return nu.IfDo(nu.Str(typed["title"]).strip() != "", kit.add_source(base, source) >> cleared)

    shown = nu.Sequential(*(i.init() for i in typed.values())) >> by.init() >> go.init()
    return shown >> kit.on_desk(plane, lambda base: nu.ReactEvery(go.on_click(), add(base)))
"""


SHELF = r"""
import nu
import nuspace
from nustd import ui
from nudemos import pages
from nudemos.research import kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    shelf = ui.CardRef.slot(title="The shelf", subtitle="in reading first, then queued, then read")


table = View.shelf[0].to(ui.DataTableRef.slot(
    columns=[
        {"key": "title", "label": "Title", "editable": False, "cell": ui.PageLinkRef.slot(variant="inline")},
        {"key": "authors", "label": "Authors", "editable": False, "width": 170, "wrap": "truncate", "hide_below": 720},
        {"key": "year", "label": "Year", "kind": "number", "editable": False, "width": 70, "align": "end"},
        {"key": "venue", "label": "Venue", "editable": False, "width": 90, "hide_below": 640},
        {"key": "status", "label": "Status", "kind": "select", "options": ["queued", "reading", "read"], "width": 110},
        {"key": "claims", "label": "Claims", "kind": "number", "editable": False, "width": 80, "align": "end"},
        {"key": "by", "label": "Added by", "editable": False, "width": 110, "hide_below": 640},
    ],
    row_key="key", editable=True, label="Reading list", density="compact",
))


@nu.host
def rows(sources, evidence, made):
    n = {}
    for e in evidence.values():
        n[e["source"]] = n.get(e["source"], 0) + 1
    order = {"reading": 0, "queued": 1, "read": 2}
    ordered = sorted(sources.values(), key=lambda s: (order.get(s.get("status"), 3), -(s.get("at") or 0)))
    return [{"key": s["key"], "title": {"page": (made or {}).get(s["key"], ""), "label": s["title"]}, "authors": s["authors"],
             "year": s["year"], "venue": s["venue"], "status": s.get("status", "queued"), "claims": n.get(s["key"], 0),
             "by": s.get("by", "")} for s in ordered]


def out(plane):
    def build(base):
        edit = lambda ev: nu.IfDo(nu.Str(ev["column"]) == "status", kit.set_status(base, nu.Str(ev["key"]), nu.Str(ev["value"])))
        read = pages.linked(rows(DESK.sources.extract(), DESK.evidence.extract(), DESK.planes.sources.extract()), "title")
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("sources", "evidence", "planes"))), nu.let(nuspace.atomic(read), table.set_rows)),
            nu.ReactEvery(table.on_edit(), edit),
        )

    return kit.on_desk(plane, build)
"""


YEARS = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    years = ui.CardRef.slot(title="The list by year")


chart = View.years[0].to(ui.BarChart.slot(("read", "reading", "queued"), stack=True, height=240))


@nu.host
def by_year(sources):
    years = sorted({s.get("year") or 0 for s in sources.values() if s.get("year")})
    return {st: [[str(y), sum(1 for s in sources.values() if s.get("year") == y and s.get("status") == st)] for y in years]
            for st in ("read", "reading", "queued")}


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("sources"))), nu.let(nuspace.atomic(by_year(DESK.sources.extract())), chart.set)))
"""


READING = (("add", ADD_SOURCE), ("shelf", SHELF), ("years", YEARS))


# --- a source page ---------------------------------------------------------------------------------


SOURCE_HEAD = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit, views
from nudemos.research.kit import DESK


STATUSES = [{"value": "queued", "label": "Queued"}, {"value": "reading", "label": "Reading"}, {"value": "read", "label": "Read"}]


class View(nu.Shape):
    head = ui.PageSectionRef.slot(gap=3)


H = View.head
arxiv = H.actions[0].to(ui.LinkRef.slot(external=True, icon="external-link"))
facts = H[0].to(ui.RowRef.slot(gap=4, align="center", wrap=True))
status = facts[0].to(ui.RadioGroupRef.slot(options=STATUSES, orientation="horizontal"))
who = facts[1].to(ui.TextRef.slot(tone="muted", size="sm"))
tldr = H[1].to(ui.MarkdownRef)


@nu.host
def head(s):
    return {
        "title": s.get("title", ""),
        "line": f"{s.get('authors', '')}  ·  {s.get('venue', '')} {s.get('year') or ''}".strip(),
        "arxiv": f"arXiv {s['arxiv']}" if s.get("arxiv") else "",
        "url": s.get("url", "") if s.get("arxiv") else "",
        "status": s.get("status", "queued"),
        "who": f"Added by {s.get('by', 'someone')}, {views.ago(s.get('at') or 0)}",
        "tldr": f"> {s['tldr']}" if s.get("tldr") else "> No summary yet. Write one in the notes below.",
    }


def draw(v):
    link = nu.IfDo(nu.Str(v["url"]) != "", arxiv.set(href=v["url"], label=v["arxiv"]))
    return (H.set_title(v["title"]) >> H.set_description(v["line"]) >> link
            >> status.set(v["status"]) >> who.set(v["who"]) >> tldr.set(v["tldr"]))


def out(plane):
    def build(base, key):
        src = DESK.sources[key]
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("sources"))), nu.let(nuspace.atomic(head(src.fallback({}))), draw)),
            nu.ReactEvery(status.on_change(), kit.set_status(base, key, nu.Str(status))),
        )

    return kit.on_page(plane, build)
"""


SOURCE_NOTES = r"""
import nu
from nustd import ui
from nudemos.research import kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    notes = ui.CardRef.slot(title="Our notes")


text = View.notes[0].to(ui.MarkdownRef.slot(
    editable=True, placeholder="What it shows, what it does not, what to check. Markdown, kept as you type.",
))


@nu.host
def notes_of(s):
    return (s or {}).get("notes") or ""


def out(plane):
    def build(base, key):
        src = DESK.sources[key]
        return text.set(notes_of(src.fallback({}))) >> nu.ReactEvery(text.on_change(), kit.patch(src, nu.Dict.of(notes=nu.Str(text))))

    return kit.on_page(plane, build)
"""


SOURCE_GIVES = r"""
import nu
import nuspace
from nustd import ui
from nudemos import pages
from nudemos.research import kit, views


class View(nu.Shape):
    gives = ui.CardRef.slot(title="On the board", subtitle="the claims this source weighs on")


table = View.gives[0].to(ui.DataTableRef.slot(
    columns=[
        {"key": "stance", "label": "Stance", "cell": ui.BadgeRef.slot(size="sm"), "width": 100},
        {"key": "claim", "label": "Claim", "cell": ui.PageLinkRef.slot(variant="inline")},
        {"key": "weight", "label": "Weight", "width": 80},
        {"key": "note", "label": "Note", "wrap": "truncate", "hide_below": 720},
        {"key": "score", "label": "Claim score", "kind": "number", "width": 110, "align": "end"},
    ],
    row_key="key", label="On the board", density="compact",
))


@nu.host
def gives(d, key):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"])
    made = (d.get("planes") or {}).get("claims") or {}
    rows = []
    for k, e in sorted(d["evidence"].items(), key=lambda kv: -(kv[1].get("at") or 0)):
        if e.get("source") != key or e["claim"] not in d["claims"]:
            continue
        rows.append({
            "key": k,
            "stance": {"label": "For", "variant": "ok"} if e["stance"] == "for" else {"label": "Against", "variant": "danger"},
            "claim": {"page": made.get(e["claim"], ""), "label": d["claims"][e["claim"]]["label"]},
            "weight": "●" * e["weight"] + "○" * (3 - e["weight"]),
            "note": e.get("note", ""),
            "score": sc[e["claim"]]["score"],
        })
    return {"rows": rows, "empty": "" if rows else "Nothing on the board from this one yet. Link it to a claim below."}


def draw(v):
    return table.set_rows(pages.linked(v["rows"], "claim")) >> View.gives.set_caption(v["empty"])


def out(plane):
    return kit.on_page(plane, lambda base, key: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("claims", "evidence", "runs", "probes", "planes"))), nu.let(nuspace.atomic(gives(kit.whole(), key)), draw)))
"""


SOURCE_LINK = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import data, kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    link = ui.CollapsibleRef.slot(title="Link this source to a claim", open=False, gap=3)


L = View.link
pick = L[0].to(ui.GridRef.slot(cols=3, stack_below=640, gap=4))
claim = pick[0, 0].to(ui.FieldRef.slot(label="Claim")).control.to(ui.SelectRef.slot(placeholder="A claim on the board"))
stance = pick[0, 1].to(ui.FieldRef.slot(label="Stance")).control.to(ui.RadioGroupRef.slot(
    options=[{"value": "for", "label": "For"}, {"value": "against", "label": "Against"}], selected="for", orientation="horizontal",
))
weight = pick[0, 2].to(ui.SliderRef.slot(label="Weight", min=1, max=3, step=1, value=2))
say = L[1].to(ui.RowRef.slot(gap=3, align="end", grow={0: 1}))
note = say[0].to(ui.InputRef.slot(placeholder="What in it bears on the claim, in a line"))
by = say[1].to(ui.SelectRef.slot(options=list(data.TEAM), selected=data.TEAM[0]))
go = say[2].to(ui.ButtonRef.slot(label="Put it on the board", icon="scale"))


@nu.host
def options(claims):
    return [{"value": k, "label": c["label"]} for k, c in sorted(claims.items(), key=lambda kv: kv[1]["label"])]


def out(plane):
    def build(base, key):
        typed = kit.typed_evidence(key, nu.Str(claim), nu.Str(stance), nu.ToStr(weight), nu.Str(note), nu.Str(by))
        add = nu.IfDo(nu.Str(claim) != "", kit.add_evidence(base, typed) >> note.set(""))
        shown = stance.init() >> weight.init() >> note.init() >> by.init() >> go.init()
        return shown >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("claims"))), nu.let(nuspace.atomic(options(DESK.claims.extract())), claim.set_options)),
            nu.ReactEvery(go.on_click(), add),
        )

    return kit.on_page(plane, build)
"""


SOURCE = (
    ("head", SOURCE_HEAD),
    ("gives", SOURCE_GIVES),
    ("link", SOURCE_LINK),
    ("notes", SOURCE_NOTES),
)


# --- claims ----------------------------------------------------------------------------------------


CLAIM_TABLE = r"""
import nu
import nuspace
from nustd import ui
from nudemos import pages
from nudemos.research import kit, views


class View(nu.Shape):
    claims = ui.CardRef.slot(title="Every claim", subtitle="best supported first")


table = View.claims[0].to(ui.DataTableRef.slot(
    columns=[
        {"key": "label", "label": "Claim", "cell": ui.PageLinkRef.slot(variant="inline")},
        {"key": "topic", "label": "Topic", "width": 120, "hide_below": 640},
        {"key": "status", "label": "Status", "cell": ui.StatusPillRef, "width": 130},
        {"key": "score", "label": "Score", "kind": "number", "width": 90, "align": "end"},
        {"key": "papers", "label": "Papers", "kind": "number", "width": 90, "align": "end", "hide_below": 640},
        {"key": "ours", "label": "Our runs", "kind": "number", "width": 100, "align": "end", "hide_below": 640},
    ],
    row_key="key", label="Claims", density="compact", sort_column="score", sort_direction="desc",
))


@nu.host
def rows(d):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"])
    made = (d.get("planes") or {}).get("claims") or {}
    return [{"key": k, "label": {"page": made.get(k, ""), "label": c["label"]}, "topic": c.get("topic", ""),
             "status": {"label": sc[k]["status"], "tone": sc[k]["tone"]}, "score": round(sc[k]["score"], 2),
             "papers": sc[k]["papers"], "ours": sc[k]["ours"]}
            for k, c in sorted(d["claims"].items(), key=lambda kv: -sc[kv[0]]["score"])]


def out(plane):
    read = lambda: pages.linked(rows(kit.whole()), "label")
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("claims", "evidence", "runs", "models", "probes", "planes"))), nu.let(nuspace.atomic(read()), table.set_rows)))
"""


ADD_CLAIM = r"""
import nu
from nustd import ui
from nudemos.research import data, kit


class View(nu.Shape):
    form = ui.RowRef.slot(gap=3, align="end", grow={0: 1}, basis={1: 200}, wrap=True)


text = View.form[0].to(ui.InputRef.slot(label="A claim to weigh", placeholder="Longer contexts make retrieval worse"))
topic = View.form[1].to(ui.InputRef.slot(label="Topic", placeholder="Long context"))
go = View.form[2].to(ui.ButtonRef.slot(label="Put on the board", icon="plus"))


def out(plane):
    def add(base):
        typed = kit.typed_claim(nu.Str(text), nu.Str(topic), data.TEAM[0])
        return nu.IfDo(nu.Str(text).strip() != "", kit.add_claim(base, typed) >> text.set("") >> topic.set(""))

    return text.init() >> topic.init() >> go.init() >> kit.on_desk(plane, lambda base: nu.ReactEvery(go.on_click(), add(base)))
"""


CLAIMS = (("board", BOARD), ("table", CLAIM_TABLE), ("add", ADD_CLAIM))


# --- a claim page ----------------------------------------------------------------------------------


CLAIM_HEAD = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit, views


KEYS = {"score": "Score, -1 to 1", "weight": "Weight for / against", "papers": "From papers", "ours": "From our runs"}


class View(nu.Shape):
    head = ui.PageSectionRef.slot(gap=3)


H = View.head
pill = H.actions[0].to(ui.StatusPillRef)
tiles = H[0].to(ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=3))


@nu.host
def head(d, key):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"]).get(key)
    c = d["claims"].get(key) or {}
    if not sc:
        return {"claim": "", "about": "", "status": "", "tone": "neutral", "score": "-", "weight": "-", "papers": "-", "ours": "-"}
    return {"claim": c["text"], "about": f"{c.get('topic', '')}  ·  on the board since {views.ago(c.get('at') or 0)}",
            "status": sc["status"], "tone": sc["tone"], "score": f"{sc['score']:+.2f}",
            "weight": f"{sc['for']} / {sc['against']}", "papers": str(sc["papers"]), "ours": str(sc["ours"])}


def draw(v):
    stat = lambda k: tiles[k].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=KEYS[k]))
    return (H.set_title(v["claim"]) >> H.set_description(v["about"]) >> pill.set(v["status"], tone=v["tone"])
            >> nu.Sequential(*(stat(k).set(v[k]) for k in KEYS)))


def out(plane):
    return kit.on_page(plane, lambda base, key: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("claims", "evidence", "runs", "models", "probes"))), nu.let(nuspace.atomic(head(kit.whole(), key)), draw)))
"""


CLAIM_HISTORY = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit, views


class View(nu.Shape):
    history = ui.CardRef.slot(title="The score as evidence landed")


chart = View.history[0].to(ui.LineChart.slot(("score",), x_type="time", step=True, symbols=True, y_min=-1, y_max=1, height=220, area=True))


@nu.host
def points(d, key):
    return views.history(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"]).get(key, [])


def out(plane):
    return kit.on_page(plane, lambda base, key: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("claims", "evidence", "runs", "models", "probes"))), nu.let(nuspace.atomic(points(kit.whole(), key)), chart.set)))
"""


CLAIM_EVIDENCE = r"""
import nu
import nuspace
from nustd import ui
from nudemos import pages
from nudemos.research import kit, views


class View(nu.Shape):
    sides = ui.GridRef.slot(cols=2, stack_below=800, gap=4)


COLUMNS = [
    {"key": "weight", "label": "Weight", "width": 80},
    {"key": "what", "label": "Evidence", "cell": ui.PageLinkRef.slot(variant="inline")},
    {"key": "note", "label": "Note", "wrap": "truncate", "hide_below": 480},
]
SIDES = {"for": (0, "For"), "against": (1, "Against")}
tables = {
    side: View.sides[0, c].to(ui.CardRef.slot(title=title))[0].to(ui.DataTableRef.slot(columns=COLUMNS, row_key="key", label=title, density="compact"))
    for side, (c, title) in SIDES.items()
}


@nu.host
def sides(d, key):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"]).get(key)
    made = d.get("planes") or {}
    page = lambda kind, k: (made.get(kind) or {}).get(k, "")

    def row(e):
        if e.get("kind") == "run":
            r = d["runs"].get(e["source"])
            what = {"page": page("runs", e["source"]), "label": f"Our run: {views.title_of_run(r)}"} if r else {"page": "", "label": "Our runs"}
        elif e.get("kind") == "models":
            what = {"page": page("sections", "models"), "label": "The model table"}
        elif e.get("kind") == "probe":
            what = {"page": page("sections", "watch"), "label": "The probe"}
        else:
            s = d["sources"].get(e["source"], {})
            what = {"page": page("sources", e["source"]), "label": f"{s.get('title', e['source'])} {s.get('year', '')}".strip()}
        return {"key": e["key"], "weight": "●" * e["weight"] + "○" * (3 - e["weight"]), "what": what, "note": e.get("note", "")}

    items = (sc or {}).get("items") or []
    return {side: [row(e) for e in items if e["stance"] == side] for side in SIDES}


def draw(v):
    return nu.Sequential(*(t.set_rows(pages.linked(v[side], "what")) for side, t in tables.items()))


def out(plane):
    return kit.on_page(plane, lambda base, key: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(sides(kit.whole(), key)), draw)))
"""


CLAIM_TAKE = r"""
import nu
from nustd import ui
from nudemos.research import kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    take = ui.CardRef.slot(title="Our take")


text = View.take[0].to(ui.MarkdownRef.slot(
    editable=True, placeholder="Where we land, and what would change our mind. Markdown, kept as you type.",
))


@nu.host
def take_of(c):
    return (c or {}).get("take") or ""


def out(plane):
    def build(base, key):
        claim = DESK.claims[key]
        return text.set(take_of(claim.fallback({}))) >> nu.ReactEvery(text.on_change(), kit.patch(claim, nu.Dict.of(take=nu.Str(text))))

    return kit.on_page(plane, build)
"""


CLAIM = (
    ("head", CLAIM_HEAD),
    ("history", CLAIM_HISTORY),
    ("evidence", CLAIM_EVIDENCE),
    ("take", CLAIM_TAKE),
)


# --- models ----------------------------------------------------------------------------------------


MODEL_TABLE = r'''
import nu
import nuspace
import nuspace.web as web
from nustd import ui
from nudemos.research import kit
from nudemos.research.kit import DESK


class View(ui.Column):
    intro = ui.MarkdownRef.slot()
    follows = ui.LineRef.slot()
    table = ui.DataTableRef.slot(
        columns=[
            {"key": "name", "label": "Model", "editable": False},
            {"key": "org", "label": "From", "editable": False, "width": 120, "hide_below": 640},
            {"key": "year", "label": "Year", "kind": "number", "width": 70, "align": "end"},
            {"key": "params", "label": "Params, B", "kind": "number", "width": 110, "align": "end"},
            {"key": "active", "label": "Active, B", "kind": "number", "width": 110, "align": "end", "hide_below": 720},
            {"key": "tokens", "label": "Tokens, T", "kind": "number", "width": 110, "align": "end"},
            {"key": "ratio", "label": "Tokens per param", "editable": False, "width": 150, "align": "end"},
            {"key": "open", "label": "Open weights", "kind": "bool", "width": 120},
        ],
        row_key="key", editable=True, label="Models", density="compact",
    )


INTRO = """\
Models as their reports give them. Tokens per parameter is training tokens over total parameters:
about 20 is where Chinchilla put the compute-optimal point. Edit a number and the chart below, and the
overtraining claim, follow. A blank token count means the report does not say."""


@nu.host
def rows(models):
    out = []
    for m in sorted(models.values(), key=lambda m: (m.get("year") or 0, m["name"])):
        ratio = m["tokens"] * 1000 / m["params"] if m.get("tokens") and m.get("params") else None
        out.append({**m, "tokens": m.get("tokens") or None, "ratio": f"{ratio:,.0f}" if ratio else "not disclosed"})
    return out


def edit(ev):
    row, col, value = DESK.models[nu.Str(ev["key"])], nu.Str(ev["column"]), ev["value"]
    typed = {"year": nu.ToInt(value), "params": nu.ToFloat(value), "active": nu.ToFloat(value),
             "tokens": nu.ToFloat(value), "open": nu.ToBool(value)}
    return nu.Sequential(*(nu.IfDo(col == k, kit.patch(row, nu.Dict.of(**{k: v}))) for k, v in typed.items()))


def follows():
    # The overtraining claim's page, by the id the desk keeps for it.
    claim = View.follows[1].to(ui.LinkRef)
    said = View.follows[0].to(ui.TextRef.slot(tone="muted", size="sm")).set("The table weighs on")
    return said >> nu.let(nuspace.atomic(kit.claim_plane("overtrain").fallback("")), lambda pid: nu.IfDo(
        nu.Str(pid) != "", nuspace.atomic(web.link(claim, nu.Str(pid), label="Open models overtrain"))
    ))


def out(plane):
    shown = nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("models"))), nu.let(nuspace.atomic(rows(DESK.models.extract())), View.table.set_rows))
    return View.intro.set(INTRO) >> kit.on_desk(
        plane, lambda b: follows() >> nu.ParallelAsync(shown, nu.ReactEvery(View.table.on_edit(), edit))
    )
'''


MODEL_CHART = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    chart = ui.CardRef.slot(title="Tokens per parameter, by year", subtitle="log scale; Chinchilla sits at 20")


chart = View.chart[0].to(ui.ScatterChart.slot(
    ("Open weights", "Closed"), symbol_size=14, x_label="Year",
    y_label="Tokens per parameter", x_format="{value}", tooltip_format="{b}", legend=True, height=360,
    x_type="category", option={"yAxis": {"type": "log"}, "xAxis": {"data": ["2020", "2021", "2022", "2023", "2024"]}},
))


@nu.host
def points(models):
    by = {"Open weights": [], "Closed": []}
    for m in models.values():
        if not (m.get("tokens") and m.get("params") and m.get("year")):
            continue
        ratio = m["tokens"] * 1000 / m["params"]
        by["Open weights" if m.get("open") else "Closed"].append(
            {"name": f"{m['name']}  ·  {ratio:,.0f} tokens per parameter", "value": [str(m["year"]), round(ratio, 1)]})
    return by


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("models"))), nu.let(nuspace.atomic(points(DESK.models.extract())), chart.set)))
"""


MODELS = (("table", MODEL_TABLE), ("chart", MODEL_CHART))


# --- evals -----------------------------------------------------------------------------------------


LAUNCH = r'''
import nu
from nustd import ui
from nudemos.research import data, evals, kit
from nudemos.research.claude import READY

ABOUT = """\
A run puts the 20 questions of our suite to Claude, one at a time, in a job of its own: twelve word problems
in the style of GSM-IC, and eight that are hard to do in one go. *Distracted* adds a sentence that changes nothing.
Every answer is graded on its last number and lands on the leaderboard, the run's page, and the claims it bears on.
A Sonnet run costs about ten cents, a Haiku run about one."""


def choices(names):
    return [{"value": k, "label": v} for k, v in names.items()]


class View(nu.Shape):
    arm = ui.CardRef.slot(title="Run an arm", gap=4)


A = View.arm
about = A[0].to(ui.MarkdownRef)
pick = A[1].to(ui.GridRef.slot(cols=3, stack_below=800, gap=4))
model = pick[0, 0].to(ui.FieldRef.slot(label="Model")).control.to(ui.SelectRef.slot(options=choices(evals.MODELS), selected="haiku"))
style = pick[0, 1].to(ui.FieldRef.slot(label="Asked for")).control.to(
    ui.RadioGroupRef.slot(options=choices(evals.STYLES), selected="direct", orientation="horizontal"))
context = pick[0, 2].to(ui.FieldRef.slot(label="Context")).control.to(
    ui.RadioGroupRef.slot(options=choices(evals.CONTEXTS), selected="noisy", orientation="horizontal"))
one = A.actions[0].to(ui.ButtonRef.slot(label="Run this arm", icon="play"))
four = A.actions[1].to(ui.ButtonRef.slot(label="Run all four arms", icon="layers", variant="secondary"))
note = A.footer[0].to(ui.TextRef.slot(tone="muted", size="sm"))


def out(plane):
    def launch(base, s, c, n):
        return kit.launch_run(base, kit.new_run(nu.Str(model), s, c, data.TEAM[1], n))

    def run_one(base):
        return nu.let(nu.Str(style), lambda s: nu.let(nu.Str(context), lambda c: launch(base, s, c, 0)))

    def run_four(base):
        arms = [(s, c) for s in evals.STYLES for c in evals.CONTEXTS]
        return nu.Sequential(*(launch(base, s, c, i) for i, (s, c) in enumerate(arms)))

    if not READY:
        return about.set("**Runs need the Claude Agent SDK.** Install the `cc` extra of nustd.") >> nu.ForeverDo(nu.Delay(3600.0))
    shown = model.init() >> style.init() >> context.init() >> one.init() >> four.init() >> note.set("Runs go on the leaderboard below as they start.")
    return about.set(ABOUT) >> shown >> kit.on_desk(plane, lambda base: nu.ParallelAsync(
        nu.ReactEvery(one.on_click(), run_one(base)),
        nu.ReactEvery(four.on_click(), run_four(base)),
    ))
'''


LEADERBOARD = r"""
import nu
import nuspace
from nustd import ui
from nudemos import pages
from nudemos.research import kit, views
from nudemos.research.kit import DESK


class View(nu.Shape):
    board = ui.CardRef.slot(title="Leaderboard", subtitle="finished runs, best first")


table = View.board[0].to(ui.DataTableRef.slot(
    columns=[
        {"key": "arm", "label": "Arm", "cell": ui.PageLinkRef.slot(variant="inline")},
        {"key": "acc", "label": "Accuracy, %", "kind": "number", "width": 120, "align": "end"},
        {"key": "word", "label": "Word problems", "width": 130, "align": "end", "hide_below": 720},
        {"key": "hard", "label": "Hard in one go", "width": 130, "align": "end", "hide_below": 720},
        {"key": "done", "label": "Answered", "width": 100, "align": "end"},
        {"key": "median", "label": "Median reply", "width": 120, "align": "end", "hide_below": 640},
        {"key": "cost", "label": "Cost", "width": 80, "align": "end"},
        {"key": "status", "label": "Status", "cell": ui.StatusPillRef, "width": 110},
        {"key": "when", "label": "When", "cell": ui.RelativeTimeRef, "width": 110, "hide_below": 640},
    ],
    row_key="key", label="Leaderboard", density="compact",
))


@nu.host
def board(runs, made):
    return views.leaderboard(runs, made or {})


def out(plane):
    read = pages.linked(board(DESK.runs.extract(), DESK.planes.runs.extract()), "arm")
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("runs", "planes"))), nu.let(nuspace.atomic(read), table.set_rows), every=20.0))
"""


GRID = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import evals, kit, views
from nudemos.research.kit import DESK


class View(nu.Shape):
    grid = ui.CardRef.slot(title="Every question, every arm", subtitle="the red cells are the misses")


chart = View.grid[0].to(ui.HeatmapChart.slot(
    height=520, legend=False,
    option={"visualMap": {"inRange": {"color": ["var(--status-danger)", "rgba(120, 140, 170, 0.22)"]}}},
))


@nu.host
def cells(runs):
    arms = views.latest(runs)
    labels = [evals.BY_ID[q]["label"] for q in evals.BY_ID]
    cols = sorted(arms, key=lambda a: (list(evals.MODELS).index(a[0]) if a[0] in evals.MODELS else 9, a[1], a[2]))
    out = []
    for a in cols:
        r = arms[a]
        name = f"{evals.MODELS.get(a[0], a[0])}\n{'steps' if a[1] == 'steps' else 'direct'}\n{'distracted' if a[2] == 'noisy' else 'clean'}"
        for q, label in zip(evals.BY_ID, labels):
            ans = (r.get("answers") or {}).get(q)
            if ans is not None:
                out.append([name, label, 1 if ans.get("correct") else 0])
    return out


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("runs"))), nu.let(nuspace.atomic(cells(DESK.runs.extract())), chart.set)))
"""


EVALS = (("launch", LAUNCH), ("leaderboard", LEADERBOARD), ("grid", GRID))


# --- a run page ------------------------------------------------------------------------------------


RUN_HEAD = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import evals, kit, views
from nudemos.research.kit import DESK


KEYS = {"acc": "Accuracy", "word": "Word problems", "hard": "Hard in one go", "median": "Median reply", "cost": "Cost"}


class View(nu.Shape):
    head = ui.PageSectionRef.slot(gap=4)


H = View.head
pill = H.actions[0].to(ui.StatusPillRef)
progress = H[0].to(ui.ProgressRef)
tiles = H[1].to(ui.GridRef.slot(max_columns=5, min_cell_width=140, gap=3))
told = H[2].to(ui.MarkdownRef)


@nu.host
def head(r):
    if not r:
        return {"title": "A run", "line": "", "told": "", "status": "Starting", "tone": "neutral", "progress": 0, "caption": "",
                **{k: "-" for k in KEYS}}
    right, n = views.accuracy(r)
    total = len(evals.BY_ID)
    row = next(iter(views.leaderboard({r["key"]: r}, {})), {})
    return {
        "title": views.title_of_run(r),
        "line": f"Run by {r.get('by', 'the desk')}, {views.ago(r.get('at') or 0)}, on {evals.MODEL_IDS.get(r['model'], r['model'])}",
        "told": f"The model is told:\n\n> {evals.SYSTEM[r['style']]}",
        "status": r.get("status", "queued").title(), "tone": views.RUN_TONES.get(r.get("status"), "neutral"),
        "progress": round(100 * n / total), "caption": f"{n} of {total} answered",
        "acc": f"{right}/{n}" if n else "-", "word": row.get("word", "-"), "hard": row.get("hard", "-"),
        "median": row.get("median", "-"), "cost": row.get("cost", "-"),
    }


def draw(v):
    stat = lambda k: tiles[k].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=KEYS[k]))
    return (H.set_title(v["title"]) >> H.set_description(v["line"]) >> pill.set(v["status"], tone=v["tone"])
            >> progress.set(v["progress"], caption=v["caption"]) >> nu.Sequential(*(stat(k).set(v[k]) for k in KEYS))
            >> told.set(v["told"]))


def out(plane):
    return kit.on_page(plane, lambda base, key: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("runs"))), nu.let(nuspace.atomic(head(DESK.runs[key].fallback(None))), draw), every=10.0))
"""


RUN_ANSWERS = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import evals, kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    work = ui.GridRef.slot(cols="3fr 2fr", stack_below=800, gap=4)


table = View.work[0, 0].to(ui.CardRef.slot(title="Answers", subtitle="click one to read its reply"))[0].to(ui.DataTableRef.slot(
    columns=[
        {"key": "label", "label": "Question"},
        {"key": "tier", "label": "Kind", "width": 130, "hide_below": 640},
        {"key": "want", "label": "Answer", "width": 100, "align": "end"},
        {"key": "got", "label": "Got", "width": 100, "align": "end"},
        {"key": "mark", "label": "", "cell": ui.BadgeRef.slot(size="sm"), "width": 80},
        {"key": "seconds", "label": "Seconds", "kind": "number", "width": 90, "align": "end", "hide_below": 640},
    ],
    row_key="q", clickable_rows=True, label="Answers", density="compact",
))
reply = View.work[0, 1].to(ui.CardRef.slot(title="The reply"))
asked = reply[0].to(ui.MarkdownRef)
said = reply[1].to(ui.CodeRef.slot(language="markdown", wrap=True))


@nu.host
def rows(r):
    out = []
    for q, item in evals.BY_ID.items():
        a = ((r or {}).get("answers") or {}).get(q)
        fmt = lambda x: f"{x:,.10g}" if isinstance(x, (int, float)) else "-"
        mark = ({"label": "right", "variant": "ok"} if a["correct"] else {"label": "wrong", "variant": "danger"}) if a else ""
        out.append({"q": q, "label": item["label"], "tier": "hard in one go" if item.get("tier") == "hard" else "word problem",
                    "want": fmt(item["answer"]), "got": fmt(a["got"]) if a else "...", "mark": mark,
                    "seconds": a["seconds"] if a else None})
    return out


@nu.host
def answer(r, q):
    answers = (r or {}).get("answers") or {}
    if not q:
        q = next(reversed(list(answers)), "")
    if q not in evals.BY_ID:
        return {"asked": "No answers yet.", "said": ""}
    a = answers.get(q)
    head = f"**{evals.BY_ID[q]['label']}**\n\n> {evals.prompt(q, (r or {}).get('context', 'clean'))}"
    return {"asked": head, "said": a["text"] if a else "Not asked yet."}


def out(plane):
    def build(base, key):
        run = DESK.runs[key].fallback(None)
        shown = lambda v: asked.set(v["asked"]) >> said.set(v["said"])
        # The latest answer as it lands; a row clicked shows that one instead, until the next lands.
        picked = nu.ReactEvery(table.on_row_click(), lambda ev: nu.let(answer(run, nu.Str(ev["key"])), shown))
        return nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("runs"))), nu.let(nuspace.atomic(rows(run)), table.set_rows)),
            nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("runs"))), nu.let(nuspace.atomic(answer(run, "")), shown)),
            picked,
        )

    return kit.on_page(plane, build)
"""


RUN = (("head", RUN_HEAD), ("answers", RUN_ANSWERS))


# --- watch -----------------------------------------------------------------------------------------


PROBE_HEAD = r"""
import time

import nu
import nuspace
import nustd.time
from nustd import ui
from nudemos.research import evals, job, kit, views
from nudemos.research.kit import DESK

ABOUT = (
    f"Sonnet gets one question from our suite every {job.INTERVAL / 60:.0f} minutes, clean and distracted by turns, "
    f"at most {job.CAP} a day: a wrong answer, or a slower one, shows here first."
)
KEYS = {"next": "Next question", "today": "Asked today", "acc": "Right, clean against distracted", "median": "Median reply, last 50"}


class View(nu.Shape):
    probe = ui.PageSectionRef.slot(title="The probe", description=ABOUT, gap=3)


P = View.probe
pill = P.actions[0].to(ui.StatusPillRef)
now = P.actions[1].to(ui.ButtonRef.slot(label="Probe now", icon="zap", variant="secondary", size="sm"))
paused = P.actions[2].to(ui.SwitchRef.slot(label="Paused"))
tiles = P[0].to(ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=3))


@nu.host
def state(probe, probes, held, at):
    p = probe or {}
    last = (probes or [])[-50:]
    asking = p.get("status") == "asking"
    wait = max(0, int(p.get("next_at", 0) - at))
    nxt = "asking now" if asking else ("paused" if held else (f"in {wait // 60}:{wait % 60:02d}" if wait else "any moment"))
    q = (p.get("asking") or {}).get("q") if asking else None
    secs = sorted(x.get("seconds") or 0 for x in last)
    return {
        "status": ("Asking: " + evals.BY_ID[q]["label"]) if q in evals.BY_ID else ("Paused" if held else "Waiting"),
        "tone": "info" if asking else ("warn" if held else "ok"),
        "next": nxt,
        "today": f"{p.get('today', 0) if p.get('day') == time.strftime('%Y-%m-%d') else 0} of {job.CAP}",
        "acc": views.probe_split(probes or []),
        "median": f"{secs[len(secs) // 2]:.1f} s" if secs else "-",
    }


def draw(v):
    stat = lambda k: tiles[k].to(ui.CardRef.slot(size="sm"))[0].to(ui.StatRef.slot(label=KEYS[k]))
    return pill.set(v["status"], tone=v["tone"]) >> nu.Sequential(*(stat(k).set(v[k]) for k in KEYS))


def out(plane):
    def build(base):
        shown = state(DESK.probe.fallback({}), DESK.probes.extract(), DESK.paused.fallback(False), nustd.time.time())
        follow = nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("probe", "probes") + [DESK.paused.on_change()])), nu.let(nuspace.atomic(shown), draw), every=1.0)
        return nu.ParallelAsync(
            now.init() >> paused.set(DESK.paused.fallback(False)) >> follow,
            nu.ReactEvery(now.on_click(), DESK.asked.set(DESK.asked.fallback(0) + 1)),
            nu.ReactEvery(paused.on_change(), DESK.paused.set(nu.ToBool(paused))),
        )

    return kit.on_desk(plane, build)
"""


PROBE_CHART = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    chart = ui.CardRef.slot(title="Seconds per reply", subtitle="every probe")


chart = View.chart[0].to(ui.LineChart.slot(
    ("Clean", "Distracted"), x_type="time", symbols=True, y_min=0, height=240, option={"xAxis": {"min": "dataMin", "max": "dataMax"}},
))


@nu.host
def points(probes):
    out = {"Clean": [], "Distracted": []}
    for p in probes or []:
        out["Distracted" if p.get("context") == "noisy" else "Clean"].append([p["at"] * 1000, p.get("seconds") or 0])
    return out


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("probes"))), nu.let(nuspace.atomic(points(DESK.probes.extract())), chart.set)))
"""


PROBE_FEED = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import evals, kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    feed = ui.CardRef.slot(title="Probe answers", subtitle="the last 25, newest first")


table = View.feed[0].to(ui.DataTableRef.slot(
    columns=[
        {"key": "at", "label": "When", "cell": ui.RelativeTimeRef, "width": 110},
        {"key": "label", "label": "Question"},
        {"key": "context", "label": "Context", "width": 110, "hide_below": 640},
        {"key": "got", "label": "Got", "width": 110, "align": "end"},
        {"key": "mark", "label": "", "cell": ui.BadgeRef.slot(size="sm"), "width": 80},
        {"key": "seconds", "label": "Seconds", "kind": "number", "width": 90, "align": "end"},
    ],
    row_key="key", label="Probe answers", density="compact",
))


@nu.host
def rows(probes):
    out = []
    for p in reversed((probes or [])[-25:]):
        q = evals.BY_ID.get(p["q"], {})
        out.append({"key": f"{p['at']}:{p['q']}", "at": (p["at"] or 0) * 1000, "label": q.get("label", p["q"]),
                    "context": "distracted" if p.get("context") == "noisy" else "clean",
                    "got": f"{p['got']:,.10g}" if isinstance(p.get("got"), (int, float)) else "-",
                    "mark": {"label": "right", "variant": "ok"} if p.get("correct") else {"label": "wrong", "variant": "danger"},
                    "seconds": p.get("seconds")})
    return out


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes("probes"))), nu.let(nuspace.atomic(rows(DESK.probes.extract())), table.set_rows)))
"""


WATCH = (("probe", PROBE_HEAD), ("chart", PROBE_CHART), ("feed", PROBE_FEED))


# --- notebook --------------------------------------------------------------------------------------


ENTRIES = r"""
import nu
import nuspace
from nustd import ui
from nudemos.research import kit, views


class View(nu.Shape):
    entries = ui.MarkdownRef.slot()


@nu.host
def written(d):
    parts = []
    for n in views.notebook(d):
        live = "  ·  *live: its numbers are read from the desk*" if n.get("live") else ""
        parts.append(f"### {n['title']}\n\n*{n['when']}  ·  {n['by']}*{live}\n\n{n['text']}")
    return "\n\n---\n\n".join(parts)


def out(plane):
    return kit.on_desk(plane, lambda base: nu.Reconcile(nuspace.atomic(nu.OnAny(*kit.changes())), nu.let(nuspace.atomic(written(kit.whole())), View.entries.set), every=60.0))
"""


WRITE = r"""
import time

import nu
from nustd import ui
from nudemos.research import data, kit
from nudemos.research.kit import DESK


class View(nu.Shape):
    write = ui.CollapsibleRef.slot(title="Write an entry", open=False, gap=3)


W = View.write
head = W[0].to(ui.RowRef.slot(gap=3, align="end", grow={0: 1}, wrap=True))
title = head[0].to(ui.InputRef.slot(placeholder="A title for the entry"))
by = head[1].to(ui.SelectRef.slot(options=list(data.TEAM), selected=data.TEAM[2]))
go = head[2].to(ui.ButtonRef.slot(label="Add the entry", icon="pen-line"))
text = W[1].to(ui.TextAreaRef.slot(placeholder="What we did and what we saw. Markdown. Write {best}, {best_acc}, {cot_gap}, {noise_gap}, {runs}, {probe_acc} or {probe_split} and the entry keeps them current."))


@nu.host
def entry(title, text, by):
    return {"title": title.strip(), "text": text.strip(), "by": by, "at": time.time(), "live": "{" in text}


def out(plane):
    add = nu.IfDo(nu.Str(title).strip() != "", DESK.notebook.append(entry(nu.Str(title), nu.Str(text), nu.Str(by))) >> title.set("") >> text.set(""))
    shown = title.init() >> by.init() >> go.init() >> text.init()
    return shown >> kit.on_desk(plane, lambda base: nu.ReactEvery(go.on_click(), add))
"""


NOTEBOOK = (("write", WRITE), ("entries", ENTRIES))
