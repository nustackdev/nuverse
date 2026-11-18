"""The engine: the one program an agent plane runs. Owns the Agent process and the Session.

One plane run of the agent plane, start to end::

    claim     one commit: owner is this run, unless another live run owns it (then end at once)
    bind      nustd.acp under the Spec's preset, permissions="ask": the Agent spawns
    open      the Session: new, else resume, else load (its replay dropped), else new + a notice
    close     what a run that died left open: its turn, permissions, tool entries
    race      the arms below, until the idle arm goes to sleep
    sleep     one commit: owner cleared, unless a prompt is past the cursor

The arms, all on one loop, sharing one :class:`~nuverse.agents.fold.Fold`:

- fold: ``updates()`` into the fold, the only source of Session Updates and
  permission requests, in wire order. Also hears what lands between turns.
- turns: a level loop on the asks, one Prompt Turn at a time. It reads its
  prompt stream only for the stop reason, which goes through the same fold
  behind every item the turn's stream gave.
- answers: a level watch on the open permission entries; an ``answer``
  written by a view is sent with ``answer_permission``.
- cancel: a level watch on ``cancel_at``; newer than the running turn's
  start, the turn is cancelled.
- writer: the only arm that commits the fold's writes. Text growing in an
  open entry is written about every 150ms; anything else at once.
- idle: once nothing has run for the idle timeout, writes are drained and
  the engine goes to sleep; the run ends ``ok`` and the Agent exits.

Errors (an ``AcpError``, not logged in, npx missing) land as status
``error`` and a notice entry, and the run ends ``failed``; the next ask
wakes it again. A failed turn the Agent answered (a JSON-RPC error) only
ends that turn.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.acp
import nustd.kv
from nuspace.places import Here
from nustd.acp import AcpError

from .fold import Fold
from .shapes import ASLEEP, STARTING, asks_of, session_of, spec_of, trace_of
from .terms import CLIS, PRESETS


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .fold import Op


__all__ = [
    "IDLE_TIMEOUT",
    "LEFTOVER_PAGE",
    "LOST_CONTEXT",
    "describe",
    "engine",
    "writes",
]


log = logging.getLogger("nuverse.agents")

#: Seconds with no turn and no permission waiting before the engine sleeps.
IDLE_TIMEOUT = 600.0

#: How many of the newest entries a restart looks through for what a dead run left open.
LEFTOVER_PAGE = 200

#: The notice when a stored Session could not be restored.
LOST_CONTEXT = "The agent lost the earlier context, so this chat goes on in a new session."

# JSON-RPC: the Agent wants a login.
_AUTH_REQUIRED = -32000

# How each agent is logged in, for the notice.
_LOGIN = {"claude": "run `claude` in a terminal and log in", "codex": "run `codex login`"}


# --- host atoms over the fold ---------------------------------------------------------------------


def _act(fn: Callable[..., Any], name: str, base: type[nu.Nu] = nu.Command) -> type[nu.Nu]:
    """A host atom that changes the fold in slot 0."""
    return nu.host(fn, name=name, base=base, mutates=frozenset({0}))


def _new_fold() -> Fold:
    return Fold()


def _session_id(fold: Fold) -> str:
    return fold.session_id


def _cursor(fold: Fold) -> str:
    return fold.cursor


def _opened(fold: Fold, response: object, session_id: object) -> None:
    held = response if isinstance(response, dict) else {}
    fold.opened(str(session_id or held.get("session_id") or ""), held)


def _loaded(fold: Fold, item: object, session_id: str) -> None:
    # The replay is the trace already: only the response, last, counts.
    if isinstance(item, dict) and "session_update" not in item and "request_permission" not in item:
        fold.opened(session_id, item)


def _lost(fold: Fold) -> None:
    fold.notice(LOST_CONTEXT)


def _leftovers(fold: Fold, turn: str, entries: list[dict[str, Any]]) -> None:
    fold.leftovers(turn, list(entries or ()))


def _begin(fold: Fold, prompt_id: str, prompt: object) -> None:
    fold.begin(prompt_id, prompt if isinstance(prompt, dict) else {"text": str(prompt)})


async def _seen(fold: Fold, item: object) -> None:
    if isinstance(item, dict) and "stop_reason" in item:
        await fold.stopped(str(item["stop_reason"]))
    else:
        fold.seen(item)


def _exception(err: object) -> BaseException:
    exc = getattr(err, "exception", None)
    return exc if isinstance(exc, BaseException) else RuntimeError(str(err))


def _turn_failed(fold: Fold, err: object, agent: str) -> None:
    exc = _exception(err)
    fold.failed(describe(exc, agent))
    # The connection itself is gone: the run ends, failed.
    if isinstance(exc, AcpError) and exc.code is None:
        raise exc


def _answered(fold: Fold, key: str, option_id: str) -> None:
    fold.answered(key, option_id)


def _open_permissions(fold: Fold) -> list[list[object]]:
    return fold.open_permissions()


def _cancel_due(fold: Fold, cancel_at: object) -> bool:
    return fold.cancel_due(cancel_at)


def _cancel_sent(fold: Fold) -> None:
    fold.cancel_sent()


def _step(fold: Fold, item: object) -> None:
    if isinstance(item, dict):
        fold.step(item)


async def _idle_for(fold: Fold, seconds: float) -> None:
    await fold.idle_for(seconds)


async def _drained(fold: Fold) -> None:
    await fold.drained()


def _committed(fold: Fold) -> None:
    fold.committed()


def _recoverable(fold: Fold, err: object) -> None:
    """Restoring failed: fall back to a new Session, unless the Agent wants a login or is gone."""
    exc = _exception(err)
    if not isinstance(exc, AcpError) or exc.code in (None, _AUTH_REQUIRED):
        raise exc
    log.info("restoring the session failed, starting a new one: %s", exc)


def _reraise(fold: Fold, err: object) -> None:
    raise _exception(err)


def _restore_mode(init: object) -> str:
    """How the Agent restores a stored Session: ``resume``, ``load``, or ``""`` for neither."""
    caps = (init or {}).get("agent_capabilities") or {} if isinstance(init, dict) else {}
    if (caps.get("session_capabilities") or {}).get("resume") is not None:
        return "resume"
    if caps.get("load_session"):
        return "load"
    return ""


NewFold = nu.host(_new_fold, name="NewFold")
SessionId = nu.host(_session_id, name="SessionId")
Cursor = nu.host(_cursor, name="Cursor")
OpenPermissions = nu.host(_open_permissions, name="OpenPermissions")
CancelDue = nu.host(_cancel_due, name="CancelDue")
RestoreMode = nu.host(_restore_mode, name="RestoreMode")
Opened = _act(_opened, "Opened")
Loaded = _act(_loaded, "Loaded")
Lost = _act(_lost, "Lost")
Leftovers = _act(_leftovers, "Leftovers")
Begin = _act(_begin, "Begin")
Seen = _act(_seen, "Seen")
TurnFailed = _act(_turn_failed, "TurnFailed")
Answered = _act(_answered, "Answered")
CancelSent = _act(_cancel_sent, "CancelSent")
Step = _act(_step, "Step")
IdleFor = _act(_idle_for, "IdleFor")
Drained = _act(_drained, "Drained")
Committed = _act(_committed, "Committed")
Recoverable = _act(_recoverable, "Recoverable")
Reraise = _act(_reraise, "Reraise")


# --- writes ------------------------------------------------------------------------------------------


def _steps(plane: str, ops: Iterable[Op]) -> list[nu.Nu]:
    session, asks, trace = session_of(plane), asks_of(plane), trace_of(plane)
    entries, turns = trace.entries, trace.turns
    steps: list[nu.Nu] = []
    for op, key, value in ops:
        if op == "entry":
            steps.append(entries.set_item(key, value))
        elif op == "text":
            steps.append(entries[key].text.set(value))
        elif op == "tool":
            steps.append(entries[key].tool.set(value))
        elif op == "outcome":
            steps.append(entries[key].permission.set_item("outcome", value))
        elif op == "session":
            steps.append(getattr(session, key).set(value))
        elif op == "turn":
            steps.append(turns.set_item(key, value))
        elif op == "ended":
            steps.extend(getattr(turns[key], slot).set(v) for slot, v in value.items())
        elif op == "cursor":
            steps.append(asks.cursor.set(value))
        else:
            raise ValueError(f"no agent write {op!r}")
    return steps


def writes(plane: str, ops: Iterable[Op]) -> nu.Nu:
    """The fold's writes as one State commit on agent plane ``plane``; ``Noop`` for none.

    ``op`` is one of ``entry`` (a new entry, whole), ``text``, ``tool``,
    ``outcome`` (a permission's, leaving its ``answer`` alone), ``session``
    (a slot), ``turn`` (a new turn, whole), ``ended`` (a turn's end slots),
    ``cursor``.
    """
    steps = _steps(plane, ops)
    return nuspace.atomic(nu.Sequential(*steps)) if steps else nu.Noop()


async def _next_writes(fold: Fold, plane: str) -> nu.Nu:
    return writes(plane, await fold.next_writes())


def _last_writes(fold: Fold, plane: str, err: object, agent: str) -> nu.Nu:
    """The run failed: everything unwritten, the failure, and the owner let go. One commit."""
    fold.failed(describe(_exception(err), agent))
    session = session_of(plane)
    let_go = nu.IfDo(session.owner.fallback("") == Here.plane_run, session.owner.set(""))
    return nuspace.atomic(nu.Sequential(*_steps(plane, fold.unwritten()), let_go))


NextWrites = _act(_next_writes, "NextWrites", base=nu.ScalarAction)
LastWrites = _act(_last_writes, "LastWrites", base=nu.ScalarAction)


def describe(exc: BaseException, agent: str) -> str:
    """What a person reads when the engine fails: what happened, and what to do about it."""
    if isinstance(exc, AcpError):
        if exc.code == _AUTH_REQUIRED:
            how = _LOGIN.get(agent, f"log {agent} in")
            return f"The agent is not logged in: {how}, then ask again."
        if exc.method == "spawn":
            return (
                f"The agent could not start ({exc}). It runs through npx: install Node.js"
                f" and make sure npx and {CLIS.get(agent, agent)} are on PATH."
            )
    return str(exc) or type(exc).__name__


# --- the arms -------------------------------------------------------------------------------------


def _past(prompts: nustd.kv.LogDictRef, cursor: nu.StrArg) -> nu.List:
    """The first prompt id past ``cursor``, as a list of none or one."""
    c = nu.Str(cursor)
    return nu.List(
        nu.If(c == "", nu.list(prompts.keys(limit=1)), nu.list(prompts.keys(after=c, limit=1)))
    )


def _turns(fold: nu.Nu, plane: str, s: nustd.acp.SessionRef, agent: str) -> nu.Nu:
    """Level loop on the asks: take the next prompt past the cursor, run one Prompt Turn, repeat."""
    prompts = asks_of(plane).prompts
    has = nu.Bool(_past(prompts, Cursor(fold)))
    wait = nu.WaitUntil(
        nuspace.atomic(prompts.on_children_change()),
        nuspace.atomic(has),
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )

    def turn(ids: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(nu.List(ids)[0])

        def run(prompt: nu.ObjectRef) -> nu.Nu:
            stream = nu.ForEachDo(
                s.prompt(nu.Str(nu.Dict(prompt)["text"])), lambda i: Seen(fold, i)
            )
            failed = nu.TryCatch(
                stream, errors=AcpError, catch=lambda err: TurnFailed(fold, err, agent)
            )
            return Begin(fold, pid, prompt) >> failed

        return nu.let(nuspace.atomic(prompts[pid]), run)

    return nu.ForeverDo(wait >> nu.let(nuspace.atomic(_past(prompts, Cursor(fold))), turn))


def _answers(fold: nu.Nu, plane: str, s: nustd.acp.SessionRef) -> nu.Nu:
    """Level watch: each open permission a view answered is sent to the Agent."""
    entries = trace_of(plane).entries

    def one(held: nu.ObjectRef) -> nu.Nu:
        key, request = nu.Str(nu.List(held)[0]), nu.List(held)[1]
        answer = nuspace.atomic(nu.Str(entries[key].permission["answer"].fallback("")))

        def send(a: nu.ObjectRef) -> nu.Nu:
            option = nu.Str(a)
            return nu.IfDo(
                option != "", s.answer_permission(request, option) >> Answered(fold, key, option)
            )

        return nu.let(answer, send)

    return nu.Reconcile(
        nuspace.atomic(entries.on_descendants_change("*", "permission", "answer")),
        nu.ForEachDo(OpenPermissions(fold), one),
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )


def _cancels(fold: nu.Nu, plane: str, s: nustd.acp.SessionRef) -> nu.Nu:
    """Level watch on ``cancel_at``: newer than the running turn's start, cancel it."""
    at = asks_of(plane).cancel_at
    due = CancelDue(fold, nuspace.atomic(at.fallback(0)))
    return nu.Reconcile(
        nuspace.atomic(at.on_change()),
        nu.IfDo(due, s.cancel() >> CancelSent(fold)),
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )


def _writer(fold: nu.Nu, plane: str) -> nu.Nu:
    """The one arm that commits: the fold's writes, as they fall due."""
    return nu.ForeverDo(nu.Eval(NextWrites(fold, plane)) >> Committed(fold))


def _sleep(plane: str, slept: nu.ObjectRef) -> nu.Nu:
    """One commit: no prompt past the stored cursor, so the owner is cleared and status asleep."""
    session, asks = session_of(plane), asks_of(plane)
    nothing = nu.Not(_past(asks.prompts, asks.cursor.fallback("")))
    mine = session.owner.fallback("") == Here.plane_run
    asleep = nu.IfDo(mine, session.owner.set("") >> session.status.set(ASLEEP))
    return nuspace.atomic(slept.set(False) >> nu.IfDo(nothing, asleep >> slept.set(True)))


def _idle(fold: nu.Nu, plane: str, seconds: float) -> nu.Nu:
    """Wait out the idle timeout, drain the writes, go to sleep; again if a prompt came meanwhile."""

    def loop(slept: nu.ObjectRef) -> nu.Nu:
        step = IdleFor(fold, seconds) >> Drained(fold) >> _sleep(plane, slept)
        return nu.WhileDo(nu.Not(slept), step)

    return nu.let(False, loop)


# --- open, leftovers, the run --------------------------------------------------------------------


def _open(fold: nu.Nu, ref: nustd.acp.AgentRef, spec: dict[str, Any]) -> nu.Nu:
    """Open the Session: new, else resume, else load, else new plus a notice."""
    cwd = spec["cwd"]
    system_prompt = spec["system_prompt"] or None
    new = nu.let(
        ref.new_session(cwd=cwd, system_prompt=system_prompt), lambda r: Opened(fold, r, "")
    )
    stored = spec["session_id"]
    if not stored:
        return new
    session = ref[stored]
    resume = nu.let(
        session.resume(cwd=cwd, system_prompt=system_prompt), lambda r: Opened(fold, r, stored)
    )
    load = nu.ForEachDo(
        session.load(cwd=cwd, system_prompt=system_prompt), lambda i: Loaded(fold, i, stored)
    )

    def restore(mode: nu.ObjectRef) -> nu.Nu:
        how = nu.Str(mode)
        return nu.IfDo(how == "resume", resume, nu.IfDo(how == "load", load, new >> Lost(fold)))

    return nu.TryCatch(
        nu.let(RestoreMode(ref.initialization()), restore),
        errors=AcpError,
        catch=lambda err: Recoverable(fold, err) >> new >> Lost(fold),
    )


def _close_leftovers(fold: nu.Nu, plane: str) -> nu.Nu:
    """Close what a run that died left open: the newest turn, when it never ended."""
    trace = trace_of(plane)
    turns, entries = trace.turns, trace.entries

    def entry(key: nu.ObjectRef) -> nu.Dict:
        return nu.Dict.of(key=key, entry=entries[nu.Str(key)].extract())

    page = nu.List(entries.reversed_keys(limit=LEFTOVER_PAGE)).iter().map(entry).to_list()

    def check(last: nu.ObjectRef) -> nu.Nu:
        turn = nu.Str(last)
        open_ = (turn != "").and_(nu.Not(turns[turn].ended_at.exists()))
        close = nu.let(nuspace.atomic(page), lambda got: Leftovers(fold, turn, got))
        return nu.IfDo(nuspace.atomic(open_), close)

    return nu.let(nuspace.atomic(turns.last(default="")), check)


def _session(fold: nu.Nu, plane: str, spec: dict[str, Any], idle: float) -> nu.Nu:
    ref = nustd.acp.AgentRef(spec["agent"])
    s = ref[SessionId(fold)]
    arms = nu.Race(
        nu.ForEachDo(s.updates(), lambda item: Step(fold, item)),
        _turns(fold, plane, s, spec["agent"]),
        _answers(fold, plane, s),
        _cancels(fold, plane, s),
        _writer(fold, plane),
        _idle(fold, plane, idle),
    )
    return _open(fold, ref, spec) >> _close_leftovers(fold, plane) >> arms


def _bound(fold: Fold, plane: str, spec: dict[str, Any], idle: float) -> nu.Nu:
    """The run, with the Agent bound by the Spec's preset."""
    agent = str(spec.get("agent") or "")
    if agent not in PRESETS:
        raise LookupError(f"no agent preset {agent!r}, one of {', '.join(PRESETS)}")
    held = {**spec, "agent": agent, "cwd": str(spec.get("cwd") or "")}
    held["system_prompt"] = str(spec.get("system_prompt") or "")
    held["session_id"] = str(spec.get("session_id") or "")
    bind = PRESETS[agent](nustd.acp.AgentRef(agent), held["cwd"])
    # The fold is the same object the outer term holds; pass it on as a value.
    inner = nu.let(nu.Literal(fold), lambda f: _session(f, plane, held, idle))
    return nu.With(bind, body=inner)


Bound = nu.host(_bound, name="Bound")


def _claim(plane: str, won: nu.ObjectRef) -> nu.Nu:
    """One commit: this run owns the engine, unless another live run does."""
    session = session_of(plane)
    owner = nu.Str(session.owner.fallback(""))
    live = nuspace.Space.exec.indexes.live.plane_runs.contains(owner)
    taken = (owner != "").and_(owner != Here.plane_run).and_(live)
    claim = (
        session.owner.set(Here.plane_run)
        >> session.status.set(STARTING)
        >> session.error.set("")
        >> won.set(True)
    )
    return nuspace.atomic(won.set(False) >> nu.IfDo(nu.Not(taken), claim))


def engine(plane: str, *, idle: float = IDLE_TIMEOUT) -> nu.Nu:
    """The engine cell's program for agent plane ``plane``.

    Args:
        plane: The agent plane's id.
        idle: Seconds with no turn and no permission waiting before it
            sleeps and the run ends.
    """
    spec, session = spec_of(plane), session_of(plane)
    read = nuspace.atomic(
        nu.Dict.of(
            agent=spec.agent.fallback(""),
            cwd=spec.cwd.fallback(""),
            system_prompt=spec.system_prompt.fallback(""),
            session_id=session.session_id.fallback(""),
        )
    )

    def held(fold: nu.ObjectRef) -> nu.Nu:
        agent = nuspace.atomic(spec.agent.fallback(""))

        def failed(err: nu.ObjectRef) -> nu.Nu:
            return nu.Eval(LastWrites(fold, plane, err, agent)) >> Reraise(fold, err)

        # On the loop: the run holds async-only atoms (the Agent, its streams, watches).
        bound = nu.ParallelAsync(nu.Eval(Bound(fold, plane, read, idle)))
        run = nu.TryCatch(bound, catch=failed)

        def claimed(won: nu.ObjectRef) -> nu.Nu:
            return _claim(plane, won) >> nu.IfDo(won, run)

        return nu.let(False, claimed)

    return nu.let(NewFold(), held)
