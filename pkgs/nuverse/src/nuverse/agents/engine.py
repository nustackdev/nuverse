"""The engine: the one program an agent plane runs. Owns the Agent process and the Session.

One plane run of the agent plane, start to end::

    claim     one commit: owner is this run, unless another live run owns it (then end at once)
    bind      nustd.acp under the Spec's preset, permissions="ask": the Agent spawns
    open      the Session: new, else resume, else load (its replay dropped), else new + a notice
    close     what a run that died left open: its turn, permissions, tool entries
    race      the arms below, until the turns arm goes to sleep
    sleep     one commit: owner cleared, unless a prompt is past the cursor

The arms, all on one loop, share one :class:`_Run` frame:

- updates: ``updates()``, everything the Agent says about the Session.
  Sets the Session slots (plan, usage, title, commands, config options)
  always; folds anything else into entries only when it came outside a
  turn, since a turn folds its own.
- turns: a level loop on the asks, one Prompt Turn at a time. A turn's
  prompt stream gives every Session Update and permission request of the
  turn in wire order, then the stop reason; each is folded into the trace
  as it comes, in a :class:`_Open` frame of the turn's own. With no prompt
  past the cursor for the idle timeout, it goes to sleep and the race ends.
- answers: a level watch on the open permission entries; an ``answer``
  written by a view is sent with ``answer_permission``.
- cancel: a level watch on ``cancel_at``; newer than the running turn's
  start, the turn is cancelled.

The fold, one item at a time: a message or thought chunk grows the open
text entry of its kind and message id, or starts one after any other
entry; a growing text is written at most every :data:`FLUSH_SECONDS`, and
once more when it closes. A ``tool_call`` is a tool entry keyed
``tool:<tool_call_id>``, a ``tool_call_update`` patches only the fields it
sends (an unknown id is a create). A permission request is a permission
entry, status ``waiting``. A turn's end closes its text, cancels its tools
still pending or in progress and its unanswered permissions.

Errors (an ``AcpError``, not logged in, npx missing) land as status
``error`` and a notice entry, and the run ends ``failed``; the next ask
wakes it again. A failed turn the Agent answered (a JSON-RPC error) only
ends that turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.acp
import nustd.kv
from nuspace.places import Here
from nustd.acp import AcpError

from .shapes import (
    ASLEEP,
    ERROR,
    IDLE,
    PROMPTING,
    STARTING,
    WAITING,
    asks_of,
    session_of,
    spec_of,
    trace_of,
)
from .terms import CLIS, PRESETS, now_ms


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = [
    "DROPPED",
    "FLUSH_SECONDS",
    "IDLE_TIMEOUT",
    "LEFTOVER_PAGE",
    "LOST_CONTEXT",
    "describe",
    "engine",
]


#: Seconds with no prompt past the cursor, after the last turn ended, before the engine sleeps.
IDLE_TIMEOUT = 600.0

#: The least time between two writes of a text entry still growing, in seconds.
FLUSH_SECONDS = 0.15

#: How many of the newest entries a restart looks through for what a dead run left open.
LEFTOVER_PAGE = 200

#: The notice when a stored Session could not be restored.
LOST_CONTEXT = "The agent lost the earlier context, so this chat goes on in a new session."

#: The notice when the engine failed with asks still waiting: they are dropped, not replayed.
DROPPED = "The asks sent before the agent stopped were not answered. Ask again to go on."

#: The Agent, as every arm reaches it: whichever preset the Spec names binds under this name.
AGENT = nustd.acp.AgentRef("agent")

# JSON-RPC: the Agent wants a login.
_AUTH_REQUIRED = -32000

# JSON-RPC errors on restoring a Session that mean "start a new one": not found, no
# method (a capability not advertised), invalid params.
_RESTORE_FALLBACK = (-32002, -32601, -32602)

# How each agent is logged in, for the notice.
_LOGIN = {"claude": "run `claude` in a terminal and log in", "codex": "run `codex login`"}

# Tool statuses a turn's end turns into ``cancelled``.
_OPEN_TOOL = ("pending", "in_progress")

# The tool fields a tool entry keeps, as ACP names them.
_TOOL_FIELDS = ("title", "kind", "status", "content", "locations")

# The Session slots an update sets, by the ACP update that carries each.
_SLOTS = ("plan", "usage", "title", "commands", "config_options")

_RECHECK = {"after": nu.RECHECK_AFTER, "every": nu.RECHECK_EVERY}


# --- memory ---------------------------------------------------------------------------------------


class _Run(nu.Shape):
    """One run's memory, around the race, so every arm shares it."""

    agent = nu.StrRef.slot()  # the Spec's preset
    cwd = nu.StrRef.slot()
    system_prompt = nu.StrRef.slot()
    session_id = nu.StrRef.slot()  # the stored one, then the one opened
    nonce = nu.StrRef.slot()  # this plane run: keys minted now never meet an earlier run's
    seq = nu.IntRef.slot()  # entries minted so far
    last = nu.StrRef.slot()  # the newest entry's key: text grows only in the newest entry
    turn = nu.StrRef.slot()  # the running turn's id, "" between turns
    started = nu.IntRef.slot()  # when it started, ms
    cancel_sent = nu.BoolRef.slot()
    perms = nu.DictRef.slot(object)  # open permission entries: key -> the fabric's request id
    taken = nu.IntRef.slot()  # items the turns arm folded from prompt streams
    skipped = nu.IntRef.slot()  # items the updates arm left to a turn
    slept = nu.BoolRef.slot()


