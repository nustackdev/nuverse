"""The gateway: Halcyon's storefront API, a real HTTP server in its job's process.

Nu owns the loop, the server owns the requests. The gateway job provides a
:class:`Gateway`, opens it on the port and release it reads from the space
(:class:`~.calls.Open`), and loops in Nu: once a second
:class:`~.calls.Drain` hands over what happened since the last flush (access log lines, app log lines, the live numbers, a metric
point), and the job writes it into the space in one short commit.

What it serves depends on the release it started with (:data:`RELEASES`):
the catalog, search, orders (each one appended to the orders store on disk,
which the backup job archives), a cart, a health check, and the help center
the link checker crawls. Release 1.9.0 shipped a new search ranking with a
bug: about a third of searches fail, they are slower, every search keeps
half a megabyte it never lets go, and the gateway dies once it holds too
much. The supervisor brings it back, and it dies again, until somebody rolls
back or ships 1.9.1.

Plain asyncio, no framework: HTTP/1.1 with keep-alive, JSON in and out.
"""

from __future__ import annotations

import asyncio
import contextlib
import errno
import json
import os
import random
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any


#: Where the traffic's and the latency's randomness comes from: no seed, every run differs.
_rng = random.Random()  # noqa: S311

__all__ = [
    "DOCS",
    "PRODUCTS",
    "QUERIES",
    "RELEASES",
    "Gateway",
    "OutOfMemory",
    "percentile",
]


#: Every release the gateway can run, oldest first: what changed, and how it behaves.
RELEASES: dict[str, dict[str, Any]] = {
    "1.8.2": {
        "date": "Sep 29",
        "notes": "Order ids are sortable by time. Cart totals include tax.",
        "search_ms": 46,
        "search_fail": 0.0,
        "leak_kb": 0,
        "drops": [],
    },
    "1.8.3": {
        "date": "Oct 8",
        "notes": "Catalog pages cached for 30 seconds. Fewer upstream timeouts.",
        "search_ms": 42,
        "search_fail": 0.0,
        "leak_kb": 0,
        "drops": [],
    },
    "1.9.0": {
        "date": "Oct 20",
        "notes": "New search ranking, by margin and stock. Help center reorganised.",
        "search_ms": 160,
        "search_fail": 0.36,
        "leak_kb": 640,
        "drops": ["returns"],
    },
    "1.9.1": {
        "date": "Oct 21",
        "notes": "Fixes the ranking crash and the result cache leak from 1.9.0.",
        "search_ms": 28,
        "search_fail": 0.0,
        "leak_kb": 0,
        "drops": [],
    },
}

#: The gateway gives up once it holds this much: the box it was sized for.
MEMORY_LIMIT_MB = 340

#: Requests that fail on any release: an upstream that times out now and then.
BASE_FAIL = 0.002

#: Halcyon's shelf: sku, name, price.
PRODUCTS: list[tuple[str, str, float]] = [
    ("TN-2P", "Ridgeline 2P tent", 349.0),
    ("TN-1P", "Ridgeline 1P tent", 279.0),
    ("SB-20", "Larch 20F sleeping bag", 219.0),
    ("SB-35", "Larch 35F sleeping bag", 169.0),
    ("SP-UL", "Ultralight sleeping pad", 129.0),
    ("ST-TI", "Titanium canister stove", 64.0),
    ("ST-FL", "Fuel canister, 230g", 7.5),
    ("HL-400", "Headlamp, 400 lumen", 39.0),
    ("HL-900", "Headlamp, 900 lumen", 69.0),
    ("JK-RN", "Rain shell", 189.0),
    ("JK-DN", "Down jacket", 249.0),
    ("PK-45", "Trail pack, 45L", 199.0),
    ("PK-28", "Day pack, 28L", 119.0),
    ("WF-SQ", "Squeeze water filter", 42.0),
    ("CK-SET", "Two-pot cook set", 54.0),
    ("TP-MN", "Trekking poles, carbon", 139.0),
    ("GL-FL", "Fleece gloves", 29.0),
    ("SK-WL", "Merino socks, 3 pairs", 36.0),
    ("MP-WR", "Waterproof map case", 18.0),
    ("FA-KT", "First aid kit", 32.0),
    ("TR-LT", "Camp lantern", 45.0),
    ("CH-UL", "Ultralight camp chair", 99.0),
    ("BT-1L", "Insulated bottle, 1L", 34.0),
    ("CM-TR", "Trail camera mount", 24.0),
]

