"""The Chat page: a conversation with an agent, where the page's cells are the conversation.

The page keeps nothing of its own: every cell on it reads the engine's plane
state (:class:`~.state.Chat`), and they run while a tab has the page open.
The page starts as one cell, the composer, and the conversation grows above
it, a cell at a time:

- ``composer``: a box, Send and Stop, and the status by them (thinking,
  running, stopped or error, nothing while idle). Its first run makes sure
  the engine, its reaction and the agent settings are there (:func:`ensure`).
- ``said``: one per message the person sends (:func:`tell`). What they said,
  and under it the trace of the agent's work on it: each turn's program,
  what came back and how it went, folded.
- ``answer``: what the agent adds itself (:func:`answer`), from its own
  program: any cell, a few lines of Markdown or a live table. It may change
  or remove the ones it added before.

The terms the cells use are here too, for anything else that drives a chat:
:func:`ensure`, :func:`tell`, :func:`say`, :func:`stop`, and :func:`answer`
for the agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
import nustd.ui
from nu.lang import ScalarQuery
from nuagent.protocol import CONSTRUCT, NO_CODE, OK, RUNTIME
from nuspace import ops
from nuspace.ops.utils import MintId
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.shell import Shell
from nuspace.system.devices.web.utils import CellRoot
from nuspace.system.services import enable_react
from nuspace.system.utils import redraws, snap

from . import settings
from .engine import IMPORTS, MADE_BY, SOURCE, engine_cell, engine_of, inbox_change
from .ext import said_prog
from .state import ERROR, IDLE, RUNNING, STOPPED, THINKING, Chat


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = [
    "ANSWER_BY",
    "SAID_BY",
    "Builds",
    "answer",
    "composer",
    "ensure",
    "said",
    "say",
    "stop",
    "tell",
]


#: What a cell the agent adds records as ``made_by``.
ANSWER_BY = "nuagent.answer"

#: What a cell a message adds records as ``made_by``.
SAID_BY = "nuagent.said"

#: The composer cell's name: messages and answers go on the page above it.
BOX = "composer"

#: The pill's tone per status shown.
TONES = {IDLE: "neutral", THINKING: "info", RUNNING: "warn", STOPPED: "neutral", ERROR: "danger"}

#: The badge's variant per outcome kind.
VARIANTS = {OK: "ok", NO_CODE: "neutral", CONSTRUCT: "warn", RUNTIME: "danger"}

#: The fold's title per outcome kind: how the turn's program went, in words.
TITLES = {
    OK: "Program ran",
    NO_CODE: "No program",
    CONSTRUCT: "Program did not build",
    RUNTIME: "Program failed",
}


def ensure(page: nu.StrArg) -> nu.Nu:
    """The page's engine, its cell, its reaction and the agent settings, each made when missing.

    Idempotent, and safe from two tabs at once: the engine and its cell
    have fixed ids, and the reaction is :func:`enable_react`'s, which is
    idempotent itself.

    Args:
        page: The chat page.
    """
    engine = engine_of(page)
    cell = engine_cell(engine)
    plane = ops.add_plane(
        engine, backend="async", name="engine", parent=page, ui=False, made_by=MADE_BY
    )
    made = nu.IfDo(snap(ops.plane_exists(engine).not_()), plane) >> nu.IfDo(
        snap(ops.cell_exists(cell).not_()),
        ops.add_cell(engine, SOURCE, cell_id=cell, name="engine"),
    )
    reaction = enable_react(inbox_change(engine), engine, imports=IMPORTS)
    return made >> settings.ensure() >> reaction


def say(engine: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """``text`` into the engine's inbox: its reaction runs it. One commit."""
    return ops.atomic_state(ops.plane_state(engine, Chat.inbox.append(text)))


def _above(page: nu.StrArg) -> nu.Int:
    """Where a new cell goes on the page: the composer's place, the end when it has none. Bare read."""
    cells = ops.cells(page)
    box = ops.cell_named(page, BOX)
    return nu.Int(nu.If(cells.contains(box), cells.index(box), cells.len()))


