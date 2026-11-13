"""ops: the records the jobs keep, the rules' turns, the gateway's releases, and the real work the jobs do."""

from __future__ import annotations

import asyncio
import tarfile

import pytest

import nu
import nuspace
from nudemos.ops import cells, model, shape
from nudemos.ops.gateway import RELEASES, Gateway
from nudemos.ops.jobs import SOURCES
from nudemos.ops.work import Shoppers, Worker


def test_every_job_has_cells() -> None:
    assert set(SOURCES) == set(model.JOBS)
    rules = {name for name, _ in SOURCES["watchdog"]} - {"up"}
    assert rules == set(model.RULES)


def test_job_up_keeps_lives_and_why_the_last_ended() -> None:
    rec = model.job_up(None, "gateway", 100, 1000.0)
    rec = model.job_crashed(rec, "out of memory", 1050.0)
    rec = model.job_up(rec, "gateway", 101, 1051.0)
    assert rec["status"] == "running"
    assert rec["pid"] == 101
    assert rec["starts"] == [1000.0, 1051.0]
    assert rec["lives"][0] == {"at": 1000.0, "pid": 100, "end": 1051.0, "why": "out of memory"}
    assert "end" not in rec["lives"][1]
    assert rec["falls"] == [1051.0]


def test_a_restart_asked_for_is_no_fall() -> None:
    rec = model.job_up(None, "gateway", 100, 1000.0)
    rec = model.job_up({**rec, "status": "restarting"}, "gateway", 101, 1010.0)
    assert rec["falls"] == []
    assert rec["lives"][0]["why"] == "restarted"


def test_job_done_counts_streaks_and_schedules_the_next() -> None:
    rec = model.job_up(None, "linkcheck", 7, 0.0)
    rec, run = model.job_done(
        rec, "linkcheck", {"ok": False, "summary": "6 broken links", "ms": 120}, 1.0
    )
    rec, _ = model.job_done(
        rec, "linkcheck", {"ok": False, "summary": "6 broken links", "ms": 90}, 92.0
    )
    assert (rec["status"], rec["streak"], rec["runs_failed"]) == ("failed", 2, 2)
    assert rec["next"] == 92.0 + model.JOBS["linkcheck"]["every"]
    assert run["summary"] == "6 broken links" and not run["ok"]
    rec, _ = model.job_done(rec, "linkcheck", {"ok": True, "summary": "13 pages", "ms": 80}, 200.0)
    assert (rec["status"], rec["streak"], rec["runs_ok"]) == ("ok", 0, 1)


def test_incidents_open_once_per_key_and_raise() -> None:
    inc, iid, new = model.open_incident(
        {}, "gateway", "Storefront API failing", 2, "10% failing", "1.9.0", 0.0
    )
    assert (iid, new, inc["status"]) == ("INC-2041", True, "open")
    calm = model.settle(inc, "monitoring", "rule", 5.0)
    again, same, new = model.open_incident(
        {iid: calm}, "gateway", "Crash loop", 1, "restarted 2 times", "1.9.0", 9.0
    )
    assert (same, new, again["sev"], again["status"]) == (iid, False, 1, "open")
    assert again["title"] == "Storefront API failing"
    done = model.settle(again, "resolved", "you", 20.0)
    _, other, new = model.open_incident(
        {iid: done}, "gateway", "Storefront API failing", 2, "back", "1.9.0", 30.0
    )
    assert (other, new) == ("INC-2042", True)


def test_rules_fire_after_hold_and_clear_once() -> None:
    rec: dict = {"on": True}
    verdicts = []
    for reason in ["x", "x", "x", "x", "", ""]:
        rec, verdict = model.decide(rec, reason, 3, 0.0)
        verdicts.append(verdict)
    assert verdicts == ["", "", "fire", "", "clear", ""]
    assert rec["fired"] == 1
    off, verdict = model.decide({"on": False}, "x", 1, 0.0)
    assert verdict == "" and not off["firing"]


def test_log_rows_filter_by_level_and_text() -> None:
    rows = [
        {
            "ts_us": 3,
            "level": "error",
            "msg": "GET /api/search 500",
            "fields": {"error": "ranking: score vector shorter"},
        },
        {"ts_us": 2, "level": "info", "msg": "GET /api/cart 200", "fields": {}},
        {"ts_us": 1, "level": "warning", "msg": "attempt 1 of 3", "fields": {"attempt": 1}},
    ]
    kept = shape.log_rows(rows, "warning", "")
    assert [r["level"] for r in kept] == [
        {"label": "error", "variant": "danger"},
        {"label": "warning", "variant": "warn"},
    ]
    assert [r["message"] for r in shape.log_rows(rows, "debug", "ranking")] == [
        "GET /api/search 500"
    ]


