"""What the cells read, shaped for the widgets: one host function per view.

Each takes the base as plain dicts (``pages``, the page ids it keeps, for
links, and the time, for anything that ages), and returns what one cell
draws: markdown, table rows, tiles, a chart's data. A row names a page as
``{page, label}``, its plane id and its title, never a url: the cell turns
it into a link with :func:`nudemos.pages.linked`. Times in rows are epoch ms,
for the browser's relative time.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import nu

from . import text
from .data import GLOSSARY, PEOPLE
from .text import KINDS, ago, all_tasks, day, short_date


__all__ = [
    "activity",
    "capture",
    "decisions",
    "digest",
    "doc_head",
    "doc_links",
    "fact_uses",
    "facts_rows",
    "glossary_rows",
    "graph_option",
    "graph_side",
    "health_view",
    "imports_view",
    "meeting_new",
    "meetings_rows",
    "notes_rows",
    "page",
    "page_query",
    "pages_rows",
    "people_cards",
    "person_view",
    "project_view",
    "projects_chart",
    "projects_view",
    "search",
    "slug_named",
    "task_rows",
    "tasks_chart",
    "tasks_option",
    "tiles",
    "welcome",
]


#: The tone of a page's status, on its head and in tables.
STATUS_TONES = {
    "open": "warn",
    "decided": "ok",
    "active": "info",
    "done": "ok",
    "paused": "neutral",
}

#: The tone of each kind of issue the checker flags.
ISSUE_TONES = {
    "Stale": "warn",
    "Broken link": "danger",
    "Missing fact": "danger",
    "Orphan": "neutral",
    "Late task": "warn",
}


def _link(docs: dict, pages: dict, slug: str) -> dict[str, str]:
    """A link to a doc page as a row carries it, ``{page, label}``: the plane id, never a url."""
    return {"page": text.page_of(pages, slug), "label": _name(docs, slug)}


def _ms(t: float) -> float:
    """A stored time (seconds) as a stamp for the browser (ms)."""
    return (t or 0.0) * 1000.0


def _name(docs: dict, slug: str) -> str:
    return (docs.get(slug) or {}).get("title") or (PEOPLE.get(slug) or (slug,))[0]


def _due_word(iso: str, today: dt.date) -> str:
    if not iso:
        return ""
    n = (dt.date.fromisoformat(iso) - today).days
    if n < 0:
        return f"{short_date(iso)}, {-n}d late"
    if n == 0:
        return "today"
    if n == 1:
        return "tomorrow"
    return short_date(iso)


@nu.host
def page(docs: dict, facts: dict, slug: str, pages: dict, now: float) -> str:
    """A doc's body, rendered: links, facts, people, tasks and queries drawn in."""
    if slug not in (docs or {}):
        return "_This page is not in the base any more._"
    return text.render(slug, docs, facts or {}, pages, now)


@nu.host
def doc_head(docs: dict, health: dict, slug: str, pages: dict) -> dict[str, Any]:
    """A doc's header line: kind, status or freshness, its owner, when and by whom it was edited, its tags."""
    d = (docs or {}).get(slug) or {}
    kind = KINDS.get(d.get("kind", ""), {}).get("one", "Page")
    status = d.get("status") or ""
    tone = STATUS_TONES.get(status, "neutral")
    stale = next((s for s in (health or {}).get("stale", []) if s["doc"] == slug), None)
    fresh = ("stale", "warn") if stale else ("fresh", "ok")
    if d.get("kind") == "meeting" and d.get("date"):
        fresh = (f"{day(d['date']):%b} {day(d['date']).day}", "info")
    elif d.get("kind") in ("meeting", "note", "decision"):
        fresh = (
            (d.get("source") or "").split(" (")[0] or "My notes" if d.get("kind") == "note" else "",
            "neutral",
        )
    editor = d.get("editor") or d.get("owner") or ""
    rest = [f"by {_name(docs, editor)}"] if d else []
    if d.get("source"):
        rest.append(f"imported from {d['source'].split(' (')[0]}")
    rest += [" ".join(f"#{t}" for t in d.get("tags") or [])]
    return {
        "kind": kind,
        "second": status or fresh[0] or kind,
        "second_tone": tone if status else fresh[1],
        "owner": _link(docs, pages, d.get("owner", "")),
        "edited": _ms(d.get("updated") or 0),
        "rest": "  ·  ".join(r for r in rest if r),
    }