class _Open(nu.Shape):
    """One stream's memory, around each turn and around the updates arm: what is open in it."""

    turn = nu.StrRef.slot()  # the turn its entries belong to, "" outside one
    key = nu.StrRef.slot()  # the open text entry, "" for none
    kind = nu.StrRef.slot()
    message_id = nu.StrRef.slot()
    text = nu.StrRef.slot()  # all of it so far
    flushed = nu.ObjectRef.slot()  # when it was last written, for the throttle
    tools = nu.DictRef.slot(bool)  # tool entries still pending or in progress


# --- pure helpers ----------------------------------------------------------------------------------


def _kind(item: object) -> str:
    """What an item is: its ``session_update``, ``permission``, ``stop``, or ``response``."""
    if not isinstance(item, dict):
        return "response"
    if "request_permission" in item:
        return "permission"
    if "session_update" in item:
        return str(item["session_update"])
    return "stop" if "stop_reason" in item else "response"


def _text(item: object) -> str:
    """A chunk's Content Block as entry text: its text, or a one-line placeholder for anything else."""
    block = item.get("content") if isinstance(item, dict) else None
    if isinstance(block, dict) and block.get("type") == "text":
        return str(block.get("text", ""))
    kind = block.get("type", "content") if isinstance(block, dict) else "content"
    return f"\n[{kind}]\n"


def _message_id(item: object) -> str:
    return str((item.get("message_id") if isinstance(item, dict) else None) or "")


def _sent(item: object) -> dict[str, Any]:
    """The tool fields an item sends, those it leaves out or sends null left out."""
    held = item if isinstance(item, dict) else {}
    return {f: held[f] for f in _TOOL_FIELDS if held.get(f) is not None}


def _tool(item: object) -> dict[str, Any]:
    """A new tool entry's ``tool``: the defaults, under what the item sends."""
    tid = str(item.get("tool_call_id", "")) if isinstance(item, dict) else ""
    return {"tool_call_id": tid, "title": "", "kind": "other", "status": "pending", **_sent(item)}


def _tool_status(item: object) -> str:
    """The status an item sends, ``""`` for none."""
    return str(_sent(item).get("status", ""))


def _permission(item: object) -> dict[str, Any]:
    """A permission entry's ``permission``, from the fabric's request."""
    held = item if isinstance(item, dict) else {}
    call = held.get("tool_call") or {}
    return {
        "request": held.get("request_permission"),
        "tool_call_id": call.get("tool_call_id", ""),
        "options": list(held.get("options") or ()),
        "answer": "",
        "outcome": "",
    }


def _slot(item: object) -> list[object]:
    """The Session slot an update sets and its value, ``["", None]`` when it sets none."""
    held = item if isinstance(item, dict) else {}
    kind = held.get("session_update")
    if kind == "plan":
        return ["plan", list(held.get("entries") or ())]
    if kind == "usage_update":
        return [
            "usage",
            {"used": held.get("used"), "size": held.get("size"), "cost": held.get("cost")},
        ]
    if kind == "session_info_update" and "title" in held:
        return ["title", held["title"] or ""]
    if kind == "available_commands_update":
        return ["commands", list(held.get("available_commands") or ())]
    if kind == "config_option_update":
        return ["config_options", list(held.get("config_options") or ())]
    return ["", None]


