"""The agent half of the prompt: reply contract, ``out()``, how a run ends, observations.

What a model is told about this loop and nothing else. What Nu is, what it
can call and what the world holds come from the caller (the generic Nu prose
is its own package), so :func:`prompt` is one piece the caller places in the
opening message, beside its own.

Two halves that have to agree. ``protocol.md`` is the prose, and
:mod:`.observation` renders what the model actually gets back. The labels
live in :data:`LABELS`, the prose quotes them, and a test reads both.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files

from .observation import (
    CONSTRUCT,
    KINDS,
    LABELS,
    NO_CODE,
    NO_CODE_TEXT,
    OK,
    OUTCOME,
    RUNTIME,
    STATE,
    observation,
    render,
)


__all__ = [
    "CONSTRUCT",
    "KINDS",
    "LABELS",
    "NO_CODE",
    "NO_CODE_TEXT",
    "OK",
    "OUTCOME",
    "RUNTIME",
    "STATE",
    "observation",
    "prompt",
    "render",
]


@cache
def prompt() -> str:
    """The protocol prose, as markdown: how to reply, what comes back, how to end the run."""
    return files(__package__).joinpath("protocol.md").read_text(encoding="utf-8")
