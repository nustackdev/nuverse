"""nulog Client -- imperative Python bridge over the same store.

Same shape as `nu_basic.py`, but writes and reads happen as plain Python calls
on a held :class:`nulog.Client`. Under the hood each call still builds a Nu
tree, wraps it in `Transaction` / `Snapshot`, and drives it against a
persistent ctx bound to the storage. Nothing to compose, nothing to run
yourself.

Run::

    python examples/py_client.py
"""

# ruff: noqa: T201  -- an example; printing is the point

from __future__ import annotations

import nulog


with nulog.init("plain_py_logs.db") as log:
    log.info("server started", stream="app", extra={"port": 8080, "env": "dev"})
    log.debug("config loaded", stream="app", extra={"source": "env"})
    log.warning("cache miss", stream="app", extra={"key": "user:42"})
    log.error("request failed", stream="app", extra={"path": "/checkout", "code": 500})
    log.info("request ok", stream="app", extra={"path": "/", "ms": 12})
    log.info("scrape started", stream="scraper", extra={"target": "example.com"})
    log.error("blocked", stream="scraper", extra={"status": 429})

    log.observe("cpu_load", 0.31)
    log.observe("cpu_load", 0.42)
    log.observe("http_latency_ms", 34.0)

    print("== app: tail(3) ==")
    for row in log.tail("app", 3):
        print(row)

    print("== app: slice(0,3) ==")
    for row in log.slice("app", 0, 3):
        print(row)

    print("== scraper: tail(5) ==")
    for row in log.tail("scraper", 5):
        print(row)

    print("== cpu_load: sample(10) ==")
    for pt in log.sample("cpu_load", 10):
        print(pt)