def test_status_components_follow_the_routes() -> None:
    gw = {
        "rps": 20,
        "routes": [
            {"route": "/api/search", "err": 38.0, "p95": 300},
            {"route": "/api/catalog", "err": 0.0, "p95": 30},
        ],
    }
    jobs = {
        "gateway": {"status": "running"},
        "linkcheck": {"last": {"ok": False, "summary": "6 broken links"}},
    }
    parts = {p["key"]: p for p in shape.components(gw, jobs, {})}
    assert parts["search"]["status"] == {"label": "Partial outage", "tone": "danger"}
    assert parts["storefront"]["status"]["tone"] == "ok"
    assert parts["help"]["status"]["label"] == "Broken links"
    assert len(parts) == 5
    down = shape.components(gw, {"gateway": {"status": "crashed"}}, {})
    assert down[0]["status"]["label"] == "Major outage"


def test_job_rows_link_each_job_to_its_page_and_carry_times() -> None:
    jobs = {
        "backup": {
            "kind": "scheduled",
            "status": "ok",
            "last": {"ended": 1000.0, "summary": "3 archives"},
        },
        "gateway": {"kind": "service", "status": "crashed", "reason": "out of memory"},
    }
    rows = {r["key"]: r for r in shape.job_rows(jobs, {"backup": "p7"}, 1010.0)}
    assert set(rows) == set(model.JOBS)
    backup, gateway = rows["backup"], rows["gateway"]
    assert backup["job"] == {"page": "p7", "label": "backup"}
    assert (backup["last"], backup["said"]) == (1_000_000, "3 archives")
    assert backup["status"] == {"label": "ok", "tone": "ok"}
    # A job whose page is not made yet draws its name unlinked.
    assert gateway["job"] == {"page": "", "label": "gateway"}
    assert (gateway["last"], gateway["said"]) == (None, "out of memory")
    assert gateway["status"]["tone"] == "danger"


def test_incident_rows_open_first_with_their_pages() -> None:
    incidents = {
        "INC-1": {"id": "INC-1", "sev": 2, "status": "resolved", "opened": 10.0, "resolved": 70.0},
        "INC-2": {"id": "INC-2", "sev": 1, "status": "open", "opened": 50.0},
    }
    rows = shape.incident_rows(incidents, {"INC-2": "p9"}, 100.0)
    assert [r["key"] for r in rows] == ["INC-2", "INC-1"]
    assert rows[0]["incident"] == {"page": "p9", "label": "INC-2"}
    assert rows[0]["sev"] == {"label": "sev 1", "variant": "danger"}
    assert (rows[0]["opened"], rows[1]["lasted"]) == (50_000, "1m 00s")
    assert rows[1]["incident"]["page"] == ""


def test_rule_rows_and_feed_rows_carry_cells() -> None:
    (rule,) = shape.rule_rows({"err": {"title": "Errors", "on": True, "firing": True, "last": 5.0}})
    assert rule["state"] == {"label": "firing", "tone": "danger"}
    assert (rule["last"], rule["fired"], rule["on"]) == (5000, 0, True)
    (off,) = shape.rule_rows({"err": {"on": False}})
    assert off["state"]["label"] == "off"
    assert off["last"] is None
    (event,) = shape.feed_rows([{"at": 2.0, "kind": "deploy", "text": "1.9.0 live"}])
    assert event["when"] == 2000
    assert event["kind"] == {"label": "deploy", "variant": "brand"}


def test_a_timeline_keeps_exact_clock_times() -> None:
    inc = {
        "timeline": [
            {"at": 1.0, "text": "opened", "who": "rule"},
            {"at": 2.0, "text": "on it", "who": "you"},
        ]
    }
    rows = shape.timeline(inc)
    assert [(r["what"], r["who"]) for r in rows] == [("opened", ""), ("on it", "you")]
    assert rows[0]["time"] == shape.clock(1.0)


# --- the cells load ------------------------------------------------------------------------------

# Every page cell, loaded as the kernel loads it and compiled. Never run: on a
# real page the welcome cell seeds the space (the gateway and supervised jobs),
# and every other cell follows them.
CELLS = {
    f"{page}.{name}": source
    for page, group in (
        ("root", cells.ROOT),
        *((key, group) for key, _, _, group in cells.FOLDERS),
        ("job", cells.JOB),
        ("incident", cells.INCIDENT_CELLS),
    )
    for name, source in group
}


@pytest.mark.parametrize("source", list(CELLS.values()), ids=list(CELLS))
async def test_every_ops_cell_loads(store, source) -> None:
    from nuspace import Space

    await store.do(nuspace.plane.add("p", backend="async"))
    await store.do(nuspace.cell.add("p", source, id="c"))
    assert await store.read(Space.cells["c"].fabrics) == ["ui"]
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"})
    nu.validate(nu.compile(await store.run(nuspace.atomic(load))))


