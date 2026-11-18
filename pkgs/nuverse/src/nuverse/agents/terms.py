"""What callers use: the terms over an agent plane's state.

The chat cell, later cells and agents all reach an agent plane through
these and nothing else:

- :func:`add`: make an agent plane and write its Spec. A wrapper.
- :func:`ask`: append a prompt, then wake the engine if it has no live
  owner. A wrapper: State, then Space.
- :func:`cancel`: stamp ``cancel_at``; the engine cancels the running turn.
- :func:`answer`: answer a permission entry with one of its options.
- :func:`installed`: which agents this machine can run.
- :func:`spec`, :func:`session`, :func:`asks`, :func:`trace`: the typed
  Shapes, for reading.

Every term brackets itself, so call them bare. :data:`PRESETS` maps an
agent name to the bind the engine runs it under.
"""

from __future__ import annotations

import importlib.util
import shutil
from typing import TYPE_CHECKING

import nu
import nuspace
import nustd.acp
import nustd.time
from nuspace.errors import Missing, Refused
from nuspace.shapes import ROOT, Space
from nuspace.specs import add_plane
from nuspace.utils import MintId
from nuspace.utils.checks import refuse
from nuverse.planes.agent import PLANE

from .shapes import ASLEEP, asks_of, session_of, spec_of, trace_of


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "CLIS",
    "PRESETS",
    "add",
    "answer",
    "ask",
    "asks",
    "cancel",
    "installed",
    "now_ms",
    "session",
    "spec",
    "trace",
]


def _claude(agent: nustd.acp.AgentRef, cwd: str) -> nu.Nu:
    return nustd.acp.claude(agent, cwd=cwd, permissions="ask")


def _codex(agent: nustd.acp.AgentRef, cwd: str) -> nu.Nu:
    return nustd.acp.codex(agent, cwd=cwd, permissions="ask")


#: The bind each agent runs under, by the name a Spec holds: ``bind(agent_ref, cwd)``.
#: Always ``permissions="ask"``: the trace shows each request and a person answers it.
PRESETS: dict[str, Callable[[nustd.acp.AgentRef, str], nu.Nu]] = {
    "claude": _claude,
    "codex": _codex,
}

#: The CLI each preset's adapter drives, which must be on PATH beside ``npx``.
CLIS = {"claude": "claude", "codex": "codex"}


def now_ms() -> nu.Int:
    """Now, in milliseconds since the epoch, as the agent shapes keep time."""
    return nu.int(nustd.time.time() * 1000)


# --- readers ------------------------------------------------------------------------------------


spec = spec_of
session = session_of
asks = asks_of
trace = trace_of


# --- add -----------------------------------------------------------------------------------------


def _seed(plane: nu.Str, agent: nu.StrArg, cwd: nu.StrArg, system_prompt: nu.StrArg) -> nu.Nu:
    """Spec as given, and every other slot made, so a first read finds it. One State commit."""
    s, n, a, t = spec_of(plane), session_of(plane), asks_of(plane), trace_of(plane)
    return nuspace.atomic(
        s.agent.set(agent)
        >> s.cwd.set(cwd)
        >> s.system_prompt.set(system_prompt)
        >> n.session_id.set("")
        >> n.title.set("")
        >> n.usage.set(nu.Dict.create())
        >> n.plan.set([])
        >> n.commands.set([])
        >> n.config_options.set([])
        >> n.status.set(ASLEEP)
        >> n.owner.set("")
        >> n.error.set("")
        >> a.prompts.set(nu.Dict.create())
        >> a.cursor.set("")
        >> a.cancel_at.set(0)
        >> t.turns.set(nu.Dict.create())
        >> t.entries.set(nu.Dict.create())
    )


