"""Smoke test for the nulog package."""

import importlib.metadata

import nulog


def test_version():
    assert nulog.__version__ == importlib.metadata.version("nulog")


def test_public_surface():
    for name in nulog.__all__:
        assert hasattr(nulog, name), name


def test_submodules_are_reachable():
    """Reads live on ``nulog.messages`` / ``nulog.metrics`` -- no top-level shadow."""
    for name in ("tail", "slice", "getLogger", "Logger", "from_std_logging"):
        assert hasattr(nulog.messages, name), name
    for name in ("range", "sample", "observe"):
        assert hasattr(nulog.metrics, name), name


def test_dropped_read_surface():
    """The old full-scan read atoms stayed dropped."""
    for name in (
        "head",
        "by_level",
        "errors",
        "search",
        "since",
        "between",
        "count_by_level",
        "range_metric",
        "sample_metric",
        "open_logs",
        "read_records",
        "LogRecord",
    ):
        assert not hasattr(nulog, name), name


def test_top_level_write_shortcuts_present():
    """The Python-``logging``-shape wrapper is at the top-level for ergonomics."""
    for name in (
        "Logger",
        "getLogger",
        "debug",
        "info",
        "warning",
        "warn",
        "error",
        "critical",
        "log",
        "DEBUG",
        "INFO",
        "WARNING",
        "WARN",
        "ERROR",
        "CRITICAL",
        "FATAL",
        "from_std_logging",
        "observe",
    ):
        assert hasattr(nulog, name), name
