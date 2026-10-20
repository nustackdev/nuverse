"""Ask Larkspur: a question answered by Claude from the base as it is now, citing its pages.

One prompt, one ``claude`` process (``nustd.cc``), no tools: the whole base
goes in the prompt (each page with its facts filled in, tasks with their
dates), and the answer cites pages as ``[[slug]]``, drawn as links here like
any page. Ask again after a fact changes and the answer follows the fact.

Importing :data:`Asker` needs the ``claude-agent-sdk`` package; the Ask page
checks :data:`READY` before it offers the box.
"""

from __future__ import annotations

import importlib.util
import re
import tempfile
import time
from typing import Any

import nu

from . import text
from .text import FACT, QUERY, day


#: One or more citations in a row, the space before them, and what comes right after.
CITES = re.compile(r"\s*\(?((?:\[\[[^\]]+\]\](?:[,;\s]+(?=\[\[))?)+)\)?(?=([.,;:!?)]|$)?)")


def cited(md: str) -> str:
    """Citations side by side, or closing a clause, as one aside: ``(Pricing, Weekly sync)``."""

    def aside(m: re.Match) -> str:
        links = [f"[[{c[0]}]]" for c in text.LINK.findall(m.group(1))]
        if len(links) == 1 and m.group(2) is None:
            return m.group(0)
        return " (" + ", ".join(links) + ")"

    return CITES.sub(aside, md)


__all__ = ["MODEL", "OPTIONS", "READY", "SYSTEM", "answered", "asked", "cited", "prompt", "shown"]


#: Whether the Claude Agent SDK is here to talk to Claude Code with.
READY = importlib.util.find_spec("claude_agent_sdk") is not None

MODEL = "claude-sonnet-5"

SYSTEM = """\
You answer questions about Larkspur, a seven-person company making Fieldnote, from its knowledge base.
Use only the pages given. If the base does not say, say so in one sentence.
Cite the pages you use inline as [[slug]], with the slug exactly as given. Never invent a slug.
Be brief and concrete: two to five sentences, or a short list. Plain markdown, no headings, no tables.
Write dates like Oct 24. Never use the em dash character."""

#: The one agent: Sonnet, no tools, one turn, our own system prompt in place of Claude Code's,
#: run from the temp dir so no project around it is read.
OPTIONS = {
    "model": MODEL,
    "system_prompt": SYSTEM,
    "allowed_tools": [],
    "max_turns": 1,
    "cwd": tempfile.gettempdir(),
}


if READY:
    import nustd.cc

    class Asker(nu.Service):
        """The base's one question endpoint."""

        answer = nustd.cc.PromptRef.method()

    __all__ += ["Asker"]


def prompt(docs: dict, facts: dict, question: str, now: float) -> str:
    """The question, after every page of the base with its facts filled in."""
    pages = []
    for k, d in sorted(docs.items(), key=lambda kv: (kv[1].get("kind", ""), kv[0])):
        body = "\n".join(
            line for line in (d.get("body") or "").split("\n") if not QUERY.match(line.strip())
        )
        body = FACT.sub(lambda m: (facts.get(m.group(1)) or {}).get("value", m.group(1)), body)
        meta = [d.get("kind", ""), f"owner {d.get('owner', '')}"]
        if d.get("status"):
            meta.append(d["status"])
        if d.get("date"):
            meta.append(f"held {day(d['date']).isoformat()}")
        meta.append(f"edited {day(d.get('updated') or now).isoformat()}")
        pages.append(f"### [[{k}]] {d.get('title', k)} ({', '.join(meta)})\n\n{body.strip()}")
    listed = "\n".join(f"- {f['label']}: {f['value']}" for f in facts.values())
    return (
        f"Today is {day(now).isoformat()}.\n\n## Facts\n\n{listed}\n\n## Pages\n\n"
        + "\n\n".join(pages)
        + f"\n\n## Question\n\n{question.strip()}"
    )


@nu.host
def asked(docs: dict, facts: dict, question: str) -> str:
    """:func:`prompt`, now."""
    return prompt(docs or {}, facts or {}, question or "", time.time())


@nu.host
def answered(asks: list, reply: dict, question: str, t0: float) -> list[dict[str, Any]]:
    """The reply onto the list of questions asked, newest first."""
    r = dict(reply or {})
    entry = {
        "t": time.time(),
        "q": (question or "").strip(),
        "a": (r.get("text") or "").strip() or "_No answer came back._",
        "cost": r.get("total_cost_usd") or 0.0,
        "secs": round(time.time() - (t0 or time.time()), 1),
    }
    return [entry, *(asks or [])][:20]


@nu.host
def shown(asks: list, docs: dict, facts: dict, base: str, now: float) -> dict[str, str]:
    """The latest answer, its line, and the ones before it, drawn with live links."""
    asks = list(asks or [])
    if not asks:
        return {"answer": "", "line": "", "before": ""}
    a = asks[0]

    def draw(md: str) -> str:
        # Citations side by side read as one aside: (Pricing, Weekly sync, Oct 13).
        md = CITES.sub(
            lambda m: (
                " ("
                + ", ".join(
                    text.LINK.findall(m.group(0))
                    and [f"[[{c[0]}]]" for c in text.LINK.findall(m.group(0))]
                )
                + ")"
            ),
            md,
        )
        return text.inline(md, docs or {}, facts or {}, base)

    before = [f"**{x['q']}**  \n{draw(x['a'])}  \n_{text.ago(x['t'], now)}_" for x in asks[1:6]]
    return {
        "answer": f"**{a['q']}**\n\n{draw(a['a'])}",
        "line": f"Answered from {len(docs or {})} pages in {a['secs']} s, {text.ago(a['t'], now)}.",
        "before": ("### Asked before\n\n" + "\n\n".join(before)) if before else "",
    }
