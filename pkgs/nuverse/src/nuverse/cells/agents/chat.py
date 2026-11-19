"""A chat cell: a view on one agent plane, its conversation and a composer.

The cell keeps one thing in its own state: the agent plane's id
(:class:`Chat`). The plane holds the conversation and runs the engine
(:mod:`nuverse.agents`); this cell only reads its trace and writes asks,
so two tabs on one chat are two views on one engine.

- **Setup**, the first time: pick an agent among the installed ones,
  preselected when there is one, an empty state when there is none (one
  for no agent CLI, another for no ACP SDK). Start makes the plane
  (:func:`nuverse.agents.add`), its folder the space's.
- **Header**: the title (or "New chat"), the agent, context used and
  size, cost and status.
- **Entries**: one keyed child per trace entry, every one of them, flat:
  the pane around the cell scrolls. Each redraws from its own slots as the
  engine writes them. A user message is a quiet card on the right, an
  agent reply markdown, a thought a quote, a tool call a collapsible with
  its content, diffs and locations folded under a header row, a notice an
  alert.
- **Permission**: a card with the request's options as buttons, answered
  through :func:`nuverse.agents.answer`; settled, the buttons go and a
  badge says how.
- **Plan** above the composer, and the **composer**, a form around an
  editable markdown that asks on shift+Enter or Send, with Stop while a
  turn runs.

Everything drawn is a generic ui-kit component through its ``nustd.ui`` ref.
"""

from __future__ import annotations

import importlib.util

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.places import Here
from nuspace.specs import CellSpec
from nuverse import agents

from .. import source


__all__ = ["CELL", "Chat", "View", "out"]


class Chat(nu.Shape):
    """The cell's own state: its agent plane."""

    plane = nustd.kv.StrRef.slot()


# --- what the cell draws -----------------------------------------------------------------------


class Setup(nustd.ui.Card):
    """The first step: which agent, then Start."""

    agent = nustd.ui.SelectRef.slot(label="Agent")
    start = nustd.ui.ButtonRef.slot(label="Start chat", icon="message-square")


class Header(nustd.ui.Row):
    """The chat's title, agent, usage, cost and status."""

    title = nustd.ui.HeadingRef.slot(level=3)
    agent = nustd.ui.BadgeRef.slot(variant="secondary", size="sm")
    usage = nustd.ui.TextRef.slot(value="", size="sm", tone="muted")
    cost = nustd.ui.TextRef.slot(value="", size="sm", tone="muted")
    status = nustd.ui.StatusPillRef.slot()


class Bubble(nustd.ui.Card):
    """A user message's card: the text as markdown."""

    text = nustd.ui.MarkdownRef.slot()


class Said(nustd.ui.Column):
    """A user message: its card, against the right edge."""

    bubble = Bubble.slot(variant="sunken", size="sm", max_width="85%")


class ThoughtHead(nustd.ui.Row):
    """A thought's header line."""

    icon = nustd.ui.IconRef.slot(name="brain", size="sm")
    label = nustd.ui.TextRef.slot(value="Thinking", size="sm", weight="medium")


class Thought(nustd.ui.Quote):
    """A thought: a header line over the text, quiet."""

    header = ThoughtHead.slot(gap=2)
    text = nustd.ui.MarkdownRef.slot()


class ToolHead(nustd.ui.Row):
    """A tool call's trigger row: its kind's icon, its title cut to one line, its status."""

    icon = nustd.ui.IconRef.slot(name="wrench", size="sm", tone="muted")
    title = nustd.ui.TextRef.slot(size="sm", lines=1)
    status = nustd.ui.BadgeRef.slot(size="sm")


class ToolCall(nustd.ui.Collapsible):
    """A tool call: the head row, its content pieces and the places it touched folded under it."""

    header = ToolHead.slot(gap=2, grow={"title": 1})
    content = nustd.ui.ColumnRef.slot(gap=2)
    locations = nustd.ui.ListRef.slot()


