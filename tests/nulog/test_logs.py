"""Log writes + reads: Logger API, ordering, tail/slice, Client, store_ro.

The write API mirrors ``nustd.logging`` / Python ``logging``; the read API
is two primitives on ``nulog.messages``: :func:`tail` and :func:`slice`. Level / substring filtering is a caller concern -- do it in
Python after ``tail``, not on the substrate.
"""

from __future__ import annotations

import logging as pylogging

import nu
import nulog
import nustd


def _write(ctx, cmd):
    """Run one write Command inside a Transaction on ``ctx``."""
    nu.run(nustd.kv.Transaction(cmd), ctx)


def _read(ctx, atom):
    """Run a read atom under a Snapshot on ``ctx``; return the yielded value."""
    return nu.run(nustd.kv.Snapshot(atom), ctx)[0]


# ---- write shape ----------------------------------------------------------


def test_getLogger_returns_a_bound_Logger():  # noqa: N802
    log = nulog.getLogger("app")
    assert isinstance(log, nulog.Logger)
    assert log.name == "app"


def test_getLogger_with_no_arg_uses_root():  # noqa: N802
    assert nulog.getLogger().name == "root"
    assert nulog.getLogger(None).name == "root"


def test_level_constants_match_stdlib():
    assert nulog.DEBUG == pylogging.DEBUG
    assert nulog.INFO == pylogging.INFO
    assert nulog.WARNING == pylogging.WARNING
    assert nulog.WARN == pylogging.WARNING
    assert nulog.ERROR == pylogging.ERROR
    assert nulog.CRITICAL == pylogging.CRITICAL
    assert nulog.FATAL == pylogging.CRITICAL


def test_write_returns_nu_without_executing(ctx):
    """Building an entry doesn't touch the store."""
    cmd = nulog.getLogger("app").info("deferred")
    assert isinstance(cmd, nu.Nu)
    assert _read(ctx, nulog.messages.tail("app", 5)) == []


def test_append_and_tail(ctx):
    log = nulog.getLogger("app")
    _write(ctx, log.info("started", extra={"port": 8080, "host": "localhost"}))
    rows = _read(ctx, nulog.messages.tail("app", 10))
    assert len(rows) == 1
    r = rows[0]
    assert r["level"] == "info"
    assert r["msg"] == "started"
    assert r["fields"] == {"port": 8080, "host": "localhost"}
    assert isinstance(r["ts_us"], int) and r["ts_us"] > 0


def test_no_extra_decodes_to_empty_dict(ctx):
    _write(ctx, nulog.getLogger("app").info("bare"))
    assert _read(ctx, nulog.messages.tail("app", 1))[0]["fields"] == {}


def test_level_shortcuts(ctx):
    log = nulog.getLogger("app")
    _write(ctx, log.debug("d"))
    _write(ctx, log.info("i"))
    _write(ctx, log.warning("w"))
    _write(ctx, log.error("e"))
    _write(ctx, log.critical("c"))
    rows = _read(ctx, nulog.messages.tail("app", 10))
    assert [r["level"] for r in rows] == ["critical", "error", "warning", "info", "debug"]


def test_warn_is_stdlib_alias_for_warning(ctx):
    _write(ctx, nulog.getLogger("app").warn("via warn"))
    assert _read(ctx, nulog.messages.tail("app", 1))[0]["level"] == "warning"


def test_generic_log_method(ctx):
    _write(
        ctx,
        nulog.getLogger("app").log(pylogging.WARNING, "via log", extra={"k": 1}),
    )
    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    assert r["level"] == "warning"
    assert r["fields"] == {"k": 1}


def test_percent_formatting_of_args(ctx):
    log = nulog.getLogger("app")
    _write(ctx, log.error("slot %s failed after %s attempts", 42, 5))
    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    assert r["msg"] == "slot 42 failed after 5 attempts"
    assert r["level"] == "error"


def test_module_level_shortcuts_target_root_stream(ctx):
    _write(ctx, nulog.info("root-level"))
    r = _read(ctx, nulog.messages.tail("root", 1))[0]
    assert r["msg"] == "root-level"
    assert r["level"] == "info"


def test_compose_log_with_other_writes_is_atomic(ctx):
    """A log Command composes with any other Command inside one Transaction."""

    class Account(nu.Shape):
        balance = nustd.kv.IntRef.slot()

    nu.run(
        nustd.kv.Transaction(
            Account.balance.set(100),
            nulog.getLogger("app").info("debit", extra={"amount": 5}),
        ),
        ctx,
    )
    bal = nu.run(nustd.kv.Snapshot(nu.Int(Account.balance)), ctx)[0]
    assert bal == 100
    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    assert r["msg"] == "debit"
    assert r["fields"] == {"amount": 5}


