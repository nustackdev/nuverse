"""nulog live: a store this program keeps writing, to watch from a space.

Run it, then open a space (``nuspace``), add **Log** from ``+`` and point
its Config at ``fast_updates.db``. The planes read the store read only,
as a RocksDB secondary, so they are safe on it while this keeps writing.
"""

from __future__ import annotations

import asyncio

import nu
import nulog
import nustd
import nustd.math
import nustd.random
import nustd.time


app = nulog.getLogger("app")
scraper = nulog.getLogger("scraper")
worker = nulog.getLogger("worker")


def _seed() -> nu.Nu:
    """A one-shot burst so the viewer has content on first repaint."""
    return nustd.kv.Transaction(
        app.info("server started", extra={"port": 8080, "env": "dev"})
        >> app.debug("config loaded", extra={"source": "env"})
        >> app.warning("cache miss", extra={"key": "user:42"})
        >> app.error("request failed", extra={"path": "/checkout", "code": 500})
        >> scraper.info("scrape started", extra={"target": "example.com"})
        >> scraper.error("blocked", extra={"status": 429})
        >> worker.info("job dequeued", extra={"id": "j-7f2"})
        >> worker.debug("stage begin", extra={"stage": "fetch"})
        >> nulog.observe("cpu_load", 0.31)
        >> nulog.observe("cpu_load", 0.37)
        >> nulog.observe("cpu_load", 0.42)
        >> nulog.observe("http_latency_ms", 12.0)
        >> nulog.observe("http_latency_ms", 18.0)
        >> nulog.observe("mem_mb", 512.0)
        >> nulog.observe("mem_mb", 528.0),
    )


def _wave(base: float, swing: float, period: float, noise: float) -> nu.Nu:
    """A value drifting on a slow wave, with some noise on it: something to chart."""
    phase = nustd.time.time() / period
    return base + nustd.math.sin(phase) * swing + nustd.random.uniform(-noise, noise)


def _tick() -> nu.Nu:
    """Five-step cycle: each step emits one message and one metric point."""
    return nu.ForeverDo(
        nustd.kv.Transaction(
            app.info("request ok", extra={"path": "/", "ms": 12})
            >> nulog.observe("cpu_load", _wave(0.5, 0.3, 20.0, 0.05)),
        )
        >> nu.Delay(0.4)
        >> nustd.kv.Transaction(
            scraper.info("page fetched", extra={"url": "/robots.txt"})
            >> nulog.observe("http_latency_ms", _wave(30.0, 12.0, 45.0, 6.0)),
        )
        >> nu.Delay(0.4)
        >> nustd.kv.Transaction(
            app.warning("slow request", extra={"ms": 210})
            >> nulog.observe("cpu_load", _wave(0.5, 0.3, 20.0, 0.05)),
        )
        >> nu.Delay(0.4)
        >> nustd.kv.Transaction(
            worker.error("stage failed", extra={"stage": "parse", "code": 3})
            >> nulog.observe("mem_mb", _wave(560.0, 40.0, 90.0, 4.0)),
        )
        >> nu.Delay(0.4)
        >> nustd.kv.Transaction(
            scraper.info("429 backoff", extra={"retry_in_s": 5})
            >> nulog.observe("http_latency_ms", _wave(30.0, 12.0, 45.0, 6.0)),
        )
        >> nu.Delay(0.4),
    )


tree = nu.With(
    nulog.store("fast_updates.db"),
    body=_seed() >> _tick(),
)


if __name__ == "__main__":
    asyncio.run(nu.arun(tree))