def _restore_mode(init: object) -> str:
    """How the Agent restores a stored Session: ``resume``, ``load``, or ``""`` for neither."""
    caps = (init or {}).get("agent_capabilities") or {} if isinstance(init, dict) else {}
    if (caps.get("session_capabilities") or {}).get("resume") is not None:
        return "resume"
    if caps.get("load_session"):
        return "load"
    return ""


def _exception(err: object) -> BaseException:
    """The exception a catch caught."""
    exc = getattr(err, "exception", None)
    return exc if isinstance(exc, BaseException) else RuntimeError(str(err))


def _recoverable(err: object) -> bool:
    """Restoring failed in a way a new Session answers: not found, or not offered."""
    exc = _exception(err)
    return isinstance(exc, AcpError) and exc.code in _RESTORE_FALLBACK


def _lost(err: object) -> bool:
    """The connection to the Agent is gone, not just the request."""
    exc = _exception(err)
    return isinstance(exc, AcpError) and exc.code is None


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


def _describe(err: object, agent: object) -> str:
    return describe(_exception(err), str(agent or ""))


Kind = nu.host(_kind, name="Kind")
TextOf = nu.host(_text, name="TextOf")
MessageId = nu.host(_message_id, name="MessageId")
ToolSent = nu.host(_sent, name="ToolSent")
ToolOf = nu.host(_tool, name="ToolOf")
ToolStatus = nu.host(_tool_status, name="ToolStatus")
PermissionOf = nu.host(_permission, name="PermissionOf")
SlotOf = nu.host(_slot, name="SlotOf")
RestoreMode = nu.host(_restore_mode, name="RestoreMode")
Recoverable = nu.host(_recoverable, name="Recoverable")
Lost = nu.host(_lost, name="Lost")
Describe = nu.host(_describe, name="Describe")


def _rethrow(err: nu.Nu) -> nu.Nu:
    """Raise the error a catch caught again, as it was.

    ``Raise`` raises ``exc_cls(message)``; with the caught error as the
    message and :func:`_exception` as ``exc_cls``, that is the original.
    """
    return nu.Raise(err, exc_cls=_exception)  # type: ignore[arg-type]


# --- entries --------------------------------------------------------------------------------------


