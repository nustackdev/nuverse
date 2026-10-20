"""What a Larkspur page says, read and written in plain Python: no Nu here.

A page's body is markdown plus a few marks, all of them read live:

- ``[[slug]]``, ``[[slug|label]]``: a link to another page.
- ``{{key}}``: a fact's value, defined once in the base.
- ``@slug``: a person.
- ``- [ ] text @owner due:2026-10-24``: a task, kept in the page it is written in.
- ``{{query name arg}}`` on a line of its own: a live table over the whole base.

Everything here takes the base as plain dicts (``docs`` by slug, ``facts`` by
key) and returns markdown or rows, so the cells stay short and the logic is
tested on its own.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any


__all__ = [
    "DAY",
    "KINDS",
    "ago",
    "all_tasks",
    "backlinks",
    "day",
    "digest",
    "facts_of",
    "graph",
    "health",
    "inline",
    "links_of",
    "meeting_body",
    "query",
    "render",
    "search",
    "set_task",
    "short_date",
    "slugify",
    "tasks_of",
]


DAY = 86400.0

LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
FACT = re.compile(r"\{\{([a-z0-9-]+)\}\}")
QUERY = re.compile(r"^\{\{query ([a-z-]+)(?: ([^}]*))?\}\}\s*$")
MENTION = re.compile(r"(?<![\w/@.\[])@([a-z]+)\b")
TASK = re.compile(r"^(\s*)- \[( |x|X)\] (.*)$")
DUE = re.compile(r"\s*due:(\d{4}-\d{2}-\d{2})")

#: Each kind of page: its label, its folder, its colour on the graph.
KINDS = {
    "wiki": {
        "label": "Handbook",
        "one": "Handbook page",
        "folder": "handbook",
        "color": "var(--chart-1)",
    },
    "project": {
        "label": "Projects",
        "one": "Project",
        "folder": "projects",
        "color": "var(--chart-2)",
    },
    "meeting": {
        "label": "Meetings",
        "one": "Meeting",
        "folder": "meetings",
        "color": "var(--chart-3)",
    },
    "decision": {
        "label": "Decisions",
        "one": "Decision",
        "folder": "decisions",
        "color": "var(--chart-4)",
    },
    "person": {"label": "People", "one": "Person", "folder": "people", "color": "var(--chart-5)"},
    "note": {"label": "Notes", "one": "Note", "folder": "notes", "color": "var(--chart-6)"},
}


# --- small things ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """``"Notes from the lab!"`` as ``notes-from-the-lab``."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "page"


def day(t: float) -> dt.date:
    """A unix time as the local date."""
    return dt.datetime.fromtimestamp(t).date()


def short_date(iso: str) -> str:
    """``2026-10-24`` as ``Oct 24``."""
    try:
        d = dt.date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d:%b} {d.day}"


def ago(t: float, now: float) -> str:
    """How long ago ``t`` was, in words: ``just now``, ``5 min ago``, ``3 days ago``."""
    s = max(0.0, now - (t or 0.0))
    if s < 45:
        return "just now"
    if s < 3600:
        return f"{round(s / 60)} min ago"
    if s < DAY:
        h = round(s / 3600)
        return f"{h} hour ago" if h == 1 else f"{h} hours ago"
    days = (day(now) - day(t)).days
    if days <= 1:
        return "yesterday"
    if days < 60:
        return f"{days} days ago"
    return f"{round(days / 30)} months ago"


def _href(base: str, slug: str) -> str:
    return f"/{base}.doc.{slug}"


def _name(docs: dict, slug: str) -> str:
    return (docs.get(slug) or {}).get("title") or slug


def _who(docs: dict, base: str, slug: str) -> str:
    return f"[{_name(docs, slug)}]({_href(base, slug)})" if slug in docs else slug


