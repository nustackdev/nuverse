"""The Chat page: a conversation with an agent, where the page's cells are the conversation.

The page keeps nothing of the conversation: every cell on it reads the
engine's plane state (:class:`~.state.Chat`), and they run while a tab has
the page open. The page's own state holds only its engine's ids
(:class:`~.state.Engine`). The page starts as one cell, the composer, and
the conversation grows above it, a cell at a time:

- ``composer``: a box, Send and Stop, and the status by them (thinking,
  running, stopped or error, nothing while idle). Its first run makes sure
  the engine, its reaction and the agent settings are there (:func:`ensure`).
- ``said``: one per message the person sends (:func:`tell`). What they said,
  and under it the trace of the agent's work on it: each turn's program,
  what came back and how it went, folded.
- ``answer``: what the agent adds itself (:func:`answer`), from its own
  program: any cell, a few lines of Markdown or a live table. It may change
  or remove the ones it added before.

A new cell goes above the composer, which the page finds by the id its spec
kept under ``composer`` (:class:`~nuspace.specs.SpecCells`), never by name.

The terms the cells use are here too, for anything else that drives a chat:
:func:`ensure`, :func:`tell`, :func:`say`, :func:`stop`, and :func:`answer`
for the agent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
import nuspace
import nustd.ui
from nu.lang import ScalarQuery
from nuagent.protocol import CONSTRUCT, NO_CODE, OK, RUNTIME
from nuspace import Space
from nuspace.ops.interactions import Fabrics
from nuspace.places import Here
from nuspace.specs import SpecCells
from nuspace.system import reactions
from nuspace.utils import MintId
from nuspace.web.shell import Shell
from nuspace.web.utils import CellRoot

from . import settings
from .engine import IMPORTS, SOURCE, SPEC, conversation, engine_of, inbox_change, pending
from .ext import said_prog
from .state import ERROR, IDLE, RUNNING, STOPPED, THINKING, Chat, Engine


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = [
    "ANSWER_SPEC",
    "SAID_SPEC",
    "Builds",
    "answer",
    "composer",
    "ensure",
    "said",
    "say",
    "stop",
    "tell",
]


#: What a cell the agent adds records as ``spec``.
ANSWER_SPEC = "nuagent.answer"

#: What a cell a message adds records as ``spec``.
SAID_SPEC = "nuagent.said"

#: The composer cell's name in the spec: messages and answers go on the page above it.
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


def _linked(page: nu.StrArg) -> Engine:
    """The page's engine ids, in its own plane state. Builds refs, reads nothing."""
    return nuspace.at.plane(id=page).state(Engine)


def ensure(page: nu.StrArg) -> nu.Nu:
    """The page's engine, its cell, its lists, its reaction and the agent settings, each made when missing.

    Idempotent, in a row of short commits:

    1. The engine's and its cell's ids, minted once into the page's state
       (:class:`~.state.Engine`). Two tabs at once agree on them: the
       second finds the first one's.
    2. The engine plane under the page, with its one cell, when there is
       none at that id. The web never shows it.
    3. The conversation's lists, made with it: the page and the engine read
       them from the start.
    4. The agent settings (:func:`.settings.ensure`).
    5. The reaction on the engine's inbox, added when the page keeps none,
       its id kept in the page's state. Two tabs opening a new chat at the
       same moment can both add one.
    6. A run of the engine, when a message waits and none is live: a
       reaction fires on changes only, so messages sent while the space was
       closed, or before it bound, wait for a run started here.

    Args:
        page: The chat page.
    """
    linked = _linked(page)
    claimed = nuspace.atomic(linked.plane.init(MintId("p")) >> linked.cell.init(MintId("c")))

    def made(ids: nu.ObjectRef) -> nu.Nu:
        got = nu.Dict(ids)
        engine, cell = nu.Str(got["plane"]), nu.Str(got["cell"])
        plane = nuspace.plane.add(engine, parent=page, name="engine", backend="async", spec=SPEC)
        add = plane >> nuspace.cell.add(engine, SOURCE, id=cell, name="engine", fabrics=[])
        built = nuspace.atomic(nu.IfDo(nuspace.plane.exists(engine, removed=True).not_(), add))
        c = conversation(engine)
        lists = c.inbox.init(nu.List.create()) >> c.turns.init(nu.List.create())
        lists = nuspace.atomic(lists >> c.messages.init(nu.List.create()))
        reacting = reactions.add(
            inbox_change(engine), engine, imports=IMPORTS, into=linked.reaction
        )
        reaction = nu.IfDo(nuspace.atomic(linked.reaction.exists().not_()), reacting)
        waiting = nuspace.plane_run.any_live(engine).not_().and_(pending(engine))

        def caught_up(kept: nu.ObjectRef) -> nu.Nu:
            return nu.IfDo(nuspace.atomic(waiting), reactions.up_plane(engine, nu.Str(kept)))

        up = nu.let(nuspace.atomic(linked.reaction), caught_up)
        return built >> lists >> settings.ensure() >> reaction >> up

    read = nuspace.atomic(nu.Dict.of(plane=linked.plane, cell=linked.cell))
    return claimed >> nu.let(read, made)


