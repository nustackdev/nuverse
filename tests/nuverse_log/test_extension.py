"""nuverse-log: found through the entry point, with its one plane."""

from __future__ import annotations

from nuspace.host import discover


def test_discovery_finds_the_log_plane():
    (ext,) = [e for e in discover() if e.name == "nuverse-log"]
    assert [p.name for p in ext.planes] == ["log"]