def test_loop_appends_each_iteration(ctx):
    """A write inside a loop appends one entry per eval (not per build)."""
    log = nulog.getLogger("app")
    nu.run(
        nu.ForEachDo(
            nu.Iter(nu.Literal([1, 2, 3, 4, 5])),
            nustd.kv.Transaction(log.info("tick")),
            item="_nl_i",
        ),
        ctx,
    )
    rows = _read(ctx, nulog.messages.tail("app", 10))
    assert len(rows) == 5


# ---- streams -------------------------------------------------------------


def test_streams_are_isolated(ctx):
    app = nulog.getLogger("app")
    scraper = nulog.getLogger("scraper")
    _write(ctx, app.info("app line"))
    _write(ctx, scraper.info("scraper line"))
    assert [r["msg"] for r in _read(ctx, nulog.messages.tail("app", 10))] == ["app line"]
    assert [r["msg"] for r in _read(ctx, nulog.messages.tail("scraper", 10))] == ["scraper line"]


def test_unwritten_stream_is_clean(ctx):
    _write(ctx, nulog.getLogger("app").info("x"))
    assert _read(ctx, nulog.messages.tail("ghost", 5)) == []


# ---- order ---------------------------------------------------------------


def test_tail_is_newest_first(ctx):
    log = nulog.getLogger("app")
    for msg in ("first", "second", "third"):
        _write(ctx, log.info(msg))
    assert [r["msg"] for r in _read(ctx, nulog.messages.tail("app", 10))] == [
        "third",
        "second",
        "first",
    ]


def test_tail_limits_to_n(ctx):
    log = nulog.getLogger("app")
    for i in range(5):
        _write(ctx, log.info("m%s", i))
    rows = _read(ctx, nulog.messages.tail("app", 2))
    assert [r["msg"] for r in rows] == ["m4", "m3"]


def test_tail_n_greater_than_len_returns_all(ctx):
    """`tail(n)` where n > len yields every entry (start clamped to 0)."""
    log = nulog.getLogger("app")
    for msg in ("a", "b", "c"):
        _write(ctx, log.info(msg))
    rows = _read(ctx, nulog.messages.tail("app", 100))
    assert [r["msg"] for r in rows] == ["c", "b", "a"]


# ---- slice ---------------------------------------------------------------


def test_slice_positional_window(ctx):
    """`slice(start, stop)` reads a positional window in chronological order."""
    log = nulog.getLogger("app")
    for i in range(6):
        _write(ctx, log.info("m%s", i))
    rows = _read(ctx, nulog.messages.slice("app", 1, 4))
    assert [r["msg"] for r in rows] == ["m1", "m2", "m3"]


def test_slice_step(ctx):
    """`slice(..., step=2)` picks every other entry in the window."""
    log = nulog.getLogger("app")
    for i in range(6):
        _write(ctx, log.info("m%s", i))
    rows = _read(ctx, nulog.messages.slice("app", 0, 6, 2))
    assert [r["msg"] for r in rows] == ["m0", "m2", "m4"]


# ---- one-tree end-to-end -------------------------------------------------


def test_bracket_form_all_in_one_tree(tmp_path):
    """Full Nu-app shape: bracket + writes + reads composed under one nu.With."""
    log = nulog.getLogger("app")
    tree = nu.With(
        nulog.store(str(tmp_path / "logs.db")),
        body=nustd.kv.Transaction(
            log.info("bracketed", extra={"n": 1}) >> log.error("boom"),
        )
        >> nustd.kv.Snapshot(nu.print(nulog.messages.tail("app", 10))),
    )
    nu.run(tree)


# ---- imperative client + read-only store ---------------------------------


def test_client_round_trip(tmp_path):
    with nulog.init(str(tmp_path / "logs.db")) as log:
        log.info("started", stream="app", extra={"port": 8080})
        log.error("failed %s", 42, stream="app")
        log.observe("cpu", 0.5, ts=1000.0)
        assert [r["msg"] for r in log.tail("app", 5)] == ["failed 42", "started"]
        assert [r["msg"] for r in log.slice("app", 0, 1)] == ["started"]
        assert [r["value"] for r in log.range("cpu", 0, 10**17)] == [0.5]
        assert [r["value"] for r in log.sample("cpu", 5)] == [0.5]


def test_client_rocksdb_survives_reopen(tmp_path):
    path = str(tmp_path / "logs.db")
    with nulog.init(path) as log:
        log.warning("persisted", stream="app")
    with nulog.init(path) as log:
        assert [r["msg"] for r in log.tail("app", 5)] == ["persisted"]


def test_store_ro_reads_a_rocksdb_nulog(tmp_path):
    path = str(tmp_path / "logs.db")
    with nulog.init(path) as log:
        log.info("from the primary", stream="app")
    tree = nu.With(
        nulog.store_ro(path, secondary_path=str(tmp_path / "sec")),
        body=nustd.kv.Snapshot(nulog.messages.tail("app", 5)),
    )
    assert [r["msg"] for r in nu.run(tree)[0]] == ["from the primary"]
