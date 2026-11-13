"""The knowledge demo's plain-Python half: pages read, rendered, queried, checked and imported."""

from __future__ import annotations

import time

import pytest

from nudemos.knowledge import ask, cells, data, jobs, seed, text


NOW = time.mktime((2026, 10, 20, 12, 0, 0, 0, 0, -1))


@pytest.fixture(scope="module")
def base() -> tuple[dict, dict]:
    return seed.base(data.DOCS, data.FACTS, NOW)


def _pages(docs: dict) -> dict:
    """The page ids a base keeps, as a seeded one would: a doc page per slug, the Facts page."""
    return {"doc": {slug: f"p-{slug}" for slug in docs}, "view": {"facts": "p-facts"}}


def test_every_cell_source_parses() -> None:
    sources = list(cells.ROOT) + [c for kind in cells.DOC_CELLS.values() for c in kind]
    sources += [c for view in cells.VIEW_CELLS.values() for c in view] + list(cells.COLLECTION)
    sources += [("checker", jobs.CHECKER), ("importer", jobs.IMPORTER)]
    for name, source in sources:
        compile(source, name, "exec")


def test_seed_dates_resolve_from_the_day_opened(base: tuple[dict, dict]) -> None:
    docs, facts = base
    assert "due:+" not in "".join(d["body"] for d in docs.values())
    assert facts["launch-date"]["value"] == "Nov 17"
    meetings = [d for d in docs.values() if d["kind"] == "meeting"]
    assert all(text.day(d["date"]).weekday() < 5 for d in meetings)
    assert all(d["updated"] <= NOW for d in docs.values())


def test_links_facts_and_people_render(base: tuple[dict, dict]) -> None:
    docs, facts = base
    pages = _pages(docs)
    md = text.render("pricing", docs, facts, pages, NOW)
    assert f"[{facts['price']['value']}](/p/p-facts)" in md
    assert "{{" not in md
    assert "](/p/p-arlo)" in md
    assert (
        "~~" not in text.inline("[[pricing]] and [[nowhere]]", docs, facts, pages).split(" and ")[0]
    )
    assert "~~nowhere~~" in text.inline("[[nowhere]]", docs, facts, pages)
    # A page the base has made no plane for yet links nowhere.
    assert "](/p/p-facts)" not in text.render("pricing", docs, facts, {"doc": {}}, NOW)


def test_a_fact_changed_once_shows_everywhere(base: tuple[dict, dict]) -> None:
    docs, facts = base
    facts = {**facts, "price": {**facts["price"], "value": "$79"}}
    citing = [k for k, d in docs.items() if "price" in text.facts_of(d["body"])]
    assert len(citing) >= 2
    pages = _pages(docs)
    assert all("[$79](/p/p-facts)" in text.render(k, docs, facts, pages, NOW) for k in citing)


def test_tasks_parse_and_tick_in_their_page() -> None:
    doc = {
        "body": "Intro\n- [ ] Order boxes @theo due:2026-10-18\n- [x] Lock scope @mara due:2026-10-01"
    }
    tasks = text.tasks_of("v2", doc)
    assert [(t["text"], t["owner"], t["due"], t["done"]) for t in tasks] == [
        ("Order boxes", "theo", "2026-10-18", False),
        ("Lock scope", "mara", "2026-10-01", True),
    ]
    ticked = text.set_task(doc["body"], 1, True)
    assert ticked.split("\n")[1].startswith("- [x] Order boxes")
    assert text.set_task(doc["body"], 0, True) == doc["body"]


def test_queries_are_tables_over_the_base(base: tuple[dict, dict]) -> None:
    docs, facts = base
    pages = _pages(docs)
    decisions = text.query("open-decisions", "", docs, facts, pages, NOW)
    assert decisions.startswith("| Open decision |")
    assert decisions.count("\n") - 1 == sum(
        1 for d in docs.values() if d["kind"] == "decision" and d["status"] == "open"
    )
    assert "Unknown query" in text.query("nope", "", docs, facts, pages, NOW)
    assert "](/p/p-" in text.query("owned-by", "theo", docs, facts, pages, NOW)


def test_backlinks_find_the_line_that_links(base: tuple[dict, dict]) -> None:
    docs, _ = base
    back = dict(text.backlinks(docs, "pricing"))
    assert back
    assert all("[[pricing" in line for line in back.values())


def test_health_flags_what_the_content_plants(base: tuple[dict, dict]) -> None:
    docs, facts = base
    h = text.health(docs, facts, NOW)
    assert {s["doc"] for s in h["stale"]} == {"lab-rules", "expenses", "security-basics"}
    assert [b["to"] for b in h["broken"]] == ["gateway-setup"]
    assert [m["fact"] for m in h["missing"]] == ["warranty-years"]
    assert [o["doc"] for o in h["orphans"]] == ["tools"]
    stricter = {**facts, "stale-days": {**facts["stale-days"], "value": "30"}}
    assert len(text.health(docs, stricter, NOW)["stale"]) > 3