class DiffPiece(nustd.ui.Column):
    """One diff in a tool call's content: the file, then the change."""

    path = nustd.ui.TextRef.slot(size="sm", tone="muted", mono=True, lines=1)
    code = nustd.ui.CodeRef.slot(original="", wrap=True)


class PermissionHead(nustd.ui.Row):
    """A permission card's header: a mark, the question, how it stands."""

    icon = nustd.ui.IconRef.slot(name="shield-question", size="sm", tone="warn")
    title = nustd.ui.TextRef.slot(weight="medium", lines=1)
    state = nustd.ui.BadgeRef.slot(size="sm")


class Permission(nustd.ui.Card):
    """A permission request: the question, the tool it is for, the options while it is open."""

    header = PermissionHead.slot(gap=2, grow={"title": 1})
    details = nustd.ui.TextRef.slot(size="sm", tone="muted", mono=True)
    options = nustd.ui.RowRef.slot(gap=2, wrap=True)


class Step(nustd.ui.Row):
    """One plan entry: a dot for its status, its text."""

    dot = nustd.ui.StatusDotRef.slot()
    text = nustd.ui.TextRef.slot(size="sm")


class Plan(nustd.ui.Card):
    """The agent's plan, one row per entry."""

    steps = nustd.ui.ColumnRef.slot(gap=1)


class Actions(nustd.ui.Row):
    """The composer's buttons: Stop while a turn runs, then Send."""

    stop = nustd.ui.ButtonRef.slot(label="Stop", icon="square", variant="secondary", size="sm")
    send = nustd.ui.ButtonRef.slot(label="Send", icon="arrow-up", size="sm", submit=True)


class Composer(nustd.ui.Form):
    """An editable markdown and its buttons: shift+Enter or Send asks, and the text clears."""

    text = nustd.ui.MarkdownRef.slot(placeholder="Message the agent...", readonly=False)
    actions = Actions.slot(gap=2, justify="end")


class Input(nustd.ui.Card):
    """The composer's frame, so the editable text reads as a box to type in."""

    composer = Composer.slot(gap=2, clear_on_submit=True)


class Conversation(nustd.ui.Column):
    """The whole chat: header, entries, plan, composer. Flat: the pane scrolls."""

    header = Header.slot(gap=2, align="center", grow={"title": 1}, wrap=True)
    entries = nustd.ui.ColumnRef.slot(gap=3)
    plan = Plan.slot(title="Plan", size="sm")
    box = Input.slot(size="sm")


class View(nu.Shape):
    """The cell's roots: an empty state, the setup step, or the chat."""

    empty = nustd.ui.EmptyStateRef.slot(
        label="No agent installed",
        description="Install Node.js and the claude or codex CLI, then add this cell again.",
        icon="bot",
        size="sm",
    )
    no_sdk = nustd.ui.EmptyStateRef.slot(
        label="Agent support not installed",
        description="The ACP SDK nuverse depends on is missing: reinstall nuverse, then add this cell again.",
        icon="bot",
        size="sm",
    )
    setup = Setup.slot(gap=3)
    chat = Conversation.slot(gap=3)


HELD = nuspace.here(Chat)
SETUP, CHAT = View.setup, View.chat
HEADER, ENTRIES, PLAN, COMPOSER = CHAT.header, CHAT.entries, CHAT.plan, CHAT.box.composer


# --- text the cell shows -------------------------------------------------------------------------


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


def _get(held: object, key: str, default: object = "") -> object:
    value = held.get(key) if isinstance(held, dict) else None
    return default if value is None else value


#: ACP tool kinds, by the lucide icon each draws.
_TOOL_ICONS = {
    "read": "file-text",
    "edit": "pencil",
    "delete": "trash-2",
    "move": "move",
    "search": "search",
    "execute": "terminal",
    "think": "brain",
    "fetch": "globe",
    "switch_mode": "toggle-left",
}