def _first(docs: dict, slug: str) -> str:
    return _name(docs, slug).split(" ")[0]


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _n(n: int, word: str) -> str:
    """``1 page``, ``3 pages``."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _table(head: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f"_{empty}_"
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


# --- reading a body -------------------------------------------------------------------------


def links_of(body: str) -> list[str]:
    """The pages a body links to, in order, each once."""
    seen: dict[str, None] = {}
    for m in LINK.finditer(body or ""):
        seen.setdefault(m.group(1).strip(), None)
    return list(seen)


def facts_of(body: str) -> list[str]:
    """The facts a body cites, each once."""
    return list(dict.fromkeys(FACT.findall(body or "")))


def tasks_of(slug: str, doc: dict) -> list[dict[str, Any]]:
    """The tasks written in a page: ``{key, doc, line, text, owner, due, done}`` each.

    ``key`` is the page and the line, which is what ticking one rewrites.
    """
    out = []
    for i, line in enumerate((doc.get("body") or "").split("\n")):
        m = TASK.match(line)
        if not m:
            continue
        rest = m.group(3)
        due = DUE.search(rest)
        owners = MENTION.findall(rest)
        text = MENTION.sub("", DUE.sub("", rest)).strip()
        text = LINK.sub(lambda lm: lm.group(2) or lm.group(1), text)
        out.append(
            {
                "key": f"{slug}:{i}",
                "doc": slug,
                "line": i,
                "text": re.sub(r"\s{2,}", " ", text),
                "owner": owners[0] if owners else "",
                "due": due.group(1) if due else "",
                "done": m.group(2) != " ",
            }
        )
    return out


def all_tasks(docs: dict) -> list[dict[str, Any]]:
    """Every task in every page, soonest due first."""
    tasks = [t for slug, d in docs.items() for t in tasks_of(slug, d)]
    return sorted(tasks, key=lambda t: (t["due"] or "9999", t["doc"], t["line"]))


def set_task(body: str, line: int, done: bool) -> str:
    """``body`` with the task on ``line`` ticked or unticked. Any other line is left alone."""
    lines = body.split("\n")
    if 0 <= line < len(lines) and TASK.match(lines[line]):
        lines[line] = re.sub(r"- \[( |x|X)\]", "- [x]" if done else "- [ ]", lines[line], count=1)
    return "\n".join(lines)


def backlinks(docs: dict, slug: str) -> list[tuple[str, str]]:
    """The pages linking ``slug``, each with the line that links it, newest first."""
    out = []
    for src, d in sorted(docs.items(), key=lambda kv: -(kv[1].get("updated") or 0)):
        if src == slug:
            continue
        for line in (d.get("body") or "").split("\n"):
            if any(m.group(1).strip() == slug for m in LINK.finditer(line)):
                out.append((src, line.strip()))
                break
    return out


def _mentions(docs: dict, slug: str) -> list[str]:
    """The meetings that link or mention ``slug``, newest first."""
    meetings = [
        (k, d)
        for k, d in docs.items()
        if d.get("kind") == "meeting"
        and k != slug
        and (slug in links_of(d.get("body", "")) or f"@{slug}" in (d.get("body") or ""))
    ]
    return [k for k, _ in sorted(meetings, key=lambda kv: -(kv[1].get("date") or 0))]


# --- rendering a body -----------------------------------------------------------------------


def inline(text: str, docs: dict, facts: dict, base: str) -> str:
    """One line of a body as plain markdown: links, facts and people drawn in."""

    def link(m: re.Match) -> str:
        slug, label = m.group(1).strip(), m.group(2)
        if slug in docs:
            return f"[{label or docs[slug]['title']}]({_href(base, slug)})"
        return f"~~{label or slug}~~"

    def fact(m: re.Match) -> str:
        f = facts.get(m.group(1))
        return f"[{f['value']}](/{base}.facts)" if f else f"`{m.group(1)}?`"

    def person(m: re.Match) -> str:
        slug = m.group(1)
        d = docs.get(slug)
        return (
            f"[{d['title']}]({_href(base, slug)})"
            if d and d.get("kind") == "person"
            else m.group(0)
        )

    text = LINK.sub(link, text)
    text = FACT.sub(fact, text)
    return MENTION.sub(person, text)


def _task_line(line: str, docs: dict, facts: dict, base: str, today: dt.date) -> str:
    m = TASK.match(line)
    if not m:
        return line
    rest = m.group(3)
    due = DUE.search(rest)
    tail = ""
    if due:
        when = dt.date.fromisoformat(due.group(1))
        late = m.group(2) == " " and when < today
        tail = f"  · _{'overdue, ' if late else 'due '}{short_date(due.group(1))}_"
    body = inline(DUE.sub("", rest).rstrip(), docs, facts, base)
    return f"{m.group(1)}- [{m.group(2).lower()}] {body}{tail}"


def render(slug: str, docs: dict, facts: dict, base: str, now: float) -> str:
    """A page's body as plain markdown: links, facts, people, tasks and queries drawn in."""
    today = day(now)
    out, fence = [], False
    for line in (docs.get(slug) or {}).get("body", "").split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
            out.append(line)
        elif fence:
            out.append(line)
        elif q := QUERY.match(line.strip()):
            out.append(query(q.group(1), (q.group(2) or "").strip(), docs, facts, base, now, slug))
        elif TASK.match(line):
            out.append(_task_line(line, docs, facts, base, today))
        else:
            out.append(inline(line, docs, facts, base))
    return "\n".join(out)


