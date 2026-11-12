"""The agent every conversation runs on: one cell on the space's Settings plane.

The cell is ``agent``, keyed :data:`KEY`, so the engines find it with one
index read: one per space, the key prefixed with the package. Its prog is a
shim over :func:`out`, and what it keeps is :class:`Config`, in its own
state. It draws as one more group of the plane: a card of four labelled
controls, saved by a button.

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
from nuspace.web.planes import role_plane


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nuagent.core import Backend


__all__ = [
    "BACKENDS",
    "CC",
    "KEY",
    "LLM",
    "NAME",
    "SOURCE",
    "Config",
    "View",
    "backend_of",
    "config",
    "ensure",
    "kept",
    "out",
]


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


class Agent(nustd.ui.Column):
    """The cell's view: a hairline, as between the Settings plane's own groups, then the group."""

    rule = nustd.ui.DividerRef.slot()
    section = nustd.ui.PageSectionRef.slot(
        title="Agent", description="The model every chat runs on"
    )


class View(nu.Shape):
    """The cell's root."""

    agent = Agent.slot(gap=2)


#: The group's card, as the Settings plane's own: a two column board, Save in the footer.
_card = View.agent.section[0].to(nustd.ui.CardRef.slot(size="sm"))
_board = _card[0].to(nustd.ui.GridRef.slot(cols=2, gap=5, stack_below=480))
_save = _card.footer[0].to(nustd.ui.ButtonRef.slot(label="Save", icon="check", size="sm"))


def _field(at: tuple[int, int], label: str, help: str) -> nu.Ref:
    """The control of the board's labelled cell ``at``."""
    return _board[at].to(nustd.ui.FieldRef.slot(label=label, help=help)).control


_backend = _field(
    (0, 0),
    "Backend",
    "cc: Claude Code on this machine's login. llm: an OpenAI-compatible endpoint.",
).to(nustd.ui.SelectRef.slot(options=list(BACKENDS)))
_model = _field((0, 1), "Model", "Empty for the backend's default.").to(
    nustd.ui.InputRef.slot(placeholder="The backend's default")
)
_endpoint = _field((1, 0), "Endpoint", "llm only: the base url.").to(
    nustd.ui.InputRef.slot(placeholder="http://localhost:11434/v1", mono=True)
)
_key_env = _field(
    (1, 1), "Key variable", "llm only: the environment variable that holds the key."
).to(nustd.ui.InputRef.slot(placeholder="OPENAI_API_KEY", mono=True))


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
    """The agent's settings as a dict, the defaults filled in. Bare read, from anywhere.

    The defaults alone while no cell has :data:`KEY` (a space with no web).
    """
    defaults = nu.Dict.of(backend=CC, model="", endpoint="", key_env="")
    return nu.If(Space.indexes.cell_keys.contains(KEY), _values(kept()), defaults)


def ensure() -> nu.Nu:
    """The cell, made when the space has a Settings plane and no cell has :data:`KEY`.

    The plane is the one the web's ``settings`` role names, read in its own
    commit (the web keeps its roles apart from the space). Then the check
    and the add land in one space commit, so two pages at once take the key
    once. Never rewrites one there. A space with no web, so no role, gets
    no cell, and :func:`config` reads the defaults.
    """

    def made(found: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(found)
        missing = (plane != "").and_(nuspace.plane.exists(plane))
        missing = missing.and_(Space.indexes.cell_keys.contains(KEY).not_())
        add = nuspace.cell.add(plane, SOURCE, name=NAME, key=KEY, fabrics=["ui"])
        return nuspace.atomic(nu.IfDo(missing, add))

    return nu.let(nuspace.atomic(role_plane("settings")), made)


def out() -> nu.Nu:
    """The cell's program: the form shows what is kept, and Save keeps what the form holds."""
    mine = nuspace.here(Config)

    def show(kept: nu.Nu) -> nu.Nu:
        c = nu.Dict(kept)
        return (
            _backend.set(c["backend"])
            >> _model.set(c["model"])
            >> _endpoint.set(c["endpoint"])
            >> _key_env.set(c["key_env"])
        )

    typed = (
        mine.backend.set(nu.Str(_backend).fallback(CC))
        >> mine.model.set(nu.Str(_model).strip())
        >> mine.endpoint.set(nu.Str(_endpoint).strip())
        >> mine.key_env.set(nu.Str(_key_env).strip())
    )
    slots = (mine.backend, mine.model, mine.endpoint, mine.key_env)
    changes = [slot.on_change() for slot in slots]
    # The rule first: children draw where first written.
    drawn = View.agent.rule.init() >> _save.set("Save")
    return drawn >> nu.ParallelAsync(
        nu.Reconcile(
            nuspace.atomic(nu.OnAny(*changes)),
            nu.let(nuspace.atomic(_values(mine)), show),
            after=nu.RECHECK_AFTER,
            every=nu.RECHECK_EVERY,
        ),
        nu.ReactEvery(_save.on_click(), nuspace.atomic(typed)),
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
