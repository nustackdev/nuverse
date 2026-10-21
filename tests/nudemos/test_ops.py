"""ops: the records the jobs keep, the rules' turns, the gateway's releases, and the real work the jobs do."""

from __future__ import annotations

import asyncio
import tarfile

import pytest

from nudemos.ops import model, shape
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
    assert [r["level"] for r in shape.log_rows(rows, "warning", "")] == ["error", "warning"]
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
    parts = {p["name"]: p for p in shape.components(gw, jobs, {})}
    assert parts["Search"]["label"] == "Partial outage"
    assert parts["Storefront"]["tone"] == "ok"
    assert parts["Help center"]["label"] == "Broken links"
    down = shape.components(gw, {"gateway": {"status": "crashed"}}, {})
    assert down[0]["label"] == "Major outage"


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
