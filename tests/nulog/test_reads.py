"""What the Log planes stand on: the store at a path, the reads, and what they are shaped into.

Run without a space. ``import nulog`` alone loads neither nuspace nor ``nustd.ui``.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

import nu
import nulog
import nustd.kv
from nulog.planes import fmt, reads
from nulog.planes.store import Opened


if TYPE_CHECKING:
    from pathlib import Path


def _write(path: Path, n: int = 5) -> str:
    """A nulog store at ``path``: ``app`` with ``n`` entries, ``db`` with one error, a ``cpu`` series."""
    log, db = nulog.getLogger("app"), nulog.getLogger("db")
    writes = [log.info("tick %s", i, extra={"i": i}) for i in range(n)]
    writes += [log.warning("slow: %s ms", 210), db.error("lost the connection")]
    writes += [nulog.observe("cpu", 0.1 * i) for i in range(1, 4)]
    nu.run(nu.With(nulog.store(str(path)), body=nustd.kv.Transaction(nu.Sequential(*writes))))
    return str(path)


def test_importing_nulog_pulls_in_no_space_and_no_ui():
    code = "import sys, nulog; print('nuspace' in sys.modules, 'nustd.ui' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)  # noqa: S603
    assert out.stdout.split() == ["False", "False"]


def test_a_path_is_looked_at_before_it_is_opened(tmp_path):
    assert fmt.look_of("")["state"] == "unset"
    assert fmt.look_of(str(tmp_path / "nope"))["state"] == "missing"
    assert fmt.look_of(str(tmp_path))["state"] == "other"
    assert fmt.look_of(_write(tmp_path / "logs.db"))["state"] == "ok"
    # Nothing made where nothing was: a RocksDB open would have made a store.
    assert not (tmp_path / "nope").exists()


def test_opened_reads_a_store_under_its_own_tags(tmp_path):
    path = _write(tmp_path / "logs.db")
    body = nu.List.of(reads.streams(), reads.series(), reads.entries("app", "tail", 2))
    streams, series, newest = nu.run(Opened(path, body))[0]
    assert streams == ["app", "db"]
    assert series == ["cpu"]
    assert [e["msg"] for e in newest] == ["slow: 210 ms", "tick 4"]
    with pytest.raises(ValueError, match="does not exist"):
        nu.run(Opened(str(tmp_path / "nope"), reads.streams()))


def test_the_messages_view_filters_one_read_only():
    read = [
        {"ts_us": 3, "level": "error", "msg": "Lost it", "fields": {"db": "main"}},
        {"ts_us": 2, "level": "info", "msg": "fine", "fields": {}},
        {"ts_us": 1, "level": "warning", "msg": "slow", "fields": {"ms": 210}},
    ]
    v = fmt.messages_of(read, "all", "LOST", 0.0)
    assert [r["message"] for r in v["rows"]] == ["Lost it"]
    assert v["rows"][0]["fields"] == "db=main"
    assert v["tiles"]["shown"]["delta"] == "of 3 read"
    assert v["tiles"]["errors"]["value"] == "1"
    assert fmt.messages_of(read, "debug", "", 0.0)["empty"].startswith("None of the 3")
    assert fmt.entry_of(read, "1")["fields"] == {"ms": 210}


def test_the_chart_reads_a_sample_in_time_order():
    v = fmt.chart_of([{"ts_us": 2_000_000, "value": 4.0}, {"ts_us": 1_000_000, "value": 1.0}], 3.0)
    assert v["points"] == [[1000, 1.0], [2000, 4.0]]
    assert v["tiles"]["latest"] == {"value": "4", "delta": "1s ago", "trend": "up"}
    assert fmt.chart_of([], 0.0)["empty"]


def test_a_read_takes_count_off_either_end(tmp_path):
    path = _write(tmp_path / "logs.db", n=3)
    body = nu.List.of(
        reads.entries("app", "take", 2),
        reads.entries("app", "tail", 0),
        reads.entries("nope", "tail", 5),
        reads.points("cpu", 0),
        reads.points("cpu", 60),
    )
    oldest, held, none, every, recent = nu.run(Opened(path, body))[0]
    assert [e["msg"] for e in oldest] == ["tick 0", "tick 1"]
    assert len(held) == 1  # held to at least one
    assert none == []
    assert sorted(p["value"] for p in every) == pytest.approx([0.1, 0.2, 0.3])
    assert len(recent) == 3


def test_a_picker_keeps_its_pick_while_it_is_there():
    assert fmt.pick_of(["b", "a"], "") == "a"
    assert fmt.pick_of(["b", "a"], "b") == "b"
    assert fmt.pick_of(["b", "a"], "gone") == "a"
    assert fmt.pick_of([], "gone") == ""
    assert fmt.options_of(["b", "a"]) == [
        {"value": "a", "label": "a"},
        {"value": "b", "label": "b"},
    ]
    assert fmt.bounded_of("12", 5, 1, 10) == 10
    assert fmt.bounded_of(None, 5, 1, 10) == 5