def say(engine: nu.StrArg, text: nu.StrArg) -> nu.Nu:
    """``text`` into the engine's inbox: its reaction runs it. One commit."""
    return nuspace.atomic(conversation(engine).inbox.append(text))


def _above(page: nu.StrArg, add: Callable[..., nu.Nu]) -> nu.Nu:
    """``add(before=composer)`` while the composer is a live cell of the page, else ``add()``, the end. Bare.

    The composer is the id the page's spec kept under :data:`BOX`, one read.
    """
    box = nuspace.at.plane(id=page).state(SpecCells).ids[BOX]
    row = Space.cells[box]
    live = (row.plane.fallback("") == page).and_(row.removed_at.exists().not_())
    on_page = nu.If(nu.IsNull(box), False, live)
    return nu.IfDo(on_page, add(before=box), add())


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
        prog = said_prog(nu.Int(at))

        def add(**where: nu.StrArg) -> nu.Nu:
            return nuspace.cell.add(
                page, prog, name="said", spec=SAID_SPEC, fabrics=["ui"], **where
            )

        return nuspace.atomic(_above(page, add)) >> say(engine, text)

    return nu.let(nuspace.atomic(conversation(engine).inbox.len()), placed)


def stop(engine: nu.StrArg) -> nu.Nu:
    """Stop the engine: every message sent so far counted handled, then its live runs stopped.

    The cursor first, so a run between two messages finds nothing more and
    ends on its own, then each live run interrupted (killed after the grace
    when a call will not let go). What it said so far stays.
    """
    c = conversation(engine)
    handled = c.cursor.set(c.inbox.len()) >> c.status.set(STOPPED)
    ids = Space.exec.indexes.live.plane_to_plane_runs[engine].ids
    live = nuspace.atomic(nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([])))
    stopping = nu.ForEachDo(live, lambda run: nuspace.atomic(nuspace.plane_run.stop(nu.Str(run))))
    return nuspace.atomic(handled) >> stopping


# --- answer ---------------------------------------------------------------------


# In process, as nuspace builds a prog to see whether it draws.
_BRACE = nu.prog.PyBrace()