@nu.host
def doc_links(docs: dict, facts: dict, slug: str, pages: dict) -> dict[str, Any]:
    """What links here, each with the line that does, where this page links to, and its broken links."""
    docs = docs or {}
    back = text.backlinks(docs, slug)[:12]
    out = text.links_of((docs.get(slug) or {}).get("body", ""))

    def excerpt(line: str) -> str:
        s = text.LINK.sub(lambda m: m.group(2) or _name(docs, m.group(1)), line)
        s = text.FACT.sub(lambda m: (facts or {}).get(m.group(1), {}).get("value", m.group(1)), s)
        s = text.MENTION.sub(lambda m: _name(docs, m.group(1)), s)
        s = re.sub(r"^[-*>#|\s]+|\[[ xX]\]\s*|\s*\|\s*$", "", s)
        s = re.sub(r"\s*due:\S+", "", s).replace(" | ", " · ")
        return (s[:110] + "...") if len(s) > 110 else s

    known = [s for s in out if s in docs]
    missing = [s for s in out if s not in docs]
    return {
        "back": [
            {"i": i, "link": _link(docs, pages, k), "excerpt": excerpt(line)}
            for i, (k, line) in enumerate(back)
        ],
        "back_count": f"{len(back)} {'page' if len(back) == 1 else 'pages'}",
        "out": [{"i": i, "link": _link(docs, pages, s)} for i, s in enumerate(known)],
        "out_count": f"{len(known)} {'page' if len(known) == 1 else 'pages'}",
        "broken": ("Broken: " + ", ".join(missing)) if missing else "",
    }


@nu.host
def tiles(docs: dict, facts: dict, health: dict, now: float) -> dict[str, dict[str, str]]:
    """Home's numbers."""
    docs, today = docs or {}, day(now)
    tasks = [t for t in all_tasks(docs) if not t["done"]]
    week = [
        t for t in tasks if t["due"] and 0 <= (dt.date.fromisoformat(t["due"]) - today).days <= 7
    ]
    late = [t for t in tasks if t["due"] and dt.date.fromisoformat(t["due"]) < today]
    open_d = [d for d in docs.values() if d.get("kind") == "decision" and d.get("status") == "open"]
    h = health or {}
    week_new = sum(1 for d in docs.values() if (d.get("updated") or 0) >= now - 7 * text.DAY)
    return {
        "pages": {
            "value": str(len(docs)),
            "delta": f"{week_new} this week",
            "trend": "up" if week_new else "flat",
        },
        "decisions": {"value": str(len(open_d)), "delta": "waiting", "trend": "flat"},
        "week": {"value": str(len(week)), "delta": f"of {len(tasks)} open", "trend": "flat"},
        "late": {
            "value": str(len(late)),
            "delta": "past due" if late else "none",
            "trend": "down" if late else "flat",
        },
        "stale": {
            "value": str(len(h.get("stale", []))),
            "delta": f"over {h.get('limit', 60)} days",
            "trend": "flat",
        },
        "health": {
            "value": f"{h.get('score', '-')}",
            "delta": ago(h.get("checked_at") or 0, now) if h else "not yet",
            "trend": "flat",
        },
    }


@nu.host
def task_rows(
    docs: dict, pages: dict, now: float, who: str = "", within: int = -1, done: bool = False
) -> list[dict[str, Any]]:
    """Tasks as table rows: by owner (``""`` everyone), due within ``within`` days (-1 any), done ones or not."""
    today = day(now)
    rows = []
    for t in all_tasks(docs or {}):
        if (t["done"] and not done) or (who and t["owner"] != who):
            continue
        if within >= 0 and (
            not t["due"] or (dt.date.fromisoformat(t["due"]) - today).days > within
        ):
            continue
        rows.append(
            {
                "key": t["key"],
                "done": t["done"],
                "task": t["text"],
                "owner": _name(docs, t["owner"]).split(" ")[0],
                "due": _due_word(t["due"], today),
                "page": _link(docs, pages, t["doc"]),
            }
        )
    return rows


