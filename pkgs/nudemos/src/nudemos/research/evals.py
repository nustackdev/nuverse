"""The eval: how a question is put to a model, and how its reply is graded. Plain Python.

An arm is one way of asking: a model, a style (``direct``: the number
alone, ``steps``: work it through, then the number) and a context
(``clean``, or ``noisy`` with the suite's irrelevant sentence added). A run
puts every question of the suite to one arm. The probe on the Watch page
asks one question at a time, alternating clean and noisy.

The reply is graded on its last number, so a stepwise answer's working
never counts against it.
"""

from __future__ import annotations

import re
from typing import Any

from .data import SUITE


__all__ = [
    "BY_ID",
    "CONTEXTS",
    "MODELS",
    "MODEL_IDS",
    "STYLES",
    "SYSTEM",
    "arm_label",
    "grade",
    "last_number",
    "prompt",
    "tier",
]


#: The models a run can ask, by the name Claude Code takes, with how the desk shows them.
MODELS = {"claude-sonnet-5": "Sonnet", "haiku": "Haiku"}

#: What each model is, said plainly on a run's page.
MODEL_IDS = {
    "claude-sonnet-5": "Claude Sonnet 5",
    "haiku": "Claude Haiku, through Claude Code's haiku alias",
}

#: How a question is asked, and with what around it.
STYLES = {"direct": "Direct", "steps": "Step by step"}
CONTEXTS = {"clean": "Clean", "noisy": "Distracted"}

#: The system prompt per style. Short on purpose: nothing else is in the model's context.
SYSTEM = {
    "direct": "You answer arithmetic word problems. Reply with the final number only: no words, no units, no working.",
    "steps": (
        "You answer arithmetic word problems. Work through the problem step by step, briefly, "
        "then give the final number on the last line as 'Answer: <number>'."
    ),
}

BY_ID: dict[str, dict[str, Any]] = {q["id"]: q for q in SUITE}


def prompt(qid: str, context: str) -> str:
    """The question as asked: with the irrelevant sentence put before the question when ``noisy``."""
    q = BY_ID[qid]
    if context != "noisy":
        return q["text"]
    # The noise goes just before the last sentence, the question itself, as GSM-IC places it.
    head, _, ask = q["text"].rpartition(". ")
    return f"{head}. {q['noise']} {ask}" if head else f"{q['noise']} {q['text']}"


_NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def last_number(text: str) -> float | None:
    """The last number in ``text``, ``1,471`` read as 1471. None for none."""
    found = _NUMBER.findall(text or "")
    if not found:
        return None
    try:
        return float(found[-1].replace(",", ""))
    except ValueError:
        return None


def grade(qid: str, text: str) -> dict[str, Any]:
    """``{got, correct}`` for a reply to ``qid``: its last number against the answer."""
    got = last_number(text)
    want = float(BY_ID[qid]["answer"])
    return {"got": got, "correct": got is not None and abs(got - want) < 1e-6 * max(1.0, abs(want))}


def tier(qid: str) -> str:
    """``word`` for the word problems, ``hard`` for the ones hard to do in one go."""
    return BY_ID.get(qid, {}).get("tier", "word")


def arm_label(model: str, style: str, context: str) -> str:
    """``Sonnet · Step by step · Distracted``."""
    return f"{MODELS.get(model, model)} · {STYLES.get(style, style)} · {CONTEXTS.get(context, context)}"
