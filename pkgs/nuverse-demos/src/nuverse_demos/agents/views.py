"""What the cells read and draw: an agent's state as terms, and plain Python that shapes it.

The terms gather what a view shows in one read (:func:`agent_view`,
:func:`board`). The ``@nu.host`` functions turn what was read into what a
widget takes: a status line, card text, transcript entries. They are plain
Python, so cells stay short and the shaping is testable on its own.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import nu
from nuspace.shapes import Space
from nuspace.system.utils import snap

from .state import Agent, agents_of, at, job_of, status_of


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "MISSING",
    "MODELS",
    "MODES",
    "TONES",
    "agent_view",
    "board",
    "cards",
    "cards_of",
    "doing_of",
    "doing_text",
    "dumped",
    "dumped_of",
    "entries",
    "entries_of",
    "events_of",
    "fresh_dir",
    "go",
    "head",
    "head_of",
    "sketch_from",
    "sketch_in",
    "spec_from",
    "spec_of",
    "tally",
    "tally_of",
    "with_job",
]


#: The models the form offers, the first the default.
MODELS = ["claude-sonnet-5", "opus", "haiku"]

#: The permission modes the form offers, the first the default.
MODES = ["acceptEdits", "bypassPermissions", "default", "plan"]

#: The pill tone for each status.
TONES = {
    "starting": "info",
    "resuming": "info",
    "working": "ok",
    "idle": "neutral",
    "stopping": "warn",
    "stopped": "neutral",
    "error": "danger",
    "down": "danger",
}

#: What a plane says when the Claude Agent SDK is not here.
MISSING = (
    "**Agents need the Claude Agent SDK and the `claude` CLI.** "
    'Install it with `pip install "nustd[cc]"`, log in with `claude`, then restart the space.'
)

#: Characters of a tool's input shown before it is cut.
CUT = 4000


# --- terms -------------------------------------------------------------------------------------


def with_job(plane: nu.StrArg, body: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """``body(job)`` once the agent page ``plane`` has its job: the launch makes it right after the page."""
    found = snap(job_of(plane) != "")
    wait = nu.WaitReactive(snap(Space.planes[plane].children.on_change()), found, every=2.0)
    return wait >> nu.let(snap(job_of(plane)), lambda job: body(nu.Str(job)))


def agent_view(job: nu.StrArg) -> nu.Nu:
    """Everything an agent's header and card show, in one dict. Bare."""
    a = Agent
    return nu.Dict.of(
        status=status_of(job),
        spec=at(job, a.spec.fallback({})),
        doing=at(job, a.doing.fallback("")),
        prompts=at(job, a.prompts.fallback(0)),
        turns=at(job, a.turns.fallback(0)),
        calls=at(job, a.calls.fallback(0)),
        tokens_in=at(job, a.tokens_in.fallback(0)),
        tokens_out=at(job, a.tokens_out.fallback(0)),
        cost=at(job, a.cost.fallback(0.0)),
        seconds=at(job, a.seconds.fallback(0.0)),
        answer=at(job, a.answer.fallback("")),
        error=at(job, a.error.fallback("")),
        queued=at(job, a.inbox.fallback([]).len()),
    )


def board(root: nu.StrArg) -> nu.Nu:
    """Every agent under the Agents plane as ``[page, job, view]``, oldest first. Bare."""

    def row(r: nu.Nu) -> nu.Nu:
        pair = nu.List(r)
        return nu.List.of(pair[0], pair[1], agent_view(nu.Str(pair[1])))

    return agents_of(root).iter().filter(lambda r: nu.Str(nu.List(r)[1]) != "").map(row).to_list()


def go(nav: nu.Nu, uri: nu.StrArg) -> nu.Nu:
    """Navigate the shell to ``uri``.

    The shell follows the browser's back and forward only, so push the page
    and one past it, and step back onto it.
    """
    return nu.let(uri, lambda u: nav.set(u) >> nav.set(nu.Str(u) + "?open") >> nav.back())


# --- launching ---------------------------------------------------------------------------------


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "agent"


def _fresh_dir(name: str, base: str = "") -> str:
    """A new empty folder for an agent to work in: under ``base`` when given, else a fresh temp dir."""
    if base:
        path = Path(base).expanduser() / _slug(name)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    return tempfile.mkdtemp(prefix=f"nu-agent-{_slug(name)}-")


#: :func:`_fresh_dir` as a term, for a launch that picks a folder when the form leaves it empty.
fresh_dir = nu.host(_fresh_dir, name="FreshDir")


def spec_from(name: str, cwd: str, model: str, mode: str, brief: str, count: int) -> dict:
    """What an agent is made as, from what the form says: blanks filled, a name made up when none is typed."""
    name = name.strip() or f"Agent {count + 1}"
    cwd = cwd.strip()
    return {
        "name": name,
        "cwd": str(Path(cwd).expanduser()) if cwd else _fresh_dir(name),
        "model": model or MODELS[0],
        "mode": mode or MODES[0],
        "brief": brief.strip(),
    }