# --- queries --------------------------------------------------------------------------------


def _task_rows(
    tasks: list[dict], docs: dict, base: str, today: dt.date, who: bool = True
) -> list[list[str]]:
    rows = []
    for t in tasks:
        late = t["due"] and dt.date.fromisoformat(t["due"]) < today
        due = ("**overdue** " if late else "") + short_date(t["due"]) if t["due"] else ""
        row = [
            t["text"],
            _who(docs, base, t["owner"]) if who else "",
            due,
            _who(docs, base, t["doc"]),
        ]
        rows.append([c for i, c in enumerate(row) if who or i != 1])
    return rows


def query(
    name: str, arg: str, docs: dict, facts: dict, base: str, now: float, here: str = ""
) -> str:
    """A live table: one of the queries a page can hold. An unknown one says so."""
    today = day(now)
    open_tasks = [t for t in all_tasks(docs) if not t["done"]]
    if name == "open-decisions":
        rows = [
            [
                _who(docs, base, k),
                _who(docs, base, d.get("owner", "")),
                ago(d.get("updated") or 0, now),
            ]
            for k, d in sorted(docs.items())
            if d.get("kind") == "decision" and d.get("status") == "open"
        ]
        return _table(["Open decision", "Owner", "Last touched"], rows, "No open decisions.")
    if name == "tasks-due":
        n = int(arg or 7)
        due = [
            t
            for t in open_tasks
            if t["due"] and (dt.date.fromisoformat(t["due"]) - today).days <= n
        ]
        return _table(
            ["Task", "Owner", "Due", "In"],
            _task_rows(due, docs, base, today),
            f"Nothing due in the next {n} days.",
        )
    if name == "tasks":
        mine = [t for t in open_tasks if t["owner"] == arg]
        return _table(
            ["Open task", "Due", "In"],
            _task_rows(mine, docs, base, today, who=False),
            "No open tasks.",
        )
    if name == "project":
        linked = {k for k, d in docs.items() if arg in links_of(d.get("body", ""))} | {arg}
        mine = [t for t in open_tasks if t["doc"] in linked]
        return _table(
            ["Open task", "Owner", "Due", "In"],
            _task_rows(mine, docs, base, today),
            "No open tasks on this project.",
        )
    if name == "mentions":
        rows = [
            [_who(docs, base, k), day(docs[k].get("date") or 0).strftime("%b %-d")]
            for k in _mentions(docs, arg or here)
        ]
        return _table(["Meeting", "Date"], rows, "No meeting has mentioned it yet.")
    if name == "owned-by":
        mine = sorted(
            ((k, d) for k, d in docs.items() if d.get("owner") == arg and k != arg),
            key=lambda kv: -(kv[1].get("updated") or 0),
        )
        rows = [
            [
                _who(docs, base, k),
                KINDS.get(d.get("kind", ""), {}).get("one", ""),
                ago(d.get("updated") or 0, now),
            ]
            for k, d in mine
        ]
        return _table(["Page", "Kind", "Edited"], rows, "Owns no pages yet.")
    if name == "stale":
        rows = [
            [_who(docs, base, s["doc"]), _who(docs, base, s["owner"]), f"{s['days']} days"]
            for s in health(docs, facts, now)["stale"]
        ]
        return _table(["Stale page", "Owner", "Untouched for"], rows, "Nothing is stale.")
    if name == "recent":
        n = int(arg or 8)
        recent = sorted(docs.items(), key=lambda kv: -(kv[1].get("updated") or 0))[:n]
        rows = [
            [
                _who(docs, base, k),
                _first(docs, d.get("editor") or d.get("owner", "")),
                ago(d.get("updated") or 0, now),
            ]
            for k, d in recent
        ]
        return _table(["Page", "By", "Edited"], rows, "Nothing yet.")
    if name == "facts":
        rows = [
            [f["label"], f"[{f['value']}](/{base}.facts)", _first(docs, f.get("owner", ""))]
            for f in facts.values()
        ]
        return _table(["Fact", "Value", "Owner"], rows, "No facts yet.")
    return f"_Unknown query: {name}_"