@nu.host
def tasks_chart(docs: dict, now: float) -> dict[str, list]:
    """Open tasks per person, split by late, this week and later: stacked bars."""
    today = day(now)
    people = list(PEOPLE)
    late, week, later = ([0] * len(people) for _ in range(3))
    for t in all_tasks(docs or {}):
        if t["done"] or t["owner"] not in people:
            continue
        i = people.index(t["owner"])
        n = (dt.date.fromisoformat(t["due"]) - today).days if t["due"] else 99
        (late if n < 0 else week if n <= 7 else later)[i] += 1
    names = [PEOPLE[p][0].split(" ")[0] for p in people]
    return {"names": names, "late": late, "week": week, "later": later}


@nu.host
def activity(log: list, docs: dict, pages: dict, n: int = 12) -> list[dict[str, Any]]:
    """What happened lately, newest first: who, what, the page it touched (when still a page), when."""
    rows = []
    for i, e in enumerate((log or [])[:n]):
        who = e.get("who", "")
        doc = e.get("doc", "")
        rows.append(
            {
                "i": i,
                "who": {"checker": "The checker", "importer": "The importer"}.get(who)
                or _name(docs, who),
                "what": e.get("what", ""),
                "link": _link(docs, pages, doc)
                if doc in (docs or {})
                else {"page": "", "label": ""},
                "at": _ms(e.get("t") or 0),
            }
        )
    return rows


@nu.host
def search(docs: dict, facts: dict, q: str, pages: dict) -> dict[str, Any]:
    """Search results as rows (``{i, link, kind, excerpt}``) and a note for when nothing matches."""
    q = (q or "").strip()
    hits = text.search(docs or {}, facts or {}, q, pages) if q else []
    return {
        "hits": [
            {
                "i": i,
                "link": {"page": h["page"], "label": h["title"]},
                "kind": h["kind"],
                "excerpt": h["excerpt"],
            }
            for i, h in enumerate(hits)
        ],
        "note": f"Nothing matches {q}." if q and not hits else "",
    }


@nu.host
def capture(title: str, docs: dict, now: float) -> dict[str, Any]:
    """A thought captured on Home, as a new note in My notes: ``{slug, doc}``, slug kept unique."""
    title = (title or "").strip()
    slug = base = "n-" + text.slugify(title)
    i = 2
    while slug in (docs or {}):
        slug, i = f"{base}-{i}", i + 1
    return {
        "slug": slug,
        "doc": {
            "title": title,
            "kind": "note",
            "folder": "notes",
            "body": f"Captured {day(now):%b} {day(now).day}.\n\n",
            "owner": "ines",
            "editor": "ines",
            "tags": ["inbox"],
            "status": "",
            "created": now,
            "updated": now,
            "date": 0.0,
            "source": "",
        },
    }


@nu.host
def pages_rows(docs: dict, health: dict, kind: str, pages: dict) -> list[dict[str, Any]]:
    """The pages of one kind as rows: title, owner, edited, freshness, links in."""
    stale = {s["doc"] for s in (health or {}).get("stale", [])}
    linked: dict[str, int] = {}
    for d in (docs or {}).values():
        for s in text.links_of(d.get("body", "")):
            linked[s] = linked.get(s, 0) + 1
    mine = sorted(
        ((k, d) for k, d in (docs or {}).items() if d.get("kind") == kind),
        key=lambda kv: kv[1]["title"],
    )
    return [
        {
            "key": k,
            "title": _link(docs, pages, k),
            "owner": _name(docs, d.get("owner", "")),
            "edited": _ms(d.get("updated") or 0),
            "fresh": {"label": "stale", "variant": "warn"}
            if k in stale
            else {"label": "fresh", "variant": "ok"},
            "links": linked.get(k, 0),
        }
        for k, d in mine
    ]