#: What shoppers search for.
QUERIES = [
    "tent",
    "sleeping bag",
    "headlamp",
    "stove",
    "rain jacket",
    "pack",
    "water filter",
    "poles",
    "down",
    "ultralight",
    "lantern",
    "socks",
]

#: The help center: slug, title, the slugs it links to.
DOCS: dict[str, tuple[str, list[str]]] = {
    "index": ("Help center", ["shipping", "returns", "sizing", "warranty", "orders", "contact"]),
    "shipping": ("Shipping and delivery", ["orders", "returns", "international"]),
    "international": ("Shipping outside the US", ["shipping", "customs"]),
    "customs": ("Customs and duties", ["international", "contact"]),
    "returns": ("Returns and exchanges", ["warranty", "orders", "contact"]),
    "sizing": ("Sizing guides", ["returns", "fit-jackets", "fit-packs"]),
    "fit-jackets": ("Jacket fit", ["sizing", "returns"]),
    "fit-packs": ("Pack fit", ["sizing"]),
    "warranty": ("Lifetime warranty", ["repairs", "returns", "contact"]),
    "repairs": ("Repairs", ["warranty", "contact"]),
    "orders": ("Your orders", ["shipping", "cancel", "returns"]),
    "cancel": ("Cancelling an order", ["orders", "contact"]),
    "contact": ("Contact us", ["index"]),
}

#: Status line texts.
REASONS = {
    200: "OK",
    201: "Created",
    400: "Bad Request",
    404: "Not Found",
    500: "Internal Server Error",
    503: "Service Unavailable",
}


def percentile(values: list[float], q: float) -> float:
    """The ``q`` percentile of ``values`` (0 to 100), nearest rank; 0 for none."""
    if not values:
        return 0.0
    ordered = sorted(values)
    k = max(0, min(len(ordered) - 1, round(q / 100 * (len(ordered) - 1))))
    return float(ordered[k])


def _rss_mb() -> float:
    """This process's resident memory, in MB, read from /proc."""
    try:
        pages = int(Path("/proc/self/statm").read_text().split()[1])
    except (OSError, ValueError, IndexError):
        return 0.0
    return pages * os.sysconf("SC_PAGE_SIZE") / 1e6


class OutOfMemory(RuntimeError):  # noqa: N818  # what the log says when it dies
    """The gateway holds more than it was sized for, and stops."""


