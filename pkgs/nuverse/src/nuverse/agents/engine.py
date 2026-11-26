"""The engine: the one program an agent plane runs. Owns the Agent process and the Session.

One plane run of the agent plane, start to end::

    claim     one commit: owner is this run, unless another live run owns it (then end at once)
    bind      nustd.acp with the Spec's preset and cwd, permissions="ask": the Agent spawns
    open      the Session: new, else resume, else load (its replay dropped), else new + a notice
    close     what a run that died left open: its turn, permissions, tool entries
    race      the arms below, until the turns arm goes to sleep
    sleep     one commit: owner cleared, unless a prompt is past the cursor

The arms, all on one loop, share one :class:`_Run` frame:

- updates: ``updates()``, everything the Agent says about the Session in
  wire order, each turn's end included, and the one stream folded. Sets
  the Session slots (plan, usage, title, commands, config options), folds
  the rest into entries of the running turn (or of none between turns),
  and ends the turn on its stop reason. Its :class:`_Open` frame holds
  what is open in the fold. First in the race: it subscribes before the
  turns arm runs at all, so no turn item is missed.
- turns: a level loop on the asks, one Prompt Turn at a time. It starts
  the turn, drains the prompt stream unread to drive it, and waits for the
  updates arm to fold the turn's end before it takes the next prompt. With
  no prompt past the cursor for the idle timeout, it goes to sleep and the
  race ends.
- answers: a level watch on the open permission entries; an ``answer``
  written by a view is sent with ``answer_permission``.
- cancel: a level watch on ``cancel_at``; newer than the running turn's
  start, the turn is cancelled.

The fold, one item at a time: a message or thought chunk grows the open
text entry of its kind and message id, or starts one after any other
entry; a growing text is written at most every :data:`FLUSH_SECONDS`, and
once more when it closes, at the next entry or the turn's end. A
``tool_call`` is a tool entry keyed ``tool:<tool_call_id>``, a
``tool_call_update`` patches only the fields it sends (an unknown id is a
create). A permission request is a permission entry, status ``waiting``.
A turn's end closes its text, cancels its tools still pending or in
progress and its unanswered permissions.

Errors (an ``AcpError``, not logged in, npx missing) land as status
``error`` and a notice entry, and the run ends ``failed``; the next ask
wakes it again. A failed turn the Agent answered (a JSON-RPC error, which
``updates()`` carries as the turn's end) only ends that turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    slept = nu.BoolRef.slot()


class _Open(nu.Shape):
    """The updates arm's memory: what is open in the fold."""

    key = nu.StrRef.slot()  # the open text entry, "" for none
    kind = nu.StrRef.slot()
    message_id = nu.StrRef.slot()
    text = nu.StrRef.slot()  # all of it so far
    flushed = nu.ObjectRef.slot()  # when it was last written, for the throttle
    tools = nu.DictRef.slot(bool)  # tool entries still pending or in progress


# --- pure helpers ----------------------------------------------------------------------------------


def _get(item: nu.Nu, key: str, default: object = None) -> nu.Nu:
    """``item[key]``, ``default`` when it is missing or null, as ACP leaves fields out."""
    got = nu.Dict(item).get_item(key, None)
    return nu.If(nu.Object(got).is_(None), default, got)


def _kind(item: nu.Nu) -> nu.Str:
    """What an item is: its ``session_update``, ``permission``, ``stop``, or ``response``."""
    return nu.Str(
        nu.If(
            nu.Contains(item, "request_permission"),
            "permission",
            nu.If(
                nu.Contains(item, "session_update"),
                nu.Dict(item)["session_update"],
                nu.If(nu.Contains(item, "stop_reason"), "stop", "response"),
            ),
        )
    )


def _text(item: nu.Nu) -> nu.Str:
    """A chunk's Content Block as entry text: its text, or a one-line placeholder for anything else."""
    block = nu.Dict(_get(item, "content", nu.Dict.create()))
    kind = nu.Str(block.get_item("type", "content"))
    return nu.Str(nu.If(kind == "text", nu.Str(block.get_item("text", "")), "\n[" + kind + "]\n"))