def add(
    agent: nu.StrArg,
    cwd: nu.StrArg,
    *,
    system_prompt: nu.StrArg = "",
    parent: nu.StrArg = ROOT,
    name: nu.StrArg | None = None,
    into: nu.Ref | None = None,
) -> nu.Nu:
    """Make an agent plane under ``parent`` and write its Spec. A wrapper: call it bare.

    The plane is made from :data:`~nuverse.planes.agent.PLANE`, headless, and
    asleep: nothing runs until the first :func:`ask`.

    Args:
        agent: The preset to bind, a name in :data:`PRESETS`.
        cwd: The Session's working directory, absolute. Fixed for its life.
        system_prompt: Appended to the agent's own, ``""`` for none.
        parent: The plane it hangs under.
        name: What to call it, ``"Agent"`` when absent.
        into: A ref set to the new plane's id, once its state is written.

    Raises:
        ValueError: A literal ``agent`` with no preset, or a literal ``cwd``
            that is not absolute (at build).
    """
    if isinstance(agent, str) and agent not in PRESETS:
        raise ValueError(f"no agent preset {agent!r}, one of {', '.join(PRESETS)}")
    if isinstance(cwd, str) and not cwd.startswith("/"):
        raise ValueError(f"an agent's cwd is absolute, got {cwd!r}")

    def made(pid: nu.ObjectRef) -> nu.Nu:
        plane = nu.Str(pid)
        steps = add_plane(PLANE, parent=parent, name=name, into=pid) >> _seed(
            plane, agent, cwd, system_prompt
        )
        return steps if into is None else steps >> nuspace.atomic(into.set(plane))

    return nu.let("", made)


# --- ask, cancel, answer ------------------------------------------------------------------------


def _wake(plane: nu.StrArg) -> nu.Nu:
    """A plane run, unless the engine has a live owner. One Space commit, the owner read from State."""
    owner = nu.Str(session_of(plane).owner.fallback(""))
    live = Space.exec.indexes.live.plane_runs.contains(owner)
    asleep = (owner == "").or_(nu.Not(live))
    return nuspace.atomic(nu.IfDo(asleep, nuspace.plane_run.add(plane, by="nuverse.agents")))


def ask(plane: nu.StrArg, text: nu.StrArg, *, by: nu.StrArg = "") -> nu.Nu:
    """Append a prompt to agent plane ``plane``, then start its engine if it has no live owner.

    A wrapper: one State commit, then one Space commit. The engine going to
    sleep is one commit that clears the owner only when no prompt is past
    the cursor, so either it sees this prompt and keeps working, or this
    sees the owner cleared and adds a run.

    Args:
        plane: The agent plane.
        text: The prompt, markdown.
        by: Who asks, eg a cell id or ``"user"``.

    Raises:
        Refused: ``text`` is blank.
        Missing: ``plane`` is no plane (from the run it adds).
    """
    prompts = asks_of(plane).prompts

    def append(qid: nu.ObjectRef) -> nu.Nu:
        prompt = nu.Dict.of(text=text, at=now_ms(), by=by)
        return nuspace.atomic(
            refuse(nu.Str(text).strip() == "", Refused, "an ask needs text")
            >> prompts.set_item(nu.Str(qid), prompt)
        )

    return nu.let(MintId("q"), append) >> _wake(plane)


def cancel(plane: nu.StrArg) -> nu.Nu:
    """Stamp ``cancel_at`` on agent plane ``plane``: the engine cancels a turn started before it. One commit."""
    return nuspace.atomic(asks_of(plane).cancel_at.set(now_ms()))


def _offers(options: object, option_id: object) -> bool:
    return any(isinstance(o, dict) and o.get("option_id") == option_id for o in options or ())


#: Whether a permission request's options hold one with this ``option_id``.
Offers = nu.host(_offers, name="Offers")


def answer(plane: nu.StrArg, entry: nu.StrArg, option_id: nu.StrArg) -> nu.Nu:
    """Answer permission entry ``entry`` with ``option_id``. One commit; the engine sends it.

    Writes the entry's ``answer`` and nothing else, so the engine's own
    writes to the entry never clobber it.

    Raises:
        Missing: No entry ``entry``.
        Refused: The request did not offer ``option_id``.
    """
    entries = trace_of(plane).entries
    permission = entries[entry].permission
    offered = Offers(permission["options"].fallback([]), option_id)
    return nuspace.atomic(
        refuse(nu.Not(entries.contains(entry)), Missing, "no entry ", entry)
        >> refuse(nu.Not(offered), Refused, "entry ", entry, " offers no option ", option_id)
        >> permission.set_item("answer", option_id)
    )


# --- installed ------------------------------------------------------------------------------------


def _installed() -> list[str]:
    if importlib.util.find_spec("acp") is None or shutil.which("npx") is None:
        return []
    return [name for name, cli in CLIS.items() if shutil.which(cli) is not None]


#: Which agents this machine can run, as a list of preset names.
Installed = nu.host(_installed, name="Installed")


def installed() -> nu.Nu:
    """Which agents this machine can run, in :data:`CLIS` order: ``npx`` and the agent's CLI on PATH.

    Empty without the ACP SDK (the ``nuverse[agents]`` extra). A read.
    """
    return Installed()
