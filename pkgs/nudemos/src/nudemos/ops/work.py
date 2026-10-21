"""The work the jobs do, in their own processes: shoppers on the gateway, and the scheduled scripts.

- :class:`Shoppers`: the traffic job's resource. Each :meth:`~Shoppers.shop`
  is one second of shoppers browsing, searching, filling carts and ordering
  over real HTTP keep-alive connections to the gateway.
- :class:`Worker`: the scheduled jobs' resource. :meth:`~Worker.run` runs one
  of them once: ``backup`` archives the orders store, ``offsite`` copies the
  newest archive to the offsite folder and checks it, ``linkcheck`` crawls
  the help center, ``digest`` writes the ops digest.

Every result is ``{ok, summary, lines, result}``: whether it worked, one
sentence, the log lines it wrote on the way, and what the space keeps of it.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import random
import shutil
import tarfile
import time
import uuid
from pathlib import Path
from typing import Any

from .gateway import PRODUCTS, QUERIES


#: Where the traffic's and the latency's randomness comes from: no seed, every run differs.
_rng = random.Random()  # noqa: S311

__all__ = ["KEEP", "Shoppers", "Worker", "get"]


#: Archives the backup job keeps, newest first.
KEEP = 8

#: What a shopper's browser calls itself.
AGENTS = ["halcyon-web/4.2", "halcyon-ios/3.9", "halcyon-android/3.8"]


def _line(level: str, msg: str, **fields: object) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "ts_us": int(time.time() * 1e6),
        "level": level,
        "msg": msg,
        "fields": fields,
    }


async def get(port: int, path: str, timeout: float = 3.0) -> tuple[int, dict[str, Any]]:
    """One GET to the gateway on the loopback: ``(status, body)``, ``(0, {error})`` when it is down."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", port), timeout)
    except (OSError, TimeoutError, asyncio.TimeoutError) as e:
        return 0, {"error": f"connection refused: {type(e).__name__}"}
    try:
        writer.write(
            f"GET {path} HTTP/1.1\r\nHost: halcyon\r\nUser-Agent: ops/1.0\r\nConnection: close\r\n\r\n".encode()
        )
        await writer.drain()
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout)
        status = int(head.split(b" ", 2)[1])
        size = next(
            (
                int(h.split(b":")[1])
                for h in head.split(b"\r\n")
                if h.lower().startswith(b"content-length")
            ),
            0,
        )
        body = await asyncio.wait_for(reader.readexactly(size), timeout) if size else b"{}"
        return status, json.loads(body or b"{}")
    except (
        OSError,
        TimeoutError,
        asyncio.TimeoutError,
        asyncio.IncompleteReadError,
        ValueError,
    ) as e:
        return 0, {"error": f"{type(e).__name__}"}
    finally:
        with contextlib.suppress(Exception):
            writer.close()


class _Conn:
    """One shopper's keep-alive connection."""

    def __init__(self) -> None:
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.agent = _rng.choice(AGENTS)

    async def call(self, port: int, method: str, path: str, body: dict | None = None) -> int:
        if self.writer is None:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", port), 2.0
            )
        raw = json.dumps(body).encode() if body is not None else b""
        self.writer.write(
            f"{method} {path} HTTP/1.1\r\nHost: halcyon\r\nUser-Agent: {self.agent}\r\n"
            f"Content-Length: {len(raw)}\r\nContent-Type: application/json\r\n\r\n".encode()
            + raw
        )
        await self.writer.drain()
        reader = self.reader
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 5.0)
        status = int(head.split(b" ", 2)[1])
        size = next(
            (
                int(h.split(b":")[1])
                for h in head.split(b"\r\n")
                if h.lower().startswith(b"content-length")
            ),
            0,
        )
        if size:
            await asyncio.wait_for(reader.readexactly(size), 5.0)
        return status

    def drop(self) -> None:
        if self.writer is not None:
            with contextlib.suppress(Exception):
                self.writer.close()
        self.reader = self.writer = None


