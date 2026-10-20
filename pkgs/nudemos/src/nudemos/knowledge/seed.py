"""The opening base and the lab notebook export, made real on the day they are read.

The content in :mod:`.data` and in ``exports/`` writes dates as day offsets
(``due:+3``, ``updated: -40``), so the base reads true whatever day it is
first opened: this week's tasks are due this week, stale pages are stale.
Plain Python, no Nu.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from .text import KINDS, day


__all__ = ["EXPORTS", "base", "export", "exports", "parse_note", "resolve_body"]


#: Where the bundled exports live, one folder each.
EXPORTS = Path(__file__).parent / "exports"

#: What an export is called on the Import page, by folder.
NAMES = {"lab-notebook": "Theo's lab notebook (Obsidian vault)"}

DUE_OFFSET = re.compile(r"due:([+-]\d+)")
DATE_OFFSET = re.compile(r"\{date:([+-]\d+)\}")


def _iso(now: float, offset: int) -> str:
    return (day(now) + dt.timedelta(days=offset)).isoformat()


def _short(now: float, offset: int) -> str:
    d = day(now) + dt.timedelta(days=offset)
    return f"{d:%b} {d.day}"


def resolve_body(body: str, now: float) -> str:
    """``due:+3`` as ``due:2026-10-23`` and ``{date:+28}`` as ``Nov 17``, from ``now``."""
    body = DUE_OFFSET.sub(lambda m: f"due:{_iso(now, int(m.group(1)))}", body)
    return DATE_OFFSET.sub(lambda m: _short(now, int(m.group(1))), body)


def _at(now: float, offset: float, hour: int) -> float:
    """``offset`` days from ``now``, at ``hour`` o'clock, never later than now."""
    d = day(now) + dt.timedelta(days=int(offset))
    t = dt.datetime(d.year, d.month, d.day, hour).timestamp()
    return min(t, now - 60)


def _weekday(now: float, offset: int) -> int:
    """``offset`` off the weekend: a Saturday to the Friday before, a Sunday to the Monday after when that is not ahead."""
    d = day(now) + dt.timedelta(days=offset)
    if d.weekday() == 6 and offset + 1 <= 0:
        return offset + 1
    return offset - max(0, d.weekday() - 4)


def base(docs: list[dict], facts: dict, now: float) -> tuple[dict[str, dict], dict[str, dict]]:
    """The opening pages and facts, by slug and key, dated from ``now``."""
    out: dict[str, dict] = {}
    for i, d in enumerate(docs):
        offset = _weekday(now, d.get("date", 0))
        date = _at(now, offset, 10) if "date" in d else 0.0
        title = d["title"].replace("{date}", _short(now, offset))
        out[d["slug"]] = {
            "title": title,
            "kind": d["kind"],
            "folder": KINDS[d["kind"]]["folder"],
            "body": resolve_body(d["body"], now).strip() + "\n",
            "owner": d.get("owner", ""),
            "editor": d.get("editor") or d.get("owner", ""),
            "tags": list(d.get("tags") or []),
            "status": d.get("status", ""),
            "created": _at(now, d.get("created", d.get("updated", 0)), 9),
            "updated": _at(now, d.get("updated", 0), 9 + i % 9),
            "date": date,
            "source": "",
        }
    kept = {
        k: {
            "label": f["label"],
            "value": resolve_body(f["value"], now),
            "owner": f.get("owner", ""),
            "note": f.get("note", ""),
            "updated": _at(now, f.get("updated", -(7 + (i * 11) % 80)), 11),
        }
        for i, (k, f) in enumerate(facts.items())
    }
    return out, kept


# --- exports --------------------------------------------------------------------------------


def exports() -> list[dict[str, Any]]:
    """The bundled exports: ``{key, label, files}`` each."""
    if not EXPORTS.is_dir():
        return []
    return [
        {"key": p.name, "label": NAMES.get(p.name, p.name), "files": len(list(p.glob("*.md")))}
        for p in sorted(EXPORTS.iterdir())
        if p.is_dir()
    ]


def _front(text: str) -> tuple[dict[str, Any], str]:
    """YAML-ish frontmatter (``key: value``, ``[a, b]`` lists) and the rest."""
    if not text.startswith("---"):
        return {}, text
    head, _, rest = text[3:].partition("\n---")
    meta: dict[str, Any] = {}
    for line in head.strip().split("\n"):
        key, _, value = line.partition(":")
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key.strip()] = [
                v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()
            ]
        else:
            meta[key.strip()] = value.strip("'\"")
    return meta, rest.lstrip("\n")


def parse_note(name: str, text: str, now: float, folder: str, source: str) -> tuple[str, dict]:
    """One exported markdown note as ``(slug, page)``: frontmatter, wikilinks and tasks kept."""
    meta, body = _front(text)
    slug = Path(name).stem
    try:
        offset = int(meta.get("updated", 0))
    except ValueError:
        offset = 0
    title = meta.get("title") or slug.replace("-", " ").capitalize()
    tags = meta.get("tags") or []
    return slug, {
        "title": title,
        "kind": meta.get("kind") or "note",
        "folder": folder,
        "body": resolve_body(body, now).strip() + "\n",
        "owner": meta.get("owner", ""),
        "editor": meta.get("owner", ""),
        "tags": tags if isinstance(tags, list) else [tags],
        "status": "",
        "created": _at(now, offset - 7, 9),
        "updated": _at(now, offset, 15),
        "date": 0.0,
        "source": source,
    }


def export(key: str) -> list[tuple[str, str]]:
    """An export's files as ``(name, text)``, its index first."""
    files = sorted(
        (EXPORTS / key).glob("*.md"), key=lambda p: (not p.stem.endswith("index"), p.name)
    )
    return [(p.name, p.read_text()) for p in files]
