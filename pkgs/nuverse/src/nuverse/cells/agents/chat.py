"""A chat cell: a view on one agent plane, its conversation and a composer.

The cell keeps one thing in its own state: the agent plane's id
(:class:`Chat`). The plane holds the conversation and runs the engine
(:mod:`nuverse.agents`); this cell only reads its trace and writes asks,
so two tabs on one chat are two views on one engine.

- **Setup**, the first time: pick an agent among the installed ones,
  preselected when there is one, an empty state when there is none. Start
  makes the plane (:func:`nuverse.agents.add`), its folder the space's.
- **Header**: the title (or "New chat"), the agent, context used and
  size, cost, status, and Stop while a turn runs.
- **Entries**: one keyed child per trace entry, the newest :data:`PAGE`
  first, older ones a page at a time from "Show earlier". Each redraws from
  its own slots as the engine writes them.
- **Permission**: the request's options as buttons, answered through
  :func:`nuverse.agents.answer`; settled, one line.
- **Plan** above the composer, and the **composer**, which asks.

Everything drawn is a ui-kit component through its ``nustd.ui`` ref.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.places import Here
from nuspace.specs import CellSpec
from nuverse import agents

from .. import source


__all__ = ["CELL", "PAGE", "Chat", "View", "out"]


#: How many entries show at first, and how many more each "Show earlier" adds.
PAGE = 50


class Chat(nu.Shape):
    """The cell's own state: its agent plane, and how many entries it shows."""

    plane = nustd.kv.StrRef.slot()
    shown = nustd.kv.IntRef.slot()


class Setup(nustd.ui.Card):
    """The first step: which agent, then Start."""

    agent = nustd.ui.SelectRef.slot(label="Agent")
    start = nustd.ui.ButtonRef.slot(label="Start chat", icon="message-square")


class Header(nustd.ui.Row):
    """The chat's title, agent, usage, cost, status and Stop."""

    title = nustd.ui.HeadingRef.slot(level=3)
    agent = nustd.ui.BadgeRef.slot(variant="secondary", size="sm")
    usage = nustd.ui.TextRef.slot(value="")
    cost = nustd.ui.TextRef.slot(value="")
    status = nustd.ui.StatusPillRef.slot()
    stop = nustd.ui.ButtonRef.slot(label="Stop", icon="square", variant="secondary", size="sm")


class Body(nustd.ui.Column):
    """The conversation: Show earlier, then one keyed child per entry."""

    earlier = nustd.ui.ButtonRef.slot(label="Show earlier", variant="ghost", size="sm")
    entries = nustd.ui.ColumnRef.slot(gap=3)


class Conversation(nustd.ui.Column):
    """The whole chat: header, entries, plan, composer."""

    header = Header.slot(gap=2, align="center", grow={"title": 1}, wrap=True)
    body = Body.slot(gap=2, scroll="y", max_height="70vh")
    plan = nustd.ui.PlanRef.slot()
    composer = nustd.ui.ComposerRef.slot(placeholder="Message the agent...")


class View(nu.Shape):
    """The cell's roots: an empty state, the setup step, or the chat."""

    empty = nustd.ui.EmptyStateRef.slot(
        label="No agent installed",
        description="Install Node.js and the claude or codex CLI, then add this cell again.",
        icon="bot",
        size="sm",
    )
    setup = Setup.slot(gap=3)
    chat = Conversation.slot(gap=3)


HELD = nuspace.here(Chat)
SETUP, CHAT = View.setup, View.chat
HEADER, BODY, ENTRIES = CHAT.header, CHAT.body, CHAT.body.entries


# --- text the header shows -----------------------------------------------------------------


def _tokens(n: object) -> str:
    if not isinstance(n, (int, float)):
        return "?"
    return f"{n / 1000:.0f}k" if n >= 1000 else str(int(n))


def _usage_text(usage: object) -> str:
    u = usage if isinstance(usage, dict) else {}
    if u.get("used") is None:
        return ""
    return f"{_tokens(u.get('used'))} / {_tokens(u.get('size'))}"


def _cost_text(usage: object) -> str:
    cost = (usage if isinstance(usage, dict) else {}).get("cost") or {}
    amount = cost.get("amount") if isinstance(cost, dict) else None
    if not isinstance(amount, (int, float)):
        return ""
    currency = cost.get("currency") or ""
    return f"${amount:.2f}" if currency == "USD" else f"{amount:.2f} {currency}".strip()


_TONES = {
    agents.ASLEEP: "neutral",
    agents.STARTING: "info",
    agents.IDLE: "ok",
    agents.PROMPTING: "info",
    agents.WAITING: "warn",
    agents.ERROR: "danger",
}


def _tone(status: object) -> str:
    return _TONES.get(str(status), "neutral")


def _permission_title(tool: object) -> str:
    title = (tool if isinstance(tool, dict) else {}).get("title")
    return f"Allow {title}?" if title else "Allow this tool call?"


def _get(held: object, key: str, default: object = "") -> object:
    value = held.get(key) if isinstance(held, dict) else None
    return default if value is None else value