@nu.host
def notes_rows(docs: dict, pages: dict) -> list[dict[str, Any]]:
    """My notes, newest first, with where they came from."""
    mine = sorted(
        ((k, d) for k, d in (docs or {}).items() if d.get("kind") == "note"),
        key=lambda kv: -(kv[1].get("updated") or 0),
    )
    return [
        {
            "key": k,
            "title": _link(docs, pages, k),
            "from": d.get("source", "").split(" (")[0]
            or ("captured" if "inbox" in (d.get("tags") or []) else "written here"),
            "tags": ", ".join(d.get("tags") or []),
            "edited": _ms(d.get("updated") or 0),
        }
        for k, d in mine
    ]


def _progress(docs: dict, slug: str) -> tuple[int, int]:
    """A project's own tasks, done and all: the ones written in its page."""
    tasks = text.tasks_of(slug, docs.get(slug) or {})
    return sum(t["done"] for t in tasks), len(tasks)


@nu.host
def projects_view(docs: dict, pages: dict, now: float) -> dict[str, Any]:
    """Projects as rows, with progress counted from the tasks in and around each, and the chart's bars."""
    docs, today = docs or {}, day(now)
    rows, names, done_b, open_b = [], [], [], []
    for k, d in sorted(
        ((k, d) for k, d in docs.items() if d.get("kind") == "project"),
        key=lambda kv: kv[1]["title"],
    ):
        done, total = _progress(docs, k)
        linked = {s for s, dd in docs.items() if k in text.links_of(dd.get("body", ""))} | {k}
        nxt = min(
            (
                t["due"]
                for t in all_tasks(docs)
                if t["doc"] in linked and not t["done"] and t["due"]
            ),
            default="",
        )
        status = d.get("status", "")
        rows.append(
            {
                "key": k,
                "title": _link(docs, pages, k),
                "owner": _name(docs, d.get("owner", "")),
                "status": {"label": status, "tone": STATUS_TONES.get(status, "neutral")}
                if status
                else "",
                "progress": done / total if total else 0.0,
                "open": total - done,
                "next": _due_word(nxt, today),
            }
        )
        names.append(d["title"].replace("Fieldnote ", ""))
        done_b.append(done)
        open_b.append(total - done)
    return {"rows": rows, "names": names, "done": done_b, "open": open_b}


@nu.host
def project_view(docs: dict, slug: str, now: float) -> dict[str, Any]:
    """One project's progress: done of all, what is late, who has the most open."""
    docs, today = docs or {}, day(now)
    done, total = _progress(docs, slug)
    linked = {k for k, d in docs.items() if slug in text.links_of(d.get("body", ""))} | {slug}
    open_t = [t for t in all_tasks(docs) if t["doc"] in linked and not t["done"]]
    elsewhere = sum(1 for t in open_t if t["doc"] != slug)
    late = [t for t in open_t if t["due"] and dt.date.fromisoformat(t["due"]) < today]
    owners: dict[str, int] = {}
    for t in open_t:
        owners[t["owner"]] = owners.get(t["owner"], 0) + 1
    top = max(owners.items(), key=lambda kv: kv[1], default=("", 0))
    meetings = [k for k in linked if docs.get(k, {}).get("kind") == "meeting"]
    return {
        "value": done / total if total else 0.0,
        "caption": f"{done} of {total} tasks in this page done, and {elsewhere} more open in the {len(linked) - 1} pages linking it",
        "late": str(len(late)),
        "late_note": "here and in linked pages" if late else "nothing late",
        "top": _name(docs, top[0]).split(" ")[0] if top[0] else "-",
        "top_note": f"{top[1]} open" if top[0] else "",
        "meetings": str(len(meetings)),
    }


@nu.host
def person_view(docs: dict, slug: str, now: float) -> dict[str, str]:
    """One person's work in numbers."""
    docs, today = docs or {}, day(now)
    owns = sum(1 for k, d in docs.items() if d.get("owner") == slug and k != slug)
    open_t = [t for t in all_tasks(docs) if t["owner"] == slug and not t["done"]]
    late = sum(1 for t in open_t if t["due"] and dt.date.fromisoformat(t["due"]) < today)
    edits = sum(
        1
        for d in docs.values()
        if d.get("editor") == slug and (d.get("updated") or 0) >= now - 14 * text.DAY
    )
    role = (PEOPLE.get(slug) or ("", ""))[1]
    return {
        "role": role,
        "owns": str(owns),
        "open": str(len(open_t)),
        "late": str(late),
        "edits": str(edits),
    }