#: ACP tool statuses, by the badge variant each draws.
_TOOL_TONES = {"pending": "neutral", "in_progress": "info", "completed": "ok", "failed": "danger"}

#: File suffixes, by the language name the code view highlights them with.
_LANGUAGES = {
    "py": "python",
    "pyi": "python",
    "ts": "typescript",
    "tsx": "tsx",
    "js": "javascript",
    "jsx": "jsx",
    "mjs": "javascript",
    "md": "markdown",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "rs": "rust",
    "go": "go",
    "css": "css",
    "html": "html",
    "sql": "sql",
}


def _tool_head(tool: object) -> dict[str, str]:
    """What a tool call's header row shows: icon, title, status label and its tone."""
    t = tool if isinstance(tool, dict) else {}
    status = str(t.get("status") or "pending")
    return {
        "icon": _TOOL_ICONS.get(str(t.get("kind") or ""), "wrench"),
        "title": str(t.get("title") or "Tool call"),
        "status": status.replace("_", " "),
        "tone": _TOOL_TONES.get(status, "dashed"),
    }


def _pieces(tool: object) -> list[dict[str, object]]:
    """A tool call's content as the pieces drawn, each keyed by its kind and its place.

    A diff (``kind`` ``diff``: path, old and new text, language) or a text
    block (``kind`` ``text``); any other content draws nothing. The kind is
    in the key, so a place whose piece changes kind gets a new child.
    """
    content = (tool if isinstance(tool, dict) else {}).get("content") or []
    out: list[dict[str, object]] = []
    for i, c in enumerate(content if isinstance(content, list) else []):
        if not isinstance(c, dict):
            continue
        if c.get("type") == "diff":
            path = str(c.get("path") or "")
            suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            out.append(
                {
                    "key": f"diff:{i}",
                    "kind": "diff",
                    "path": path,
                    "old": c.get("old_text") or "",
                    "new": c.get("new_text") or "",
                    "language": _LANGUAGES.get(suffix, ""),
                }
            )
            continue
        block = c.get("content") if isinstance(c.get("content"), dict) else {}
        if block.get("type") == "text":
            out.append({"key": f"text:{i}", "kind": "text", "text": str(block.get("text") or "")})
    return out


def _keys(pieces: object) -> list[str]:
    return [str(p["key"]) for p in pieces or () if isinstance(p, dict)]


def _locations(tool: object) -> list[str]:
    """The places a tool call touched, ``path:line`` each."""
    found = (tool if isinstance(tool, dict) else {}).get("locations") or []
    out = []
    for loc in found if isinstance(found, list) else []:
        if isinstance(loc, dict) and loc.get("path"):
            line = loc.get("line")
            out.append(f"{loc['path']}:{line}" if line is not None else str(loc["path"]))
    return out


def _permission_view(permission: object, tool: object) -> dict[str, object]:
    """What a permission card shows: the question, the tool's details, its state, open or not."""
    p = permission if isinstance(permission, dict) else {}
    t = tool if isinstance(tool, dict) else {}
    title = t.get("title")
    kind = str(t.get("kind") or "")
    details = "  ".join(x for x in [kind, *_locations(t)] if x)
    outcome, answer = str(p.get("outcome") or ""), str(p.get("answer") or "")
    options = [o for o in p.get("options") or () if isinstance(o, dict)]
    if outcome in ("cancelled", "expired"):
        state, tone, open_ = outcome, "dashed", False
    elif answer:
        chosen = next((o for o in options if o.get("option_id") == answer), {})
        state = str(chosen.get("name") or answer)
        tone = "danger" if str(chosen.get("kind") or "").startswith("reject") else "ok"
        open_ = False
    else:
        state, tone, open_ = "waiting", "warn", True
    return {
        "title": f"Allow {title}?" if title else "Allow this tool call?",
        "details": details,
        "state": state,
        "tone": tone,
        "open": open_,
    }