def test_the_checker_logs_only_what_is_new(base: tuple[dict, dict]) -> None:
    docs, facts = base
    first = jobs.check(docs, facts, {}, NOW)
    assert first["events"] == []
    fresh = {**docs, "lab-rules": {**docs["lab-rules"], "updated": NOW}}
    second = jobs.check(fresh, facts, first["health"], NOW + 20)
    assert [(e["what"], e["doc"]) for e in second["events"]] == [
        ("cleared, fresh again", "lab-rules")
    ]
    assert second["health"]["runs"] == 2


def test_the_importer_plans_every_note_into_a_folder(base: tuple[dict, dict]) -> None:
    docs, _ = base
    plan = jobs.plan("lab-notebook", docs, NOW)
    assert len(plan["notes"]) == 10
    assert plan["notes"][0]["slug"] == "lab-index"
    assert all(n["new"] and n["doc"]["folder"] == "notes.lab-notebook" for n in plan["notes"])
    assert all("due:+" not in n["doc"]["body"] for n in plan["notes"])
    p = jobs.step({}, None, 10, NOW, "x")
    p = jobs.step(p, plan["notes"][0], 10, NOW)
    assert (p["status"], p["done"]) == ("importing", 1)
    assert jobs.step(p, None, 10, NOW)["status"] == "done"


def test_a_meeting_note_writes_itself(base: tuple[dict, dict]) -> None:
    docs, _ = base
    body = text.meeting_body("battery-push", ["theo", "ravi", "ines"], docs, NOW)
    assert "@theo" in body and "[[battery-push]]" in body
    assert "## Still open" in body and "## Open decisions" in body
    assert sum(1 for line in body.split("\n") if text.TASK.match(line)) == 1


def test_ask_prompt_and_citations(base: tuple[dict, dict]) -> None:
    docs, facts = base
    p = ask.prompt(docs, facts, "When do we launch?", NOW)
    assert "{{" not in p and "[[v2-launch]]" in p and p.endswith("When do we launch?")
    assert (
        ask.cited("late [[a]] [[b]]. See [[c]] for more, end [[d]]")
        == "late ([[a]], [[b]]). See [[c]] for more, end ([[d]])"
    )


def test_digest_reads_the_week(base: tuple[dict, dict]) -> None:
    docs, facts = base
    md = text.digest(docs, facts, [], _pages(docs), NOW)
    assert "## Due in the next seven days" in md and "Still open" in md


def test_an_imported_notebook_leaves_the_base_healthy(base: tuple[dict, dict]) -> None:
    docs, facts = base
    before = text.health(docs, facts, NOW)
    imported = {
        **docs,
        **{n["slug"]: n["doc"] for n in jobs.plan("lab-notebook", docs, NOW)["notes"]},
    }
    after = text.health(imported, facts, NOW)
    assert after["broken"] == before["broken"]
    assert after["missing"] == before["missing"]
    assert not any(o["doc"].startswith("lab-") for o in after["orphans"])


# --- on a store --------------------------------------------------------------------------------


def _all_sources() -> dict[str, str]:
    found = {f"root.{name}": source for name, source in cells.ROOT}
    for kind, group in cells.DOC_CELLS.items():
        found.update({f"doc.{kind}.{name}": source for name, source in group})
    for view, group in cells.VIEW_CELLS.items():
        found.update({f"view.{view}.{name}": source for name, source in group})
    found.update({f"collection.{name}": source for name, source in cells.COLLECTION})
    found["checker"], found["importer"] = jobs.CHECKER, jobs.IMPORTER
    return found


SOURCES = _all_sources()


@pytest.mark.parametrize("name", list(SOURCES))
async def test_every_cell_loads(store, name) -> None:
    import nu
    import nuspace
    from nuspace import Space

    await store.do(nuspace.plane.add("p", backend="async"))
    await store.do(nuspace.cell.add("p", SOURCES[name], id="c"))
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"})
    nu.validate(nu.compile(await store.run(nuspace.atomic(load))))


