"""The engine: a conversation's headless plane, one cell, run by a reaction on its inbox.

Each chat page has its own engine, a child plane the web never shows, its
id kept in the page's state (:class:`~.state.Engine`). Nothing keeps it
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
import nuspace
from nuagent import prompt
from nuagent.core import follow, seed, turn

from . import settings
from .state import ERROR, IDLE, THINKING, Chat, Engine, Run
from .store import SpaceStore


if TYPE_CHECKING:
    from collections.abc import Mapping

    from nuagent.core import Backend


__all__ = [
    "CHAT",
    "IMPORTS",
    "OPS",
    "SOURCE",
    "SPEC",
    "Handling",
    "conversation",
    "engine_of",
    "handling",
    "inbox_change",
    "out",
    "parts",
    "pending",
]


#: What an engine plane records as ``spec``.
SPEC = "nuagent.engine"

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
          return answer(CELL) >> nuspace.at.plane.state(Run).done.set(True)

- `answer` builds the cell first, the way the page will: one that does not
  build fails your program and adds nothing, so fix it and try again. Add it
  in a turn before the one that sets `Run.done`, or in the same program
  before setting it. A message that only asks something still gets one.
- Your earlier answers are cells on the page, `spec` `"nuagent.answer"`.
  Change or remove them through `nuspace.cell` when a later message asks:
  the page is `nuspace.Space.planes[nuspace.places.Here.plane].parent`.
- Your program runs as a cell on this conversation's own plane: a Shape you
  read through `nuspace.at.plane.state(Shape)` or `nuspace.here(Shape)`
  lands there, and `Run` is one. Act on the rest of the space through
  `nuspace.plane`, `nuspace.cell` and the other ops."""


def engine_of(page: nu.StrArg) -> nu.Str:
    """A chat page's engine plane id, as the page keeps it (:class:`~.state.Engine`). Bare read, NULL before one is made."""
    return nu.Str(nuspace.at.plane(id=page).state(Engine).plane)


def conversation(engine: nu.StrArg | None = None) -> Chat:
    """A conversation's state: ``engine``'s plane state read through :class:`~.state.Chat`.

    Bare, the running plane's: the engine's own, read from its cell. Builds
    refs, reads nothing.
    """
    place = nuspace.at.plane if engine is None else nuspace.at.plane(id=engine)
    return place.state(Chat)


#: The nuspace op modules the catalogue lists, spelled as a program writes them.
OPS = ("nuspace.plane", "nuspace.cell", "nuspace.plane_run", "nuspace.cell_run", "nuspace.state")

#: What the reaction's source imports, for :func:`inbox_change` to name.
IMPORTS = "from nuagent.planes.state import Chat"


def inbox_change(engine: nu.StrArg) -> nu.Str:
    """The change a reaction runs the engine on, as source: its inbox, in its plane state.

    Named through the typed :class:`~.state.Chat` on the engine's place, and
    not as an untyped key: an untyped key is a leaf, and a leaf hears its
    own writes, not an append to the list under it.
    """
    head = nu.Str("nuspace.at.plane(id=") + nu.Repr(engine)
    return head + nu.Str(").state(Chat).inbox.on_change()")


def pending(engine: nu.StrArg | None = None) -> nu.Bool:
    """Whether a message waits past the cursor. Bare, on ``engine``'s state, the running plane's when absent."""
    c = conversation(engine)
    return c.cursor.fallback(0) < c.inbox.len()


def parts() -> tuple[prompt.Section, ...]:
    """The opening prompt's sections: the protocol, :data:`CHAT`, Nu, nuspace, what exists, Run."""
    modules = (*prompt.MODULES, "nustd.kv", "nuspace", *OPS, "nuagent.planes")
    found = prompt.sections(add=prompt.NUSPACE, modules=modules, run=Run)
    return prompt.inserted(found, prompt.Section("chat", lambda: CHAT), after="protocol")


def _record(at: nu.Int) -> nu.Nu:
    """The turn that just ran, kept for the page: the reply, its program, how it went. No bracket."""
    c = conversation()
    told = nu.Dict(c.messages.last_elem())
    kept = nu.Dict.of(
        at=at,
        reply=c.reply.fallback(""),
        program=nu.str(c.program.fallback("")),
        kind=c.outcome.kind.fallback(""),
        observation=nu.str(told["content"]),
    )
    return c.turns.append(kept)


def _past(at: nu.Int, status: str) -> nu.Nu:
    """The cursor past message ``at``, never back, and the status. No bracket.

    Never back: a stop moves the cursor to the end while a run may still be
    finishing, and that run's own move must not undo it.
    """
    c = conversation()
    return nu.IfDo(c.cursor.fallback(0) <= at, c.cursor.set(at + 1)) >> c.status.set(status)


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
    c = conversation()

    def message(at: nu.ObjectRef) -> nu.Nu:
        i = nu.Int(at)

        def handle(text: nu.ObjectRef) -> nu.Nu:
            first = nu.Int(nuspace.atomic(c.messages.len())) == 0
            begin = nu.IfDo(first, seed(store, prompt.opening(text, opened)), follow(store, text))
            going = store.rewrite(store.run.done.not_())
            turns = nu.WhileDo(going, turn(store, held.ask) >> write(_record(i)))
            started = write(c.status.set(THINKING) >> c.error.set(""))
            return started >> begin >> turns >> write(_past(i, IDLE))

        def failed(err: nu.Nu) -> nu.Nu:
            return write(c.error.set(nu.Str(err)) >> _past(i, ERROR))

        return nu.TryCatch(nu.let(nuspace.atomic(c.inbox[i]), handle), catch=failed)

    kept = nu.Noop() if got["sid"] else write(c.sid.set(sid))
    every = nu.WhileDo(
        nuspace.atomic(pending()), nu.let(nuspace.atomic(c.cursor.fallback(0)), message)
    )
    return kept >> held.wrap(every)


#: :func:`handling` as an atom, so what it builds from comes from the store at run time.
Handling = nu.host(handling, name="NuagentHandling")


def out(backend: Backend | None = None) -> nu.Nu:
    """The engine cell's program: every message past the cursor handled, then it returns.

    Args:
        backend: the backend to run on. None reads the settings each time the
            engine wakes, and builds the one they name.
    """
    c = conversation()
    woke = nuspace.atomic(nu.Dict.of(config=settings.config(), sid=c.sid.fallback("")))
    run = nu.let(woke, lambda got: nu.Eval(Handling(got, nu.Literal(backend))))

    def failed(err: nu.Nu) -> nu.Nu:
        # Nothing could start (the settings, the backend): every message sent so far fails with it.
        given_up = c.cursor.set(c.inbox.len()) >> c.status.set(ERROR)
        return nuspace.atomic(c.error.set(nu.Str(err)) >> given_up)

    return nu.IfDo(nuspace.atomic(pending()), nu.TryCatch(run, catch=failed))