class Shoppers:
    """The traffic job's shoppers: a pool of keep-alive connections, one per shopper."""

    def __init__(self) -> None:
        self.conns: list[_Conn] = []
        self.totals = {"sent": 0, "ok": 0, "failed": 0, "refused": 0, "orders": 0}
        self.down_since = 0.0
        self.calls = 0
        self.window = {"sent": 0, "failed": 0, "refused": 0, "orders": 0}

    def setup(self, ctx: object) -> None:
        """Nothing: shoppers connect on their first call."""

    async def acleanup(self) -> None:
        """Close every shopper's connection."""
        for c in self.conns:
            c.drop()

    async def _visit(self, conn: _Conn, port: int, tally: dict[str, int]) -> None:
        # What one shopper does in about a second: mostly browse and search, now and then buy.
        await asyncio.sleep(_rng.random() * 0.9)
        roll = _rng.random()
        if roll < 0.32:
            steps = [("GET", f"/api/search?q={_rng.choice(QUERIES).replace(' ', '+')}", None)]
        elif roll < 0.62:
            steps = [("GET", f"/api/catalog?page={_rng.randint(1, 3)}", None)]
        elif roll < 0.76:
            steps = [("GET", "/api/cart", None)]
        elif roll < 0.86:
            sku = _rng.choice(PRODUCTS)[0]
            steps = [
                ("GET", "/api/cart", None),
                ("POST", "/api/orders", {"sku": sku, "qty": _rng.choice([1, 1, 1, 2])}),
            ]
        elif roll < 0.95:
            steps = [("GET", f"/api/orders/HC-{_rng.randint(18000, 18400)}", None)]
        else:
            steps = [("GET", "/health", None)]
        for method, path, body in steps:
            tally["sent"] += 1
            try:
                status = await conn.call(port, method, path, body)
            except (
                OSError,
                TimeoutError,
                asyncio.TimeoutError,
                asyncio.IncompleteReadError,
                ValueError,
                IndexError,
            ):
                conn.drop()
                tally["refused"] += 1
                return
            if status >= 500:
                tally["failed"] += 1
            else:
                tally["ok"] += 1
            if method == "POST" and status == 201:
                tally["orders"] += 1

    async def shop(self, port: int, users: int) -> dict[str, Any]:
        """About one second of ``users`` shoppers on the gateway: what they sent and what came back.

        Returns ``{sent, ok, failed, refused, orders, users, totals, lines}``;
        ``lines`` says when the gateway stops answering and when it is back.
        """
        users = max(0, min(int(users), 80))
        while len(self.conns) < users:
            self.conns.append(_Conn())
        for c in self.conns[users:]:
            c.drop()
        del self.conns[users:]
        tally = {"sent": 0, "ok": 0, "failed": 0, "refused": 0, "orders": 0}
        began = time.time()
        if users:
            await asyncio.gather(*(self._visit(c, int(port), tally) for c in self.conns))
        await asyncio.sleep(max(0.0, 1.0 - (time.time() - began)))
        for k, v in tally.items():
            self.totals[k] += v
            if k in self.window:
                self.window[k] += v
        self.calls += 1
        lines = []
        if self.calls % 10 == 0:
            w, self.window = self.window, dict.fromkeys(self.window, 0)
            level = "warning" if w["failed"] + w["refused"] > w["sent"] * 0.05 else "info"
            lines.append(
                _line(
                    level,
                    f"last 10s: {w['sent']} requests, {w['failed']} failed, {w['refused']} refused, {w['orders']} orders",
                    users=users,
                    **w,
                )
            )
        if tally["refused"] and not tally["ok"] and not self.down_since:
            self.down_since = time.time()
            lines.append(
                _line(
                    "error",
                    "gateway is not answering, shoppers are waiting",
                    refused=tally["refused"],
                    users=users,
                )
            )
        elif tally["ok"] and self.down_since:
            lines.append(
                _line(
                    "info",
                    f"gateway answering again after {time.time() - self.down_since:.0f}s",
                    users=users,
                )
            )
            self.down_since = 0.0
        return {**tally, "users": users, "totals": dict(self.totals), "lines": lines}