@nu.host
def people_cards(docs: dict, pages: dict) -> list[dict[str, Any]]:
    """Everyone, keyed by slug, with what they own and what is on them."""
    docs, out = docs or {}, []
    tasks = [t for t in all_tasks(docs) if not t["done"]]
    for slug, (name, role) in PEOPLE.items():
        owns = sum(1 for k, d in docs.items() if d.get("owner") == slug and k != slug)
        open_t = sum(1 for t in tasks if t["owner"] == slug)
        out.append(
            {
                "slug": slug,
                "name": name,
                "link": {"page": text.page_of(pages, slug), "label": name},
                "role": role,
                "note": f"owns {owns} pages  ·  {open_t} open tasks",
            }
        )
    return out


@nu.host
def decisions(docs: dict, pages: dict) -> list[dict[str, Any]]:
    """Decisions as rows, open first."""
    mine = [(k, d) for k, d in (docs or {}).items() if d.get("kind") == "decision"]
    mine.sort(key=lambda kv: (kv[1].get("status") != "open", kv[0]))
    return [
        {
            "key": k,
            "title": _link(docs, pages, k),
            "status": d.get("status") or "open",
            "owner": _name(docs, d.get("owner", "")),
            "touched": _ms(d.get("updated") or 0),
            "cited": sum(1 for dd in docs.values() if k in text.links_of(dd.get("body", ""))),
        }
        for k, d in mine
    ]


@nu.host
def meetings_rows(docs: dict, pages: dict) -> list[dict[str, Any]]:
    """Meetings, newest first: when, who, what they decided, what they left open."""
    docs = docs or {}
    mine = sorted(
        ((k, d) for k, d in docs.items() if d.get("kind") == "meeting"),
        key=lambda kv: -(kv[1].get("date") or 0),
    )
    rows = []
    for k, d in mine:
        body = d.get("body", "")
        people = [p for p in dict.fromkeys(text.MENTION.findall(body)) if p in PEOPLE]
        tasks = text.tasks_of(k, d)
        decided = [s for s in text.links_of(body) if docs.get(s, {}).get("kind") == "decision"]
        rows.append(
            {
                "key": k,
                "date": f"{day(d.get('date') or 0):%a %b} {day(d.get('date') or 0).day}",
                "title": _link(docs, pages, k),
                "people": len(people),
                "decisions": len(decided),
                "open": sum(1 for t in tasks if not t["done"]),
            }
        )
    return rows


@nu.host
def meeting_new(
    title: str, project: str, attendees: list, date: str, docs: dict, now: float
) -> dict[str, Any]:
    """A new meeting note that writes itself, as ``{slug, doc}``."""
    docs = docs or {}
    names = {v[0].lower(): k for k, v in PEOPLE.items()} | {
        v[0].split(" ")[0].lower(): k for k, v in PEOPLE.items()
    }
    who = [
        names.get(str(a).strip().lower().lstrip("@"), str(a).strip().lower().lstrip("@"))
        for a in attendees or []
    ]
    who = [w for w in dict.fromkeys(who) if w in PEOPLE]
    try:
        when = dt.datetime.fromisoformat(date[:10]).replace(hour=10).timestamp() if date else now
    except ValueError:
        when = now
    title = (title or "").strip() or (
        "Sync on " + _name(docs, project) if project in docs else "Meeting"
    )
    slug = base = "m-" + text.slugify(title)
    i = 2
    while slug in docs:
        slug, i = f"{base}-{i}", i + 1
    body = text.meeting_body(project if project in docs else "", who, docs, now)
    return {
        "slug": slug,
        "doc": {
            "title": title,
            "kind": "meeting",
            "folder": "meetings",
            "body": body + "\n",
            "owner": "ines",
            "editor": "ines",
            "tags": ["meeting"],
            "status": "",
            "created": now,
            "updated": now,
            "date": min(when, now + 30 * text.DAY),
            "source": "",
        },
    }


