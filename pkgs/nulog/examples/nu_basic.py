"""nulog basics: write lines across levels and streams, read them back.

The whole app is one Nu tree. Writes compose under a `Transaction`, reads
compose under `Snapshot` and get piped through `nu.print`. No held ctx, no
imperative Python.

Run::

    python examples/nu_basic.py
"""

from __future__ import annotations

import nu
import nulog
import nustd


app = nulog.getLogger("app")
scraper = nulog.getLogger("scraper")


writes = (
    app.info("server started", extra={"port": 8080, "env": "dev"})
    >> app.debug("config loaded", extra={"source": "env"})
    >> app.warning("cache miss", extra={"key": "user:42"})
    >> app.error("request failed", extra={"path": "/checkout", "code": 500})
    >> app.info("request ok", extra={"path": "/", "ms": 12})
    >> scraper.info("scrape started", extra={"target": "example.com"})
    >> scraper.error("blocked", extra={"status": 429})
)

reads = (
    nustd.kv.Snapshot(nu.print("== app: tail(3) ==", nulog.messages.tail("app", 3)))
    >> nustd.kv.Snapshot(nu.print("== app: slice(0,3) ==", nulog.messages.slice("app", 0, 3)))
    >> nustd.kv.Snapshot(nu.print("== scraper: tail(5) ==", nulog.messages.tail("scraper", 5)))
)

tree = nu.With(nulog.store("basic.db"), body=nustd.kv.Transaction(writes) >> reads)


if __name__ == "__main__":
    nu.run(tree)
