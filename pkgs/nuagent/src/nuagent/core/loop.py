"""The loop: one turn, and that turn under a ``WhileDo`` until the model ends the run.

A turn is one prompt and one response, then the program in it::

    read the conversation        short bracket   -> plain data
    ask(conversation)            no bracket      -> text
    reply, message, program      short bracket
    attempt(program)             no bracket      -> outcome    the program runs exactly once
    outcome, observation         short bracket

Every step writes a session slot, so a watcher reads the run's progress off
state and the loop has no hooks. The conversation is a list that grows by
append and is never rebuilt or cut.

**The model ends the run, and nothing else does.** It redeclares the store's
``run`` Shape in its own module and sets ``done`` in the program that
finishes the work. There is no turn counter, budget or stall guard here, and
no predicate over the world: a predicate tests what a program did, not
whether the task is done. Limits like those are layers around the loop,
never inside it.

**A run can be carried on.** Once the model ended it, :func:`follow` appends
one more message and sets ``done`` back, and the same turns run again over
the whole conversation. What decides that a run is carried on (a chat, a
person) is the caller's.

**The core knows no storage and no backend.** A :class:`Store` brings the
session Shape (``messages``, ``reply``, ``program``, ``outcome``), the run
Shape, and two brackets: ``bracket`` around the loop's own short session
steps, ``rewrite`` around anything on the world (``done``, the state line,
the model's program, which it gets through ``LoadNu``). Neither is ever held
across the backend's answer or the program's run, so a store that locks
(one sqlite file for session and world) never waits on itself. The backend
is any :class:`Backend`: it answers a conversation with text and wraps the
whole run in whatever it needs open for it (a process, a session id, a
client). What it does between prompt and response is its own business.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import nu
from nuagent.protocol import observation

from .program import attempt, extract


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu, StrArg


__all__ = ["Backend", "Run", "Store", "agent", "follow", "seed", "turn"]


class Run(nu.Shape):
    """The run itself, on mem: the model sets ``done`` and the loop stops after that turn.

    Notes:
        - Untagged and flat on purpose. The model redeclares it in its own
          module, which makes a different class, and only an untagged Shape
          is reached by both: a tagged one is a store the model's ``Run``
          never writes, and the run would never end.
        - The mem store's run. A store with its world elsewhere brings its
          own one-slot Shape on that fabric.
    """

    done = nu.BoolRef.slot()


class Store(Protocol):
    """Where a run keeps its session and its world, and how a term reaches them.

    Attributes:
        session: the session Shape, slots ``messages``, ``reply``,
            ``program`` and ``outcome``.
        run: the world's one-slot Shape the model ends the run through.
    """

    session: type[nu.Shape]
    run: type[nu.Shape]

    def bracket(self, body: Nu) -> Nu:
        """``body``, a short step on the session, ready to run on the session's store."""
        ...

    def rewrite(self, term: Nu) -> Nu:
        """``term``, a read or write on the world, ready to run on the world's store.

        The model's program is one: it reaches this through ``LoadNu``'s
        ``rewrite``, so it gets its brackets without knowing it needs any.
        """
        ...

    def bound(self, body: Nu) -> Nu:
        """``body`` with the session's store and the world's bound around it."""
        ...


class Backend(Protocol):
    """What the loop needs from a model: an answer, and a scope to run in."""

    def ask(self, messages: Nu) -> Nu:
        """The model's reply to the conversation, as a Str-yielding term.

        Args:
            messages: the conversation as plain data, a list of
                ``{role, content}`` dicts read out of the session before the
                ask. A stateless backend sends them all, a stateful one the
                newest.
        """
        ...

    def wrap(self, body: Nu) -> Nu:
        """The whole run inside whatever the backend holds open for its lifetime."""
        ...


