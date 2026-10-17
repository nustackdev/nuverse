"""The engine: a conversation's headless plane, one cell, run by a reaction on its inbox.

Each chat page has its own engine, a child plane with no ui. Nothing keeps it
running: a reaction on its ``inbox`` (made by the page) starts a run of it
whenever the person sends something, and the run handles every message past
its ``cursor`` and returns. That is the reactions contract, so an extra fire
finds nothing past the cursor and ends at once.

One message is one run of the nuagent loop on the engine's plane state
(:class:`~.store.SpaceStore`):

    the first message      the full opening prompt, the message as its task (seed)
    every later one        the message alone, appended, the run not done (follow)
    then                   turns until the model sets ``Run.done``, each one recorded
    then                   the cursor past it

The backend comes from the settings (:mod:`.settings`), read when the engine
wakes, so the loop is built while it runs: :data:`Handling` builds it from
what was read, and ``nu.Eval`` runs what it built. A failure outside the
model's program (the backend, the settings) ends that message with status
``error`` and moves on, and one before any message could start ends every
message waiting: a message that cannot be handled is not tried again on
every fire.

On the cc backend the conversation id lives in the engine's state, minted on
the first message, so every later message, in any later run, resumes the
same Claude Code conversation.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import nu
from nuagent import prompt
from nuagent.core import follow, seed, turn
from nuspace import ops

from . import settings
from .state import ERROR, IDLE, THINKING, Chat, Run
from .store import SpaceStore, here


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nuagent.core import Backend


__all__ = [
    "CHAT",
    "IMPORTS",
    "MADE_BY",
    "SOURCE",
    "Handling",
    "engine_cell",
    "engine_of",
    "handling",
    "inbox_change",
    "out",
    "parts",
    "pending",
]


#: What an engine plane records as ``made_by``.
MADE_BY = "nuagent.engine"

#: The engine cell's prog: the engine on the backend the settings name.
SOURCE = """\
from nuagent.planes import engine


out = engine.out()
"""

#: What the model is told about talking to a person, ahead of the Nu pieces.
CHAT = """\
# This is a conversation

A person is talking to you from a page in their space. Each message from them
is one run: you work on it in turns, as above, and end the run when you are
done with it. Their next message comes in after that, as a new task in the
same conversation.

- The person reads only the cells on the page, never your replies: your
  prose is for you. Your answer to them is a cell you add with
  `nuagent.planes.answer(source)`, the source of a cell as a str. It goes on
  the page above the box they type in, and runs there like any cell: a few
  lines of Markdown, or anything `nustd.ui` draws, tables, charts, forms,
  live state.

      from nuagent.planes import answer

      CELL = '''
      import nustd.ui


      def out():
          return nustd.ui.MarkdownRef("answer").set("Six times seven is **42**.")
      '''


      def out():
          return answer(CELL) >> Run.done.set(True)

- `answer` builds the cell first, the way the page will: one that does not
  build fails your program and adds nothing, so fix it and try again. Add it
  in a turn before the one that sets `Run.done`, or in the same program
  before setting it. A message that only asks something still gets one.
- Your earlier answers are cells on the page, `made_by` `"nuagent.answer"`.
  Change or remove them through `nuspace.ops` when a later message asks:
  the page is `ops.parent(ops.Here.plane)`.
- Your program runs as a cell on this conversation's own plane: a `PlaneState`
  or `CellState` you declare lands there. Act on the rest of the space
  through `nuspace.ops`."""


def engine_of(page: nu.StrArg) -> nu.Str:
    """A chat page's engine plane id: the page's, with ``_engine`` after it."""
    return nu.Str(page) + "_engine"


def engine_cell(engine: nu.StrArg) -> nu.Str:
    """The engine's one cell id: the engine's, with ``_cell`` after it."""
    return nu.Str(engine) + "_cell"


#: What the reaction's source imports, for :func:`inbox_change` to name.
IMPORTS = "from nuagent.planes.state import Chat"


def inbox_change(engine: nu.StrArg) -> nu.Str:
    """The change a reaction runs the engine on, as source: its inbox, in its plane state.

    Named through the typed :class:`~.state.Chat`, placed with ``ops.plane_state``,
    and not as ``States.planes[engine].state["inbox"]``: an untyped key is a
    leaf, and a leaf hears its own writes, not an append to the list under it.
    """
    return "ops.plane_state(" + nu.Str(nu.Repr(engine)) + ", Chat.inbox.on_change())"


def pending() -> nu.Bool:
    """Whether a message waits past the cursor. Bare, on the engine's own state."""
    return Chat.cursor.fallback(0) < Chat.inbox.len()