class Gateway:
    """The storefront API, provided per job run; :meth:`open` starts it serving."""

    def __init__(self) -> None:
        self.port, self.release, self.spec = 0, "", RELEASES["1.8.3"]
        self.started = time.time()
        self.server: asyncio.base_events.Server | None = None
        self.lines: list[dict[str, Any]] = []
        self.window: deque[tuple[float, str, int, float]] = deque()
        self.totals = {"requests": 0, "errors": 0, "orders": 0}
        self.order_times: deque[float] = deque()
        self.held: list[bytes] = []
        self.next_order = 0
        self.dying = ""

    # --- lifecycle ---------------------------------------------------------------------------

    async def open(self, port: int, release: str, data: str) -> dict[str, Any]:
        """Bind ``port`` on the loopback and serve as ``release`` does; the orders store in ``data``.

        Returns the first drain: the lines it logged on the way up.
        """
        self.port = int(port)
        self.release = release if release in RELEASES else "1.8.3"
        self.spec = RELEASES[self.release]
        folder = Path(data)
        folder.mkdir(parents=True, exist_ok=True)
        self.orders = folder / "orders.jsonl"
        self.next_order = 18000 + (
            sum(1 for _ in self.orders.open()) if self.orders.exists() else 0
        )
        # A restart can start before the old process has let go of the port: wait for it.
        for tries in range(50):
            try:
                self.server = await asyncio.start_server(
                    self._serve, "127.0.0.1", self.port, reuse_address=True
                )
                break
            except OSError as e:
                if e.errno != errno.EADDRINUSE or tries == 49:
                    raise
                await asyncio.sleep(0.2)
        self.started = time.time()
        self._app(
            "info",
            f"listening on :{self.port}, release {self.release}",
            release=self.release,
            pid=os.getpid(),
        )
        if self.spec["drops"]:
            self._app("info", "help center reorganised", removed=", ".join(self.spec["drops"]))
        return self.drain()

    def setup(self, ctx: object) -> None:
        """Nothing until :meth:`open`: the port and the release are read from the space first."""

    async def acleanup(self) -> None:
        """Stop serving."""
        if self.server is not None:
            self.server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.server.wait_closed(), 2.0)

    # --- serving -----------------------------------------------------------------------------

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                head = await reader.readuntil(b"\r\n\r\n")
                lines = head.decode("latin-1").split("\r\n")
                method, target, _ = [*lines[0].split(" "), "", "", ""][:3]
                headers = {
                    k.strip().lower(): v.strip()
                    for k, _, v in (line.partition(":") for line in lines[1:] if line)
                }
                size = int(headers.get("content-length") or 0)
                body = await reader.readexactly(size) if size else b""
                began = time.perf_counter()
                status, payload = await self._route(method, target, body)
                ms = (time.perf_counter() - began) * 1000
                raw = json.dumps(payload).encode()
                writer.write(
                    f"HTTP/1.1 {status} {REASONS.get(status, 'OK')}\r\nContent-Type: application/json\r\n"
                    f"Content-Length: {len(raw)}\r\nConnection: keep-alive\r\n\r\n".encode()
                    + raw
                )
                await writer.drain()
                self._access(
                    method, target, status, ms, len(raw), headers.get("user-agent", ""), payload
                )
        except (asyncio.IncompleteReadError, ConnectionError, asyncio.LimitOverrunError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    async def _route(self, method: str, target: str, body: bytes) -> tuple[int, dict[str, Any]]:
        path, _, query = target.partition("?")
        params = dict(p.partition("=")[::2] for p in query.split("&") if p)
        if path == "/health":
            return 200, {
                "ok": True,
                "release": self.release,
                "up_s": round(time.time() - self.started),
                "rss_mb": round(_rss_mb()),
            }
        if path.startswith("/docs/"):
            await self._wait(6)
            slug = path.removeprefix("/docs/")
            if slug not in DOCS or slug in self.spec["drops"]:
                return 404, {"error": f"no help page {slug!r}"}
            title, links = DOCS[slug]
            return 200, {"title": title, "links": [f"docs/{s}" for s in links]}
        if _rng.random() < BASE_FAIL:
            await self._wait(900)
            return 503, {"error": "upstream timed out after 900ms: inventory"}
        if path == "/api/catalog":
            await self._wait(16)
            page = int(params.get("page") or 1)
            items = PRODUCTS[(page - 1) * 8 % len(PRODUCTS) :][:8]
            return 200, {
                "page": page,
                "items": [{"sku": s, "name": n, "price": p} for s, n, p in items],
            }
        if path == "/api/search":
            return await self._search(params.get("q", "").replace("+", " ").replace("%20", " "))
        if path == "/api/cart":
            await self._wait(9)
            return 200, {"items": _rng.randint(0, 4)}
        if path == "/api/orders" and method == "POST":
            return await self._order(body)
        if path.startswith("/api/orders/"):
            await self._wait(11)
            return 200, {
                "id": path.rsplit("/", 1)[-1],
                "status": _rng.choice(["packed", "shipped", "delivered"]),
            }
        return 404, {"error": f"no route {method} {path}"}

    async def _search(self, q: str) -> tuple[int, dict[str, Any]]:
        await self._wait(self.spec["search_ms"])
        if self.spec["leak_kb"]:
            # 1.9.0 caches every ranked result set and never evicts it.
            self.held.append(b"\x01" * (self.spec["leak_kb"] * 1024))
        if _rng.random() < self.spec["search_fail"]:
            hits = _rng.randint(13, 24)
            return 500, {
                "error": f"ranking: score vector shorter than results ({hits - _rng.randint(1, 6)} < {hits})",
                "q": q,
            }
        hits = [
            {"sku": s, "name": n} for s, n, _ in PRODUCTS if any(w in n.lower() for w in q.split())
        ]
        return 200, {"q": q, "hits": hits[:10]}

    async def _order(self, body: bytes) -> tuple[int, dict[str, Any]]:
        await self._wait(24)
        try:
            ask = json.loads(body or b"{}")
            sku, qty = str(ask["sku"]), int(ask.get("qty") or 1)
        except (ValueError, KeyError, TypeError):
            return 400, {"error": "an order needs a sku"}
        self.next_order += 1
        oid = f"HC-{self.next_order}"
        price = next((p for s, _, p in PRODUCTS if s == sku), 0.0)
        record = {
            "id": oid,
            "sku": sku,
            "qty": qty,
            "total": round(price * qty, 2),
            "at": round(time.time(), 3),
        }
        with self.orders.open("a") as f:
            f.write(json.dumps(record) + "\n")
        self.totals["orders"] += 1
        self.order_times.append(time.time())
        return 201, {"id": oid, "total": record["total"]}

    async def _wait(self, ms: float) -> None:
        # Real time spent, with the long tail real services have.
        await asyncio.sleep(ms * _rng.lognormvariate(0, 0.35) / 1000)

    # --- what it saw -------------------------------------------------------------------------

    def _access(
        self, method: str, target: str, status: int, ms: float, size: int, agent: str, payload: dict
    ) -> None:
        path = target.partition("?")[0]
        route = (
            "/docs/*"
            if path.startswith("/docs/")
            else ("/api/orders/:id" if path.startswith("/api/orders/") else path)
        )
        now = time.time()
        self.window.append((now, route, status, ms))
        self.totals["requests"] += 1
        failed = status >= 500
        self.totals["errors"] += failed
        level = "error" if failed else ("warning" if status >= 400 else "info")
        fields = {
            "method": method,
            "path": target[:80],
            "status": status,
            "ms": round(ms, 1),
            "bytes": size,
            "agent": agent.split("/")[0],
        }
        if status >= 400:
            fields["error"] = str(payload.get("error", ""))[:120]
        self.lines.append(
            {
                "id": uuid.uuid4().hex,
                "ts_us": int(now * 1e6),
                "level": level,
                "msg": f"{method} {target[:60]} {status} {ms:.0f}ms",
                "fields": fields,
            }
        )

    def _app(self, level: str, msg: str, **fields: object) -> None:
        self.lines.append(
            {
                "id": uuid.uuid4().hex,
                "ts_us": int(time.time() * 1e6),
                "level": level,
                "msg": msg,
                "fields": fields,
            }
        )

    def drain(self) -> dict[str, Any]:
        """Everything since the last drain: log lines, the live numbers, a metric point.

        Raises:
            OutOfMemory: The gateway holds more than :data:`MEMORY_LIMIT_MB`.
                Its last lines are logged first, so the flush that raises has
                already been asked for its words.
        """
        if self.dying:
            raise OutOfMemory(self.dying)
        now = time.time()
        while self.window and self.window[0][0] < now - 60:
            self.window.popleft()
        while self.order_times and self.order_times[0] < now - 60:
            self.order_times.popleft()
        recent = [w for w in self.window if w[0] >= now - 15]
        rps = sum(1 for w in self.window if w[0] >= now - 5) / 5
        err = sum(1 for w in recent if w[2] >= 500) / len(recent) if recent else 0.0
        lat = [w[3] for w in recent]
        routes: dict[str, list[tuple[int, float]]] = {}
        codes: dict[str, int] = {}
        for _, route, status, ms in self.window:
            routes.setdefault(route, []).append((status, ms))
            codes[str(status)] = codes.get(str(status), 0) + 1
        rss = _rss_mb()
        if rss > MEMORY_LIMIT_MB:
            self.dying = f"out of memory: {rss:.0f} MB held, over the {MEMORY_LIMIT_MB} MB limit"
            self._app("critical", self.dying + ", exiting", rss_mb=round(rss), release=self.release)
        table = [
            {
                "route": r,
                "rpm": len(v),
                "err": round(sum(1 for s, _ in v if s >= 500) / len(v) * 100, 1),
                "p50": round(percentile([m for _, m in v], 50)),
                "p95": round(percentile([m for _, m in v], 95)),
            }
            for r, v in sorted(routes.items(), key=lambda kv: -len(kv[1]))
        ]
        gw = {
            "release": self.release,
            "pid": os.getpid(),
            "port": self.port,
            "started": self.started,
            "at": now,
            "rps": round(rps, 2),
            "err": round(err, 4),
            "p50": round(percentile(lat, 50), 1),
            "p95": round(percentile(lat, 95), 1),
            "routes": table,
            "codes": codes,
            "rss_mb": round(rss, 1),
            "held_mb": round(len(self.held) * self.spec["leak_kb"] / 1024, 1),
            "orders_min": len(self.order_times),
            "dying": self.dying,
            **self.totals,
        }
        lines, self.lines = self.lines, []
        point = {
            "t": int(now),
            "rps": rps,
            "err": err,
            "p50": gw["p50"],
            "p95": gw["p95"],
            "gw_rss": rss,
            "orders": float(len(self.order_times)),
        }
        return {"lines": lines, "gw": gw, "point": point}
