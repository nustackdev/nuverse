"""The agent every conversation runs on: one cell in the space's Settings plane.

The cell is ``agent``, keyed :data:`KEY`, so the engines find it with one
index read: one per space, the key prefixed with the package. Its prog is a
shim over :func:`out`, and what it keeps is :class:`Config`, in its own
state: a small form, saved by a button.

A chat page makes the cell when no cell has the key (:func:`ensure`), and
leaves it alone when one does: after that it is the owner's to edit. An
engine reads it each time it wakes (:func:`config`), so a change holds from
the next message on, and builds its backend from it (:func:`backend_of`).

Secrets are not kept here yet. ``key_env`` is the name of an environment
variable, read where the engine runs.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace import Space


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nuagent.core import Backend


__all__ = [
    "BACKENDS",
    "CC",
    "KEY",
    "LLM",
    "NAME",
    "PLANE",
    "SOURCE",
    "Config",
    "backend_of",
    "config",
    "ensure",
    "kept",
    "out",
]


#: The space's Settings plane, where the cell lives.
PLANE = "settings"

#: The cell's key, one per space.
KEY = "nuagent_agent"

#: What the cell is called.
NAME = "agent"

#: Claude Code, on this machine's ``claude`` login.
CC = "cc"

#: An OpenAI-compatible chat endpoint.
LLM = "llm"

#: The backends a conversation can run on, the default first.
BACKENDS = (CC, LLM)

#: Seconds an llm call may take before it gives up.
TIMEOUT = 300.0

#: The cell's prog.
SOURCE = """\
from nuagent.planes import settings


out = settings.out()
"""


class Config(nu.Shape):
    """The agent, in the cell's own state: which backend, which model, and for an endpoint where and with what key."""

    backend = nustd.kv.StrRef.slot()  #: one of :data:`BACKENDS`, :data:`CC` when unset
    model = nustd.kv.StrRef.slot()  #: empty for the backend's default
    endpoint = nustd.kv.StrRef.slot()  #: the endpoint's base url, :data:`LLM` only
    key_env = nustd.kv.StrRef.slot()  #: the environment variable holding the key, :data:`LLM` only


class BackendField(nustd.ui.Field):
    input = nustd.ui.SelectRef.slot(options=list(BACKENDS))


class ModelField(nustd.ui.Field):
    input = nustd.ui.InputRef.slot(placeholder="The backend's default")


class EndpointField(nustd.ui.Field):
    input = nustd.ui.InputRef.slot(placeholder="http://localhost:11434/v1", mono=True)


class KeyField(nustd.ui.Field):
    input = nustd.ui.InputRef.slot(placeholder="OPENAI_API_KEY", mono=True)


class Form(nustd.ui.Form):
    backend = BackendField.slot(
        label="Backend",
        help="cc: Claude Code on this machine's login. llm: an OpenAI-compatible endpoint.",
    )
    model = ModelField.slot(label="Model", help="Empty for the backend's default.")
    endpoint = EndpointField.slot(label="Endpoint", help="llm only: the base url.")
    key_env = KeyField.slot(
        label="Key variable", help="llm only: the environment variable that holds the key."
    )
    save = nustd.ui.ButtonRef.slot(label="Save", icon="check")


def kept() -> Config:
    """What the cell keeps: its state read through :class:`Config`, found by :data:`KEY`. Builds refs."""
    return nuspace.at.cell(KEY).state(Config)


def _values(c: Config) -> nu.Nu:
    """What ``c`` holds, as plain data, the defaults filled in. Bare."""
    return nu.Dict.of(
        backend=c.backend.fallback(CC),
        model=c.model.fallback(""),
        endpoint=c.endpoint.fallback(""),
        key_env=c.key_env.fallback(""),
    )


def config() -> nu.Nu:
    """The agent's settings as a dict, the defaults filled in. Bare read, from anywhere."""
    return _values(kept())


def ensure() -> nu.Nu:
    """The cell, made when the Settings plane is there and no cell has :data:`KEY`. One commit.

    Never rewrites one there. Safe from two pages at once: the check and the
    add land in one commit, and the key is taken once.
    """
    missing = nuspace.plane.exists(PLANE).and_(Space.indexes.cell_keys.contains(KEY).not_())
    made = nuspace.cell.add(PLANE, SOURCE, name=NAME, key=KEY, fabrics=["ui"])
    return nuspace.atomic(nu.IfDo(missing, made))


def out() -> nu.Nu:
    """The cell's program: the form shows what is kept, and Save keeps what the form holds."""
    form = Form
    mine = nuspace.here(Config)

    def show(kept: nu.Nu) -> nu.Nu:
        c = nu.Dict(kept)
        return (
            form.backend.input.set(c["backend"])
            >> form.model.input.set(c["model"])
            >> form.endpoint.input.set(c["endpoint"])
            >> form.key_env.input.set(c["key_env"])
        )

    typed = (
        mine.backend.set(nu.Str(form.backend.input).fallback(CC))
        >> mine.model.set(nu.Str(form.model.input).strip())
        >> mine.endpoint.set(nu.Str(form.endpoint.input).strip())
        >> mine.key_env.set(nu.Str(form.key_env.input).strip())
    )
    slots = (mine.backend, mine.model, mine.endpoint, mine.key_env)
    changes = [slot.on_change() for slot in slots]
    return form.save.set("Save") >> nu.ParallelAsync(
        nu.Reconcile(
            nuspace.atomic(nu.OnAny(*changes)),
            nu.let(nuspace.atomic(_values(mine)), show),
            after=nu.RECHECK_AFTER,
            every=nu.RECHECK_EVERY,
        ),
        nu.ReactEvery(form.save.on_click(), nuspace.atomic(typed)),
    )


def backend_of(settings: Mapping[str, str], sid: str = "") -> Backend:
    """The backend the settings name, built. Python, called while the engine builds its run.

    Args:
        settings: what :func:`config` read, as plain data.
        sid: the conversation id, for a backend that holds one (cc).

    Raises:
        ValueError: an unknown backend, or an llm with no endpoint.
    """
    kind = settings.get("backend") or CC
    model = settings.get("model") or None
    if kind == CC:
        from nuagent.presets.backends.cc import ClaudeCode

        return ClaudeCode(model=model, sid=sid or None)
    if kind != LLM:
        msg = f"unknown backend {kind!r}, expected one of {BACKENDS}"
        raise ValueError(msg)
    from nuagent.presets.backends import llm

    if not settings.get("endpoint"):
        msg = "the llm backend needs an endpoint: set it in Settings, under agent"
        raise ValueError(msg)
    endpoint: dict[str, object] = {"base_url": settings["endpoint"], "timeout": TIMEOUT}
    if model is not None:
        endpoint["model"] = model
    if settings.get("key_env"):
        endpoint["api_key"] = os.environ.get(settings["key_env"], "")
    return llm.LLM("bind", **endpoint)