# --- the job's tallies -------------------------------------------------------------------------


def _short(text: str, n: int = 60) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _tool_line(name: str, args: dict) -> str:
    """A tool call in a few words: ``Bash ls -la``, ``Write index.html``."""
    args = args or {}
    for key in ("command", "file_path", "path", "pattern", "url", "query", "description", "prompt"):
        if args.get(key):
            value = str(args[key])
            if key in ("file_path", "path"):
                value = Path(value).name or value
            return f"{name} {_short(value, 70)}"
    return name


def doing_text(ev: dict) -> str:
    """What an event says the agent is doing now, for its card and header."""
    kind = ev.get("type")
    if kind == "user":
        return "reading the brief"
    if kind == "init":
        return "starting up"
    if kind == "thinking":
        return "thinking"
    if kind == "text":
        return "writing"
    if kind == "tool_use":
        return _tool_line(ev.get("name", ""), ev.get("input") or {})
    if kind == "tool_result":
        return "reading the result"
    if kind == "result":
        return "done" if not ev.get("is_error") else "failed"
    if kind == "error":
        return "failed"
    return ""


def tally_of(ev: dict) -> dict:
    """A result event's accounting: model turns, tokens in and out, dollars, seconds."""
    usage = ev.get("usage") or {}
    tokens_in = sum(
        int(usage.get(k) or 0)
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    return {
        "turns": int(ev.get("num_turns") or 0),
        "in": tokens_in,
        "out": int(usage.get("output_tokens") or 0),
        "cost": float(ev.get("total_cost_usd") or 0.0),
        "seconds": float(ev.get("duration_ms") or 0) / 1000.0,
    }


def sketch_from(cwd: str, seen: object) -> object:
    """The elements in ``sketch.json`` in the agent's folder, or ``seen`` when there is none or it does not parse."""
    try:
        drawn = json.loads((Path(cwd) / "sketch.json").read_text())
    except (OSError, ValueError):
        return seen
    if isinstance(drawn, dict):
        drawn = drawn.get("elements", [])
    return drawn if isinstance(drawn, list) else seen


# --- shaping -----------------------------------------------------------------------------------


def _tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _stats(v: dict) -> str:
    calls = v.get("calls", 0)
    parts = [
        f"{v['prompts']} prompt{'s' if v['prompts'] != 1 else ''}",
        f"{calls} tool call{'s' if calls != 1 else ''}",
        f"{_tokens(v['tokens_in'] + v['tokens_out'])} tokens",
        f"${v['cost']:.2f}",
    ]
    return " · ".join(parts)


def _where(spec: dict) -> str:
    """The agent's folder, short: a temp folder by its name, a home folder from ``~``."""
    cwd = spec.get("cwd", "")
    for base, short in (
        (tempfile.gettempdir(), "tmp"),
        ("/private" + tempfile.gettempdir(), "tmp"),
        (str(Path.home()), "~"),
    ):
        if cwd.startswith(base.rstrip("/") + "/"):
            return short + "/" + cwd[len(base.rstrip("/")) + 1 :]
    return cwd


def head_of(v: dict) -> dict:
    """An :func:`agent_view` as the strings an agent page's header shows."""
    spec = v["spec"] or {}
    status = v["status"]
    doing = v["doing"] if status in ("working", "starting", "resuming", "stopping") else ""
    if status == "idle" and v["queued"] == 0:
        doing = "waiting for you to say something"
    return {
        "name": spec.get("name", "Agent"),
        "status": status,
        "tone": TONES.get(status, "neutral"),
        "facts": " · ".join(
            p for p in (spec.get("model", ""), spec.get("mode", ""), _where(spec)) if p
        ),
        "doing": doing or ("queued: " + str(v["queued"]) if v["queued"] else ""),
        "prompts": str(v["prompts"]),
        "turns": str(v["turns"]),
        "calls": str(v.get("calls", 0)),
        "tokens": _tokens(v["tokens_in"] + v["tokens_out"]),
        "cost": f"${v['cost']:.2f}",
        "seconds": f"{v['seconds']:.0f}s",
        "error": v["error"],
        "button": "Resume" if status in ("stopped", "error", "down") else "Stop",
    }


def cards_of(rows: list) -> list:
    """One dict per agent for its card on the board, oldest first."""
    out = []
    for page, job, v in rows:
        spec = v["spec"] or {}
        status = v["status"]
        live = status in ("working", "starting", "resuming", "stopping")
        answer = (v["answer"] or "").replace("`", "").replace("**", "").strip().splitlines()
        said = _short(answer[0], 120) if answer else ""
        out.append(
            {
                "key": job,
                "href": f"/{page}",
                "name": spec.get("name", "Agent"),
                "where": f"{spec.get('model', '')} · {_where(spec)}",
                "status": status,
                "tone": TONES.get(status, "neutral"),
                "doing": _short(v["doing"], 70) if live and v["doing"] else (said or "-"),
                "stats": _stats(v),
            }
        )
    return out


def _lang(path: str) -> str:
    ext = Path(path).suffix.lstrip(".").lower()
    return {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "md": "markdown",
        "htm": "html",
        "yml": "yaml",
    }.get(ext, ext)


def _cut(text: str) -> str:
    return text if len(text) <= CUT else text[:CUT] + f"\n... {len(text) - CUT:,} more characters"


def _call(name: str, args: dict) -> tuple[str, str]:
    """A tool call's body and its language: the command, the file written, or the input as JSON."""
    args = args or {}
    if name == "Bash" and "command" in args:
        return args["command"], "bash"
    if name == "Write" and "content" in args:
        return _cut(str(args["content"])), _lang(args.get("file_path", ""))
    if name in ("Edit", "MultiEdit") and "old_string" in args:
        old = "\n".join("- " + line for line in str(args["old_string"]).splitlines())
        new = "\n".join("+ " + line for line in str(args["new_string"]).splitlines())
        return _cut(f"{old}\n{new}"), "diff"
    return _cut(json.dumps(args, indent=2, ensure_ascii=False)), "json"


def entries_of(events: list, seen: dict) -> dict:
    """New log events as transcript entries, and what to remember for the next ones.

    ``seen`` carries the index of the next event and each open tool call's
    title, by its id, so a result lands in its call's entry. An entry is
    ``{key, kind, ...}``: ``user``, ``text`` and ``note`` carry ``text``,
    ``tool`` carries ``title``, ``code`` and ``lang``, ``back`` carries
    ``title`` and ``code``.
    """
    seen = dict(seen or {})
    i = int(seen.get("i", 0))
    titles = dict(seen.get("titles", {}))
    out: list[dict[str, Any]] = []
    for raw in events or []:
        ev = json.loads(raw) if isinstance(raw, str) else raw
        key = f"e{i}"
        kind = ev.get("type")
        if kind == "user":
            out.append({"key": key, "kind": "user", "text": ev.get("text", "")})
        elif kind == "text" and ev.get("text", "").strip():
            out.append({"key": key, "kind": "text", "text": ev["text"]})
        elif kind == "thinking" and ev.get("text", "").strip():
            out.append(
                {"key": key, "kind": "tool", "title": "Thinking", "code": ev["text"], "lang": ""}
            )
        elif kind == "tool_use":
            title = _tool_line(ev.get("name", ""), ev.get("input") or {})
            code, lang = _call(ev.get("name", ""), ev.get("input") or {})
            titles[ev.get("id", key)] = title
            out.append(
                {
                    "key": ev.get("id", key),
                    "kind": "tool",
                    "title": title,
                    "code": code,
                    "lang": lang,
                }
            )
        elif kind == "tool_result":
            tid = ev.get("id", key)
            title = titles.pop(tid, "Tool")
            mark = "failed" if ev.get("is_error") else "done"
            lines = len((ev.get("content") or "").splitlines())
            more = f" · {lines} lines" if lines > 1 else ""
            out.append(
                {
                    "key": tid,
                    "kind": "back",
                    "title": f"{title}  ·  {mark}{more}",
                    "code": ev.get("content") or "(no output)",
                }
            )
        elif kind == "result":
            t = tally_of(ev)
            word = "Turn failed" if ev.get("is_error") else "Turn done"
            steps = f"{t['turns']} step{'s' if t['turns'] != 1 else ''}"
            text = f"{word} · {steps} · {t['seconds']:.1f}s · ${t['cost']:.3f}"
            out.append({"key": key, "kind": "note", "text": text})
        elif kind == "error":
            out.append(
                {"key": key, "kind": "note", "text": "Error: " + _short(ev.get("text", ""), 300)}
            )
        i += 1
    return {"entries": out, "seen": {"i": i, "titles": titles}}


def dumped_of(ev: object) -> str:
    """An event as the JSON a log keeps it as."""
    return json.dumps(ev, default=str, ensure_ascii=False)


def events_of(log: list) -> list[dict]:
    """A log's events, read back from their JSON."""
    return [json.loads(raw) for raw in log or []]


#: The shaping above as terms, for the cells: each reads what it is given and hands back plain data.
spec_of = nu.host(spec_from, name="SpecOf")
doing_of = nu.host(doing_text, name="DoingOf")
tally = nu.host(tally_of, name="Tally")
sketch_in = nu.host(sketch_from, name="SketchIn")
head = nu.host(head_of, name="Head")
cards = nu.host(cards_of, name="Cards")
entries = nu.host(entries_of, name="Entries")
dumped = nu.host(dumped_of, name="Dumped")
