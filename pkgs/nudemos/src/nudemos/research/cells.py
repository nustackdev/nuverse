"""The desk's cells, as sources: one short Nu program each.

Every cell is ``def out(plane)``: the id of the page it runs on comes in, and
:mod:`.kit` lands the desk wherever that page's desk is. Pages of one kind
run the same cells: twenty-odd source pages, one program each, told apart by
their page's meta.

- The desk (:data:`ROOT`): welcome, pulse, the week, the board.
- Reading list (:data:`READING`) and a source page (:data:`SOURCE`).
- Claims (:data:`CLAIMS`) and a claim page (:data:`CLAIM`): standing, history, evidence, our take.
- Models (:data:`MODELS`).
- Evals (:data:`EVALS`) and a run page (:data:`RUN`).
- Watch (:data:`WATCH`), the probe's page.
- Notebook (:data:`NOTEBOOK`).
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
import nustd.ui
from nudemos.research import kit

TEXT = """\
A three-person desk on what is new in large language models, and what of it holds up.
Papers come in and get read, their claims go on the board, and our own eval runs on Claude weigh in next to them.
Every source, claim and run is a page, and every block on a page is a small program: open its code, change it, run it again.
"""


class Links(nustd.ui.Row):
    reading = nustd.ui.LinkRef.slot()
    claims = nustd.ui.LinkRef.slot()
    models = nustd.ui.LinkRef.slot()
    evals = nustd.ui.LinkRef.slot()
    watch = nustd.ui.LinkRef.slot()
    notebook = nustd.ui.LinkRef.slot()


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    links = Links.slot(gap=5, wrap=True)


def out(plane):
    L = View.links
    links = nu.Sequential(*(
        getattr(L, name).set(href=f"/{plane}.{name}", label=label)
        for name, label in (("reading", "Reading list"), ("claims", "Claims"), ("models", "Models"),
                            ("evals", "Evals"), ("watch", "Watch"), ("notebook", "Notebook"))
    ))
    # The first open brings in the sections, the sources, the claims and the runs, each a page, and starts the probe.
    return View.about.set(TEXT) >> links >> kit.on_desk(plane, lambda base: kit.seed(base) >> nu.ForeverDo(nu.Delay(3600.0)))
'''


PULSE = r"""
import time

import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


class Tiles(nustd.ui.Grid):
    sources = nustd.ui.StatRef.slot(label="Sources")
    claims = nustd.ui.StatRef.slot(label="Claims")
    evidence = nustd.ui.StatRef.slot(label="Evidence")
    runs = nustd.ui.StatRef.slot(label="Eval runs")
    probe = nustd.ui.StatRef.slot(label="Probe")
    spend = nustd.ui.StatRef.slot(label="Spent on Claude")


class View(nustd.ui.Column):
    tiles = Tiles.slot(columns=6, min_width=120, gap=3)


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
        "sources": (str(len(sources)), f"{sum(1 for s in sources.values() if s.get('status') == 'read')} read"),
        "claims": (str(len(sc)), f"{sum(1 for s in sc.values() if s['status'] == 'Supported')} supported"),
        "evidence": (str(len(d["evidence"]) + ours), f"{ours} from our runs"),
        "runs": (str(len(done)), f"{len(live)} running now" if live else f"best {best:.0%}"),
        "probe": (("right" if last["correct"] else "wrong") + f", {last['seconds']:.1f} s" if last else "waiting",
                  views.ago(last["at"]) if last else "first question soon"),
        "spend": (f"${cost:.2f}", f"{len(probes)} probes, {sum(len(r.get('answers') or {}) for r in runs.values())} run answers"),
    }


def draw(t):
    keys = ("sources", "claims", "evidence", "runs", "probe", "spend")
    return nu.Sequential(*(getattr(View.tiles, k).set(t[k][0], delta=t[k][1]) for k in keys))


def out(plane):
    return kit.on_desk(plane, lambda base: redraws(kit.changes(), pulse(kit.whole()), draw, every=20.0))
"""


WEEK = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


class View(nustd.ui.Column):
    heading = nustd.ui.HeadingRef.slot(level=3)
    digest = nustd.ui.MarkdownRef.slot()


def out(plane):
    # Reads the whole desk: sources, evidence, runs, the probe. Anything that lands there shows here.
    digest = nu.host(views.digest)
    return View.heading.set_label("This week on the desk") >> kit.on_desk(
        plane, lambda base: redraws(kit.changes(), digest(kit.whole(), base), View.digest.set, every=30.0)
    )
"""


BOARD = r"""
import nu
import nustd.ui
from nuspace import ops
from nuspace.system.utils import redraws
from nudemos.research import kit, views


class View(nustd.ui.Column):
    chart = nustd.ui.BarChart.slot(
        ("For", "Against"), title="Where the claims stand: evidence for and against, by weight",
        stack=True, horizontal=True, height=380, option={"grid": {"left": 300, "outerBoundsMode": "none", "bottom": 24}},
    )


@nu.host
def bars(d, base):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"])
    order = sorted(sc, key=lambda k: -sc[k]["score"])
    label = lambda k: f"{d['claims'][k]['label']}  {sc[k]['score']:+.2f}"
    return {
        "bars": {"For": [[label(k), sc[k]["for"]] for k in order], "Against": [[label(k), -sc[k]["against"]] for k in order]},
        # Each claim's page wears its standing in the sidebar.
        "icons": [[f"{base}.claim.{k}", kit.CLAIM_ICONS[sc[k]["tone"]]] for k in order],
    }


def draw(v):
    icons = nu.ForEachDo(v["icons"], lambda i: ops.set_plane_meta(nu.List(i)[0], nu.Dict.of(icon=nu.List(i)[1])))
    return View.chart.set(v["bars"]) >> icons


def out(plane):
    return kit.on_desk(plane, lambda base: redraws(kit.changes("claims", "evidence", "runs", "models", "probes"), bars(kit.whole(), base), draw))
"""