def _tool(item: nu.Nu) -> nu.Dict:
    """A new tool entry's ``tool`` before the item's own fields land on it: the defaults."""
    return nu.Dict.of(
        tool_call_id=nu.Str(_get(item, "tool_call_id", "")),
        title="",
        kind="other",
        status="pending",
    )


def _patched(tool: nu.Nu, item: nu.Nu) -> nu.Nu:
    """Each tool field ``item`` sends lands on ``tool``; one it leaves out or sends null is kept."""
    return nu.Sequential(
        *(
            nu.IfDo(nu.Not(nu.Object(_get(item, f)).is_(None)), tool.set_item(f, _get(item, f)))
            for f in _TOOL_FIELDS
        )
    )


def _permission(item: nu.Nu) -> nu.Dict:
    """A permission entry's ``permission``, from the fabric's request."""
    call = nu.Dict(_get(item, "tool_call", nu.Dict.create()))
    return nu.Dict.of(
        request=nu.Dict(item)["request_permission"],
        tool_call_id=call.get_item("tool_call_id", ""),
        options=_get(item, "options", nu.List.create()),
        answer="",
        outcome="",
    )


def _restore_mode(init: nu.Nu) -> nu.Str:
    """How the Agent restores a stored Session: ``resume``, ``load``, or ``""`` for neither."""
    caps = _get(init, "agent_capabilities", nu.Dict.create())
    resume = _get(_get(caps, "session_capabilities", nu.Dict.create()), "resume")
    load = nu.Bool(_get(caps, "load_session", False))
    return nu.Str(nu.If(nu.Not(nu.Object(resume).is_(None)), "resume", nu.If(load, "load", "")))


def _code(exc: nu.Nu) -> nu.Nu:
    """An ``AcpError``'s JSON-RPC code: None when the connection itself failed."""
    return nu.Object(nu.GetAttr(exc, "code", None))


def _caught(err: nu.Nu) -> nu.Nu:
    """The exception a catch caught, as a failed turn's end carries it."""
    return nu.GetAttr(err, "exception")


def describe(exc: nu.Nu, agent: nu.StrArg) -> nu.Str:
    """What a person reads when the engine fails on ``exc``: what happened, and what to do about it."""
    name = nu.Str(agent)
    said = nu.str(exc)
    login = nu.Str(nu.Switch(name, _LOGIN, default=nu.Str("log ") + name + " in"))
    cli = nu.Str(nu.Switch(name, CLIS, default=name))
    spawn = (
        nu.Str("The agent could not start (")
        + said
        + "). It runs through npx: install Node.js and make sure npx and "
        + cli
        + " are on PATH."
    )
    other = nu.If(said == "", nu.GetAttr(nu.GetAttr(exc, "__class__"), "__name__"), said)
    return nu.Str(
        nu.If(
            _code(exc) == _AUTH_REQUIRED,
            nu.Str("The agent is not logged in: ") + login + ", then ask again.",
            nu.If(nu.Object(nu.GetAttr(exc, "method", None)) == "spawn", spawn, other),
        )
    )


# --- entries --------------------------------------------------------------------------------------


def _minted(kind: str, fn: Callable[[nu.Str], nu.Nu]) -> nu.Nu:
    """The body ``fn`` builds over a fresh entry key, ``<kind>:<run>-<n>``."""
    key = nu.Str(f"{kind}:") + _Run.nonce + "-" + nu.str(_Run.seq)
    return _Run.seq.inc() >> nu.let(lambda k: fn(nu.Str(k)), k=key)


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
        nu.Sequential(_flush(plane), _put(plane, key, kind, _Run.turn, **slots), *also)
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


