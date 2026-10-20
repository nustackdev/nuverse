"""The Imports page's side of the inbox: dropping a sample export in, watching it, the log.

The loading itself is the importer job's (:mod:`.jobs`); this is what the
page reads and does, as host terms.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

import nu

from .gen import sample_csv
from .jobs import pending


__all__ = ["drop", "log", "watch"]


@nu.host
def drop(inbox: str, kind: str) -> str:
    """A sample export of ``kind`` written into the inbox, as if it had just been saved there."""
    now = time.time()
    name, text = sample_csv(kind, now, int(now * 1000) % 100_000)
    folder = Path(inbox)
    folder.mkdir(parents=True, exist_ok=True)
    part = folder / (name + ".part")
    part.write_text(text, encoding="utf-8")
    part.rename(folder / name)
    return name


@nu.host
def watch(importer: dict, live: bool, inbox: str) -> dict[str, Any]:
    """The importer's status line, and what waits in the inbox."""
    waiting = pending(inbox) if inbox else []
    files = int(importer.get("files") or 0)
    if live and importer.get("status") == "watching":
        line = f"Watching inbox/ in its own process (pid {importer.get('pid')})  ·  {files} file{'' if files == 1 else 's'} loaded so far"
        tone, pulse = "ok", True
    else:
        line, tone, pulse = "Importer starting", "warn", False
    shown = "Waiting in the inbox: " + ", ".join(waiting) if waiting else "The inbox is empty."
    return {"tone": tone, "pulse": pulse, "line": line, "waiting": shown}


@nu.host
def log(entries: list[dict]) -> dict[str, Any]:
    """The import log as table rows, and the latest import in a few lines."""
    rows = [
        {
            "key": f"{e.get('at')}-{e.get('file')}",
            "when": datetime.fromtimestamp(int(e.get("at") or 0)).strftime("%H:%M:%S"),
            "file": e.get("file"),
            "kind": e.get("kind"),
            "loaded": e.get("loaded"),
            "rejected": e.get("rejected"),
            "orders": e.get("orders"),
            "revenue": e.get("revenue"),
            "took": f"{e.get('ms', 0):.0f} ms",
        }
        for e in entries
    ]
    if not entries:
        return {"rows": [], "latest": "Nothing imported yet. Drop an export above."}
    e = entries[0]
    lines = [
        f"**{e.get('file')}**: {e.get('rows')} rows read, {e.get('loaded')} kept as shard "
        f"{', '.join(str(s) for s in e.get('shards') or []) or '(none)'}, {e.get('orders')} orders "
        f"worth ${e.get('revenue', 0):,.2f}, parsed in {e.get('ms', 0):.0f} ms by the importer (pid {e.get('pid')})."
    ]
    if e.get("errors"):
        lines.append("Turned down:\n\n" + "\n".join(f"- {x}" for x in e["errors"]))
    return {"rows": rows, "latest": "\n\n".join(lines)}