def seed(store: Store, prompt: StrArg) -> Nu:
    """Open a run: the conversation is the prompt alone, and the run is not done.

    Args:
        store: the store the run keeps its session and world in.
        prompt: the opening message as the caller composed it (the protocol,
            the Nu prose, the task). Sent as the first ``user`` message, so
            every backend reads the run the same way.

    Returns:
        A Command.

    Notes:
        - ``done`` is written False before the first turn. Unset it reads
          EMPTY, the loop condition is never true, and no turn runs.
    """
    opening = nu.Dict.of(role="user", content=prompt)
    return store.bracket(store.session.messages.set(nu.List.of(opening))) >> store.rewrite(
        store.run.done.set(False)
    )


def follow(store: Store, message: StrArg) -> Nu:
    """Carry an ended run on: the message appended to the conversation, and the run not done.

    Args:
        store: the store the ended run kept its session and world in.
        message: what comes next, as the caller composed it. Sent as one more
            ``user`` message, after everything the conversation already holds.

    Returns:
        A Command. Put where :func:`seed` would go, ahead of the turns.

    Notes:
        - The conversation is kept as it is and grows by the one message, so a
          stateful backend sends it alone and a stateless one sends it all.
    """
    said = nu.Dict.of(role="user", content=message)
    return store.bracket(store.session.messages.append(said)) >> store.rewrite(
        store.run.done.set(False)
    )


def turn(store: Store, ask: Callable[[Nu], Nu], *, state: Nu | None = None) -> Nu:
    """One turn: ask, extract, attempt, observe.

    Args:
        store: the store the run keeps its session and world in.
        ask: the backend's ``ask``.
        state: what the model sees of the world after each run, a read on
            the world. Omitted, the observation is the outcome alone.

    Returns:
        A term, one turn, ready to run once or under a loop.

    Notes:
        - The slow parts, the ask and the program's run, sit outside every
          bracket. What crosses between steps is plain data held in a
          ``nu.let``: the conversation, the reply, the source, the outcome.
        - The program runs once. Its outcome is held, then written to a slot
          and rendered into the observation from the held value.
        - The reply goes into the conversation as soon as it is in, so the
          conversation holds it even when what follows fails.
    """
    session = store.session

    def asked(said: Nu) -> Nu:
        """The conversation is read: ask it, then take the answer."""
        return nu.let(ask(said), answered)

    def answered(text: Nu) -> Nu:
        """The reply is in: take the source out of it."""
        return nu.let(extract(text), lambda source: kept(text, source))

    def kept(text: Nu, source: Nu) -> Nu:
        """Keep the reply, its message and its source, then run the source on the world."""
        said = nu.Dict.of(role="assistant", content=text)
        keep = (
            session.reply.set(text) >> session.messages.append(said) >> session.program.set(source)
        )
        ran = attempt(source, reply=text, rewrite=store.rewrite)
        return store.bracket(keep) >> nu.let(ran, observed)

    def observed(out: Nu) -> Nu:
        """The program ran: read the world for the observation, then keep both."""
        return nu.let(store.rewrite(observation(out, state)), lambda told: noted(out, told))

    def noted(out: Nu, told: Nu) -> Nu:
        """Keep the outcome and send the observation as the next message."""
        said = nu.Dict.of(role="user", content=told)
        return store.bracket(session.outcome.set(out) >> session.messages.append(said))

    return nu.let(store.bracket(session.messages.extract()), asked)


def agent(store: Store, backend: Backend, prompt: StrArg, *, state: Nu | None = None) -> Nu:
    """The whole run: seed, then turns until the model sets ``done``.

    Args:
        store: the store the run keeps its session and world in. Bind it
            around this term with ``store.bound``.
        backend: answers each turn and wraps the run.
        prompt: the opening message.
        state: what the model sees of the world after each run.

    Returns:
        The run as one term, inside the backend's wrap.
    """
    going = store.rewrite(store.run.done.not_())
    body = seed(store, prompt) >> nu.WhileDo(going, turn(store, backend.ask, state=state))
    return backend.wrap(body)
