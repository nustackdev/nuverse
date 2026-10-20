"""The data demo's plain parts: the seeded history, the views over it, the stream's tick, the importer's parse."""

from __future__ import annotations

import time

import numpy as np
import pytest

from nudemos.data import calc, gen, jobs, kit


NOW = 1_792_500_000.0  # a fixed moment, so the history is the same every run


@pytest.fixture(scope="module")
def history() -> dict[str, np.ndarray]:
    return gen.history(NOW)


@pytest.fixture(scope="module")
def tables(history: dict[str, np.ndarray]) -> calc.Tables:
    return calc.Tables(history["lines"], history["people"], history["events"])


def test_history_is_seeded_and_sized(history: dict[str, np.ndarray]) -> None:
    again = gen.history(NOW)
    assert np.array_equal(history["lines"], again["lines"])
    assert len(history["events"]) > 1_000_000
    assert history["lines"]["ts"].max() <= NOW
    # Every line's customer is someone in people.
    assert np.isin(history["lines"]["customer"], history["people"]["id"]).all()


def test_shards_round_trip(history: dict[str, np.ndarray]) -> None:
    rows = history["lines"][:500]
    assert np.array_equal(kit.unpack("lines", kit.pack(rows)), rows)


def test_filters_narrow_revenue(tables: calc.Tables) -> None:
    every = calc.revenue(tables, {"range": "Last 30 days"}, NOW)
    web = calc.revenue(tables, {"range": "Last 30 days", "channel": "Web store"}, NOW)
    total = lambda v: float(v["tiles"]["revenue"][0].strip("$").replace(",", "").replace("M", ""))  # noqa: E731
    assert 0 < total(web) < total(every)
    assert set(web["series"]) == {"Web store"}


def test_funnel_narrows(tables: calc.Tables) -> None:
    stages = [n for _, n in calc.funnel(tables, {"range": "Last 30 days"}, NOW)["stages"]]
    assert stages == sorted(stages, reverse=True)
    assert 0.01 < stages[-1] / stages[0] < 0.08


def test_forecast_moves_with_the_plan(tables: calc.Tables) -> None:
    base = calc.forecast(tables, kit.PLAN, {}, NOW)
    dearer = calc.forecast(tables, {**kit.PLAN, "price": 10}, {}, NOW)
    churny = calc.forecast(tables, {**kit.PLAN, "churn": 12}, {}, NOW)
    total = lambda v: sum(r["plan"] for r in v["rows"])  # noqa: E731
    assert len(base["rows"]) == 12
    assert total(dearer) != total(base)
    assert total(churny) < total(base)


def test_metric_from_a_few_lines(tables: calc.Tables) -> None:
    def value(t: calc.Tables, keep: np.ndarray) -> float:
        return t.money[keep].sum() / max(len(np.unique(t.lines["order"][keep])), 1)

    m = calc.metric(tables, value, {"range": "Last 30 days"}, "money", NOW)
    assert m["value"].startswith("$")
    assert len(m["spark"]) == 26


def test_stream_tick_appends_to_a_live_shard(history: dict[str, np.ndarray]) -> None:
    stream = {
        "shard": kit.LIVE,
        "order": int(history["lines"]["order"].max()) + 1,
        "person": int(history["people"]["id"].max()) + 1,
        "session": int(history["events"]["session"].max()) + 1,
        "live": {},
        "at": NOW - 2,
    }
    catalog = {"LK-HB": {"price": 99.0, "stock": 10}}
    w = jobs.step({}, stream, catalog, [], "Launch day", NOW)
    assert w["moved"]
    entries = dict(w["index"])
    assert all(e["origin"] == "live" for e in entries.values())
    lines = kit.unpack("lines", dict(w["shards"])[w["stream"]["live"]["lines"]])
    # Sold at the price the sheet holds now.
    assert (lines["price"][lines["sku"] == 0] == 99.0).all()
    again = jobs.step(dict(w["index"]), w["stream"], catalog, w["feed"], "Launch day", NOW + 2)
    assert again["stream"]["live"]["lines"] == w["stream"]["live"]["lines"]
    assert dict(again["index"])[str(w["stream"]["live"]["lines"])]["v"] == 2


@pytest.mark.parametrize("kind", sorted(gen.EXPORTS))
def test_importer_parses_every_export(kind: str) -> None:
    name, text = gen.sample_csv(kind, time.time(), 42)
    cafes = {c: i + 1 for i, c in enumerate(gen.CAFES)}
    out = jobs.load_csv(name, text, {}, cafes, time.time())
    assert out["log"]["kind"] != "unknown"
    assert out["log"]["loaded"] > 0
    if kind == "popup":
        assert out["log"]["rejected"] == 2


def test_importer_turns_down_a_stranger() -> None:
    out = jobs.load_csv("x.csv", "name,amount\nAda,3\n", {}, {}, time.time())
    assert out["log"]["loaded"] == 0
    assert out["log"]["errors"]


def test_a_price_in_the_sheet_moves_the_forecast(tables: calc.Tables) -> None:
    assert abs(calc.price_index(tables, {}, NOW) - 1) < 1e-6
    dearer = {"LK-HB": {"price": 24.0}}
    assert calc.price_index(tables, dearer, NOW) > 1.01
    a = calc.forecast(tables, kit.PLAN, {}, NOW)["rows"]
    b = calc.forecast(tables, kit.PLAN, dearer, NOW)["rows"]
    assert a != b


def test_the_feed_opens_full() -> None:
    h = gen.history(NOW)
    t = calc.Tables(h["lines"], h["people"], h["events"])
    rows = calc.feed(h["lines"][-400:], t.name, 12)
    assert len(rows) == 12
    assert rows[0]["order"] == f"#{int(h['lines']['order'].max())}"
    assert all(r["customer"] and r["items"] for r in rows)