def _minted(kind: str, fn: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """The body ``fn`` builds over a fresh entry key, ``<kind>:<run>-<n>``."""
    key = nu.Str(f"{kind}:") + _Run.nonce + "-" + nu.str(_Run.seq)
    return _Run.seq.inc() >> nu.let(key, lambda k: fn(nu.Str(k)))


def _put(plane: str, key: nu.StrArg, kind: str, turn: nu.StrArg, **slots: object) -> nu.Nu:
    """Entry ``key``, whole. Inside the caller's commit."""
    entry = nu.Dict.of(kind=kind, turn=turn, at=now_ms(), **slots)
    return trace_of(plane).entries.set_item(key, entry)


def _flush(plane: str) -> nu.Nu:
    """The open text entry's last write, inside the caller's commit."""
    return nu.IfDo(_Open.key != "", trace_of(plane).entries[_Open.key].text.set(_Open.text))


def _starts(plane: str, key: nu.Str, kind: str, *also: nu.Nu, **slots: object) -> nu.Nu:
    """A new entry in this stream: the open text closed, the entry written, and ``also``. One commit."""
    commit = nuspace.atomic(
        nu.Sequential(_flush(plane), _put(plane, key, kind, _Open.turn, **slots), *also)
    )
    return commit >> _Open.key.set("") >> _Run.last.set(key)


def _notice(plane: str, key: nu.Str, text: nu.StrArg) -> nu.Nu:
    """A notice entry, between turns: something a person should know that the Agent did not say."""
    return _put(plane, key, "notice", "", text=text)


def _told(plane: str, text: nu.StrArg) -> nu.Nu:
    """A notice entry on its own. One commit."""
    return _minted(
        "notice",
        lambda key: nuspace.atomic(_notice(plane, key, text)) >> _Run.last.set(key),
    )


# --- the fold -------------------------------------------------------------------------------------


def _chunk(plane: str, u: nu.Nu, kind: str, *, throttled: bool) -> nu.Nu:
    """A message or thought chunk: grows the open text entry, or starts one."""
    entries = trace_of(plane).entries
    mid = MessageId(u)
    same = (
        (_Open.key != "")
        .and_(_Open.key == _Run.last)
        .and_(_Open.kind == kind)
        .and_(_Open.message_id == mid)
    )
    write = nuspace.atomic(entries[_Open.key].text.set(_Open.text))
    if throttled:
        write = nu.Throttle(FLUSH_SECONDS, write, last=_Open.flushed)

    def held(got: nu.ObjectRef) -> nu.Nu:
        piece = nu.Str(got)
        grow = _Open.text.set(_Open.text + piece) >> write

        def start(key: nu.Str) -> nu.Nu:
            return (
                _starts(plane, key, kind, text=piece)
                >> _Open.key.set(key)
                >> _Open.kind.set(kind)
                >> _Open.message_id.set(mid)
                >> _Open.text.set(piece)
            )

        return nu.IfDo(same, grow, _minted(kind, start))

    return nu.let(TextOf(u), held)


def _tool_entry(plane: str, u: nu.Nu, *, create: bool) -> nu.Nu:
    """A tool call: a new tool entry, or an update patching only the fields it sends."""
    entries = trace_of(plane).entries

    def held(got: nu.ObjectRef) -> nu.Nu:
        key = nu.Str(got)
        sent = nu.Str(ToolStatus(u))

        def track(status: nu.Str) -> nu.Nu:
            open_ = (status == _OPEN_TOOL[0]).or_(status == _OPEN_TOOL[1])
            closed = nu.IfDo(status != "", _Open.tools.del_item(key, missing_ok=True))
            return nu.IfDo(open_, _Open.tools.set_item(key, True), closed)

        made = _starts(plane, key, "tool", tool=ToolOf(u)) >> track(
            nu.Str(nu.Dict(ToolOf(u))["status"])
        )
        if create:
            return made
        patch = nuspace.atomic(entries[key].tool.update(ToolSent(u))) >> track(sent)
        return nu.IfDo(nuspace.atomic(entries.contains(key)), patch, made)

    tid = nu.Str(nu.Dict(u).get_item("tool_call_id", ""))
    return nu.let(nu.Str("tool:") + tid, held)


def _permission_entry(plane: str, u: nu.Nu) -> nu.Nu:
    """A permission request: a permission entry, held open until it is answered or the turn ends."""
    request = nu.Dict(u)["request_permission"]

    def held(got: nu.ObjectRef) -> nu.Nu:
        key = nu.Str(got)
        waiting = session_of(plane).status.set(WAITING)
        made = _starts(plane, key, "permission", waiting, permission=PermissionOf(u))
        return made >> _Run.perms.set_item(key, request)

    return nu.let(nu.Str("perm:") + _Run.nonce + "-" + nu.str(request), held)


def _fold(plane: str, u: nu.Nu, *, throttled: bool, stop: nu.Nu | None = None) -> nu.Nu:
    """Fold item ``u`` into the trace, in the stream's :class:`_Open` frame.

    ``user_message_chunk`` is skipped: the user entry is written from the
    ask when the turn starts, so an agent echoing the prompt shows it once.
    The Session slots are the updates arm's; anything else is dropped.
    """
    cases = {
        "agent_message_chunk": _chunk(plane, u, "agent", throttled=throttled),
        "agent_thought_chunk": _chunk(plane, u, "thought", throttled=throttled),
        "tool_call": _tool_entry(plane, u, create=True),
        "tool_call_update": _tool_entry(plane, u, create=False),
        "permission": _permission_entry(plane, u),
    }
    if stop is not None:
        cases["stop"] = stop
    return nu.SwitchDo(Kind(u), cases)


def _open_frame(body: nu.Nu, turn: nu.StrArg) -> nu.Nu:
    """``body`` in a fresh :class:`_Open` frame, its entries in turn ``turn``."""
    return nu.Frame(
        _Open,
        body,
        turn=turn,
        key="",
        kind="",
        message_id="",
        text="",
        flushed=None,
        tools=nu.Dict.create(),
    )


# --- a turn ---------------------------------------------------------------------------------------


def _cancel_permissions(plane: str) -> nu.Nu:
    """Every open permission entry ``cancelled``, inside the caller's commit."""
    entries = trace_of(plane).entries
    return nu.ForEachDo(
        nu.list(_Run.perms.keys()),
        lambda k: entries[nu.Str(k)].permission.set_item("outcome", "cancelled"),
    )


def _ended(plane: str, slot: str, value: nu.StrArg, *also: nu.Nu) -> nu.Nu:
    """The running turn ends with ``slot`` (``stop_reason`` or ``error``) set to ``value``.

    Its text is written, its open tools and permissions are ``cancelled``,
    and ``also`` lands in the same commit. Then nothing is open.
    """
    entries, turns = trace_of(plane).entries, trace_of(plane).turns
    turn = turns[_Run.turn]
    tools = nu.ForEachDo(
        nu.list(_Open.tools.keys()),
        lambda k: entries[nu.Str(k)].tool.set_item("status", "cancelled"),
    )
    commit = nuspace.atomic(
        nu.Sequential(
            _flush(plane),
            tools,
            _cancel_permissions(plane),
            turn.ended_at.set(now_ms()),
            getattr(turn, slot).set(value),
            *also,
        )
    )
    return (
        commit
        >> _Open.key.set("")
        >> _Open.tools.clear()
        >> _Run.perms.clear()
        >> _Run.turn.set("")
    )


def _turn_failed(plane: str, err: nu.Nu) -> nu.Nu:
    """The turn failed: it ends with the error. The Agent answered: a notice, status error.

    The connection gone, the error goes on: the run fails, and says so.
    """
    session = session_of(plane)

    def held(got: nu.ObjectRef) -> nu.Nu:
        message = nu.Str(got)

        def told(key: nu.Str) -> nu.Nu:
            notice = _notice(plane, key, message)
            failed = _ended(
                plane,
                "error",
                message,
                notice,
                session.error.set(message),
                session.status.set(ERROR),
            )
            return failed >> _Run.last.set(key)

        gone = _ended(plane, "error", message) >> _rethrow(err)
        return nu.IfDo(Lost(err), gone, _minted("notice", told))

    return nu.let(Describe(err, _Run.agent), held)


def _begin(plane: str, pid: nu.Str, text: nu.Str) -> nu.Nu:
    """A Prompt Turn starts on prompt ``pid``: the cursor, the turn, its user entry. One commit."""
    session, asks, trace = session_of(plane), asks_of(plane), trace_of(plane)
    user = nu.Str("user:") + pid
    turn = nu.Dict.of(prompt=pid, started_at=_Run.started)
    entry = nu.Dict.of(kind="user", turn=_Run.turn, at=_Run.started, text=text)
    commit = nuspace.atomic(
        asks.cursor.set(pid)
        >> trace.turns.set_item(_Run.turn, turn)
        >> trace.entries.set_item(user, entry)
        >> session.status.set(PROMPTING)
    )
    memory = (
        _Run.turn.set(nu.Str("turn:") + pid)
        >> _Run.started.set(now_ms())
        >> _Run.cancel_sent.set(False)
    )
    return memory >> commit >> _Run.last.set(user)


def _stream(plane: str, items: nu.Nu) -> nu.Nu:
    """Fold a turn's prompt stream ``items`` into the trace, in an :class:`_Open` frame of its own.

    Every item but the last is a Session Update or a permission request, in
    wire order; the last, the stop reason, ends the turn.
    """

    def one(u: nu.ObjectRef) -> nu.Nu:
        stop = nu.Str(nu.Dict(u).get_item("stop_reason", ""))
        ended = _ended(plane, "stop_reason", stop, session_of(plane).status.set(IDLE))
        counted = nu.IfDo(nu.Str(Kind(u)) != "stop", _Run.taken.inc())
        return counted >> _fold(plane, u, throttled=True, stop=ended)

    folded = nu.TryCatch(
        nu.ForEachDo(items, one), errors=AcpError, catch=lambda err: _turn_failed(plane, err)
    )
    return _open_frame(folded, _Run.turn)


# --- the arms -------------------------------------------------------------------------------------


def _past(prompts: nustd.kv.LogDictRef, cursor: nu.StrArg) -> nu.List:
    """The first prompt id past ``cursor``, as a list of none or one."""
    c = nu.Str(cursor)
    return nu.List(
        nu.If(c == "", nu.list(prompts.keys(limit=1)), nu.list(prompts.keys(after=c, limit=1)))
    )


def _updates(plane: str, s: nustd.acp.SessionRef) -> nu.Nu:
    """Everything the Agent says about the Session: the Session slots, and what lands between turns.

    Whether an item came in a turn is told by the turns arm's memory: a
    turn runs, or the turns arm folded more items than this arm has passed
    over yet (it is behind). Started first in the race, so it listens
    before any turn begins.
    """
    session = session_of(plane)

    def slot(got: nu.ObjectRef) -> nu.Nu:
        pair = nu.List(got)
        sets = {name: nuspace.atomic(getattr(session, name).set(pair[1])) for name in _SLOTS}
        return nu.SwitchDo(pair[0], sets)

    def one(u: nu.ObjectRef) -> nu.Nu:
        in_turn = (_Run.turn != "").or_(_Run.skipped < _Run.taken)
        between = _fold(plane, u, throttled=False)
        return nu.let(SlotOf(u), slot) >> nu.IfDo(in_turn, _Run.skipped.inc(), between)

    heard = nu.ForEachDo(s.updates(), one)
    # The connection gone in a turn, the turn's own stream says so: it ends the turn first.
    gone = nu.TryCatch(
        heard,
        errors=AcpError,
        catch=lambda err: nu.IfDo(_Run.turn != "", nu.Park(), _rethrow(err)),
    )
    return _open_frame(gone, "")


def _sleep(plane: str) -> nu.Nu:
    """One commit: no prompt past the stored cursor, so the owner is cleared and status asleep."""
    session, asks = session_of(plane), asks_of(plane)
    nothing = nu.Not(_past(asks.prompts, asks.cursor.fallback("")))
    mine = session.owner.fallback("") == Here.plane_run
    asleep = nu.IfDo(mine, session.owner.set("") >> session.status.set(ASLEEP))
    return nuspace.atomic(_Run.slept.set(False) >> nu.IfDo(nothing, asleep >> _Run.slept.set(True)))


def _turns(plane: str, s: nustd.acp.SessionRef, idle: float) -> nu.Nu:
    """Level loop on the asks: take the next prompt past the cursor, run one Prompt Turn, repeat.

    Turns run one after another and permissions only in a turn, so idle is
    no prompt past the cursor for ``idle`` seconds after the last turn
    ended: then the engine sleeps, and this arm, so the race, ends.
    """
    prompts, cursor = asks_of(plane).prompts, asks_of(plane).cursor.fallback("")
    wait = nu.WaitUntil(
        nuspace.atomic(prompts.on_children_change()),
        nuspace.atomic(nu.Bool(_past(prompts, cursor))),
        **_RECHECK,
    )

    def turn(ids: nu.ObjectRef) -> nu.Nu:
        pid = nu.Str(nu.List(ids)[0])

        def run(prompt: nu.ObjectRef) -> nu.Nu:
            text = nu.Str(nu.Dict(prompt)["text"])
            return _begin(plane, pid, text) >> _stream(plane, s.prompt(text))

        return nu.let(nuspace.atomic(prompts[pid]), run)

    take = nu.let(nuspace.atomic(_past(prompts, cursor)), turn)
    step = nu.Timeout(idle, wait, on_timeout=_sleep(plane)) >> nu.IfDo(nu.Not(_Run.slept), take)
    return nu.WhileDo(nu.Not(_Run.slept), step)


def _answers(plane: str, s: nustd.acp.SessionRef) -> nu.Nu:
    """Level watch: each open permission a view answered is sent to the Agent."""
    session, entries = session_of(plane), trace_of(plane).entries

    def one(k: nu.ObjectRef) -> nu.Nu:
        key = nu.Str(k)
        answer = nuspace.atomic(nu.Str(entries[key].permission["answer"].fallback("")))

        def send(a: nu.ObjectRef) -> nu.Nu:
            option = nu.Str(a)
            busy = (_Run.turn != "").and_(nu.Int(nu.Len(_Run.perms)) == 0)
            selected = nuspace.atomic(
                entries[key].permission.set_item("outcome", "selected")
                >> nu.IfDo(busy, session.status.set(PROMPTING))
            )
            sent = (
                s.answer_permission(_Run.perms[key], option)
                >> _Run.perms.del_item(key, missing_ok=True)
                >> selected
            )
            return nu.IfDo((option != "").and_(_Run.perms.contains(key)), sent)

        return nu.let(answer, send)

    return nu.Reconcile(
        nuspace.atomic(entries.on_descendants_change("*", "permission", "answer")),
        nu.ForEachDo(nu.list(_Run.perms.keys()), one),
        **_RECHECK,
    )


def _cancels(plane: str, s: nustd.acp.SessionRef) -> nu.Nu:
    """Level watch on ``cancel_at``: newer than the running turn's start, cancel it, once."""
    at = asks_of(plane).cancel_at
    due = (
        (_Run.turn != "").and_(nu.Not(_Run.cancel_sent)).and_(nu.Int(at.fallback(0)) > _Run.started)
    )
    return nu.Reconcile(
        nuspace.atomic(at.on_change()),
        nu.IfDo(nuspace.atomic(due), s.cancel() >> _Run.cancel_sent.set(True)),
        **_RECHECK,
    )


# --- open, leftovers, the run --------------------------------------------------------------------


def _opened(plane: str, session_id: nu.StrArg, response: nu.Nu) -> nu.Nu:
    """The Session is open: its id, its config options when the Agent sent them, status idle."""
    session = session_of(plane)
    options = nu.Dict(response).get_item("config_options", None)
    commit = nuspace.atomic(
        session.session_id.set(_Run.session_id)
        >> nu.IfDo(nu.Not(nu.Object(options).is_(None)), session.config_options.set(options))
        >> session.error.set("")
        >> session.status.set(IDLE)
    )
    return _Run.session_id.set(session_id) >> commit


def _open(plane: str) -> nu.Nu:
    """Open the Session: new, else resume, else load (its replay dropped), else new plus a notice."""
    cwd = _Run.cwd
    system_prompt = nu.If(_Run.system_prompt == "", None, _Run.system_prompt)

    def new() -> nu.Nu:
        made = AGENT.new_session(cwd=cwd, system_prompt=system_prompt)
        return nu.let(made, lambda r: _opened(plane, nu.Str(nu.Dict(r)["session_id"]), r))

    def fresh() -> nu.Nu:
        return new() >> _told(plane, LOST_CONTEXT)

    stored = AGENT[_Run.session_id]
    resume = nu.let(
        stored.resume(cwd=cwd, system_prompt=system_prompt),
        lambda r: _opened(plane, _Run.session_id, r),
    )
    # The replay is the trace already: only the response, last, counts.
    load = nu.ForEachDo(
        stored.load(cwd=cwd, system_prompt=system_prompt),
        lambda i: nu.IfDo(nu.Str(Kind(i)) == "response", _opened(plane, _Run.session_id, i)),
    )

    def restore(mode: nu.ObjectRef) -> nu.Nu:
        return nu.SwitchDo(nu.Str(mode), {"resume": resume, "load": load}, default=fresh())

    restored = nu.TryCatch(
        nu.let(RestoreMode(AGENT.initialization()), restore),
        errors=AcpError,
        catch=lambda err: nu.IfDo(Recoverable(err), fresh(), _rethrow(err)),
    )
    return nu.IfDo(_Run.session_id == "", new(), restored)


def _close_leftovers(plane: str) -> nu.Nu:
    """Close what a run that died left open in the newest turn, when it never ended.

    The turn ends with error ``engine restarted``; its unanswered
    permissions are ``expired`` and its open tool entries ``cancelled``.
    In-flight turns and pending permissions do not survive the Agent
    process, so the trace says so. One commit.
    """
    turns, entries = trace_of(plane).turns, trace_of(plane).entries

    def check(last: nu.ObjectRef) -> nu.Nu:
        turn = nu.Str(last)

        def close(k: nu.ObjectRef) -> nu.Nu:
            e = entries[nu.Str(k)]
            mine = nu.Str(e.turn.fallback("")) == turn
            outcome = nu.Str(e.permission["outcome"].fallback(""))
            status = nu.Str(e.tool["status"].fallback(""))
            perm = mine.and_(nu.Str(e.kind.fallback("")) == "permission").and_(outcome == "")
            tool = mine.and_(nu.Str(e.kind.fallback("")) == "tool").and_(
                (status == _OPEN_TOOL[0]).or_(status == _OPEN_TOOL[1])
            )
            return nu.IfDo(perm, e.permission.set_item("outcome", "expired")) >> nu.IfDo(
                tool, e.tool.set_item("status", "cancelled")
            )

        page = nu.list(entries.reversed_keys(limit=LEFTOVER_PAGE))
        ended = (
            nu.ForEachDo(page, close)
            >> turns[turn].ended_at.set(now_ms())
            >> turns[turn].error.set("engine restarted")
        )
        open_ = (turn != "").and_(nu.Not(turns[turn].ended_at.exists()))
        return nuspace.atomic(nu.IfDo(open_, ended))

    return nu.let(nuspace.atomic(turns.last(default="")), check)


def _session(plane: str, idle: float) -> nu.Nu:
    """With the Agent bound: open, close the leftovers, race the arms."""
    s = AGENT[_Run.session_id]
    arms = nu.Race(
        _updates(plane, s),
        _turns(plane, s, idle),
        _answers(plane, s),
        _cancels(plane, s),
    )
    return _open(plane) >> _close_leftovers(plane) >> arms


def _bound(plane: str, idle: float) -> nu.Nu:
    """The run, with the Agent bound by the Spec's preset.

    The Session's ``cwd`` goes with each new, load and resume, so the bind
    gets none: what a bind takes is fixed when the tree is built.
    """
    cases = {
        name: nu.With(bind(AGENT, None), body=_session(plane, idle))  # type: ignore[arg-type]
        for name, bind in PRESETS.items()
    }
    unknown = nu.raise_(
        LookupError,
        nu.Str("no agent preset '") + _Run.agent + f"', one of {', '.join(PRESETS)}",
    )
    return nu.SwitchDo(_Run.agent, cases, default=unknown)


def _failed(plane: str, err: nu.Nu) -> nu.Nu:
    """The run failed: one last commit, then the error goes on.

    The running turn ends with the failure, a notice says it, status
    error, and the owner is let go. Asks still past the cursor would be
    replayed by the next run, long after they were sent: the cursor moves
    to the newest prompt, and a notice says they were dropped.
    """
    session, asks, trace = session_of(plane), asks_of(plane), trace_of(plane)
    turn = trace.turns[_Run.turn]
    newest = nu.Str(asks.prompts.last(default=""))
    waiting = (newest != "").and_(newest != asks.cursor.fallback(""))

    def held(got: nu.ObjectRef) -> nu.Nu:
        message = nu.Str(got)

        def told(key: nu.Str) -> nu.Nu:
            def dropped(also: nu.Str) -> nu.Nu:
                running = (
                    _cancel_permissions(plane)
                    >> turn.ended_at.set(now_ms())
                    >> turn.error.set(message)
                )
                drop = asks.cursor.set(newest) >> _notice(plane, also, DROPPED)
                let_go = nu.IfDo(
                    session.owner.fallback("") == Here.plane_run, session.owner.set("")
                )
                return nuspace.atomic(
                    nu.IfDo(_Run.turn != "", running)
                    >> _notice(plane, key, message)
                    >> session.error.set(message)
                    >> session.status.set(ERROR)
                    >> nu.IfDo(waiting, drop)
                    >> let_go
                )

            return _minted("notice", dropped)

        return _minted("notice", told) >> _rethrow(err)

    return nu.let(Describe(err, _Run.agent), held)


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
        idle: Seconds with no prompt past the cursor, after the last turn
            ended, before it sleeps and the run ends.
    """
    spec, session = spec_of(plane), session_of(plane)
    read = nuspace.atomic(
        _Run.agent.set(spec.agent.fallback(""))
        >> _Run.cwd.set(spec.cwd.fallback(""))
        >> _Run.system_prompt.set(spec.system_prompt.fallback(""))
        >> _Run.session_id.set(session.session_id.fallback(""))
    )
    run = nu.TryCatch(_bound(plane, idle), catch=lambda err: _failed(plane, err))

    def claimed(won: nu.ObjectRef) -> nu.Nu:
        return _claim(plane, won) >> nu.IfDo(won, run)

    body = read >> nu.let(False, claimed)
    return nu.Frame(
        _Run,
        body,
        nonce=Here.plane_run,
        seq=0,
        last="",
        turn="",
        started=0,
        cancel_sent=False,
        perms=nu.Dict.create(),
        taken=0,
        skipped=0,
        slept=False,
    )