# --- the base as a whole --------------------------------------------------------------------


def stale_days(facts: dict) -> int:
    """How many days untouched make a page stale: the ``stale-days`` fact, 60 without it."""
    try:
        return int(re.sub(r"[^0-9]", "", (facts.get("stale-days") or {}).get("value", "")) or 60)
    except ValueError:
        return 60


def health(docs: dict, facts: dict, now: float) -> dict[str, Any]:
    """What a careful editor would flag: stale pages, broken links, orphans, missing facts, late tasks."""
    today, limit = day(now), stale_days(facts)
    linked = {s for d in docs.values() for s in links_of(d.get("body", ""))}
    stale, broken, missing, orphans = [], [], [], []
    for k, d in sorted(docs.items()):
        days = (today - day(d.get("updated") or now)).days
        if (
            days > limit
            and d.get("kind") in ("wiki", "project", "person")
            and d.get("status") != "done"
        ):
            stale.append({"doc": k, "owner": d.get("owner", ""), "days": days})
        broken += [{"doc": k, "to": s} for s in links_of(d.get("body", "")) if s not in docs]
        missing += [{"doc": k, "fact": f} for f in facts_of(d.get("body", "")) if f not in facts]
        if k not in linked and d.get("kind") in ("wiki", "project", "decision"):
            orphans.append({"doc": k, "owner": d.get("owner", "")})
    overdue = [
        {"key": t["key"], "doc": t["doc"], "text": t["text"], "owner": t["owner"], "due": t["due"]}
        for t in all_tasks(docs)
        if not t["done"] and t["due"] and dt.date.fromisoformat(t["due"]) < today
    ]
    issues = len(stale) + len(broken) + len(missing) + len(orphans)
    score = max(0, round(100 - 100 * issues / max(1, len(docs))))
    return {
        "stale": sorted(stale, key=lambda s: -s["days"]),
        "broken": broken,
        "missing": missing,
        "orphans": orphans,
        "overdue": overdue,
        "limit": limit,
        "score": score,
        "pages": len(docs),
        "links": sum(len(links_of(d.get("body", ""))) for d in docs.values()),
    }