async def test_the_first_open_makes_every_page_once_and_the_checker(store) -> None:
    import nu
    import nuspace.specs
    from nudemos.knowledge import PLANE, kit
    from nuspace import Space
    from nuspace.system.supervisor import ON_FAILURE, Policy

    await store.run(nuspace.specs.add_plane(PLANE, "k"))
    await store.run(kit.seed(nu.Str("k")))
    await store.run(kit.seed(nu.Str("k")))
    b = kit.base_at("k")
    pages = await store.read(b.planes.extract())
    assert set(pages["view"]) == {name for name, _, _ in kit.VIEWS}
    docs = await store.read(b.docs.extract())
    assert set(pages["doc"]) == set(docs)
    assert await store.read(Space.planes["k"].name) == "Larkspur"
    pricing = pages["doc"]["pricing"]
    assert (
        await store.read(Space.planes[pricing].parent) == pages["view"][docs["pricing"]["folder"]]
    )
    assert await store.read(Space.planes[pricing].meta.extract()) == {"subject": "pricing"}
    assert await store.read(kit.base_of(pricing)) == "k"
    assert await store.read(Space.planes[pricing].icon) == kit.ICONS[docs["pricing"]["kind"]]
    # Seeded twice, made once: the root holds its folders and tools, then the checker.
    kids = await store.read(nu.list(Space.planes["k"].children.keys()))
    checker = await store.read(kit.job_of("k", "checker"))
    assert kids == [pages["view"][name] for name, _, _ in kit.VIEWS] + [checker]
    assert await store.read(Space.planes[checker].spec) == "knowledge_checker"
    assert await store.read(kit.base_of(checker)) == "k"
    policy = nuspace.at.plane(id="supervisor").state(Policy).planes[checker].policy
    assert await store.read(policy) == ON_FAILURE
    assert await store.read(kit.live("k", "checker")) is False
    # A second start writes the job's prog again, on the same job.
    await store.run(kit.start_checker(nu.Str("k")))
    assert await store.read(kit.job_of("k", "checker")) == checker


async def test_a_doc_page_links_the_pages_the_base_made(store) -> None:
    import asyncio

    import nu
    import nuspace
    import nuspace.places
    import nuspace.specs
    from nudemos.knowledge import PLANE, kit
    from nuspace import Space
    from nuspace.specs import SpecCells
    from nuspace.web.env import session_env
    from nustd.ui.core import WsSession
    from nustd.ui.core.session import Session

    class Browser(WsSession):
        def __init__(self) -> None:
            super().__init__(ws=None)
            self.drawn: list = []

        async def send(self, frame) -> None:
            if frame.ref and frame.ref[-1] == "page":
                self.drawn.append(frame.payload)

    await store.run(nuspace.specs.add_plane(PLANE, "k"))
    await store.run(kit.seed(nu.Str("k")))
    pages = await store.read(kit.base_at("k").planes.extract())
    pricing = pages["doc"]["pricing"]
    cell = await store.read(nuspace.at.plane(id=pricing).state(SpecCells).ids["page"])
    env = session_env("127.0.0.1:9")("s1")
    load = Space.cells[cell].prog.load(scope={"plane": pricing, "cell": cell}, rewrite=env.rewrite)
    term = nuspace.places.inside(await store.run(nuspace.atomic(load)), plane=pricing, cell=cell)
    browser = Browser()
    task = asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))
    try:
        for _ in range(200):
            if browser.drawn:
                break
            await asyncio.sleep(0.05)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    md = str(browser.drawn[-1])
    assert f"](/p/{pages['doc']['arlo']})" in md
    assert f"](/p/{pages['view']['facts']})" in md


# --- what the cells draw ------------------------------------------------------------------------


def _call(host, *args):
    """A view, run on plain values."""
    import nu

    got, _ = nu.run(host(*args))
    return got


def test_rows_name_pages_by_id_never_by_url(base: tuple[dict, dict]) -> None:
    from nudemos.knowledge import views

    docs, facts = base
    pages = _pages(docs)
    links = _call(views.doc_links, docs, facts, "pricing", pages)
    assert links["back"] and all(r["link"]["page"].startswith("p-") for r in links["back"])
    assert [r["i"] for r in links["out"]] == list(range(len(links["out"])))
    hits = _call(views.search, docs, facts, "battery", pages)
    assert hits["hits"] and hits["note"] == ""
    assert {"page", "label"} == set(hits["hits"][0]["link"])
    assert _call(views.search, docs, facts, "zzzz", pages)["note"] == "Nothing matches zzzz."
    rows = _call(views.pages_rows, docs, {}, "wiki", pages)
    assert rows[0]["title"] == {"page": f"p-{rows[0]['key']}", "label": rows[0]["title"]["label"]}
    assert rows[0]["edited"] == docs[rows[0]["key"]]["updated"] * 1000
    health = _call(views.health_view, text.health(docs, facts, NOW), True, docs, pages)
    assert all("/" not in str(r["page"]) for r in health["rows"])


def test_page_links_turn_into_hrefs_in_the_cell(base: tuple[dict, dict]) -> None:
    from nudemos import pages as links
    from nudemos.knowledge import views
    from nuspace.web import url

    docs, _ = base
    rows = _call(views.task_rows, docs, _pages(docs), NOW, "", 7, False)
    linked = _call(links.linked, rows, "page")
    first = rows[0]["page"]
    assert linked[0]["page"] == {"href": url(first["page"]), "title": first["label"]}
