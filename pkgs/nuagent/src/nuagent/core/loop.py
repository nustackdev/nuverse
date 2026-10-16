"""The loop: one turn, and that turn under a ``WhileDo`` until the model ends the run.

A turn is one prompt and one response, then the program in it::

    ask(messages)       -> reply
    extract(reply)      -> program
    attempt(program)    -> outcome         the program runs exactly once
    observation(outcome) appended          the next prompt

Every step writes a session slot, so a watcher reads the run's progress off
state and the loop has no hooks. The conversation is a list that grows by
append and is never rebuilt or cut.

**The model ends the run, and nothing else does.** It redeclares :class:`Run`
in its own module and sets ``done`` in the program that finishes the work.
There is no turn counter, budget or stall guard here, and no predicate over
the world: a predicate tests what a program did, not whether the task is
done. Limits like those are layers around the loop, never inside it.

**The core knows no storage and no backend.** The session is any Shape with
the four slots (``messages``, ``reply``, ``program``, ``outcome``), bound by a
store preset. The backend is any :class:`Backend`: it answers a conversation
with text and wraps the whole run in whatever it needs open for it (a
process, a session id, a client). What it does between prompt and response
is its own business.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import nu
from nuagent.protocol import observation

from .program import attempt, extract


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu, StrArg


__all__ = ["Backend", "Run", "agent", "seed", "turn"]


class Run(nu.Shape):
    """The run itself: the model sets ``done`` and the loop stops after that turn.

    Notes:
        - Untagged and flat on purpose. The model redeclares it in its own
          module, which makes a different class, and only an untagged Shape
          is reached by both: a tagged one is a store the model's ``Run``
          never writes, and the run would never end.
        - On mem by default. A world on another fabric passes its own
          one-slot ``Run`` to :func:`agent`.
    """

    done = nu.BoolRef.slot()


class Backend(Protocol):
    """What the loop needs from a model: an answer, and a scope to run in."""

    def ask(self, messages: Nu) -> Nu:
        """The model's reply to the conversation, as a Str-yielding term.

        Args:
            messages: the session's ``messages`` ref, ``{role, content}`` dicts.
                A stateless backend sends them all, a stateful one the newest.
        """
        ...

    def wrap(self, body: Nu) -> Nu:
        """The whole run inside whatever the backend holds open for its lifetime."""
        ...


def seed(session: type[nu.Shape], prompt: StrArg, *, run: type[nu.Shape] = Run) -> Nu:
    """Open a run: the conversation is the prompt alone, and the run is not done.

    Args:
        session: the session Shape.
        prompt: the opening message as the caller composed it (the protocol,
            the Nu prose, the task). Sent as the first ``user`` message, so
            every backend reads the run the same way.
        run: the Shape the model ends the run through.

    Returns:
        A Command.

    Notes:
        - ``done`` is written False before the first turn. Unset it reads
          EMPTY, the loop condition is never true, and no turn runs.
    """
    opening = nu.Dict.of(role="user", content=prompt)
    return session.messages.set(nu.List.of(opening)) >> run.done.set(False)


def turn(session: type[nu.Shape], ask: Callable[[Nu], Nu], *, state: Nu | None = None) -> Nu:
    """One turn: ask, extract, attempt, observe.

    Args:
        session: the session Shape.
        ask: the backend's ``ask``.
        state: what the model sees of the world after each run. Omitted,
            the observation is the outcome alone.

    Returns:
        A Flow, one turn, ready to run once or under a loop.

    Notes:
        - The program runs once. Its outcome is written to a slot and both
          the observation and any watcher read the slot.
        - The reply goes into the conversation as soon as it is in, so the
          conversation holds it even when what follows fails.
    """
    reply = session.reply
    outcome = session.outcome
    return (
        reply.set(ask(session.messages))
        >> session.messages.append(nu.Dict.of(role="assistant", content=reply))
        >> session.program.set(extract(reply))
        >> outcome.set(attempt(session.program, reply=reply))
        >> session.messages.append(nu.Dict.of(role="user", content=observation(outcome, state)))
    )


def agent(
    session: type[nu.Shape],
    backend: Backend,
    prompt: StrArg,
    *,
    state: Nu | None = None,
    run: type[nu.Shape] = Run,
) -> Nu:
    """The whole run: seed, then turns until the model sets ``done``.

    Args:
        session: the session Shape, bound by a store preset around this term.
        backend: answers each turn and wraps the run.
        prompt: the opening message.
        state: what the model sees of the world after each run.
        run: the Shape the model ends the run through, on the world's fabric.

    Returns:
        The run as one term, inside the backend's wrap.
    """
    body = seed(session, prompt, run=run) >> nu.WhileDo(
        run.done.not_(), turn(session, backend.ask, state=state)
    )
    return backend.wrap(body)