def _chunk(plane: str, u: nu.Nu, kind: str) -> nu.Nu:
    """A message or thought chunk: grows the open text entry, or starts one."""
    entries = trace_of(plane).entries
    mid = nu.Str(_get(u, "message_id", ""))
    same = (
        (_Open.key != "")
        .and_(_Open.key == _Run.last)
        .and_(_Open.kind == kind)
        .and_(_Open.message_id == mid)
    )
    write = nu.Throttle(
        FLUSH_SECONDS, nuspace.atomic(entries[_Open.key].text.set(_Open.text)), last=_Open.flushed
    )

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

    return nu.let(held, got=_text(u))


def _tool_entry(plane: str, u: nu.Nu, *, create: bool) -> nu.Nu:
    """A tool call: a new tool entry, or an update patching only the fields it sends."""
    entries = trace_of(plane).entries
    sent = nu.Str(_get(u, "status", ""))

    def held(got: nu.ObjectRef) -> nu.Nu:
        key = nu.Str(got)
        tool = entries[key].tool

        def track(status: nu.Str) -> nu.Nu:
            open_ = (status == _OPEN_TOOL[0]).or_(status == _OPEN_TOOL[1])
            closed = nu.IfDo(status != "", _Open.tools.del_item(key, missing_ok=True))
            return nu.IfDo(open_, _Open.tools.set_item(key, True), closed)

        made = _starts(plane, key, "tool", _patched(tool, u), tool=_tool(u)) >> track(
            nu.Str(nu.If(sent == "", "pending", sent))
        )
        if create:
            return made
        patch = nuspace.atomic(_patched(tool, u)) >> track(sent)
        return nu.IfDo(nuspace.atomic(entries.contains(key)), patch, made)

    return nu.let(held, got=nu.Str("tool:") + nu.Str(_get(u, "tool_call_id", "")))


def _permission_entry(plane: str, u: nu.Nu) -> nu.Nu:
    """A permission request: a permission entry, held open until it is answered or the turn ends."""
    request = nu.Dict(u)["request_permission"]

    def held(got: nu.ObjectRef) -> nu.Nu:
        key = nu.Str(got)
        waiting = session_of(plane).status.set(WAITING)
        made = _starts(plane, key, "permission", waiting, permission=_permission(u))
        return made >> _Run.perms.set_item(key, request)

    return nu.let(held, got=nu.Str("perm:") + _Run.nonce + "-" + nu.str(request))


def _fold(plane: str, u: nu.Nu) -> nu.Nu:
    """Fold item ``u`` of ``updates()`` into the trace and the Session slots.

    ``user_message_chunk`` is skipped: the user entry is written from the
    ask when the turn starts, so an agent echoing the prompt shows it once.
    A turn's end ends the running turn; anything else is dropped.
    """
    session = session_of(plane)

    def put(slot: str, value: object) -> nu.Nu:
        return nuspace.atomic(getattr(session, slot).set(value))

    usage = nu.Dict.of(used=_get(u, "used"), size=_get(u, "size"), cost=_get(u, "cost"))
    titled = nu.IfDo(nu.Contains(u, "title"), put("title", nu.Str(_get(u, "title", ""))))
    slots = {
        "plan": put("plan", _get(u, "entries", nu.List.create())),
        "usage_update": put("usage", usage),
        "session_info_update": titled,
        "available_commands_update": put(
            "commands", _get(u, "available_commands", nu.List.create())
        ),
        "config_option_update": put("config_options", _get(u, "config_options", nu.List.create())),
    }
    error = nu.Dict(u).get_item("error", None)
    stopped = _ended(
        plane, "stop_reason", nu.Str(nu.Dict(u)["stop_reason"]), session.status.set(IDLE)
    )
    cases = {
        "agent_message_chunk": _chunk(plane, u, "agent"),
        "agent_thought_chunk": _chunk(plane, u, "thought"),
        "tool_call": _tool_entry(plane, u, create=True),
        "tool_call_update": _tool_entry(plane, u, create=False),
        "permission": _permission_entry(plane, u),
        "stop": nu.IfDo(nu.Object(error).is_(None), stopped, _turn_failed(plane, error)),
        **slots,
    }
    return nu.SwitchDo(_kind(u), cases)