@pytest.mark.parametrize("release", ["1.8.3", "1.9.0"])
def test_gateway_serves_its_release_and_jobs_do_real_work(
    release: str, tmp_path, unused_port: int, monkeypatch
) -> None:
    # The gateway reads its own process's memory, here the whole test run's; keep it
    # out of the out-of-memory check, as it is on a machine with no /proc.
    monkeypatch.setattr("nudemos.ops.gateway._rss_mb", lambda: 0.0)

    async def run() -> tuple[dict, dict, dict]:
        gw = Gateway()
        await gw.open(unused_port, release, str(tmp_path))
        shoppers = Shoppers()
        for _ in range(3):
            await shoppers.shop(unused_port, 12)
        worker = Worker()
        backup = await worker.run("backup", {"data": str(tmp_path)})
        links = await worker.run("linkcheck", {"port": unused_port})
        drained = gw.drain()
        await shoppers.acleanup()
        await gw.acleanup()
        return backup, links, drained

    backup, links, drained = asyncio.run(run())
    assert backup["ok"]
    archive = tmp_path / "backups" / backup["result"]["archives"][0]["name"]
    with tarfile.open(archive) as tar:
        assert tar.getnames() == ["orders.jsonl"]
    assert links["ok"] is (release == "1.8.3")
    assert drained["gw"]["release"] == release
    assert drained["gw"]["requests"] > 0
    if RELEASES[release]["search_fail"]:
        assert "returns" in links["summary"]


@pytest.fixture
def unused_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_a_monitored_incident_is_not_open_on_the_tiles() -> None:
    incidents = {"INC-1": {"status": "monitoring", "sev": 3}}
    tile = shape.pulse({}, {}, {}, incidents, {})["incidents"]
    assert tile == {"value": "0", "delta": "1 monitoring", "trend": "flat"}


# --- the first open, on a store ------------------------------------------------------------------


async def test_the_first_open_makes_the_pages_and_the_jobs_once(store, tmp_path):
    from nudemos import headless, ops
    from nudemos.ops import jobs, kit, state
    from nuspace import Space
    from nuspace.system import supervisor
    from nuspace.web import Web

    await store.run(nuspace.specs.add_plane(ops.PLANE, "o"))
    await store.do(Space.info.path.set(str(tmp_path)))
    assert await store.read(state.ROOT_ID) == "o"
    await store.run(kit.seed(nu.Str("o")))
    await store.run(kit.seed(nu.Str("o")))
    kids = await store.read(Space.planes["o"].children.keys(limit=50))
    # Every plane at an id minted at the first open, kept in the root's state.
    made = await store.read(state.OPS.made.extract())
    folders = made["folders"]
    assert {folders[k] for k in ("jobs", "deploys", "incidents", "status")} <= set(kids)
    assert await store.read(Space.planes[folders["jobs"]].meta.extract()) == {"view": "jobs"}
    assert await store.read(Web.planes[folders["jobs"]].width) == "board"
    gateway = made["views"]["gateway"]
    assert await store.read(Space.planes[gateway].parent) == folders["jobs"]
    assert await store.read(Space.planes[gateway].meta["job"]) == "gateway"
    # Every job a headless plane under the root, on its schedule, its cells by name.
    for name, spec in model.JOBS.items():
        jid = made["workers"][name]
        assert jid in kids
        assert await store.read(Space.planes[jid].spec) == state.WORKER
        assert not await store.read(Web.planes.contains(jid))
        for cell, _ in jobs.SOURCES[name]:
            assert await store.read(headless.cell_of(jid, cell)) in await store.read(
                nu.list(Space.planes[jid].cells.keys())
            )
        policy = await store.read(supervisor.supervised()[jid].policy)
        assert policy == (supervisor.ALWAYS if spec["every"] else supervisor.ON_FAILURE)
    assert await store.read(state.OPS.settings["data"]) == str(tmp_path / "ops-data")
    assert await store.read(state.OPS.release["version"]) == model.HISTORY[-1][0]


async def test_pausing_a_job_takes_it_off_its_schedule_and_resuming_puts_it_back(store, tmp_path):
    from nudemos import ops
    from nudemos.ops import kit, state
    from nuspace.system import supervisor

    await store.run(nuspace.specs.add_plane(ops.PLANE, "o"))
    await store.run(kit.seed(nu.Str("o")))
    await store.run(kit.pause("o", "offsite"))
    offsite = await store.read(state.worker_of("offsite"))
    gateway = await store.read(state.worker_of("gateway"))
    assert await store.read(supervisor.supervised().contains(offsite)) is False
    assert await store.read(state.OPS.jobs["offsite"]["paused"]) is True
    await store.run(kit.resume("o", "offsite"))
    assert await store.read(supervisor.supervised()[offsite].policy) == supervisor.ALWAYS
    await store.run(kit.restart("o", "gateway"))
    assert await store.read(supervisor.supervised()[gateway].policy) == supervisor.ON_FAILURE