def _stands(built: object, plane: str, cell: str) -> bool:
    """True when what construction gave back is a term the page would run. Raises when not.

    Rewritten the way a tab's session rewrites a page cell (its ui under the
    cell's node on the viewer), then compiled and validated, as the
    kernel's ``Eval`` does before it drives it.
    """
    if not isinstance(built, nu.Nu):
        msg = f"the answer does not build: {built}"
        raise ValueError(msg)
    term = CellRoot(Shell.viewer, cell)(built)
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

    Construction runs the prog's module code in this process, offered the
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
    nothing added. Then its fabrics are worked out from that build, and it
    is written as one commit, ``spec`` :data:`ANSWER_SPEC`. It runs on the
    page like any cell while a tab has it open.

    Args:
        source: The cell's source: a module with ``out()``, as any cell.
        into: Set to the new cell's id once it is written, its own commit,
            for a program that edits it after.
    """
    page = nuspace.atomic(Space.planes[Here.plane].parent)

    def placed(on: nu.ObjectRef) -> nu.Nu:
        p = nu.Str(on)

        def built(minted: nu.ObjectRef) -> nu.Nu:
            cid = nu.Str(minted)

            def written(used: nu.ObjectRef) -> nu.Nu:
                def add(**where: nu.StrArg) -> nu.Nu:
                    return nuspace.cell.add(
                        p, source, id=cid, name="answer", spec=ANSWER_SPEC, fabrics=used, **where
                    )

                made = nuspace.atomic(_above(p, add))
                return made if into is None else made >> nuspace.atomic(into.set(cid))

            return nu.IfDo(Builds(source, p, cid), nu.let(Fabrics(source, p, cid), written))

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


def _trace(c: Chat, at: nu.IntArg) -> nu.Nu:
    """Message ``at`` as plain data: its text, its turns, and whether it is handled. Bare, on the conversation ``c``.

    The text is ``""`` until it lands: the cell is on the page before the
    message is in the inbox.
    """
    mine = c.turns.iter().enumerate().filter(lambda p: nu.Dict(nu.Tuple(p)[1])["at"] == at)
    return nu.Dict.of(
        text=nu.If(c.inbox.len() > at, c.inbox[at], ""),
        steps=mine.map(_step).to_list(),
        done=c.cursor.fallback(0) > at,
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
    """The said cell: message ``at``, and the trace of the agent's work on it, drawn again as it grows.

    A level flow with re-checks: a missed notification redraws late, never
    leaves the trace stale.
    """
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

    def follow(engine: nu.ObjectRef) -> nu.Nu:
        c = conversation(nu.Str(engine))
        changes = [c.inbox.on_change(), c.turns.on_change(), c.cursor.on_change()]
        return nu.Reconcile(
            nuspace.atomic(nu.OnAny(*changes)),
            nu.let(nuspace.atomic(_trace(c, at)), draw),
            after=nu.RECHECK_AFTER,
            every=nu.RECHECK_EVERY,
        )

    return nu.let(nuspace.atomic(engine_of(page)), follow)


# --- status, drawn by the composer ----------------------------------------------------------------------


def _shown(c: Chat) -> nu.Nu:
    """The status as the page shows it. Bare, on the conversation ``c``.

    Thinking reads as running while the latest reply's program runs: the
    conversation ends on the model's message until the observation lands.
    """
    kept = c.status.fallback(IDLE)
    last = nu.If(c.messages.len() > 0, nu.Dict(c.messages.last_elem()).get_item("role", ""), "")
    running = (kept == THINKING).and_(nu.Str(last) == "assistant")
    shown = nu.Str(nu.If(running, RUNNING, kept))
    return nu.Dict.of(
        status=shown,
        tone=nu.Dict(TONES).get_item(shown, "neutral"),
        error=nu.If(kept == ERROR, c.error.fallback(""), ""),
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
    is live only while it thinks, and a failure shows above the box. The
    status is a level flow re-checked every few seconds, so a missed
    notification shows late, never not at all.
    """
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

    def follow(e: nu.ObjectRef) -> nu.Nu:
        engine = nu.Str(e)
        c = conversation(engine)
        on = [c.status.on_change(), c.messages.on_change(), c.inbox.on_change()]
        return nu.ParallelAsync(
            nu.Reconcile(
                nuspace.atomic(nu.OnAny(*on)),
                nu.let(nuspace.atomic(_shown(c)), draw),
                after=nu.RECHECK_AFTER,
                every=5.0,
            ),
            nu.ReactEvery(actions.send.on_click(), nu.let(nu.Str(box).strip(), sent)),
            nu.ReactEvery(actions.stop.on_click(), stop(engine)),
        )

    placed = box.set("") >> actions.send.set("Send") >> actions.stop.set("Stop", disabled=True)
    return ensure(page) >> placed >> nu.let(nuspace.atomic(engine_of(page)), follow)