def _folding(plane: str, items: nu.Nu, catch: Callable[[nu.Nu], nu.Nu] | None = None) -> nu.Nu:
    """Fold every item of ``items`` in turn, in a fresh :class:`_Open` frame: nothing open.

    ``catch`` takes an ``AcpError`` the stream raises, inside the frame.
    """
    folded = nu.ForEachDo(items, lambda u: _fold(plane, u))
    if catch is not None:
        folded = nu.TryCatch(folded, errors=AcpError, catch=catch)
    open_ = {"key": "", "kind": "", "message_id": "", "text": "", "flushed": None}
    return nu.let(_Open, folded, **open_, tools=nu.Dict.create())


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
    and ``also`` lands in the same commit. What is open is taken from the
    memory and the memory cleared first, so once the turn's end is in the
    trace nothing of it is open here any more: the trace alone says a turn
    is over.
    """
    entries, turns = trace_of(plane).entries, trace_of(plane).turns
    open_ = nu.Dict.of(
        turn=_Run.turn,
        key=_Open.key,
        text=_Open.text,
        tools=nu.list(_Open.tools.keys()),
        perms=nu.list(_Run.perms.keys()),
    )

    def close(got: nu.ObjectRef) -> nu.Nu:
        held = nu.Dict(got)
        key, turn = nu.Str(held["key"]), turns[nu.Str(held["turn"])]
        tools = nu.ForEachDo(
            held["tools"], lambda k: entries[nu.Str(k)].tool.set_item("status", "cancelled")
        )
        perms = nu.ForEachDo(
            held["perms"],
            lambda k: entries[nu.Str(k)].permission.set_item("outcome", "cancelled"),
        )
        commit = nuspace.atomic(
            nu.Sequential(
                nu.IfDo(key != "", entries[key].text.set(held["text"])),
                tools,
                perms,
                turn.ended_at.set(now_ms()),
                getattr(turn, slot).set(value),
                *also,
            )
        )
        forget = _Open.key.set("") >> _Open.tools.clear() >> _Run.perms.clear() >> _Run.turn.set("")
        return forget >> commit

    return nu.let(close, got=open_)


def _turn_failed(plane: str, error: nu.Nu) -> nu.Nu:
    """The Agent answered the turn with a JSON-RPC ``error``: it ends with it, a notice, status error."""
    session = session_of(plane)

    def held(got: nu.ObjectRef) -> nu.Nu:
        message = nu.Str(got)

        def told(key: nu.Str) -> nu.Nu:
            also = (_notice(plane, key, message), session.error.set(message))
            failed = _ended(plane, "error", message, *also, session.status.set(ERROR))
            return failed >> _Run.last.set(key)

        return _minted("notice", told)

    return nu.let(held, got=describe(error, _Run.agent))


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


# --- the arms -------------------------------------------------------------------------------------


def _past(prompts: nustd.kv.LogDictRef, cursor: nu.StrArg) -> nu.List:
    """The first prompt id past ``cursor``, as a list of none or one."""
    c = nu.Str(cursor)
    return nu.List(
        nu.If(c == "", nu.list(prompts.keys(limit=1)), nu.list(prompts.keys(after=c, limit=1)))
    )


def _updates(plane: str, s: nustd.acp.SessionRef) -> nu.Nu:
    """Everything the Agent says about the Session, each turn's end included, folded in wire order.

    The connection gone, the running turn ends with the error first, then
    the error goes on and the run fails.
    """

    def gone(err: nu.Nu) -> nu.Nu:
        message = describe(_caught(err), _Run.agent)
        return nu.IfDo(_Run.turn != "", _ended(plane, "error", message)) >> nu.Raise(err)

    return _folding(plane, s.updates(), gone)


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

    The prompt stream is drained unread: the updates arm folds the same
    items and the turn's end. A JSON-RPC error ends the turn there too; the
    connection gone, the updates arm fails the run, so this arm parks. The
    next turn waits until the updates arm has ended this one, so its items
    never land in the next.
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
            drained = nu.TryCatch(
                nu.ForEachDo(s.prompt(text), lambda _: nu.Noop()),
                errors=AcpError,
                catch=lambda err: nu.IfDo(nu.Object(_code(_caught(err))).is_(None), nu.Park()),
            )
            ended = trace_of(plane).turns[nu.Str("turn:") + pid].ended_at
            folded = nu.WaitUntil(
                nuspace.atomic(ended.on_change()), nuspace.atomic(ended.exists()), **_RECHECK
            )
            return _begin(plane, pid, text) >> drained >> folded

        return nu.let(run, prompt=nuspace.atomic(prompts[pid]))

    take = nu.let(turn, ids=nuspace.atomic(_past(prompts, cursor)))
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

        return nu.let(send, a=answer)

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
        return nu.let(lambda r: _opened(plane, nu.Str(nu.Dict(r)["session_id"]), r), r=made)

    def fresh() -> nu.Nu:
        return new() >> _told(plane, LOST_CONTEXT)

    stored = AGENT[_Run.session_id]
    resume = nu.let(
        lambda r: _opened(plane, _Run.session_id, r),
        r=stored.resume(cwd=cwd, system_prompt=system_prompt),
    )
    # The replay is the trace already: only the response, last, counts.
    load = nu.ForEachDo(
        stored.load(cwd=cwd, system_prompt=system_prompt),
        lambda i: nu.IfDo(_kind(i) == "response", _opened(plane, _Run.session_id, i)),
    )

    def restore(mode: nu.ObjectRef) -> nu.Nu:
        return nu.SwitchDo(nu.Str(mode), {"resume": resume, "load": load}, default=fresh())

    restored = nu.TryCatch(
        nu.let(restore, mode=_restore_mode(AGENT.initialization())),
        errors=AcpError,
        catch=lambda err: nu.IfDo(
            nu.Contains(nu.Literal(list(_RESTORE_FALLBACK)), _code(_caught(err))),
            fresh(),
            nu.Raise(err),
        ),
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

    return nu.let(check, last=nuspace.atomic(turns.last(default="")))


def _session(plane: str, idle: float) -> nu.Nu:
    """With the Agent bound: open, close the leftovers, race the arms."""
    s = AGENT[_Run.session_id]
    # Updates first: the race starts its arms in order, and this one subscribes
    # before it first suspends, so it listens before the turns arm runs at all.
    arms = nu.Race(
        _updates(plane, s),
        _turns(plane, s, idle),
        _answers(plane, s),
        _cancels(plane, s),
    )
    return _open(plane) >> _close_leftovers(plane) >> arms


def _bound(plane: str, idle: float) -> nu.Nu:
    """The run, with the Agent the Spec names spawned in the Spec's ``cwd``.

    The preset is read when the bracket opens, so one bind and one body
    serve every agent.
    """
    presets = {name: nu.Literal(dict(preset)) for name, preset in PRESETS.items()}
    unknown = nu.raise_(
        LookupError,
        nu.Str("no agent preset '") + _Run.agent + f"', one of {', '.join(PRESETS)}",
    )

    def bound(got: nu.ObjectRef) -> nu.Nu:
        preset = nu.Dict(got)
        spawn = nustd.acp.bind(
            AGENT,
            command=preset["command"],
            cwd=nu.If(_Run.cwd == "", None, _Run.cwd),
            env=preset.get_item("env", None),
            permissions="ask",
        )
        found = nu.With(spawn, body=_session(plane, idle))
        return nu.IfDo(nu.Object(got).is_(None), unknown, found)

    return nu.let(bound, got=nu.Switch(_Run.agent, presets, default=None))


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

        return _minted("notice", told) >> nu.Raise(err)

    return nu.let(held, got=describe(_caught(err), _Run.agent))


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

    body = read >> nu.let(claimed, won=False)
    return nu.let(
        _Run,
        body,
        nonce=Here.plane_run,
        seq=0,
        last="",
        turn="",
        started=0,
        cancel_sent=False,
        perms=nu.Dict.create(),
        slept=False,
    )
