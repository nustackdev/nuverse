"""The agent every conversation runs on: one cell in the space's Settings plane.

The cell is ``agent``, under a fixed id, :data:`CELL`, so the engines find it
without a lookup. Its prog is a shim over :func:`out`, and what it keeps is
:class:`Config`, in its own state: a small form, saved by a button.

A chat page makes the cell when it is missing (:func:`ensure`), and leaves it
alone when it is there: after that it is the owner's to edit. An engine reads
it each time it wakes (:func:`config`), so a change holds from the next
message on, and builds its backend from it (:func:`backend_of`).

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
from nuspace import ops
from nuspace.system.utils import redraws, snap


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nuagent.core import Backend


__all__ = [
    "BACKENDS",
    "CC",
    "CELL",
    "LLM",
    "NAME",
    "PLANE",
    "SOURCE",
    "Config",
    "backend_of",
    "config",
    "ensure",
    "out",
]


#: The space's Settings plane, where the cell lives.
PLANE = "settings"

#: The cell's id, fixed.
CELL = "settings_agent"

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


class Config(nuspace.CellState):
    """The agent: which backend, which model, and for an endpoint where and with what key."""

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


def _values() -> nu.Nu:
    """What the cell keeps, as plain data, the defaults filled in. Bare, the cell's own state."""
    return nu.Dict.of(
        backend=Config.backend.fallback(CC),
        model=Config.model.fallback(""),
        endpoint=Config.endpoint.fallback(""),
        key_env=Config.key_env.fallback(""),
    )


def config() -> nu.Nu:
    """The agent's settings as a dict, the defaults filled in. Bare read, from anywhere."""
    return ops.cell_state(CELL, _values())


def ensure() -> nu.Nu:
    """The cell, made when the Settings plane has none. Idempotent, and never rewrites one there."""
    missing = snap(ops.plane_exists(PLANE).and_(ops.cell_exists(CELL).not_()))
    return nu.IfDo(missing, ops.add_cell(PLANE, SOURCE, cell_id=CELL, name=NAME))


def out() -> nu.Nu:
    """The cell's program: the form shows what is kept, and Save keeps what the form holds."""
    form = Form

    def show(kept: nu.Nu) -> nu.Nu:
        c = nu.Dict(kept)
        return (
            form.backend.input.set(c["backend"])
            >> form.model.input.set(c["model"])
            >> form.endpoint.input.set(c["endpoint"])
            >> form.key_env.input.set(c["key_env"])
        )

    typed = (
        Config.backend.set(nu.Str(form.backend.input).fallback(CC))
        >> Config.model.set(nu.Str(form.model.input).strip())
        >> Config.endpoint.set(nu.Str(form.endpoint.input).strip())
        >> Config.key_env.set(nu.Str(form.key_env.input).strip())
    )
    slots = (Config.backend, Config.model, Config.endpoint, Config.key_env)
    return form.save.set("Save") >> nu.ParallelAsync(
        redraws([slot.on_change() for slot in slots], _values(), show),
        nu.ReactForever(form.save.on_click(), ops.atomic_state(typed)),
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