@nu.host
def facts_rows(docs: dict, facts: dict) -> list[dict[str, Any]]:
    """Facts as rows, with how many pages cite each."""
    cited: dict[str, int] = {}
    for d in (docs or {}).values():
        for f in text.facts_of(d.get("body", "")):
            cited[f] = cited.get(f, 0) + 1
    return [
        {
            "key": k,
            "label": f.get("label", k),
            "value": f.get("value", ""),
            "cite": "{{" + k + "}}",
            "owner": _name(docs, f.get("owner", "")).split(" ")[0],
            "cited": cited.get(k, 0),
            "changed": _ms(f.get("updated") or 0),
        }
        for k, f in (facts or {}).items()
    ]


@nu.host
def fact_uses(docs: dict, facts: dict, pages: dict) -> dict[str, list[dict[str, Any]]]:
    """Where each cited fact is cited: a head per fact (``{i, label, value, n}``), its links (``{i, j, link}``)."""
    heads, links = [], []
    for k, f in (facts or {}).items():
        where = [s for s, d in (docs or {}).items() if k in text.facts_of(d.get("body", ""))]
        if not where:
            continue
        i = len(heads)
        heads.append({"i": i, "label": f["label"], "value": f["value"], "n": len(where)})
        links += [{"i": i, "j": j, "link": _link(docs, pages, s)} for j, s in enumerate(where)]
    return {"heads": heads, "links": links}


@nu.host
def glossary_rows(docs: dict) -> list[dict[str, Any]]:
    """The glossary, with how many pages use each term, scanned live."""
    bodies = [(d.get("title", "") + "\n" + d.get("body", "")) for d in (docs or {}).values()]
    rows = []
    for term, meaning in GLOSSARY:
        short = term.split(" (")[0]
        pat = re.compile(rf"(?<![\w-]){re.escape(short)}s?(?![\w-])", re.I if len(short) > 4 else 0)
        rows.append(
            {
                "key": text.slugify(term),
                "term": term,
                "meaning": meaning,
                "used": sum(1 for b in bodies if pat.search(b)),
            }
        )
    return rows


@nu.host
def graph_option(docs: dict, pages: dict) -> dict[str, Any]:
    """The whole base as a force graph: pages as nodes, links as edges, coloured by kind."""
    g = text.graph(docs or {}, pages)
    return {
        "color": [KINDS[k]["color"] for k in KINDS],
        "legend": [{"data": [c["name"] for c in g["categories"]], "top": 0, "left": 0}],
        "tooltip": {"show": True, "formatter": "{b}"},
        "animationDurationUpdate": 600,
        "series": [
            {
                "type": "graph",
                "layout": "force",
                "roam": True,
                "draggable": True,
                "data": g["nodes"],
                "links": g["edges"],
                "categories": g["categories"],
                "force": {
                    "repulsion": 260,
                    "edgeLength": [60, 150],
                    "gravity": 0.06,
                    "layoutAnimation": True,
                },
                "label": {"position": "right", "fontSize": 11, "color": "inherit"},
                "lineStyle": {"color": "source", "opacity": 0.35, "width": 1, "curveness": 0.08},
                "emphasis": {
                    "focus": "adjacency",
                    "label": {"show": True},
                    "lineStyle": {"width": 2, "opacity": 0.9},
                },
                "top": 36,
            }
        ],
    }


@nu.host
def graph_side(docs: dict, pages: dict) -> dict[str, Any]:
    """The graph in words: its size, the hubs, the islands."""
    g = text.graph(docs or {}, pages)
    hubs = sorted(g["nodes"], key=lambda n: -n["value"])[:6]
    alone = [n for n in g["nodes"] if n["value"] == 0]
    link = lambda n: {"page": text.page_of(pages, n["slug"]), "label": n["name"]}  # noqa: E731
    return {
        "size": f"{len(g['nodes'])} pages, {len(g['edges'])} links",
        "hubs": [
            {"i": i, "link": link(n), "count": f"{n['value']} links"} for i, n in enumerate(hubs)
        ],
        "alone": [{"i": i, "link": link(n)} for i, n in enumerate(alone[:6])],
        "alone_count": f"{len(alone)} linked to nothing" if alone else "none, every page is linked",
    }