def tell(page: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """The person's message: a said cell on the page above the composer, then ``text`` into the inbox.

    Two commits, the cell first, so it is on the page before anything the
    agent adds for it. The cell knows its message by its place in the
    inbox, baked into its prog (:func:`~.ext.said_prog`), and reads the text
    from there: the inbox stays the one place it is kept. Two tabs sending
    at the same moment can both read the same place.
    """
    engine = engine_of(page)

    def placed(at: nu.ObjectRef) -> nu.Nu:
        cell = ops.add_cell(
            page, said_prog(nu.Int(at)), name="said", index=_above(page), made_by=SAID_BY
        )
        return cell >> say(engine, text)

    return nu.let(snap(ops.plane_state(engine, Chat.inbox.len())), placed)


def stop(engine: nu.StrArg) -> nu.Nu:
    """Stop the engine: every message sent so far counted handled, then its live runs stopped.

    The cursor first, so a run between two messages finds nothing more and
    ends on its own, then each live run interrupted (killed after the grace
    when a call will not let go). What it said so far stays.
    """
    handled = Chat.cursor.set(Chat.inbox.len()) >> Chat.status.set(STOPPED)
    live = snap(nu.list(Space.kernel.planes_running[engine].runs))
    stopping = nu.ForEachDo(live, lambda run: ops.plane_stop(nu.Str(run)))
    return ops.atomic_state(ops.plane_state(engine, handled)) >> stopping


# --- answer ---------------------------------------------------------------------


# In process, as nuspace builds a prog to see whether it draws.
_BRACE = nu.prog.PyBrace()


def _stands(built: object, plane: str, cell: str) -> bool:
    """True when what construction gave back is a term the page would run. Raises when not.

    Rewritten the way the kernel rewrites a page cell (rerooted, then its ui
    under the cell's node on the viewer), then compiled and validated, as
    the kernel's ``Eval`` does before it drives it.
    """
    if not isinstance(built, nu.Nu):
        msg = f"the answer does not build: {built}"
        raise ValueError(msg)
    term = CellRoot(Shell.viewer, cell)(Reroot(plane, cell)(built))
    try:
        nu.validate(nu.compile(term))
    except Exception as err:
        msg = f"the answer builds but would not run: {err}"
        raise ValueError(msg) from err
    return True


def _paged(plane: object) -> str:
    """The page, or a raise when there is none: :func:`answer` ran outside a chat's engine."""
    if not plane:
        msg = "answer has no page to add to: it runs from a chat's engine"
        raise ValueError(msg)
    return str(plane)


class Builds(ScalarQuery):
    """True when ``prog`` builds as cell ``cell_id`` of ``plane_id`` would, and validates. Raises when not.

    Construction runs the snippet's module code in this process, offered the
    ``plane`` and ``cell`` a run offers, as the kernel would on the page.
    What fails raises ``ValueError``, with the construction's diagnostic or
    the validation's message.
    """

    def __init__(self, prog: nu.StrArg, plane_id: nu.StrArg, cell_id: nu.StrArg) -> None:
        super().__init__(prog, plane_id, cell_id)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        prog, plane, cell = children

        def thunk(rt: Runtime) -> object:
            p, c = _paged(plane(rt)), str(cell(rt))
            built = _BRACE.construct(str(prog(rt)), scope={"plane": p, "cell": c})
            return _stands(built, p, c)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        prog, plane, cell = children

        async def athunk(rt: Runtime) -> object:
            p, c = _paged(await plane(rt)), str(await cell(rt))
            built = await _BRACE.aconstruct(str(await prog(rt)), scope={"plane": p, "cell": c})
            return _stands(built, p, c)

        return athunk


def answer(source: nu.StrArg, *, into: nu.Ref | None = None) -> nu.Nu:
    """Add a cell to the chat page, above the composer: the agent's answer to the person.

    Called from the agent's program, which runs as the engine's cell: the
    page is the engine's parent. The source is built first, the way the page
    will build it, and one that does not build raises (``ValueError``),
    nothing added. Then it is written as one commit, ``made_by``
    :data:`ANSWER_BY`, and runs on the page like any cell while a tab has it
    open.

    Args:
        source: The cell's source: a module with ``out()``, as any cell.
        into: Set to the new cell's id, for a program that edits it after.
    """
    page = snap(ops.parent(ops.Here.plane))

    def placed(on: nu.ObjectRef) -> nu.Nu:
        def built(minted: nu.ObjectRef) -> nu.Nu:
            cid = nu.Str(minted)
            add = ops.add_cell(
                nu.Str(on),
                source,
                cell_id=cid,
                name="answer",
                index=_above(nu.Str(on)),
                made_by=ANSWER_BY,
                into=into,
            )
            return nu.IfDo(Builds(source, nu.Str(on), cid), add)

        return nu.let(MintId("c"), built)

    return nu.let(page, placed)


# --- said --------------------------------------------------------------------


class Bubble(nustd.ui.Box):
    text = nustd.ui.MarkdownRef.slot()


class Said(nustd.ui.Row):
    bubble = Bubble.slot(padding="sm", border="none", background="muted")


class Ran(nustd.ui.Collapsible):
    kind = nustd.ui.BadgeRef.slot()
    program = nustd.ui.CodeRef.slot(language="python", max_height=360)
    observation = nustd.ui.CodeRef.slot(wrap=True, max_height=240)


class Trace(nustd.ui.Collapsible):
    steps = nustd.ui.ColumnRef.slot(Ran, gap=2)


class Message(nustd.ui.Column):
    said = Said.slot(justify="end")
    trace = Trace.slot(title="working...")


def _step(pair: nu.Nu) -> nu.Nu:
    """One turn, keyed by its place among all turns."""
    at, kept = nu.Tuple(pair)[0], nu.Dict(nu.Tuple(pair)[1])
    return nu.Dict.of(
        key="t" + nu.str(at),
        title=nu.Dict(TITLES).get_item(kept["kind"], "Program"),
        program=kept["program"],
        observation=kept["observation"],
        kind=kept["kind"],
        variant=nu.Dict(VARIANTS).get_item(kept["kind"], "neutral"),
    )


def _trace(at: nu.IntArg) -> nu.Nu:
    """Message ``at`` as plain data: its text, its turns, and whether it is handled. Bare, on the engine's state.

    The text is ``""`` until it lands: the cell is on the page before the
    message is in the inbox.
    """
    mine = Chat.turns.iter().enumerate().filter(lambda p: nu.Dict(nu.Tuple(p)[1])["at"] == at)
    return nu.Dict.of(
        text=nu.If(Chat.inbox.len() > at, Chat.inbox[at], ""),
        steps=mine.map(_step).to_list(),
        done=Chat.cursor.fallback(0) > at,
    )


def _title(steps: nu.List, done: nu.Nu) -> nu.Str:
    """The trace's title: ``3 steps · ok`` once handled, ``working...`` until then."""
    n = steps.len()
    count = nu.str(n) + nu.Str(nu.If(n == 1, " step", " steps"))
    last = nu.If(n > 0, nu.Dict(steps.last_elem()).get_item("kind", ""), "")
    working = nu.If(n == 0, "working...", count + " · working...")
    handled = nu.If(n == 0, "no steps", count + " · " + nu.Str(last))
    return nu.Str(nu.If(done, handled, working))


def said(page: nu.StrArg, at: nu.IntArg) -> nu.Nu:
    """The said cell: message ``at``, and the trace of the agent's work on it, drawn again as it grows."""
    engine = engine_of(page)
    trace = Message.trace

    def turn(t: nu.Nu) -> nu.Nu:
        s = nu.Dict(t)
        ran = trace.steps[s["key"]]
        return (
            ran.set(title=s["title"])
            >> ran.kind.set(s["kind"], variant=s["variant"])
            >> ran.program.set(s["program"])
            >> ran.observation.set(s["observation"])
        )

    def draw(seen: nu.Nu) -> nu.Nu:
        s = nu.Dict(seen)
        steps = nu.List(s["steps"])
        text = Message.said.bubble.text.set(s["text"])
        return text >> trace.set(title=_title(steps, s["done"])) >> nu.ForEachDo(steps, turn)

    moves = [Chat.inbox.on_change(), Chat.turns.on_change(), Chat.cursor.on_change()]
    return redraws(
        [ops.plane_state(engine, m) for m in moves], ops.plane_state(engine, _trace(at)), draw
    )


# --- status, drawn by the composer ----------------------------------------------------------------------


def _shown() -> nu.Nu:
    """The status as the page shows it. Bare, on the engine's state.

    Thinking reads as running while the latest reply's program runs: the
    conversation ends on the model's message until the observation lands.
    """
    kept = Chat.status.fallback(IDLE)
    last = nu.If(
        Chat.messages.len() > 0, nu.Dict(Chat.messages.last_elem()).get_item("role", ""), ""
    )
    running = (kept == THINKING).and_(nu.Str(last) == "assistant")
    shown = nu.Str(nu.If(running, RUNNING, kept))
    return nu.Dict.of(
        status=shown,
        tone=nu.Dict(TONES).get_item(shown, "neutral"),
        error=nu.If(kept == ERROR, Chat.error.fallback(""), ""),
    )


# --- composer --------------------------------------------------------------------


class Actions(nustd.ui.Row):
    pill = nustd.ui.StatusPillRef.slot()
    send = nustd.ui.ButtonRef.slot(label="Send", icon="send")
    stop = nustd.ui.ButtonRef.slot(label="Stop", variant="secondary", icon="square")


class Composer(nustd.ui.Column):
    error = nustd.ui.AlertRef.slot(variant="danger")
    text = nustd.ui.TextAreaRef.slot(placeholder="Message the agent", rows=3, auto_resize=True)
    actions = Actions.slot(gap=2, justify="end", align="center")


def composer(page: nu.StrArg) -> nu.Nu:
    """The composer cell: the engine made sure of, then Send and Stop, and the status by them.

    Send puts the message on the page and in the inbox (:func:`tell`). The
    status pill shows while the engine works and is gone while idle, Stop
    is live only while it thinks, and a failure shows above the box.
    """
    engine = engine_of(page)
    box, actions = Composer.text, Composer.actions

    def sent(typed: nu.Nu) -> nu.Nu:
        text = nu.Str(typed)
        return nu.IfDo(text != "", tell(page, text) >> box.set(""))

    def draw(seen: nu.Nu) -> nu.Nu:
        s = nu.Dict(seen)
        shown = nu.Str(s["status"])
        pill = nu.IfDo(shown == IDLE, actions.pill.erase(), actions.pill.set(shown, tone=s["tone"]))
        failed = Composer.error.set("The last message failed", body=s["error"])
        error = nu.IfDo(nu.Str(s["error"]) != "", failed, Composer.error.erase())
        idle = (shown != THINKING).and_(shown != RUNNING)
        return pill >> error >> actions.stop.set_disabled(idle)

    moves = [Chat.status.on_change(), Chat.messages.on_change(), Chat.inbox.on_change()]
    on = [ops.plane_state(engine, m) for m in moves]
    placed = box.set("") >> actions.send.set("Send") >> actions.stop.set("Stop", disabled=True)
    return (
        ensure(page)
        >> placed
        >> nu.ParallelAsync(
            redraws(on, ops.plane_state(engine, _shown()), draw, every=5.0),
            nu.ReactForever(actions.send.on_click(), nu.let(nu.Str(box).strip(), sent)),
            nu.ReactForever(actions.stop.on_click(), stop(engine)),
        )
    )