def _option_variant(option: object) -> str:
    """An option button's look: allow once is the primary one, the rest step back."""
    kind = str((option if isinstance(option, dict) else {}).get("kind") or "")
    return "primary" if kind == "allow_once" else "secondary"


#: ACP plan entry statuses, by the dot tone each draws.
_STEP_TONES = {"completed": "ok", "in_progress": "info", "pending": "neutral"}


def _steps(plan: object) -> list[dict[str, object]]:
    """The plan's entries as rows: key, text, dot tone, and whether the dot pulses."""
    out = []
    for i, e in enumerate(plan if isinstance(plan, list) else []):
        e = e if isinstance(e, dict) else {}
        status = str(e.get("status") or "pending")
        out.append(
            {
                "key": f"s{i}",
                "text": str(e.get("content") or ""),
                "tone": _STEP_TONES.get(status, "neutral"),
                "label": status.replace("_", " "),
                "pulse": status == "in_progress",
            }
        )
    return out


def _has_sdk() -> bool:
    return importlib.util.find_spec("acp") is not None


#: ``held[key]``, or ``default`` when it is missing or None.
Get = nu.host(_get, name="Get")
UsageText = nu.host(_usage_text, name="UsageText")
CostText = nu.host(_cost_text, name="CostText")
Tone = nu.host(_tone, name="Tone")
ToolHeadOf = nu.host(_tool_head, name="ToolHeadOf")
Pieces = nu.host(_pieces, name="Pieces")
Keys = nu.host(_keys, name="Keys")
Locations = nu.host(_locations, name="Locations")
PermissionView = nu.host(_permission_view, name="PermissionView")
OptionVariant = nu.host(_option_variant, name="OptionVariant")
Steps = nu.host(_steps, name="Steps")
#: Whether the ACP SDK is importable here: without it no agent is installed, whatever is on PATH.
HasSdk = nu.host(_has_sdk, name="HasSdk")


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
        # No agent is installed without the SDK, so say which is missing.
        none = nu.IfDo(HasSdk(), View.empty.init(), View.no_sdk.init())
        return nu.IfDo(
            found,
            View.empty.erase()
            >> View.no_sdk.erase()
            >> draw
            >> nu.ReactOnce(SETUP.start.on_click(), start),
            none,
        )

    return CHAT.erase() >> nu.let(agents.installed(), shown)


# --- the chat ----------------------------------------------------------------------------------