@nu.host
def health_view(health: dict, live: bool, docs: dict, pages: dict) -> dict[str, Any]:
    """The checker's word: its status line, the score, the issues as rows."""
    h, docs = health or {}, docs or {}

    def issue(key: str, slug: str, what: str, owner: str, detail: str) -> dict[str, Any]:
        return {
            "key": key,
            "issue": {"label": what, "variant": ISSUE_TONES[what]},
            "page": _link(docs, pages, slug),
            "owner": _name(docs, owner).split(" ")[0],
            "detail": detail,
        }

    def owner_of(slug: str) -> str:
        return docs.get(slug, {}).get("owner", "")

    rows = [
        issue(f"stale:{s['doc']}", s["doc"], "Stale", s["owner"], f"untouched for {s['days']} days")
        for s in h.get("stale", [])
    ]
    rows += [
        issue(
            f"broken:{b['doc']}:{b['to']}",
            b["doc"],
            "Broken link",
            owner_of(b["doc"]),
            f"links to {b['to']}, which is not a page",
        )
        for b in h.get("broken", [])
    ]
    rows += [
        issue(
            f"missing:{m['doc']}:{m['fact']}",
            m["doc"],
            "Missing fact",
            owner_of(m["doc"]),
            f"cites {m['fact']}, which is not defined",
        )
        for m in h.get("missing", [])
    ]
    rows += [
        issue(f"orphan:{o['doc']}", o["doc"], "Orphan", o["owner"], "no page links here")
        for o in h.get("orphans", [])
    ]
    rows += [
        issue(
            f"late:{t['key']}",
            t["doc"],
            "Late task",
            t["owner"],
            f"{t['text'][:60]}, due {short_date(t['due'])}",
        )
        for t in h.get("overdue", [])
    ]
    if not h:
        line, tone = "The checker has not run yet.", "neutral"
    else:
        line = f"Checked {h.get('pages', 0)} pages and {h.get('links', 0)} links in {h.get('took_ms', 0)} ms, run {h.get('runs', 0)} since it started. Last run"
        tone = "ok" if live else "neutral"
    return {
        "status": "running" if live else "stopped",
        "tone": tone,
        "pulse": bool(live),
        "line": line,
        "checked": _ms(h.get("checked_at") or 0),
        "score": float(h.get("score", 0)),
        "gauge": float(h.get("score", 0)) / 100.0,
        "caption": f"{len(rows)} things to look at",
        "rows": rows,
        "history": [p[1] for p in h.get("history", [])],
        "limit": h.get("limit", 60),
    }


@nu.host
def imports_view(imports: dict, live: bool, now: float) -> dict[str, Any]:
    """The importer's progress, for its bar and its log."""
    p = imports or {}
    total, done = int(p.get("total") or 0), int(p.get("done") or 0)
    status = p.get("status") or "idle"
    if status == "importing":
        caption = f"{done} of {total}: {p.get('current', '')}"
    elif status == "done":
        caption = f"Done: {total} notes, {ago(p.get('finished') or 0, now)}"
    elif status == "starting":
        caption = "Starting the importer in its own process..."
    else:
        caption = "Nothing imported yet."
    log = (
        "\n".join(f"- {line}" for line in p.get("lines") or [])
        or "_The importer's log shows here._"
    )
    return {
        "value": (done / total) if total else (1.0 if status == "done" else 0.0),
        "caption": caption,
        "busy": status in ("importing", "starting"),
        "status": {"importing": "importing", "starting": "starting", "done": "done"}.get(
            status, "idle"
        ),
        "tone": {"importing": "info", "starting": "info", "done": "ok"}.get(status, "neutral"),
        "log": log,
    }


@nu.host
def page_query(name: str, arg: str, docs: dict, facts: dict, pages: dict, now: float) -> str:
    """One of the queries a page can hold, on its own."""
    return text.query(name, arg, docs or {}, facts or {}, pages, now)