def search(docs: dict, facts: dict, q: str, base: str, limit: int = 8) -> list[dict[str, str]]:
    """Pages and facts matching ``q``: title hits first, then body hits, each with its line."""
    words = [w for w in q.lower().split() if w]
    if not words:
        return []
    hits = []
    for k, d in docs.items():
        title, body = d.get("title", "").lower(), d.get("body") or ""
        if not all(w in title + " " + body.lower() for w in words):
            continue
        line = next((ln for ln in body.split("\n") if any(w in ln.lower() for w in words)), "")
        snippet = re.sub(
            r"[#>*`\-\[\]]+", " ", LINK.sub(lambda m: m.group(2) or _name(docs, m.group(1)), line)
        )
        snippet = FACT.sub(
            lambda m: (facts.get(m.group(1)) or {}).get("value", m.group(1)), snippet
        )
        score = (0 if all(w in title for w in words) else 1, -(d.get("updated") or 0))
        hits.append(
            (
                score,
                {
                    "title": d["title"],
                    "href": _href(base, k),
                    "kind": KINDS.get(d.get("kind", ""), {}).get("one", ""),
                    "snippet": " ".join(snippet.split())[:140],
                },
            )
        )
    for key, f in facts.items():
        if all(w in (f["label"] + " " + f["value"] + " " + key).lower() for w in words):
            hits.append(
                (
                    (0, 0),
                    {
                        "title": f["label"],
                        "href": f"/{base}.facts",
                        "kind": "Fact",
                        "snippet": f["value"],
                    },
                )
            )
    return [h for _, h in sorted(hits, key=lambda h: h[0])][:limit]


def graph(docs: dict, base: str) -> dict[str, Any]:
    """Every page as a node and every link as an edge, as an ECharts graph option's data."""
    degree: dict[str, int] = dict.fromkeys(docs, 0)
    edges = []
    for k, d in docs.items():
        for s in links_of(d.get("body", "")):
            if s in docs and s != k:
                # By title: an edge's tooltip reads "Weekly sync, Oct 6 > Pricing".
                edges.append({"source": d["title"], "target": docs[s]["title"]})
                degree[k] += 1
                degree[s] += 1
    cats = list(KINDS)
    nodes = [
        {
            "id": d["title"],
            "slug": k,
            "name": d["title"],
            "value": degree[k],
            "category": cats.index(d.get("kind")) if d.get("kind") in cats else 0,
            "symbolSize": 8 + min(26, degree[k] * 2.2),
            "label": {"show": degree[k] >= 11},
        }
        for k, d in docs.items()
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "categories": [{"name": KINDS[c]["label"]} for c in cats],
    }