def parts() -> tuple[prompt.Section, ...]:
    """The opening prompt's sections: the protocol, :data:`CHAT`, Nu, nuspace, what exists, Run."""
    modules = (*prompt.MODULES, "nustd.kv", "nuspace.ops", "nuagent.planes")
    found = prompt.sections(add=prompt.NUSPACE, modules=modules, run=Run)
    return prompt.inserted(found, prompt.Section("chat", lambda: CHAT), after="protocol")


def _read(term: nu.Nu) -> nu.Nu:
    """``term`` on the engine's own state, read in a snapshot."""
    return ops.snapshot(here(term))


def _record(at: nu.Int) -> nu.Nu:
    """The turn that just ran, kept for the page: the reply, its program, how it went. No bracket."""
    told = nu.Dict(Chat.messages.last_elem())
    kept = nu.Dict.of(
        at=at,
        reply=Chat.reply.fallback(""),
        program=nu.str(Chat.program).fallback(""),
        kind=Chat.outcome.kind.fallback(""),
        observation=nu.str(told["content"]),
    )
    return Chat.turns.append(kept)


def _past(at: nu.Int, status: str) -> nu.Nu:
    """The cursor past message ``at``, never back, and the status. No bracket.

    Never back: a stop moves the cursor to the end while a run may still be
    finishing, and that run's own move must not undo it.
    """
    return nu.IfDo(Chat.cursor.fallback(0) <= at, Chat.cursor.set(at + 1)) >> Chat.status.set(
        status
    )


def handling(got: Mapping[str, object], backend: Backend | None = None) -> nu.Nu:
    """Every message past the cursor through the loop, as a term. Built while the engine runs.

    Args:
        got: what the engine read as it woke: ``config``, the settings, and
            ``sid``, the conversation id, ``""`` before the first message.
        backend: the backend to run on. None builds the one the settings name.

    Returns:
        The term to run, in the same cell run, through ``nu.Eval``.
    """
    sid = str(got["sid"]) or str(uuid.uuid4())
    held = backend or settings.backend_of(got["config"], sid=sid)
    store = SpaceStore()
    write = store.bracket
    opened = parts()

    def message(at: nu.ObjectRef) -> nu.Nu:
        i = nu.Int(at)

        def handle(text: nu.ObjectRef) -> nu.Nu:
            first = nu.Int(_read(Chat.messages.len())) == 0
            begin = nu.IfDo(first, seed(store, prompt.opening(text, opened)), follow(store, text))
            going = store.rewrite(Run.done.not_())
            turns = nu.WhileDo(going, turn(store, held.ask) >> write(_record(i)))
            started = write(Chat.status.set(THINKING) >> Chat.error.set(""))
            return started >> begin >> turns >> write(_past(i, IDLE))

        def failed(err: nu.Nu) -> nu.Nu:
            return write(Chat.error.set(nu.Str(err)) >> _past(i, ERROR))

        return nu.TryCatch(nu.let(_read(Chat.inbox[i]), handle), catch=failed)

    kept = nu.Noop() if got["sid"] else write(Chat.sid.set(sid))
    every = nu.WhileDo(_read(pending()), nu.let(_read(Chat.cursor.fallback(0)), message))
    return kept >> held.wrap(every)


#: :func:`handling` as an atom, so what it builds from comes from the store at run time.
Handling = nu.host(handling, name="NuagentHandling")


def out(backend: Backend | None = None) -> nu.Nu:
    """The engine cell's program: every message past the cursor handled, then it returns.

    Args:
        backend: the backend to run on. None reads the settings each time the
            engine wakes, and builds the one they name.
    """
    woke = ops.snapshot(nu.Dict.of(config=settings.config(), sid=Chat.sid.fallback("")))
    run = nu.let(woke, lambda got: nu.Eval(Handling(got, nu.Literal(backend))))

    def failed(err: nu.Nu) -> nu.Nu:
        # Nothing could start (the settings, the backend): every message sent so far fails with it.
        given_up = Chat.cursor.set(Chat.inbox.len()) >> Chat.status.set(ERROR)
        return ops.atomic_state(Chat.error.set(nu.Str(err)) >> given_up)

    return nu.IfDo(ops.snapshot(pending()), nu.TryCatch(run, catch=failed))