@nu.host
def digest(docs: dict, facts: dict, log: list, pages: dict, now: float) -> str:
    """This week, written from the base."""
    return text.digest(docs or {}, facts or {}, log or [], pages, now)


@nu.host
def slug_named(title: str, docs: dict) -> str:
    """The slug of the page called ``title``, for a click on the graph."""
    return next((k for k, d in (docs or {}).items() if d.get("title") == title), "")


@nu.host
def first(rows: list, n: int) -> list:
    """The first ``n`` rows."""
    return list(rows or [])[:n]


@nu.host
def more(rows: list, n: int) -> str:
    """A line saying how many rows are not shown, ``""`` when all are."""
    left = len(rows or []) - n
    return f"And {left} more on Tasks" if left > 0 else ""


@nu.host
def projects_chart(v: dict) -> dict[str, Any]:
    """Projects' tasks, done and open, as stacked bars."""

    def bar(name: str, key: str, color: str) -> dict[str, Any]:
        return {
            "name": name,
            "type": "bar",
            "stack": "t",
            "data": v[key],
            "itemStyle": {"color": color},
            "barWidth": 18,
        }

    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0, "left": 0},
        "grid": {"left": 4, "right": 16, "top": 32, "bottom": 4, "containLabel": True},
        "yAxis": {"type": "category", "data": v["names"], "inverse": True},
        "xAxis": {"type": "value", "minInterval": 1},
        "series": [bar("Done", "done", "var(--chart-2)"), bar("Open", "open", "var(--chart-4)")],
    }


def launch_in(value: str, now: float) -> int | None:
    """Days from now to a date written like ``Nov 17``: this year's, or next year's once well past."""
    today = day(now)
    try:
        d = dt.datetime.strptime(f"{value.strip()} {today.year}", "%b %d %Y").date()
    except ValueError:
        return None
    if (d - today).days < -60:
        d = d.replace(year=d.year + 1)
    return (d - today).days


@nu.host
def welcome(facts: dict, pages: dict, now: float) -> str:
    """Home's opening lines, the launch date read from its fact."""
    launch = ((facts or {}).get("launch-date") or {}).get("value", "")
    n = launch_in(launch, now) if launch else None
    when = f"[{launch}]({text._view(pages, 'facts')})"
    if n is None:
        line = f"Fieldnote v2 launches on {when}."
    elif n > 1:
        line = f"Fieldnote v2 launches on {when}, **in {n} days**."
    elif n == 1:
        line = f"Fieldnote v2 launches **tomorrow**, {when}."
    elif n == 0:
        line = f"Fieldnote v2 launches **today**, {when}."
    else:
        line = f"Fieldnote v2 launched on {when}, {-n} days ago."
    return (
        "Larkspur makes **Fieldnote**, a soil sensor and app for small farms and community gardens. "
        f"{line}\n\n"
        "This is where the team keeps how it works and what it is doing, and where I keep my own notes. "
        "Every page is a small program over one base: a fact is written once and cited everywhere, "
        "tables inside pages are live queries, links run both ways, and a checker in its own process keeps it honest. "
        f"Start with the [handbook]({text._view(pages, 'handbook')}), this week's [digest]({text._view(pages, 'digest')}), the [graph]({text._view(pages, 'graph')}), "
        f"or [ask the base]({text._view(pages, 'ask')})."
    )


@nu.host
def tasks_option(v: dict) -> dict[str, Any]:
    """Open tasks per person, late, this week and later, as stacked bars."""

    def bar(name: str, key: str, color: str) -> dict[str, Any]:
        return {
            "name": name,
            "type": "bar",
            "stack": "t",
            "data": v[key],
            "itemStyle": {"color": color},
            "barWidth": 22,
        }

    return {
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 0, "left": 0},
        "grid": {"left": 4, "right": 16, "top": 32, "bottom": 4, "containLabel": True},
        "xAxis": {"type": "category", "data": v["names"]},
        "yAxis": {"type": "value", "minInterval": 1},
        "series": [
            bar("Late", "late", "var(--status-danger)"),
            bar("This week", "week", "var(--chart-1)"),
            bar("Later", "later", "var(--chart-3)"),
        ],
    }