ACTIVITY = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


class View(nustd.ui.Column):
    heading = nustd.ui.HeadingRef.slot(level=3)
    feed = nustd.ui.MarkdownRef.slot()


def out(plane):
    # Who did what on the desk, newest first: every line links to the page it happened on.
    feed = nu.host(views.activity)
    return View.heading.set_label("Lately") >> kit.on_desk(
        plane, lambda base: redraws(kit.changes(), feed(kit.whole(), base), View.feed.set, every=30.0)
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
import nustd.ui
from nudemos.research import data, kit


class Line1(nustd.ui.Row):
    title = nustd.ui.InputRef.slot(label="Title", placeholder="Scaling Laws for Neural Language Models")
    authors = nustd.ui.InputRef.slot(label="Authors", placeholder="Kaplan et al.")


class Line2(nustd.ui.Row):
    year = nustd.ui.InputRef.slot(label="Year", placeholder="2020")
    venue = nustd.ui.InputRef.slot(label="Venue", placeholder="arXiv, NeurIPS, ICLR...")
    arxiv = nustd.ui.InputRef.slot(label="arXiv id", placeholder="2001.08361")
    by = nustd.ui.SelectRef.slot(options=list(data.TEAM), selected=data.TEAM[0])
    add = nustd.ui.ButtonRef.slot(label="Add to the list", icon="plus")


class Add(nustd.ui.Collapsible):
    one = Line1.slot(gap=3, align="end")
    two = Line2.slot(gap=3, align="end")


class View(nustd.ui.Column):
    add = Add.slot(title="Add a source", open=False)


def out(plane):
    A = View.add

    def add(base):
        typed = kit.typed_source(nu.Str(A.one.title), nu.Str(A.one.authors), nu.Str(A.two.year),
                                 nu.Str(A.two.venue), nu.Str(A.two.arxiv), nu.Str(A.two.by))
        cleared = nu.Sequential(*(f.set("") for f in (A.one.title, A.one.authors, A.two.year, A.two.venue, A.two.arxiv)))
        return nu.IfDo(nu.Str(A.one.title).strip() != "", kit.add_source(base, typed) >> cleared)

    shown = nu.Sequential(*(f.set("") for f in (A.one.title, A.one.authors, A.two.year, A.two.venue, A.two.arxiv)))
    shown = shown >> A.two.by.set(data.TEAM[0]) >> A.two.add.set_label("Add to the list")
    return shown >> kit.on_desk(plane, lambda base: nu.ReactForever(A.two.add.on_click(), add(base)))
"""


SHELF = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views
from nudemos.research.kit import Desk

COLUMNS = [
    {"key": "title", "label": "Title", "editable": False},
    {"key": "authors", "label": "Authors", "editable": False, "width": 170},
    {"key": "year", "label": "Year", "kind": "number", "editable": False, "width": 70},
    {"key": "venue", "label": "Venue", "editable": False, "width": 90},
    {"key": "status", "label": "Status", "kind": "select", "options": ["queued", "reading", "read"], "width": 110},
    {"key": "claims", "label": "Claims", "kind": "number", "editable": False, "width": 80},
    {"key": "by", "label": "Added by", "editable": False, "width": 110},
]


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, clickable_rows=True, label="Reading list", dense=True)


@nu.host
def rows(sources, evidence):
    n = {}
    for e in evidence.values():
        n[e["source"]] = n.get(e["source"], 0) + 1
    order = {"reading": 0, "queued": 1, "read": 2}
    ordered = sorted(sources.values(), key=lambda s: (order.get(s.get("status"), 3), -(s.get("at") or 0)))
    return [{"key": s["key"], "title": s["title"], "authors": s["authors"], "year": s["year"], "venue": s["venue"],
             "status": s.get("status", "queued"), "claims": n.get(s["key"], 0), "by": s.get("by", "")} for s in ordered]


def out(plane):
    T = View.table

    def build(base):
        edit = lambda ev: nu.IfDo(nu.Str(ev["column"]) == "status", kit.set_status(base, nu.Str(ev["key"]), nu.Str(ev["value"])))
        return nu.ParallelAsync(
            redraws(kit.changes("sources", "evidence"), rows(Desk.sources.extract(), Desk.evidence.extract()), T.set_rows),
            nu.ReactForever(T.on_edit(), edit),
            nu.ReactForever(T.on_row_click(), lambda ev: kit.go(View.nav, nu.Str("/") + kit.source_page(base, nu.Str(ev["key"])))),
        )

    return kit.on_desk(plane, build)
"""


YEARS = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit
from nudemos.research.kit import Desk


class View(nustd.ui.Column):
    chart = nustd.ui.BarChart.slot(("read", "reading", "queued"), title="The list by year", stack=True, height=240)


@nu.host
def by_year(sources):
    years = sorted({s.get("year") or 0 for s in sources.values() if s.get("year")})
    return {st: [[str(y), sum(1 for s in sources.values() if s.get("year") == y and s.get("status") == st)] for y in years]
            for st in ("read", "reading", "queued")}


def out(plane):
    return kit.on_desk(plane, lambda base: redraws(kit.changes("sources"), by_year(Desk.sources.extract()), View.chart.set))
"""


READING = (("add", ADD_SOURCE), ("shelf", SHELF), ("years", YEARS))


# --- a source page ---------------------------------------------------------------------------------


SOURCE_HEAD = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views
from nudemos.research.kit import Desk


STATUSES = [{"value": "queued", "label": "Queued"}, {"value": "reading", "label": "Reading"}, {"value": "read", "label": "Read"}]


class Facts(nustd.ui.Row):
    status = nustd.ui.RadioGroupRef.slot(options=STATUSES, orientation="horizontal")
    who = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    line = nustd.ui.MarkdownRef.slot()
    facts = Facts.slot(gap=3)
    tldr = nustd.ui.MarkdownRef.slot()


TONES = {"read": "ok", "reading": "info", "queued": "neutral"}


@nu.host
def head(s):
    link = f"  ·  [arXiv {s['arxiv']}]({s['url']})" if s.get("arxiv") else ""
    return {
        "line": f"**{s.get('authors', '')}**  ·  {s.get('venue', '')} {s.get('year') or ''}{link}",
        "status": s.get("status", "queued"),
        "label": s.get("status", "queued").title(),
        "tone": TONES.get(s.get("status"), "neutral"),
        "who": f"Added by {s.get('by', 'someone')}, {views.ago(s.get('at') or 0)}",
        "tldr": f"> {s['tldr']}" if s.get("tldr") else "> No summary yet. Write one in the notes below.",
    }


def draw(v):
    F = View.facts
    return View.line.set(v["line"]) >> F.status.set(v["status"]) >> F.who.set(v["who"]) >> View.tldr.set(v["tldr"])


def out(plane):
    def build(base, key):
        src = Desk.sources[key]
        return nu.ParallelAsync(
            redraws(kit.changes("sources"), head(src.fallback({})), draw),
            nu.ReactForever(View.facts.status.on_change(), kit.set_status(base, key, nu.Str(View.facts.status))),
        )

    return kit.on_page(plane, build)
"""


SOURCE_NOTES = r"""
import nu
import nustd.ui
from nudemos.research import kit
from nudemos.research.kit import Desk


class View(nustd.ui.Column):
    heading = nustd.ui.HeadingRef.slot(level=4)
    notes = nustd.ui.MarkdownRef.slot()


@nu.host
def notes_of(s):
    return (s or {}).get("notes") or ""


def out(plane):
    def build(base, key):
        src, notes = Desk.sources[key], View.notes
        return (
            View.heading.set_label("Our notes")
            >> notes.set(notes_of(src.fallback({})))
            >> notes.set_editable(True)
            >> notes.set_placeholder("What it shows, what it does not, what to check. Markdown, kept as you type.")
            >> nu.ReactForever(notes.on_change(), kit.patch(src, nu.Dict.of(notes=nu.Str(notes))))
        )

    return kit.on_page(plane, build)
"""


SOURCE_GIVES = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


@nu.host
def gives(d, key, base):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"])
    lines = []
    for e in sorted(d["evidence"].values(), key=lambda e: -(e.get("at") or 0)):
        if e.get("source") != key or e["claim"] not in d["claims"]:
            continue
        c, s = d["claims"][e["claim"]], sc[e["claim"]]
        mark = "for" if e["stance"] == "for" else "against"
        lines.append(f"- **{mark.title()}** [{c['label']}](/{base}.claim.{e['claim']})  {'●' * e['weight']}{'○' * (3 - e['weight'])}  \n"
                     f"  {e.get('note', '')}  The claim stands at **{s['score']:+.2f}**, {s['status'].lower()}.")
    body = "\n".join(lines) if lines else "Nothing on the board from this one yet. Link it to a claim below."
    return "#### On the board\n\n" + body


def out(plane):
    text = nustd.ui.MarkdownRef("gives")
    return kit.on_page(plane, lambda base, key: redraws(
        kit.changes("claims", "evidence", "runs", "probes"), gives(kit.whole(), key, base), text.set
    ))
"""


SOURCE_LINK = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import data, kit
from nudemos.research.kit import Desk


class Pick(nustd.ui.Row):
    claim = nustd.ui.SelectRef.slot(placeholder="A claim on the board")
    stance = nustd.ui.RadioGroupRef.slot(options=[{"value": "for", "label": "For"}, {"value": "against", "label": "Against"}], selected="for", orientation="horizontal")
    weight = nustd.ui.SliderRef.slot(label="Weight", min=1, max=3, step=1)


class Say(nustd.ui.Row):
    note = nustd.ui.InputRef.slot(placeholder="What in it bears on the claim, in a line")
    by = nustd.ui.SelectRef.slot(options=list(data.TEAM), selected=data.TEAM[0])
    add = nustd.ui.ButtonRef.slot(label="Put it on the board", icon="scale")


class Link(nustd.ui.Collapsible):
    pick = Pick.slot(gap=4, align="center")
    say = Say.slot(gap=3, align="end")


class View(nustd.ui.Column):
    link = Link.slot(title="Link this source to a claim", open=False)


@nu.host
def options(claims):
    return [{"value": k, "label": c["label"]} for k, c in sorted(claims.items(), key=lambda kv: kv[1]["label"])]


def out(plane):
    L = View.link

    def build(base, key):
        typed = kit.typed_evidence(key, nu.Str(L.pick.claim), nu.Str(L.pick.stance), nu.ToStr(L.pick.weight), nu.Str(L.say.note), nu.Str(L.say.by))
        add = nu.IfDo(nu.Str(L.pick.claim) != "", kit.add_evidence(base, typed) >> L.say.note.set(""))
        shown = (L.pick.claim.set("") >> L.pick.stance.set("for") >> L.pick.weight.set_value(2.0) >> L.say.note.set("")
                 >> L.say.by.set(data.TEAM[0]) >> L.say.add.set_label("Put it on the board"))
        return shown >> nu.ParallelAsync(
            redraws(kit.changes("claims"), options(Desk.claims.extract()), L.pick.claim.set_options),
            nu.ReactForever(L.say.add.on_click(), add),
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
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views

COLUMNS = [
    {"key": "label", "label": "Claim"},
    {"key": "topic", "label": "Topic", "width": 120},
    {"key": "status", "label": "Status", "width": 120},
    {"key": "score", "label": "Score", "kind": "number", "width": 90},
    {"key": "papers", "label": "Papers", "kind": "number", "width": 90},
    {"key": "ours", "label": "Our runs", "kind": "number", "width": 100},
]


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, label="Claims", dense=True, sort_column="score", sort_direction="desc")


@nu.host
def rows(d):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"])
    return [{"key": k, "label": c["label"], "topic": c.get("topic", ""), "status": sc[k]["status"],
             "score": round(sc[k]["score"], 2), "papers": sc[k]["papers"], "ours": sc[k]["ours"]}
            for k, c in sorted(d["claims"].items(), key=lambda kv: -sc[kv[0]]["score"])]


def out(plane):
    def build(base):
        opened = nu.ReactForever(View.table.on_row_click(), lambda ev: kit.go(View.nav, nu.Str("/") + kit.claim_page(base, nu.Str(ev["key"]))))
        return nu.ParallelAsync(redraws(kit.changes("claims", "evidence", "runs", "models", "probes"), rows(kit.whole()), View.table.set_rows), opened)

    return kit.on_desk(plane, build)
"""


ADD_CLAIM = r"""
import nu
import nustd.ui
from nudemos.research import data, kit


class Form(nustd.ui.Row):
    text = nustd.ui.InputRef.slot(placeholder="A claim to weigh, eg Longer contexts make retrieval worse")
    topic = nustd.ui.InputRef.slot(placeholder="Topic")
    add = nustd.ui.ButtonRef.slot(label="Put on the board", icon="plus")


class View(nustd.ui.Column):
    form = Form.slot(gap=3, align="end")


def out(plane):
    F = View.form

    def add(base):
        typed = kit.typed_claim(nu.Str(F.text), nu.Str(F.topic), data.TEAM[0])
        return nu.IfDo(nu.Str(F.text).strip() != "", kit.add_claim(base, typed) >> F.text.set("") >> F.topic.set(""))

    return F.text.set("") >> F.topic.set("") >> F.add.set_label("Put on the board") >> kit.on_desk(plane, lambda base: nu.ReactForever(F.add.on_click(), add(base)))
"""


CLAIMS = (("board", BOARD), ("table", CLAIM_TABLE), ("add", ADD_CLAIM))


# --- a claim page ----------------------------------------------------------------------------------


CLAIM_HEAD = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


class Tiles(nustd.ui.Row):
    status = nustd.ui.StatusPillRef.slot()
    score = nustd.ui.StatRef.slot(label="Score, -1 to 1")
    weight = nustd.ui.StatRef.slot(label="Weight for / against")
    papers = nustd.ui.StatRef.slot(label="From papers")
    ours = nustd.ui.StatRef.slot(label="From our runs")


class View(nustd.ui.Column):
    claim = nustd.ui.MarkdownRef.slot()
    tiles = Tiles.slot(gap=4, wrap=True)


@nu.host
def head(d, key):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"]).get(key)
    c = d["claims"].get(key) or {}
    if not sc:
        return {"claim": "", "status": "", "tone": "neutral", "score": "-", "weight": "-", "papers": "-", "ours": "-"}
    return {"claim": f"## {c['text']}\n\n{c.get('topic', '')}  ·  on the board since {views.ago(c.get('at') or 0)}",
            "status": sc["status"], "tone": sc["tone"], "score": f"{sc['score']:+.2f}",
            "weight": f"{sc['for']} / {sc['against']}", "papers": str(sc["papers"]), "ours": str(sc["ours"])}


def draw(v):
    T = View.tiles
    return (View.claim.set(v["claim"]) >> T.status.set(v["status"], tone=v["tone"]) >> T.score.set_value(v["score"])
            >> T.weight.set_value(v["weight"]) >> T.papers.set_value(v["papers"]) >> T.ours.set_value(v["ours"]))


def out(plane):
    return kit.on_page(plane, lambda base, key: redraws(kit.changes("claims", "evidence", "runs", "models", "probes"), head(kit.whole(), key), draw))
"""


CLAIM_HISTORY = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


class View(nustd.ui.Column):
    chart = nustd.ui.LineChart.slot(("score",), title="The score as evidence landed", x_type="time", step=True, symbols=True,
                                    y_min=-1, y_max=1, height=220, area=True)


@nu.host
def points(d, key):
    return views.history(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"]).get(key, [])


def out(plane):
    return kit.on_page(plane, lambda base, key: redraws(kit.changes("claims", "evidence", "runs", "models", "probes"), points(kit.whole(), key), View.chart.set))
"""


CLAIM_EVIDENCE = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


class View(nustd.ui.Row):
    pro = nustd.ui.MarkdownRef.slot()
    con = nustd.ui.MarkdownRef.slot()


def dots(w):
    return "●" * w + "○" * (3 - w)


@nu.host
def sides(d, key, base):
    sc = views.scores(d["claims"], d["evidence"], d["runs"], d["models"], d["probes"]).get(key)
    if not sc:
        return {"pro": "", "con": ""}

    def line(e):
        if e.get("kind") == "run":
            r = d["runs"].get(e["source"], {})
            what = f"[Our run: {views.title_of_run(r)}](/{base}.run.{e['source']})" if r else "Our runs"
        elif e.get("kind") == "models":
            what = f"[The model table](/{base}.models)"
        elif e.get("kind") == "probe":
            what = f"[The probe](/{base}.watch)"
        else:
            s = d["sources"].get(e["source"], {})
            what = f"[{s.get('title', e['source'])}](/{base}.src.{e['source']}) {s.get('year', '')}"
        return f"- {dots(e['weight'])}  {what}  \n  {e.get('note', '')}"

    pro = [line(e) for e in sc["items"] if e["stance"] == "for"]
    con = [line(e) for e in sc["items"] if e["stance"] == "against"]
    return {"pro": "#### For\n\n" + ("\n".join(pro) or "Nothing yet."), "con": "#### Against\n\n" + ("\n".join(con) or "Nothing yet.")}


def out(plane):
    draw = lambda v: View.pro.set(v["pro"]) >> View.con.set(v["con"])
    return kit.on_page(plane, lambda base, key: redraws(kit.changes(), sides(kit.whole(), key, base), draw))
"""


CLAIM_TAKE = r"""
import nu
import nustd.ui
from nudemos.research import kit
from nudemos.research.kit import Desk


class View(nustd.ui.Column):
    heading = nustd.ui.HeadingRef.slot(level=4)
    take = nustd.ui.MarkdownRef.slot()


@nu.host
def take_of(c):
    return (c or {}).get("take") or ""


def out(plane):
    def build(base, key):
        claim, take = Desk.claims[key], View.take
        return (
            View.heading.set_label("Our take")
            >> take.set(take_of(claim.fallback({})))
            >> take.set_editable(True)
            >> take.set_placeholder("Where we land, and what would change our mind. Markdown, kept as you type.")
            >> nu.ReactForever(take.on_change(), kit.patch(claim, nu.Dict.of(take=nu.Str(take))))
        )

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
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit
from nudemos.research.kit import Desk

COLUMNS = [
    {"key": "name", "label": "Model", "editable": False},
    {"key": "org", "label": "From", "editable": False, "width": 120},
    {"key": "year", "label": "Year", "kind": "number", "width": 70},
    {"key": "params", "label": "Params, B", "kind": "number", "width": 110},
    {"key": "active", "label": "Active, B", "kind": "number", "width": 110},
    {"key": "tokens", "label": "Tokens, T", "kind": "number", "width": 110},
    {"key": "ratio", "label": "Tokens per param", "editable": False, "width": 150},
    {"key": "open", "label": "Open weights", "kind": "bool", "width": 120},
]


class View(nustd.ui.Column):
    intro = nustd.ui.MarkdownRef.slot()
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", editable=True, label="Models", dense=True)


INTRO = """\
Models as their reports give them. Tokens per parameter is training tokens over total parameters:
about 20 is where Chinchilla put the compute-optimal point. Edit a number and the chart below, and the
[overtraining claim](CLAIM), follow. A blank token count means the report does not say."""


@nu.host
def rows(models):
    out = []
    for m in sorted(models.values(), key=lambda m: (m.get("year") or 0, m["name"])):
        ratio = m["tokens"] * 1000 / m["params"] if m.get("tokens") and m.get("params") else None
        out.append({**m, "tokens": m.get("tokens") or None, "ratio": f"{ratio:,.0f}" if ratio else "not disclosed"})
    return out


def edit(ev):
    row, col, value = Desk.models[nu.Str(ev["key"])], nu.Str(ev["column"]), ev["value"]
    typed = {"year": nu.ToInt(value), "params": nu.ToFloat(value), "active": nu.ToFloat(value),
             "tokens": nu.ToFloat(value), "open": nu.ToBool(value)}
    return nu.Sequential(*(nu.IfDo(col == k, kit.patch(row, nu.Dict.of(**{k: v}))) for k, v in typed.items()))


def out(plane):
    base = plane.rsplit(".", 1)[0]
    shown = redraws(kit.changes("models"), rows(Desk.models.extract()), View.table.set_rows)
    return View.intro.set(INTRO.replace("CLAIM", f"/{base}.claim.overtrain")) >> kit.on_desk(
        plane, lambda b: nu.ParallelAsync(shown, nu.ReactForever(View.table.on_edit(), edit))
    )
'''


MODEL_CHART = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit
from nudemos.research.kit import Desk


class View(nustd.ui.Column):
    chart = nustd.ui.ScatterChart.slot(
        ("Open weights", "Closed"), title="Tokens per parameter, by year (log scale; Chinchilla sits at 20)", symbol_size=14, x_label="Year",
        y_label="Tokens per parameter", x_format="{value}", tooltip_format="{b}", legend=True, height=360,
        x_type="category", option={"yAxis": {"type": "log"}, "xAxis": {"data": ["2020", "2021", "2022", "2023", "2024"]}},
    )


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
    return kit.on_desk(plane, lambda base: redraws(kit.changes("models"), points(Desk.models.extract()), View.chart.set))
"""


MODELS = (("table", MODEL_TABLE), ("chart", MODEL_CHART))


# --- evals -----------------------------------------------------------------------------------------


LAUNCH = r'''
import nu
import nustd.ui
from nuspace.system.utils import snap
from nudemos.research import data, evals, kit
from nudemos.research.claude import READY
from nudemos.research.kit import Desk

MODELS = [{"value": k, "label": v} for k, v in evals.MODELS.items()]
STYLES = [{"value": k, "label": v} for k, v in evals.STYLES.items()]
CONTEXTS = [{"value": k, "label": v} for k, v in evals.CONTEXTS.items()]

ABOUT = """\
A run puts the 20 questions of our suite to Claude, one at a time, in a job of its own: twelve word problems
in the style of GSM-IC, and eight that are hard to do in one go. *Distracted* adds a sentence that changes nothing.
Every answer is graded on its last number and lands on the leaderboard, the run's page, and the claims it bears on.
A Sonnet run costs about ten cents, a Haiku run about one."""


def field(name, ref):
    return type(name, (nustd.ui.Field,), {"choice": ref})


class Arm(nustd.ui.Grid):
    model = field("Model", nustd.ui.SelectRef.slot(options=MODELS, selected="haiku")).slot(label="Model")
    style = field("Style", nustd.ui.RadioGroupRef.slot(options=STYLES, selected="direct", orientation="horizontal")).slot(label="Asked for")
    context = field("Context", nustd.ui.RadioGroupRef.slot(options=CONTEXTS, selected="noisy", orientation="horizontal")).slot(label="Context")


class Go(nustd.ui.Row):
    run = nustd.ui.ButtonRef.slot(label="Run this arm", icon="play")
    four = nustd.ui.ButtonRef.slot(label="Run all four arms", icon="layers", variant="secondary")
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    about = nustd.ui.MarkdownRef.slot()
    arm = Arm.slot(columns=3, min_width=200, gap=4)
    go = Go.slot(gap=3)


def out(plane):
    A = View.arm

    def launch(base, style, context, n):
        run = kit.new_run(nu.Str(A.model.choice), style, context, data.TEAM[1], n)
        return kit.launch_run(base, run)

    def one(base):
        return nu.let(nu.Str(A.style.choice), lambda s: nu.let(nu.Str(A.context.choice), lambda c: launch(base, s, c, 0)))

    def four(base):
        arms = [(s, c) for s in evals.STYLES for c in evals.CONTEXTS]
        return nu.Sequential(*(launch(base, s, c, i) for i, (s, c) in enumerate(arms)))

    if not READY:
        return View.about.set("**Runs need the Claude Agent SDK.** Install the `cc` extra of nustd.") >> nu.ForeverDo(nu.Delay(3600.0))
    said = (A.model.choice.set("haiku") >> A.style.choice.set("direct") >> A.context.choice.set("noisy")
            >> View.go.run.set_label("Run this arm") >> View.go.four.set_label("Run all four arms")
            >> View.go.note.set("Runs go on the leaderboard below as they start."))
    return View.about.set(ABOUT) >> said >> kit.on_desk(plane, lambda base: nu.ParallelAsync(
        nu.ReactForever(View.go.run.on_click(), one(base)),
        nu.ReactForever(View.go.four.on_click(), four(base)),
    ))
'''


LEADERBOARD = r"""
import nu
import nustd.ui
from nuspace import ops
from nuspace.system.utils import redraws
from nudemos.research import kit, views
from nudemos.research.kit import Desk

COLUMNS = [
    {"key": "arm", "label": "Arm"},
    {"key": "acc", "label": "Accuracy, %", "kind": "number", "width": 120},
    {"key": "word", "label": "Word problems", "width": 130},
    {"key": "hard", "label": "Hard in one go", "width": 130},
    {"key": "done", "label": "Answered", "width": 100},
    {"key": "median", "label": "Median reply", "width": 120},
    {"key": "cost", "label": "Cost", "width": 80},
    {"key": "status", "label": "Status", "width": 90},
    {"key": "when", "label": "When", "width": 110},
]


class View(nustd.ui.Column):
    nav = nustd.ui.NavRef.slot()
    heading = nustd.ui.HeadingRef.slot(level=4)
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="key", clickable_rows=True, label="Leaderboard", dense=True)


def out(plane):
    board = nu.host(views.leaderboard)

    def build(base):
        opened = nu.ReactForever(View.table.on_row_click(), lambda ev: kit.go(View.nav, nu.Str("/") + kit.run_page(base, nu.Str(ev["key"]))))
        return nu.ParallelAsync(redraws(kit.changes("runs"), board(Desk.runs.extract()), View.table.set_rows, every=20.0), opened)

    return View.heading.set_label("Leaderboard") >> kit.on_desk(plane, build)
"""


GRID = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import evals, kit, views
from nudemos.research.kit import Desk


class View(nustd.ui.Column):
    grid = nustd.ui.HeatmapChart.slot(
        title="Every question, every arm: the red cells are the misses", height=520, legend=False,
        option={"visualMap": {"inRange": {"color": ["#e5484d", "rgba(120, 140, 170, 0.22)"]}}},
    )


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
    return kit.on_desk(plane, lambda base: redraws(kit.changes("runs"), cells(Desk.runs.extract()), View.grid.set))
"""


EVALS = (("launch", LAUNCH), ("leaderboard", LEADERBOARD), ("grid", GRID))


# --- a run page ------------------------------------------------------------------------------------


RUN_HEAD = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import evals, kit, views
from nudemos.research.kit import Desk


class Tiles(nustd.ui.Grid):
    acc = nustd.ui.StatRef.slot(label="Accuracy")
    word = nustd.ui.StatRef.slot(label="Word problems")
    hard = nustd.ui.StatRef.slot(label="Hard in one go")
    median = nustd.ui.StatRef.slot(label="Median reply")
    cost = nustd.ui.StatRef.slot(label="Cost")


class Top(nustd.ui.Row):
    status = nustd.ui.StatusPillRef.slot()
    progress = nustd.ui.ProgressRef.slot()


class View(nustd.ui.Column):
    line = nustd.ui.MarkdownRef.slot()
    top = Top.slot(gap=4)
    tiles = Tiles.slot(columns=5, min_width=140, gap=3)


TONES = {"done": "ok", "running": "info", "queued": "neutral"}


@nu.host
def head(r):
    if not r:
        return {"line": "", "status": "Starting", "tone": "neutral", "progress": 0, "caption": "", "acc": "-",
                "word": "-", "hard": "-", "median": "-", "cost": "-"}
    right, n = views.accuracy(r)
    total = len(evals.BY_ID)
    row = next((x for x in views.leaderboard({r["key"]: r})), {})
    return {
        "line": f"Run by {r.get('by', 'the desk')}, {views.ago(r.get('at') or 0)}, on {evals.MODEL_IDS.get(r['model'], r['model'])}. "
                f"The model is told:\n\n> {evals.SYSTEM[r['style']]}",
        "status": r.get("status", "queued").title(), "tone": TONES.get(r.get("status"), "neutral"),
        "progress": round(100 * n / total), "caption": f"{n} of {total} answered",
        "acc": f"{right}/{n}" if n else "-", "word": row.get("word", "-"), "hard": row.get("hard", "-"),
        "median": row.get("median", "-"), "cost": row.get("cost", "-"),
    }


def draw(v):
    T = View.tiles
    return (View.line.set(v["line"]) >> View.top.status.set(v["status"], tone=v["tone"])
            >> View.top.progress.set(v["progress"], caption=v["caption"])
            >> nu.Sequential(*(getattr(T, k).set_value(v[k]) for k in ("acc", "word", "hard", "median", "cost"))))


def out(plane):
    return kit.on_page(plane, lambda base, key: redraws(kit.changes("runs"), head(Desk.runs[key].fallback(None)), draw, every=10.0))
"""


RUN_ANSWERS = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import evals, kit
from nudemos.research.kit import Desk

COLUMNS = [
    {"key": "label", "label": "Question"},
    {"key": "tier", "label": "Kind", "width": 120},
    {"key": "want", "label": "Answer", "width": 120},
    {"key": "got", "label": "Got", "width": 120},
    {"key": "mark", "label": "", "width": 60},
    {"key": "seconds", "label": "Seconds", "kind": "number", "width": 100},
]


class Reply(nustd.ui.Column):
    asked = nustd.ui.MarkdownRef.slot()
    said = nustd.ui.CodeRef.slot(language="markdown")


class View(nustd.ui.Column):
    table = nustd.ui.TableRef.slot(columns=COLUMNS, row_key="q", clickable_rows=True, label="Answers", dense=True)
    reply = Reply.slot(gap=2)


@nu.host
def rows(r):
    out = []
    for q, item in evals.BY_ID.items():
        a = ((r or {}).get("answers") or {}).get(q)
        fmt = lambda x: f"{x:,.10g}" if isinstance(x, (int, float)) else "-"
        out.append({"q": q, "label": item["label"], "tier": "hard in one go" if item.get("tier") == "hard" else "word problem",
                    "want": fmt(item["answer"]), "got": fmt(a["got"]) if a else "...",
                    "mark": ("right" if a["correct"] else "wrong") if a else "", "seconds": a["seconds"] if a else None})
    return out


@nu.host
def reply(r, q):
    answers = (r or {}).get("answers") or {}
    if not q:
        q = next(reversed(list(answers)), "")
    if q not in evals.BY_ID:
        return {"asked": "#### The reply\n\nNo answers yet.", "said": ""}
    a = answers.get(q)
    head = f"#### {evals.BY_ID[q]['label']}\n\n> {evals.prompt(q, (r or {}).get('context', 'clean'))}"
    return {"asked": head, "said": a["text"] if a else "Not asked yet."}


def out(plane):
    def build(base, key):
        run = Desk.runs[key].fallback(None)
        shown = lambda v: View.reply.asked.set(v["asked"]) >> View.reply.said.set(v["said"])
        # The latest answer as it lands; a row clicked shows that one instead, until the next lands.
        picked = nu.ReactForever(View.table.on_row_click(), lambda ev: nu.let(reply(run, nu.Str(ev["key"])), shown))
        return nu.ParallelAsync(
            redraws(kit.changes("runs"), rows(run), View.table.set_rows),
            redraws(kit.changes("runs"), reply(run, ""), shown),
            picked,
        )

    return kit.on_page(plane, build)
"""


RUN = (("head", RUN_HEAD), ("answers", RUN_ANSWERS))


# --- watch -----------------------------------------------------------------------------------------


PROBE_HEAD = r'''
import time

import nu
import nustd.time
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import evals, job, kit, views
from nudemos.research.kit import Desk

ABOUT = f"""\
A probe job asks Sonnet one question from our suite every {job.INTERVAL / 60:.0f} minutes, clean and distracted by turns,
at most {job.CAP} a day. It is how we would notice the model drift under us: a wrong answer, or a slower one, shows here first."""


class Tiles(nustd.ui.Grid):
    next = nustd.ui.StatRef.slot(label="Next question")
    today = nustd.ui.StatRef.slot(label="Asked today")
    acc = nustd.ui.StatRef.slot(label="Right, clean against distracted")
    median = nustd.ui.StatRef.slot(label="Median reply, last 50")


class Controls(nustd.ui.Row):
    status = nustd.ui.StatusPillRef.slot()
    now = nustd.ui.ButtonRef.slot(label="Probe now", icon="zap")
    paused = nustd.ui.SwitchRef.slot(label="Paused")


class View(nustd.ui.Column):
    about = nustd.ui.MarkdownRef.slot()
    controls = Controls.slot(gap=4)
    tiles = Tiles.slot(columns=4, min_width=150, gap=3)


@nu.host
def state(probe, probes, paused, now):
    p = probe or {}
    last = (probes or [])[-50:]
    asking = p.get("status") == "asking"
    wait = max(0, int(p.get("next_at", 0) - now))
    nxt = "asking now" if asking else ("paused" if paused else (f"in {wait // 60}:{wait % 60:02d}" if wait else "any moment"))
    q = (p.get("asking") or {}).get("q") if asking else None
    secs = sorted(x.get("seconds") or 0 for x in last)
    return {
        "status": ("Asking: " + evals.BY_ID[q]["label"]) if q in evals.BY_ID else ("Paused" if paused else "Waiting"),
        "tone": "info" if asking else ("warn" if paused else "ok"),
        "next": nxt,
        "today": f"{p.get('today', 0) if p.get('day') == time.strftime('%Y-%m-%d') else 0} of {job.CAP}",
        "acc": views.probe_split(probes or []),
        "median": f"{secs[len(secs) // 2]:.1f} s" if secs else "-",
    }


def draw(v):
    T, C = View.tiles, View.controls
    return (C.status.set(v["status"], tone=v["tone"]) >> T.next.set_value(v["next"]) >> T.today.set_value(v["today"])
            >> T.acc.set_value(v["acc"]) >> T.median.set_value(v["median"]))


def out(plane):
    C = View.controls

    def build(base):
        shown = state(Desk.probe.fallback({}), Desk.probes.extract(), Desk.paused.fallback(False), nustd.time.time())
        return nu.ParallelAsync(
            C.now.set_label("Probe now") >> C.paused.set(Desk.paused.fallback(False)) >> redraws(kit.changes("probe", "probes") + [Desk.paused.on_change()], shown, draw, every=1.0),
            nu.ReactForever(C.now.on_click(), Desk.asked.set(Desk.asked.fallback(0) + 1)),
            nu.ReactForever(C.paused.on_change(), Desk.paused.set(nu.ToBool(C.paused))),
        )

    return View.about.set(ABOUT) >> kit.on_desk(plane, build)
'''


PROBE_CHART = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit
from nudemos.research.kit import Desk


class View(nustd.ui.Column):
    chart = nustd.ui.LineChart.slot(("Clean", "Distracted"), title="Seconds per reply, every probe", x_type="time",
                                    symbols=True, y_min=0, height=240, option={"xAxis": {"min": "dataMin", "max": "dataMax"}})


@nu.host
def points(probes):
    out = {"Clean": [], "Distracted": []}
    for p in probes or []:
        out["Distracted" if p.get("context") == "noisy" else "Clean"].append([p["at"] * 1000, p.get("seconds") or 0])
    return out


def out(plane):
    return kit.on_desk(plane, lambda base: redraws(kit.changes("probes"), points(Desk.probes.extract()), View.chart.set))
"""


PROBE_FEED = r"""
import time

import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import evals, kit
from nudemos.research.kit import Desk

COLUMNS = [
    {"key": "when", "label": "When", "width": 90},
    {"key": "label", "label": "Question"},
    {"key": "context", "label": "Context", "width": 110},
    {"key": "got", "label": "Got", "width": 120},
    {"key": "mark", "label": "", "width": 70},
    {"key": "seconds", "label": "Seconds", "kind": "number", "width": 100},
]


class View(nustd.ui.Column):
    table = nustd.ui.TableRef.slot(columns=COLUMNS, label="Probe answers", dense=True)


@nu.host
def rows(probes):
    out = []
    for p in reversed((probes or [])[-25:]):
        q = evals.BY_ID.get(p["q"], {})
        out.append({"when": time.strftime("%H:%M", time.localtime(p["at"])), "label": q.get("label", p["q"]),
                    "context": "distracted" if p.get("context") == "noisy" else "clean",
                    "got": f"{p['got']:,.10g}" if isinstance(p.get("got"), (int, float)) else "-",
                    "mark": "right" if p.get("correct") else "wrong", "seconds": p.get("seconds")})
    return out


def out(plane):
    return kit.on_desk(plane, lambda base: redraws(kit.changes("probes"), rows(Desk.probes.extract()), View.table.set_rows))
"""


WATCH = (("probe", PROBE_HEAD), ("chart", PROBE_CHART), ("feed", PROBE_FEED))


# --- notebook --------------------------------------------------------------------------------------


ENTRIES = r"""
import nu
import nustd.ui
from nuspace.system.utils import redraws
from nudemos.research import kit, views


@nu.host
def pages(d):
    parts = []
    for n in views.notebook(d):
        live = "  ·  *live: its numbers are read from the desk*" if n.get("live") else ""
        parts.append(f"### {n['title']}\n\n*{n['when']}  ·  {n['by']}*{live}\n\n{n['text']}")
    return "\n\n---\n\n".join(parts)


def out(plane):
    text = nustd.ui.MarkdownRef("entries")
    return kit.on_desk(plane, lambda base: redraws(kit.changes(), pages(kit.whole()), text.set, every=60.0))
"""


WRITE = r"""
import time

import nu
import nustd.ui
from nudemos.research import data, kit
from nudemos.research.kit import Desk


class Head(nustd.ui.Row):
    title = nustd.ui.InputRef.slot(placeholder="A title for the entry")
    by = nustd.ui.SelectRef.slot(options=list(data.TEAM), selected=data.TEAM[2])
    add = nustd.ui.ButtonRef.slot(label="Add the entry", icon="pen-line")


class Compose(nustd.ui.Collapsible):
    head = Head.slot(gap=3, align="end")
    text = nustd.ui.TextAreaRef.slot(placeholder="What we did and what we saw. Markdown. Write {best}, {best_acc}, {cot_gap}, {noise_gap}, {runs}, {probe_acc} or {probe_split} and the entry keeps them current.")


class View(nustd.ui.Column):
    write = Compose.slot(title="Write an entry", open=False)


@nu.host
def entry(title, text, by):
    return {"title": title.strip(), "text": text.strip(), "by": by, "at": time.time(), "live": "{" in text}


def out(plane):
    W = View.write
    add = nu.IfDo(nu.Str(W.head.title).strip() != "", Desk.notebook.append(entry(nu.Str(W.head.title), nu.Str(W.text), nu.Str(W.head.by)))
                  >> W.head.title.set("") >> W.text.set(""))
    shown = W.head.title.set("") >> W.head.by.set(data.TEAM[2]) >> W.text.set("") >> W.head.add.set_label("Add the entry")
    return shown >> kit.on_desk(plane, lambda base: nu.ReactForever(W.head.add.on_click(), add))
"""


NOTEBOOK = (("write", WRITE), ("entries", ENTRIES))