#: ``held[key]``, or ``default`` when it is missing or None.
Get = nu.host(_get, name="Get")
UsageText = nu.host(_usage_text, name="UsageText")
CostText = nu.host(_cost_text, name="CostText")
Tone = nu.host(_tone, name="Tone")
PermissionTitle = nu.host(_permission_title, name="PermissionTitle")


# --- setup ------------------------------------------------------------------------------------


def _setup() -> nu.Nu:
    """Pick an agent among the installed ones and start a chat; an empty state with none."""

    def shown(names: nu.ObjectRef) -> nu.Nu:
        found = nu.List(names)

        def start(_: nu.Nu) -> nu.Nu:
            cwd = nu.Str(nuspace.atomic(nuspace.Space.info.path))
            return agents.add(
                nu.Str(SETUP.agent), cwd, parent=Here.plane, name="Chat", into=HELD.plane
            )

        draw = (
            SETUP.init()
            >> SETUP.set_title("New chat")
            >> SETUP.agent.set_options(found)
            >> SETUP.agent.set(nu.Str(found[0]))
        )
        return nu.IfDo(
            found,
            View.empty.erase() >> draw >> nu.ReactOnce(SETUP.start.on_click(), start),
            View.empty.init(),
        )

    return CHAT.erase() >> nu.let(agents.installed(), shown)


# --- the chat ----------------------------------------------------------------------------------


def _header(plane: nu.Str) -> nu.Nu:
    """The header and the composer's busy flag, redrawn when the Session moves."""
    session, spec = agents.session(plane), agents.spec(plane)
    status = nu.Str(session.status.fallback(agents.ASLEEP))
    title = nu.Str(session.title.fallback(""))
    usage = session.usage.fallback({})
    busy = (status == agents.PROMPTING).or_(status == agents.WAITING)

    def draw(held: nu.ObjectRef) -> nu.Nu:
        h = nu.Dict(held)
        return (
            HEADER.title.set(nu.If(nu.Str(h["title"]) == "", "New chat", h["title"]))
            >> HEADER.agent.set_label(h["agent"])
            >> HEADER.usage.set(UsageText(h["usage"]))
            >> HEADER.cost.set(CostText(h["usage"]))
            >> HEADER.status.set(h["status"], tone=Tone(h["status"]))
            >> HEADER.stop.set_disabled(nu.Not(h["busy"]))
            >> CHAT.composer.set_busy(h["busy"])
        )

    read = nu.Dict.of(
        title=title, agent=spec.agent.fallback(""), usage=usage, status=status, busy=busy
    )
    change = nu.OnAny(
        session.status.on_change(), session.title.on_change(), session.usage.on_change()
    )
    return nu.Reconcile(
        nuspace.atomic(change),
        nu.let(nuspace.atomic(read), draw),
        after=nu.RECHECK_AFTER,
        every=nu.RECHECK_EVERY,
    )


def _plan(plane: nu.Str) -> nu.Nu:
    """The plan above the composer, replaced whole as the Agent sends it."""
    plan = agents.session(plane).plan
    entries = nuspace.atomic(nu.If(plan.exists(), plan.extract(), []))
    return nu.Reconcile(nuspace.atomic(plan.on_change()), CHAT.plan.set(entries))


def _window(plane: nu.Str) -> nu.List:
    """The newest entry keys the cell shows, oldest first."""
    entries = agents.trace(plane).entries
    limit = nu.Int(HELD.shown.fallback(PAGE))
    return nu.List(nu.Collect(nu.Reversed(nu.list(entries.reversed_keys(limit=limit)))))


def _tool(entry: agents.Entry, call: nustd.ui.ToolCallRef) -> nu.Nu:
    """A tool entry: its row, then each piece of its content, a diff or text, keyed by place."""
    tool = entry.tool

    def draw(held: nu.ObjectRef) -> nu.Nu:
        t = nu.Dict(held)

        def piece(e: nu.Nu) -> nu.Nu:
            at, c = nu.Str("c") + nu.str(e[0]), nu.Dict(e[1])
            diff = nustd.ui.DiffRef(at, parent_ref=call)
            text = nustd.ui.MarkdownRef(at, parent_ref=call)
            block = nu.Dict(Get(c, "content", {}))
            return nu.IfDo(
                nu.Str(Get(c, "type", "")) == "diff",
                diff.set(c["new_text"], old_text=Get(c, "old_text", None), path=c["path"]),
                nu.IfDo(nu.Str(Get(block, "type", "")) == "text", text.set(block["text"])),
            )

        content = nu.List(Get(t, "content", []))
        row = call.set(title=Get(t, "title", ""), kind=Get(t, "kind", "other"), status=t["status"])
        return row >> nu.ForEachDo(nu.Enumerate(content), piece)

    redraw = nu.let(nuspace.atomic(tool.extract()), draw)
    return redraw >> nu.Reconcile(nuspace.atomic(tool.on_change()), redraw)


