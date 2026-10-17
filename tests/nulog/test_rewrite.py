"""``nulog.from_std_logging(tree)`` rewrites ``nustd.logging.Log`` into persistent writes.

App code writes ``log.info(...)`` / ``log.warning(...)`` via ``nustd.logging``;
wrapping the tree in :func:`nulog.from_std_logging` swaps every ``Log``
for the equivalent ``nulog`` persistent-write subtree. After that rewrite the
tree compiles and runs like any other Nu tree -- log records land in the
per-stream ``entries`` list under a ``nulog.store(...)`` bracket, no Python
``logging`` involved.
"""

from __future__ import annotations

import logging as pylogging

import nu
import nulog
import nustd
from nustd import logging as nu_logging


def _write(ctx, cmd):
    nu.run(nustd.kv.Transaction(cmd), ctx)


def _read(ctx, atom):
    return nu.run(nustd.kv.Snapshot(atom), ctx)[0]


# ---- structural: Log nodes get swapped ------------------------------


def test_rewrite_returns_a_tree_without_logcommand_nodes():
    log = nu_logging.getLogger("app")
    body = log.info("hi") >> log.warning("cache miss for %s", "key")

    rewritten = nulog.from_std_logging(body)

    # No Log survives; the rewrite is total.
    def _has_logcommand(node):
        if isinstance(node, nu_logging.Log):
            return True
        return any(_has_logcommand(c) for c in getattr(node, "_children", ()))

    assert not _has_logcommand(rewritten)


def test_rewrite_leaves_non_log_nodes_intact():
    log = nu_logging.getLogger("app")
    tree = nustd.kv.Transaction(log.info("x") >> nu.print("side-channel"))

    rewritten = nulog.from_std_logging(tree)

    # The Transaction wrapper and the print are untouched.
    assert type(rewritten).__name__ == "Transaction"


def test_rewrite_is_a_pure_construction_time_pass():
    """The rewrite doesn't touch a store or run anything -- just returns a new tree."""
    log = nu_logging.getLogger("app")
    body = log.info("deferred")
    rewritten = nulog.from_std_logging(body)
    # Both are Nu trees; nothing has fired.
    assert isinstance(body, nu.Nu)
    assert isinstance(rewritten, nu.Nu)
    assert body is not rewritten


# ---- functional: writes land in the store ----------------------------------


def test_rewritten_info_lands_in_the_named_stream(ctx):
    log = nu_logging.getLogger("app")
    _write(ctx, nulog.from_std_logging(log.info("hello")))

    rows = _read(ctx, nulog.messages.tail("app", 5))
    assert len(rows) == 1
    assert rows[0]["msg"] == "hello"
    assert rows[0]["level"] == "info"


def test_rewritten_percent_args_format_at_eval_time(ctx):
    log = nu_logging.getLogger("app")
    _write(ctx, nulog.from_std_logging(log.error("slot %s failed after %s attempts", 42, 5)))

    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    assert r["msg"] == "slot 42 failed after 5 attempts"
    assert r["level"] == "error"


def test_rewritten_extra_survives_as_fields(ctx):
    log = nu_logging.getLogger("app")
    _write(
        ctx,
        nulog.from_std_logging(log.warning("checkout failed", extra={"code": 500, "user": "u42"})),
    )

    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    assert r["level"] == "warning"
    assert r["fields"] == {"code": 500, "user": "u42"}


def test_rewritten_every_python_level_maps_to_canonical_name(ctx):
    log = nu_logging.getLogger("app")
    _write(ctx, nulog.from_std_logging(log.debug("d")))
    _write(ctx, nulog.from_std_logging(log.info("i")))
    _write(ctx, nulog.from_std_logging(log.warning("w")))
    _write(ctx, nulog.from_std_logging(log.error("e")))
    _write(ctx, nulog.from_std_logging(log.critical("c")))

    rows = _read(ctx, nulog.messages.tail("app", 10))
    assert [r["level"] for r in rows] == ["critical", "error", "warning", "info", "debug"]


def test_rewritten_int_level_via_generic_log_also_normalizes(ctx):
    log = nu_logging.getLogger("app")
    _write(ctx, nulog.from_std_logging(log.log(pylogging.WARNING, "via log")))

    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    assert r["level"] == "warning"


def test_rewritten_composed_seq_writes_in_order(ctx):
    log = nu_logging.getLogger("app")
    body = log.info("first") >> log.info("second") >> log.info("third")

    _write(ctx, nulog.from_std_logging(body))

    # tail is newest-first
    assert [r["msg"] for r in _read(ctx, nulog.messages.tail("app", 5))] == [
        "third",
        "second",
        "first",
    ]


def test_rewritten_stays_atomic_inside_a_transaction(ctx):
    """The rewritten Command still composes inside a Transaction."""

    class Account(nu.Shape):
        balance = nustd.kv.IntRef.slot()

    log = nu_logging.getLogger("app")
    body = Account.balance.set(100) >> log.info("debit", extra={"amount": 5})

    nu.run(nustd.kv.Transaction(nulog.from_std_logging(body)), ctx)

    bal = nu.run(nustd.kv.Snapshot(nu.Int(Account.balance)), ctx)[0]
    assert bal == 100
    r = _read(ctx, nulog.messages.tail("app", 1))[0]
    assert r["msg"] == "debit"
    assert r["fields"] == {"amount": 5}


# ---- two loggers, two streams ---------------------------------------------


def test_rewritten_multiple_loggers_route_to_separate_streams(ctx):
    app = nu_logging.getLogger("app")
    scraper = nu_logging.getLogger("scraper")

    body = app.info("app line") >> scraper.info("scraper line")
    _write(ctx, nulog.from_std_logging(body))

    assert [r["msg"] for r in _read(ctx, nulog.messages.tail("app", 5))] == ["app line"]
    assert [r["msg"] for r in _read(ctx, nulog.messages.tail("scraper", 5))] == ["scraper line"]