def _header(plane: nu.Str) -> nu.Nu:
    """The header, and Stop shown while a turn runs, redrawn when the Session moves."""
    session, spec = agents.session(plane), agents.spec(plane)
    status = nu.Str(session.status.fallback(agents.ASLEEP))
    title = nu.Str(session.title.fallback(""))
    usage = session.usage.fallback({})
    busy = (status == agents.PROMPTING).or_(status == agents.WAITING)
    stop = COMPOSER.actions.stop

    def draw(held: nu.ObjectRef) -> nu.Nu:
        h = nu.Dict(held)
        return (
            HEADER.title.set(nu.If(nu.Str(h["title"]) == "", "New chat", h["title"]))
            >> HEADER.agent.set_label(h["agent"])
            >> HEADER.usage.set(UsageText(h["usage"]))
            >> HEADER.cost.set(CostText(h["usage"]))
            >> HEADER.status.set(h["status"], tone=Tone(h["status"]))
            >> nu.IfDo(h["busy"], stop.display(), stop.hide())
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
    """The plan above the composer, a row per entry, replaced whole as the Agent sends it; hidden while empty."""
    plan = agents.session(plane).plan
    steps = PLAN.steps

    def draw(held: nu.ObjectRef) -> nu.Nu:
        rows = nu.List(Steps(held))

        def row(s: nu.Nu) -> nu.Nu:
            d = nu.Dict(s)
            step = steps[nu.Str(d["key"])].to(Step.slot(gap=2))
            return step.dot.set(d["tone"], label=d["label"], pulse=d["pulse"]) >> step.text.set(
                d["text"]
            )

        shown = nu.ForEachDo(rows, row) >> steps.keep(Keys(rows)) >> PLAN.display()
        return nu.IfDo(rows, shown, PLAN.hide())

    redraw = nu.let(nuspace.atomic(nu.If(plan.exists(), plan.extract(), [])), draw)
    return nu.Reconcile(nuspace.atomic(plan.on_change()), redraw)


def _keys_of(plane: nu.Str) -> nu.List:
    """Every entry key, oldest first."""
    return nu.List(nu.list(agents.trace(plane).entries.keys()))


def _tool(entry: agents.Entry, call: ToolCall) -> nu.Nu:
    """A tool entry: its head row, then each piece of its content, a diff or text, and its locations."""
    tool = entry.tool
    head, content = call.header, call.content

    def draw(held: nu.ObjectRef) -> nu.Nu:
        h = nu.Dict(ToolHeadOf(held))
        pieces = nu.List(Pieces(held))
        places = nu.List(Locations(held))

        def piece(p: nu.Nu) -> nu.Nu:
            d = nu.Dict(p)
            at = nu.Str(d["key"])
            diff = content[at].to(DiffPiece.slot(gap=1))
            text = content[at].to(nustd.ui.MarkdownRef.slot())
            return nu.IfDo(
                nu.Str(d["kind"]) == "diff",
                diff.path.set(d["path"])
                >> diff.code.set_language(d["language"])
                >> diff.code.set(d["new"], original=d["old"]),
                text.set(d["text"]),
            )

        drawn = (
            head.icon.set(h["icon"])
            >> head.title.set(h["title"])
            >> head.status.set(h["status"], variant=h["tone"])
        )
        # Pieces gone from the content go from the view, and the rest keep its order.
        keys = Keys(pieces)
        listed = call.locations.set(places) >> call.locations.display()
        return (
            drawn
            >> nu.ForEachDo(pieces, piece)
            >> content.keep(keys)
            >> content.set_order(keys)
            >> nu.IfDo(places, listed, call.locations.hide())
        )

    redraw = nu.let(nuspace.atomic(tool.extract()), draw)
    return nu.Reconcile(nuspace.atomic(tool.on_change()), redraw)


def _permission(plane: nu.Str, key: nu.Str, entry: agents.Entry) -> nu.Nu:
    """A permission entry: a card answered through ``agents.answer``; settled, its state alone."""
    card = ENTRIES[key].to(Permission.slot(size="sm", variant="outline"))
    head = card.header
    entries = agents.trace(plane).entries
    permission = entry.permission
    options = nu.List(nuspace.atomic(permission["options"].fallback([])))

    def draw(held: nu.ObjectRef) -> nu.Nu:
        p = nu.Dict(held)
        call = entries[nu.Str("tool:") + nu.Str(Get(p, "tool_call_id", ""))].tool
        tool = nuspace.atomic(nu.If(call.exists(), call.extract(), {}))
        v = nu.Dict(PermissionView(p, tool))
        return (
            head.title.set(v["title"])
            >> head.state.set(v["state"], variant=v["tone"])
            >> card.details.set(v["details"])
            >> nu.IfDo(v["open"], card.options.display(), card.options.hide())
        )

    redraw = nu.let(nuspace.atomic(permission.extract()), draw)

    def button(o: nu.Nu) -> nustd.ui.ButtonRef:
        oid = nu.Str(nu.Dict(o)["option_id"])
        return card.options[oid].to(nustd.ui.ButtonRef.slot(size="sm"))

    def offer(o: nu.Nu) -> nu.Nu:
        d = nu.Dict(o)
        return button(o).set(d["name"], variant=OptionVariant(d))

    def listen(o: nu.Nu) -> nu.Nu:
        oid = nu.Str(nu.Dict(o)["option_id"])
        # A request settled meanwhile refuses it; the redraw shows how it settled.
        picked = nu.TryCatch(agents.answer(plane, key, oid), catch=lambda _: redraw)
        return nu.ReactEvery(button(o).on_click(), lambda _: picked)

    return (
        ENTRIES.insert(card)
        >> nu.ForEachDo(options, offer)
        >> nu.ParallelAsync(
            nu.Reconcile(nuspace.atomic(permission.on_change()), redraw),
            nu.ForEachParAsync(options, listen),
        )
    )


def _entry(plane: nu.Str, at: nu.Nu) -> nu.Nu:
    """One entry's arm: its child up while it is in the trace, redrawn as the engine writes it."""
    key = nu.Str(at)
    entry = agents.trace(plane).entries[key]
    said = ENTRIES[key].to(Said.slot(align="end"))
    reply = ENTRIES[key].to(nustd.ui.MarkdownRef.slot())
    thought = ENTRIES[key].to(Thought.slot(gap=1))
    notice = ENTRIES[key].to(nustd.ui.AlertRef.slot(variant="warn"))
    call = ENTRIES[key].to(ToolCall.slot(gap=2))
    text = nuspace.atomic(nu.Str(entry.text.fallback("")))

    def follow(child: nu.Nu, body: nustd.ui.MarkdownRef) -> nu.Nu:
        # The text grows as chunks land: the whole of it again each time.
        return ENTRIES.insert(child) >> nu.Reconcile(
            nuspace.atomic(entry.text.on_change()), body.set(text)
        )

    def by_kind(k: nu.ObjectRef) -> nu.Nu:
        return nu.SwitchDo(
            nu.Str(k),
            {
                "user": follow(said, said.bubble.text),
                "agent": follow(reply, reply),
                "thought": follow(thought, thought.text),
                "notice": ENTRIES.insert(notice) >> notice.set_body(text),
                "tool": ENTRIES.insert(call) >> _tool(entry, call),
                "permission": _permission(plane, key, entry),
            },
            default=nu.Noop(),
        )

    # Placed in the trace's order, whichever arm comes up first.
    order = nu.let(nuspace.atomic(_keys_of(plane)), ENTRIES.set_order)
    live = nu.let(nuspace.atomic(nu.Str(entry.kind.fallback(""))), by_kind)
    leave = nu.TryCatch(ENTRIES.remove(key), catch=lambda _: nu.Noop())
    return nu.TryCatch(nu.ParallelAsync(live, order), finally_=leave)


def _entries(plane: nu.Str) -> nu.Nu:
    """One arm per entry, kept in step with the trace."""
    change = agents.trace(plane).entries.on_children_change()
    keys = nuspace.atomic(_keys_of(plane))
    return nu.ReconcileLatestEach(keys, nuspace.atomic(change), lambda k: _entry(plane, k))


def _chat(plane: nu.Str) -> nu.Nu:
    """The chat on ``plane``: header, entries, plan, composer, all live."""

    def ask(sub: nu.Nu) -> nu.Nu:
        typed = nu.Str(nu.Dict(sub)["values"]["text"])
        return nu.IfDo(typed.strip() != "", agents.ask(plane, typed, by=Here.cell))

    stop = agents.cancel(plane)
    draw = (
        View.empty.erase()
        >> View.no_sdk.erase()
        >> SETUP.erase()
        >> CHAT.init()
        >> PLAN.hide()
        >> COMPOSER.actions.stop.hide()
    )
    return draw >> nu.ParallelAsync(
        _header(plane),
        _plan(plane),
        _entries(plane),
        nu.ReactEvery(COMPOSER.on_submit(), ask),
        nu.ReactEvery(COMPOSER.actions.stop.on_click(), lambda _: stop),
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