class Worker:
    """The scheduled jobs: :meth:`run` does one run of one, for real, on files in the space's folder."""

    def setup(self, ctx: object) -> None:
        """Nothing to open."""

    async def run(self, name: str, ask: dict[str, Any]) -> dict[str, Any]:
        """One run of job ``name``, with what the space told it (``data`` folder, gateway ``port``, ``state``)."""
        began = time.time()
        lines: list[dict[str, Any]] = []
        try:
            ok, summary, result = await getattr(self, "_" + name)(ask, lines)
        except Exception as e:  # a job's failure is its result, logged, not a crash
            ok, summary, result = False, f"{type(e).__name__}: {e}", {}
            lines.append(_line("error", summary))
        ms = round((time.time() - began) * 1000)
        return {"ok": ok, "summary": summary, "lines": lines, "result": result, "ms": ms}

    async def _backup(self, ask: dict[str, Any], lines: list) -> tuple[bool, str, dict]:
        data = Path(ask["data"])
        orders, folder = data / "orders.jsonl", data / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        if not orders.exists():
            lines.append(_line("warning", "no orders store yet, nothing to archive"))
            return True, "nothing to archive yet", {"archives": _archives(folder)}
        count = sum(1 for _ in orders.open())
        lines.append(
            _line(
                "info",
                f"snapshot of the orders store: {count:,} orders",
                orders=count,
                kb=round(orders.stat().st_size / 1024),
            )
        )
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = folder / f"orders-{stamp}.tar.gz"
        await asyncio.to_thread(_tar, orders, out)
        kb = out.stat().st_size / 1024
        lines.append(
            _line(
                "info", f"wrote orders-{stamp}.tar.gz, {kb:.0f} KB", archive=out.name, kb=round(kb)
            )
        )
        old = sorted(folder.glob("orders-*.tar.gz"), reverse=True)[KEEP:]
        for p in old:
            p.unlink()
        if old:
            lines.append(
                _line(
                    "info",
                    f"pruned {len(old)} archive{'s' if len(old) > 1 else ''} past the newest {KEEP}",
                    pruned=len(old),
                )
            )
        return (
            True,
            f"archived {count:,} orders, {kb:.0f} KB",
            {"archives": _archives(folder), "orders": count},
        )

    async def _offsite(self, ask: dict[str, Any], lines: list) -> tuple[bool, str, dict]:
        data = Path(ask["data"])
        archives = sorted((data / "backups").glob("orders-*.tar.gz"), reverse=True)
        if not archives:
            lines.append(_line("warning", "no archive to send yet"))
            return True, "no archive yet", {}
        newest, there = archives[0], data / "offsite"
        there.mkdir(parents=True, exist_ok=True)
        target = there / newest.name
        if target.exists() and _sha(target) == _sha(newest):
            lines.append(_line("info", f"{newest.name} already offsite, checksum matches"))
            return True, f"{newest.name} already offsite", {"sent": newest.name}
        await asyncio.to_thread(shutil.copyfile, newest, target)
        a, b = _sha(newest), _sha(target)
        if a != b:
            lines.append(_line("error", "checksum mismatch after copy", archive=newest.name))
            return False, f"checksum mismatch on {newest.name}", {}
        kept = sorted(there.glob("orders-*.tar.gz"), reverse=True)
        for p in kept[KEEP * 2 :]:
            p.unlink()
        lines.append(
            _line(
                "info",
                f"sent {newest.name} offsite, sha256 {a[:12]} verified",
                archive=newest.name,
                sha256=a[:16],
            )
        )
        return True, f"sent {newest.name}, verified", {"sent": newest.name, "sha": a[:12]}

    async def _linkcheck(self, ask: dict[str, Any], lines: list) -> tuple[bool, str, dict]:
        port = int(ask["port"])
        for attempt in (1, 2, 3):
            seen: dict[str, int] = {}
            links: dict[str, list[str]] = {}
            queue, refused = ["index"], False
            while queue:
                slug = queue.pop(0)
                if slug in seen:
                    continue
                status, body = await get(port, f"/docs/{slug}")
                if status == 0:
                    refused = True
                    break
                seen[slug] = status
                links[slug] = [x.removeprefix("docs/") for x in body.get("links", [])]
                queue += [t for t in links[slug] if t not in seen]
            if refused:
                lines.append(
                    _line(
                        "warning",
                        f"attempt {attempt} of 3: the gateway did not answer, retrying in 2s",
                        attempt=attempt,
                    )
                )
                await asyncio.sleep(2.0)
                continue
            # A link is broken when the page it points to answers 404.
            broken = [
                (src, dst) for src, outs in links.items() for dst in outs if seen.get(dst) == 404
            ]
            pages = sum(1 for s in seen.values() if s == 200)
            if broken:
                for src, dst in broken:
                    lines.append(
                        _line(
                            "error",
                            f"broken link: docs/{src} links to docs/{dst}, which answers 404",
                            page=f"docs/{src}",
                            target=f"docs/{dst}",
                        )
                    )
                return (
                    False,
                    f"{len(broken)} broken links to docs/{broken[0][1]}",
                    {"pages": pages, "broken": [f"{s} -> {d}" for s, d in broken]},
                )
            lines.append(
                _line("info", f"crawled {pages} help pages, every link answers", pages=pages)
            )
            return True, f"{pages} pages, no broken links", {"pages": pages, "broken": []}
        return False, "the gateway did not answer, 3 attempts", {"pages": 0, "broken": []}

    async def _digest(self, ask: dict[str, Any], lines: list) -> tuple[bool, str, dict]:
        text = digest_text(ask.get("state") or {})
        out = Path(ask["data"]) / "digest.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        lines.append(_line("info", f"wrote the ops digest, {len(text.splitlines())} lines"))
        return True, "digest written", {"text": text}