def _permission(plane: nu.Str, key: nu.Str, entry: agents.Entry) -> nu.Nu:
    """A permission entry: a card answered through ``agents.answer``; settled, one line."""
    card = ENTRIES[key].to(nustd.ui.PermissionRequestRef.slot())
    entries = agents.trace(plane).entries
    permission = entry.permission

    def draw(held: nu.ObjectRef) -> nu.Nu:
        p = nu.Dict(held)
        call = entries[nu.Str("tool:") + nu.Str(Get(p, "tool_call_id", ""))].tool
        title = PermissionTitle(nuspace.atomic(nu.If(call.exists(), call.extract(), {})))
        outcome, answer = nu.Str(Get(p, "outcome", "")), nu.Str(Get(p, "answer", ""))
        state = nu.IfDo(
            (outcome == "cancelled").or_(outcome == "expired"),
            card.set_state(outcome),
            nu.IfDo(answer != "", card.set_answer(answer), card.set_state("open")),
        )
        return card.set(title, options=Get(p, "options", [])) >> state

    redraw = nu.let(nuspace.atomic(permission.extract()), draw)

    def picked(event: nu.Nu) -> nu.Nu:
        option = nu.Str(nu.Dict(event)["option_id"])
        # A request settled meanwhile refuses it; the redraw shows how it settled.
        return nu.TryCatch(agents.answer(plane, key, option), catch=lambda _: redraw)

    return (
        ENTRIES.insert(card)
        >> redraw
        >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(permission.on_change()), redraw),
            nu.ReactEvery(card.on_select(), picked),
        )
    )


def _entry(plane: nu.Str, at: nu.Nu) -> nu.Nu:
    """One entry's arm: its child up while it is in the window, redrawn as the engine writes it."""
    key = nu.Str(at)
    entry = agents.trace(plane).entries[key]
    message = ENTRIES[key].to(nustd.ui.MessageRef.slot())
    notice = ENTRIES[key].to(nustd.ui.AlertRef.slot(variant="warn"))
    call = ENTRIES[key].to(nustd.ui.ToolCallRef.slot())
    text = nu.Str(entry.text.fallback(""))

    def by_kind(k: nu.ObjectRef) -> nu.Nu:
        kind = nu.Str(k)
        said = (
            ENTRIES.insert(message)
            >> message.set_role(kind)
            >> nu.Reconcile(
                nuspace.atomic(entry.text.on_change()), message.set(nuspace.atomic(text))
            )
        )
        told = ENTRIES.insert(notice) >> notice.set_body(nuspace.atomic(text))
        return nu.SwitchDo(
            kind,
            {
                "user": said,
                "agent": said,
                "thought": said,
                "notice": told,
                "tool": ENTRIES.insert(call) >> _tool(entry, call),
                "permission": _permission(plane, key, entry),
            },
            default=nu.Noop(),
        )

    # Placed in the window's order, whichever arm comes up first.
    order = nu.let(nuspace.atomic(_window(plane)), ENTRIES.set_order)
    live = nu.let(nuspace.atomic(nu.Str(entry.kind.fallback(""))), by_kind)
    leave = nu.TryCatch(ENTRIES.remove(key), catch=lambda _: nu.Noop())
    return nu.TryCatch(nu.ParallelAsync(live, order), finally_=leave)


def _entries(plane: nu.Str) -> nu.Nu:
    """One arm per entry in the window, kept in step with the trace and the window's size."""
    change = nu.OnAny(agents.trace(plane).entries.on_children_change(), HELD.shown.on_change())
    keys = nuspace.atomic(_window(plane))
    return nu.ReconcileLatestEach(keys, nuspace.atomic(change), lambda k: _entry(plane, k))


def _chat(plane: nu.Str) -> nu.Nu:
    """The chat on ``plane``: header, entries, plan, composer, all live."""
    composer = CHAT.composer

    def ask(sub: nu.Nu) -> nu.Nu:
        return agents.ask(plane, nu.Str(nu.Dict(sub)["value"]), by=Here.cell)

    stop = agents.cancel(plane)
    earlier = nuspace.atomic(HELD.shown.set(nu.Int(HELD.shown.fallback(PAGE)) + PAGE))
    draw = View.empty.erase() >> SETUP.erase() >> CHAT.init()
    return draw >> nu.ParallelAsync(
        _header(plane),
        _plan(plane),
        _entries(plane),
        nu.ReactEvery(composer.on_submit(), ask),
        nu.ReactEvery(composer.on_stop(), lambda _: stop),
        nu.ReactEvery(HEADER.stop.on_click(), lambda _: stop),
        nu.ReactEvery(BODY.earlier.on_click(), lambda _: earlier),
    )


def _showing(at: nu.ObjectRef) -> nu.Nu:
    plane = nu.Str(at)
    return nu.IfDo(plane == "", _setup(), _chat(plane))


def out() -> nu.Nu:
    """Setup until the cell has an agent plane, then the chat on it."""
    held = nuspace.atomic(nu.Str(HELD.plane.fallback("")))
    return nu.ReconcileLatest(held, nuspace.atomic(HELD.plane.on_change()), _showing)


CELL = CellSpec(
    "chat",
    "Agent chat",
    source(__name__),
    description="Chat with a coding agent, Claude Code or Codex, run on a plane of its own.",
    group="Agents",
    icon="bot",
)
