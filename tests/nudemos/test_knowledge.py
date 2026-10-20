"""The knowledge demo's plain-Python half: pages read, rendered, queried, checked and imported."""

from __future__ import annotations

import time

import pytest

from nudemos.knowledge import ask, cells, data, jobs, seed, text


NOW = time.mktime((2026, 10, 20, 12, 0, 0, 0, 0, -1))


@pytest.fixture(scope="module")
def base() -> tuple[dict, dict]:
    return seed.base(data.DOCS, data.FACTS, NOW)


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
    md = text.render("pricing", docs, facts, "b", NOW)
    assert f"[{facts['price']['value']}](/b.facts)" in md
    assert "{{" not in md
    assert "](/b.doc.arlo)" in md
    assert (
        "~~" not in text.inline("[[pricing]] and [[nowhere]]", docs, facts, "b").split(" and ")[0]
    )
    assert "~~nowhere~~" in text.inline("[[nowhere]]", docs, facts, "b")


def test_a_fact_changed_once_shows_everywhere(base: tuple[dict, dict]) -> None:
    docs, facts = base
    facts = {**facts, "price": {**facts["price"], "value": "$79"}}
    citing = [k for k, d in docs.items() if "price" in text.facts_of(d["body"])]
    assert len(citing) >= 2
    assert all("[$79](/b.facts)" in text.render(k, docs, facts, "b", NOW) for k in citing)


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
    decisions = text.query("open-decisions", "", docs, facts, "b", NOW)
    assert decisions.startswith("| Open decision |")
    assert decisions.count("\n") - 1 == sum(
        1 for d in docs.values() if d["kind"] == "decision" and d["status"] == "open"
    )
    assert "Unknown query" in text.query("nope", "", docs, facts, "b", NOW)
    assert "](/b.doc." in text.query("owned-by", "theo", docs, facts, "b", NOW)


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
    md = text.digest(docs, facts, [], "b", NOW)
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