def _tar(src: Path, out: Path) -> None:
    with tarfile.open(out, "w:gz") as tar:
        tar.add(src, arcname=src.name)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _archives(folder: Path) -> list[dict[str, Any]]:
    return [
        {"name": p.name, "kb": round(p.stat().st_size / 1024), "at": p.stat().st_mtime}
        for p in sorted(folder.glob("orders-*.tar.gz"), reverse=True)
    ]


def digest_text(s: dict[str, Any]) -> str:
    """The ops digest, as markdown, from a snapshot of the space: ``{gw, release, jobs, incidents, machine}``."""
    gw, rel, jobs = s.get("gw") or {}, s.get("release") or {}, s.get("jobs") or {}
    incidents = list((s.get("incidents") or {}).values())
    m = s.get("machine") or {}
    stamp = time.strftime("%H:%M")
    open_ = [i for i in incidents if i.get("status") != "resolved"]
    lines = [
        f"### Ops digest, {stamp}",
        "",
        f"Release **{rel.get('version', '?')}** live. "
        f"{gw.get('rps', 0):.1f} requests a second, {gw.get('err', 0) * 100:.1f}% failing, p95 {gw.get('p95', 0):.0f} ms. "
        f"{gw.get('orders_min', 0)} orders in the last minute.",
        "",
        f"**Incidents:** {len(open_)} open, {len(incidents) - len(open_)} resolved today."
        + "".join(f"\n- {i.get('id')} {i.get('title')} ({i.get('status')})" for i in open_),
        "",
        "**Jobs:**",
    ]
    for name, j in sorted(jobs.items()):
        last = j.get("last") or {}
        lines.append(
            f"- {name}: {j.get('status', '?')}"
            + (f", last run {last.get('summary', '')}" if last else "")
        )
    if m:
        lines += [
            "",
            f"**Machine:** cpu {m.get('cpu', 0):.0f}%, memory {m.get('mem', 0):.0f}%, disk {m.get('disk', 0):.0f}% used.",
        ]
    return "\n".join(lines)