def digest(docs: dict, facts: dict, log: list[dict], base: str, now: float, days: int = 7) -> str:
    """This week at Larkspur, written from the pages and what happened to them."""
    since = now - days * DAY
    today = day(now)
    changed = sorted(
        ((k, d) for k, d in docs.items() if (d.get("updated") or 0) >= since),
        key=lambda kv: -(kv[1].get("updated") or 0),
    )
    new = [k for k, d in changed if (d.get("created") or 0) >= since]
    meetings = [
        k for k, d in docs.items() if d.get("kind") == "meeting" and (d.get("date") or 0) >= since
    ]
    meetings.sort(key=lambda k: -(docs[k].get("date") or 0))
    decided = [
        k for k, d in changed if d.get("kind") == "decision" and d.get("status") == "decided"
    ]
    open_d = [
        k for k, d in docs.items() if d.get("kind") == "decision" and d.get("status") == "open"
    ]
    tasks = all_tasks(docs)
    week_end = today + dt.timedelta(days=7)
    coming = [
        t
        for t in tasks
        if not t["done"] and t["due"] and today <= dt.date.fromisoformat(t["due"]) <= week_end
    ]
    late = [
        t for t in tasks if not t["done"] and t["due"] and dt.date.fromisoformat(t["due"]) < today
    ]
    done_recent = [
        e for e in log if e.get("t", 0) >= since and e.get("what", "").startswith("ticked")
    ]
    editors: dict[str, int] = {}
    for _, d in changed:
        who = d.get("editor") or d.get("owner") or ""
        editors[who] = editors.get(who, 0) + 1
    busiest = sorted(editors.items(), key=lambda kv: -kv[1])[:3]
    h = health(docs, facts, now)

    def lst(keys: list[str], n: int = 6) -> str:
        shown = ", ".join(_who(docs, base, k) for k in keys[:n])
        return shown + (f" and {len(keys) - n} more" if len(keys) > n else "")

    lines = [
        f"_{day(since):%b} {day(since).day} to {today:%b} {today.day}, written from the base as it is right now._",
        "",
        "## In short",
        "",
        f"- **{len(changed)} pages** changed, {len(new)} of them new"
        + (f": {lst(new, 4)}." if new else "."),
        f"- **{len(meetings)} meetings**: {lst(meetings, 5)}."
        if meetings
        else "- No meetings this week.",
        f"- **Decided**: {lst(decided)}." if decided else "- Nothing was decided this week.",
        f"- **Still open**: {lst(open_d)}." if open_d else "- No decision is waiting.",
        f"- Most active: {', '.join(f'{_who(docs, base, w)} ({n})' for w, n in busiest)}."
        if busiest
        else "",
        "",
        "## Due in the next seven days",
        "",
        _table(
            ["Task", "Owner", "Due", "In"],
            _task_rows(coming[:10], docs, base, today),
            "Nothing due.",
        ),
        "",
        f"## Running late ({len(late)})",
        "",
        _table(
            ["Task", "Owner", "Due", "In"],
            _task_rows(late[:8], docs, base, today),
            "Nothing is late.",
        ),
        "",
        "## Needs a look",
        "",
        f"- {len(h['stale'])} pages untouched for more than {h['limit']} days"
        + (f": {lst([s['doc'] for s in h['stale']], 4)}." if h["stale"] else "."),
        f"- {_n(len(h['broken']), 'broken link')}, {_n(len(h['missing']), 'missing fact')}, {_n(len(h['orphans']), 'page')} nothing links to.",
    ]
    if done_recent:
        lines += ["", f"_{len(done_recent)} tasks ticked off here this week._"]
    return "\n".join(line for line in lines if line is not None)


def meeting_body(project: str, attendees: list[str], docs: dict, now: float) -> str:
    """A new meeting note that writes itself: who is there, what is open, what was said last time."""
    today = day(now)
    lines = [
        "**Attendees:** " + ", ".join(f"@{a}" for a in attendees)
        if attendees
        else "**Attendees:** ",
        "",
    ]
    if project in docs:
        lines += [f"**Project:** [[{project}]]", ""]
    last = next(iter(_mentions(docs, project)), "") if project else ""
    if last:
        lines += [f"Last time: [[{last}]].", ""]
    agenda = [
        f"- Where [[{project}]] stands" if project in docs else "- Where we are",
        "- What is still open, below",
    ]
    lines += ["## Agenda", "", *agenda, "- Anything else", ""]
    linked = {k for k, d in docs.items() if project and project in links_of(d.get("body", ""))} | {
        project
    }
    open_t = [
        t
        for t in all_tasks(docs)
        if not t["done"] and t["doc"] in linked and (not attendees or t["owner"] in attendees)
    ]
    if open_t:
        # Pointers, not copies: the task stays in its page, ticked there once.
        lines += ["## Still open", ""]
        for t in open_t[:8]:
            due = f", due {short_date(t['due'])}" if t["due"] else ""
            lines.append(f"- {t['text']}, @{t['owner']}{due} (in [[{t['doc']}]])")
        lines.append("")
    open_d = [
        k
        for k, d in docs.items()
        if d.get("kind") == "decision"
        and d.get("status") == "open"
        and (k in linked or project in links_of(d.get("body", "")))
    ]
    if open_d:
        lines += ["## Open decisions", ""] + [f"- [[{k}]]" for k in open_d] + [""]
    lines += [
        "## Notes",
        "",
        "",
        "## Action items",
        "",
        f"- [ ] Write up and share the notes @{'ines' if 'ines' in attendees or not attendees else attendees[0]} due:{today + dt.timedelta(days=1)}",
    ]
    return "\n".join(lines)
