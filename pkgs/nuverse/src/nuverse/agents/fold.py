"""The fold: what the Agent says, turned into trace entries and Session slots.

ACP's Session Updates are patches and chunks; a view would have to replay
all of them to draw one message. :class:`Fold` keeps what the engine knows
of the conversation in memory and turns each item into writes, one entry
per thing a person sees, in arrival order:

- ``user_message_chunk``: skipped; the user entry is written from the ask
  when the turn starts, so an agent echoing the prompt does not show it twice.
- ``agent_message_chunk``, ``agent_thought_chunk``: appended to the open
  entry of that kind. A new one starts when the kind or ``message_id``
  changes, or after any other entry. Non-text blocks become a one-line
  placeholder.
- ``tool_call``: a tool entry keyed ``tool:<tool_call_id>``.
- ``tool_call_update``: patches it, only the fields sent, ``content`` and
  ``locations`` replaced whole. An unknown id is a create.
- a permission request: a permission entry keyed ``perm:<run>-<id>``,
  status ``waiting``.
- ``plan``, ``usage_update``, ``session_info_update``,
  ``available_commands_update``, ``config_option_update``: the matching
  Session slot.
- the turn's stop reason: the turn ends; tool entries still pending or in
  progress become ``cancelled`` and open permissions ``cancelled``, locally.
- anything else: dropped.

The fold writes nothing itself. It queues writes, coalesced by what they
write, and :meth:`take` hands them to the one writer, which commits them
in the order they were first queued. Text growing in an open entry waits
up to :data:`FLUSH_SECONDS`; anything else is written at once.

The async waits (:meth:`next_writes`, :meth:`reached`, :meth:`idle_for`,
:meth:`drained`) are for the engine's arms, all on one event loop.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from typing import Any

from .shapes import ERROR, IDLE, PROMPTING, WAITING


__all__ = [
    "BARRIER_SECONDS",
    "FLUSH_SECONDS",
    "Fold",
    "Op",
]


#: How long text growing in an open entry waits before it is written, in seconds.
FLUSH_SECONDS = 0.15

#: How long a stop reason waits for the updates arm to fold the turn's last item.
BARRIER_SECONDS = 5.0

#: One write: ``(op, key, value)``. See :func:`nuverse.agents.engine.writes`.
Op = tuple[str, str, Any]

# Tool statuses a turn's end turns into ``cancelled``.
_OPEN_TOOL = ("pending", "in_progress")

# The tool fields a tool entry keeps, as ACP names them.
_TOOL_FIELDS = ("title", "kind", "status", "content", "locations")

# How many folded items the barrier remembers.
_FOLDED = 4096


def _ms() -> int:
    return int(time.time() * 1000)


def _text(block: object) -> str:
    """A Content Block as entry text: its text, or a one-line placeholder for anything else."""
    if isinstance(block, dict) and block.get("type") == "text":
        return str(block.get("text", ""))
    kind = block.get("type", "content") if isinstance(block, dict) else "content"
    return f"\n[{kind}]\n"


class Fold:
    """One engine run's memory of the conversation, and the writes waiting to land.

    Args:
        nonce: Told apart entries this run mints from an earlier run's; a
            fresh one when None.
    """

    def __init__(self, nonce: str | None = None) -> None:
        self.nonce = nonce or uuid.uuid4().hex[:8]
        self._seq = 0
        # Writes waiting, by what they write, in the order first queued.
        self._pending: dict[tuple[str, str], Op] = {}
        # Writes taken by the writer and not yet committed.
        self._inflight: list[Op] = []
        self._urgent = False
        self._last_flush = 0.0
        self._event: asyncio.Event | None = None
        #: The Session id, once opened.
        self.session_id = ""
        #: The last prompt id taken.
        self.cursor = ""
        #: The running turn's id, ``""`` between turns.
        self.turn = ""
        #: When the running turn started, ms.
        self.started = 0
        self._cancel_sent = False
        # The last item the turn's own stream gave, for the stop reason's barrier.
        self._turn_last: object = None
        # The open text entry: key, kind, message id, text.
        self._open: dict[str, Any] | None = None
        self._last_key = ""
        # Tool entries by key, as last written.
        self._tools: dict[str, dict[str, Any]] = {}
        self._open_tools: dict[str, None] = {}
        # Open permission entries: key -> the fabric's request id.
        self._perms: dict[str, object] = {}
        self._folded: deque[int] = deque(maxlen=_FOLDED)
        self._folded_ids: set[int] = set()
        self._idle_since = time.monotonic()

    # --- the writes ---------------------------------------------------------

    def _queue(self, op: str, key: str, value: object, *, urgent: bool = True) -> None:
        held = self._pending.get((op, key))
        if op == "ended" and held is not None:
            value = {**held[2], **value}  # type: ignore[dict-item]
        self._pending[(op, key)] = (op, key, value)
        self._urgent = self._urgent or urgent
        self._poke()

    def _session(self, slot: str, value: object, *, urgent: bool = True) -> None:
        self._queue("session", slot, value, urgent=urgent)

    @property
    def pending(self) -> bool:
        """Whether writes wait to be taken."""
        return bool(self._pending)

    def due(self, now: float | None = None) -> float | None:
        """Seconds until the writes waiting are due: 0 for now, None with nothing waiting."""
        if not self._pending:
            return None
        if self._urgent:
            return 0.0
        now = time.monotonic() if now is None else now
        return max(0.0, self._last_flush + FLUSH_SECONDS - now)

    def take(self) -> list[Op]:
        """The writes waiting, in order, now in flight until :meth:`committed`."""
        ops = list(self._pending.values())
        self._pending.clear()
        self._inflight = ops
        self._urgent = False
        self._last_flush = time.monotonic()
        return ops

    def committed(self) -> None:
        """The writes in flight landed."""
        self._inflight = []
        self._poke()

    def unwritten(self) -> list[Op]:
        """Everything not committed, in flight first, then waiting: what a last commit writes."""
        ops = [*self._inflight, *self._pending.values()]
        self._inflight = []
        self._pending.clear()
        return ops

    # --- entries --------------------------------------------------------------

    def _mint(self, kind: str) -> str:
        self._seq += 1
        return f"{kind}:{self.nonce}-{self._seq}"

    def _close_text(self) -> None:
        """Write the open text entry's text now, and close it."""
        if self._open is not None:
            self._queue("text", self._open["key"], self._open["text"])
            self._open = None

    def _entry(self, key: str, kind: str, **slots: object) -> None:
        self._close_text()
        self._queue("entry", key, {"kind": kind, "turn": self.turn, "at": _ms(), **slots})
        self._last_key = key

    def notice(self, text: str) -> None:
        """A notice entry: something a person should know that the Agent did not say."""
        self._entry(self._mint("notice"), "notice", text=text)

    def _chunk(self, kind: str, item: dict[str, Any]) -> None:
        piece = _text(item.get("content"))
        mid = item.get("message_id")
        held = self._open
        if (
            held is not None
            and held["kind"] == kind
            and held["message_id"] == mid
            and self._last_key == held["key"]
        ):
            held["text"] += piece
            self._queue("text", held["key"], held["text"], urgent=False)
            return
        key = self._mint(kind)
        self._entry(key, kind, text=piece)
        self._open = {"key": key, "kind": kind, "message_id": mid, "text": piece}

    def _tool(self, item: dict[str, Any], *, create: bool) -> None:
        tid = str(item.get("tool_call_id", ""))
        key = f"tool:{tid}"
        held = self._tools.get(key)
        if held is None or create:
            tool = {"tool_call_id": tid, "title": "", "kind": "other", "status": "pending"}
            tool.update({f: item[f] for f in _TOOL_FIELDS if item.get(f) is not None})
            self._tools[key] = tool
            self._entry(key, "tool", tool=dict(tool))
        else:
            held.update({f: item[f] for f in _TOOL_FIELDS if item.get(f) is not None})
            self._queue("tool", key, dict(held))
        status = self._tools[key]["status"]
        if status in _OPEN_TOOL:
            self._open_tools[key] = None
        else:
            self._open_tools.pop(key, None)

    def _permission(self, item: dict[str, Any]) -> None:
        key = f"perm:{self.nonce}-{item['request_permission']}"
        call = item.get("tool_call") or {}
        permission = {
            "request": item["request_permission"],
            "tool_call_id": call.get("tool_call_id", ""),
            "options": list(item.get("options") or ()),
            "answer": "",
            "outcome": "",
        }
        self._perms[key] = item["request_permission"]
        self._entry(key, "permission", permission=permission)
        self._status(WAITING)

    # --- what the engine tells it ---------------------------------------------------

    def _status(self, status: str) -> None:
        self._session("status", status)
        busy = bool(self.turn) or bool(self._perms)
        if not busy:
            self._idle_since = time.monotonic()

    def opened(self, session_id: str, response: dict[str, Any] | None) -> None:
        """The Session is open: its id, its config options, status idle."""
        self.session_id = session_id
        self._session("session_id", session_id)
        options = (response or {}).get("config_options")
        if options is not None:
            self._session("config_options", list(options))
        self._session("error", "")
        self._status(IDLE)

    def leftovers(self, turn: str, entries: list[dict[str, Any]]) -> None:
        """Close what a run that died left open in turn ``turn``.

        The turn ends with error ``engine restarted``; its unanswered
        permissions are ``expired`` and its open tool entries ``cancelled``.
        In-flight turns and pending permissions do not survive the Agent
        process, so the trace says so.

        Args:
            turn: The newest turn, which has no ``ended_at``.
            entries: The newest entries, ``{key, entry}`` each, newest first.
        """
        for held in entries:
            key, entry = held["key"], held.get("entry") or {}
            if entry.get("turn") != turn:
                continue
            if entry.get("kind") == "permission" and not (entry.get("permission") or {}).get(
                "outcome"
            ):
                self._queue("outcome", key, "expired")
            tool = entry.get("tool") or {}
            if entry.get("kind") == "tool" and tool.get("status") in _OPEN_TOOL:
                self._queue("tool", key, {**tool, "status": "cancelled"})
        self._queue("ended", turn, {"ended_at": _ms(), "error": "engine restarted"})

    def begin(self, prompt_id: str, prompt: dict[str, Any]) -> str:
        """A Prompt Turn starts on ``prompt_id``: the turn, the user entry, the cursor. Its id."""
        self._close_text()
        self.cursor = prompt_id
        self.turn = f"turn:{prompt_id}"
        self.started = _ms()
        self._cancel_sent = False
        self._turn_last = None
        self._queue("cursor", "", prompt_id)
        self._queue("turn", self.turn, {"prompt": prompt_id, "started_at": self.started})
        self._entry(f"user:{prompt_id}", "user", text=str(prompt.get("text", "")))
        self._status(PROMPTING)
        return self.turn

    def step(self, item: dict[str, Any]) -> None:
        """Fold one item from ``updates()``, in wire order."""
        try:
            self._step(item)
        finally:
            self._folded.append(id(item))
            self._folded_ids.add(id(item))
            if len(self._folded_ids) > _FOLDED:
                self._folded_ids = set(self._folded)
            self._poke()

    def _step(self, item: dict[str, Any]) -> None:
        if "request_permission" in item:
            self._permission(item)
            return
        kind = item.get("session_update")
        if kind == "agent_message_chunk":
            self._chunk("agent", item)
        elif kind == "agent_thought_chunk":
            self._chunk("thought", item)
        elif kind == "tool_call":
            self._tool(item, create=True)
        elif kind == "tool_call_update":
            self._tool(item, create=False)
        elif kind == "plan":
            self._session("plan", list(item.get("entries") or ()))
        elif kind == "usage_update":
            usage = {"used": item.get("used"), "size": item.get("size"), "cost": item.get("cost")}
            self._session("usage", usage, urgent=False)
        elif kind == "session_info_update":
            if "title" in item:
                self._session("title", item["title"] or "", urgent=False)
        elif kind == "available_commands_update":
            self._session("commands", list(item.get("available_commands") or ()), urgent=False)
        elif kind == "config_option_update":
            self._session("config_options", list(item.get("config_options") or ()), urgent=False)
        # user_message_chunk, current_mode_update and anything newer are dropped.

    def seen(self, item: object) -> None:
        """The turn's own stream gave ``item``: the stop reason waits until it is folded."""
        self._turn_last = item

    def _end(self, **turn: object) -> None:
        self._close_text()
        for key in list(self._open_tools):
            self._tools[key]["status"] = "cancelled"
            self._queue("tool", key, dict(self._tools[key]))
        self._open_tools.clear()
        for key in list(self._perms):
            self._queue("outcome", key, "cancelled")
        self._perms.clear()
        if self.turn:
            self._queue("ended", self.turn, {"ended_at": _ms(), **turn})
        self.turn = ""
        self._turn_last = None

    def stop(self, stop_reason: str) -> None:
        """The turn ended with ``stop_reason``."""
        self._end(stop_reason=stop_reason)
        self._status(IDLE)

    def failed(self, message: str) -> None:
        """The turn, or the engine, failed: the turn ends with the error, a notice says it."""
        self._end(error=message)
        self.notice(message)
        self._session("error", message)
        self._status(ERROR)

    def answered(self, key: str, option_id: str) -> None:
        """Permission ``key`` was sent ``option_id``."""
        if self._perms.pop(key, None) is None:
            return
        self._queue("outcome", key, "selected")
        if self.turn and not self._perms:
            self._status(PROMPTING)

    def open_permissions(self) -> list[list[object]]:
        """The permissions waiting on an answer, ``[key, request]`` each."""
        return [[key, request] for key, request in self._perms.items()]

    def cancel_due(self, cancel_at: object) -> bool:
        """Whether ``cancel_at`` asks to cancel the running turn, not yet cancelled."""
        due = isinstance(cancel_at, int) and cancel_at > self.started
        return bool(self.turn) and due and not self._cancel_sent

    def cancel_sent(self) -> None:
        """The running turn was cancelled."""
        self._cancel_sent = True

    @property
    def busy(self) -> bool:
        """Whether a turn runs or a permission waits: the idle timer does not run."""
        return bool(self.turn) or bool(self._perms)

    # --- waits ---------------------------------------------------------------------

    def _poke(self) -> None:
        event, self._event = self._event, None
        if event is not None:
            event.set()

    async def _changed(self, timeout: float | None = None) -> None:
        if self._event is None:
            self._event = asyncio.Event()
        event = self._event
        try:
            await asyncio.wait_for(event.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    async def next_writes(self) -> list[Op]:
        """Wait until writes are due, then take them."""
        while True:
            wait = self.due()
            if wait == 0.0:
                return self.take()
            await self._changed(wait)

    async def reached(self, item: object, timeout: float = BARRIER_SECONDS) -> bool:
        """Wait until ``item`` is folded: False when it was not within ``timeout``."""
        deadline = time.monotonic() + timeout
        while item is not None and id(item) not in self._folded_ids:
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            await self._changed(left)
        return True

    async def stopped(self, stop_reason: str) -> None:
        """The turn's stop reason, folded behind every item its stream gave."""
        await self.reached(self._turn_last)
        self.stop(stop_reason)

    async def idle_for(self, seconds: float) -> None:
        """Wait until no turn has run and no permission waited for ``seconds``."""
        while True:
            if self.busy:
                await self._changed()
                continue
            left = self._idle_since + seconds - time.monotonic()
            if left <= 0:
                return
            await self._changed(left)

    async def drained(self) -> None:
        """Wait until every write queued so far has landed."""
        while self._pending or self._inflight:
            await self._changed()
