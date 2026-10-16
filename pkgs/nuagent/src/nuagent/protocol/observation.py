"""What the model reads back after each turn: the outcome, rendered, then the state.

A turn ends in a typed outcome, a record with a ``kind`` from a closed set
and the payload that kind carries. The host branches on ``kind`` and never
on text. The text is made here, once, from the record: the label each kind
gets and the words around it. The prose in ``protocol.md`` quotes the same
labels, and a test holds the two together.

The observation is two lines at most::

    outcome: <the rendered outcome>
    state: <repr of the caller's state term>

The state line is there only when the caller passes a state term. Nothing is
cut short: a model shown half a list it just wrote cannot tell a landed
append from a failed one, so it appends again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
from nu.domains.shape.interactions import Extract


if TYPE_CHECKING:
    from nu.lang import Nu


__all__ = [
    "CONSTRUCT",
    "KINDS",
    "LABELS",
    "NO_CODE",
    "NO_CODE_TEXT",
    "OK",
    "OUTCOME",
    "RUNTIME",
    "STATE",
    "observation",
    "render",
]


#: The program built and ran. ``value`` is the repr of its yield.
OK = "ok"

#: The reply had no complete fenced block and did not parse as source either.
NO_CODE = "no_code"

#: The module did not build. ``message`` and ``line`` come off the Diagnostic.
CONSTRUCT = "construct"

#: The term built and raised while it ran. ``message`` is the error, typed.
RUNTIME = "runtime"

#: Every kind an outcome can have.
KINDS = (OK, NO_CODE, CONSTRUCT, RUNTIME)

#: The label each failure kind is read under. ``ok`` has none: its text is the value.
LABELS = {
    NO_CODE: "NO CODE BLOCK",
    CONSTRUCT: "CONSTRUCTION FAILED",
    RUNTIME: "RUNTIME FAILED",
}

#: The whole of a ``no_code`` outcome. No line number: there is no source to have one.
NO_CODE_TEXT = (
    f"{LABELS[NO_CODE]}: your reply had no complete fenced block "
    "and does not parse, so nothing ran."
)

#: Heads the first line of every observation.
OUTCOME = "outcome: "

#: Heads the state line, when there is one.
STATE = "\nstate: "


def render(outcome: Nu) -> Nu:
    """The outcome as the model reads it, picked by its kind.

    Args:
        outcome: the outcome record, a ref or a dict term with ``kind`` and
            the payload that kind carries.

    Returns:
        A ``Str`` term: the value for ``ok``, the label and message for a
        failure, with the line when a construction failure has one.
    """
    record = nu.Dict(outcome)
    message = nu.Str(record.get_item("message", ""))
    line = record.get_item("line", None)
    where = nu.If(line, " (line " + nu.str(line) + ")", "")
    return nu.Str(
        nu.Switch(
            record["kind"],
            {
                OK: record["value"],
                NO_CODE: NO_CODE_TEXT,
                CONSTRUCT: f"{LABELS[CONSTRUCT]}: " + message + where,
                RUNTIME: f"{LABELS[RUNTIME]}: " + message,
            },
        )
    )


def observation(outcome: Nu, state: Nu | None = None) -> Nu:
    """The next message's text: the rendered outcome, then the state when given.

    Args:
        outcome: the outcome record of the turn that just ran.
        state: what the model should see of the world after the run. Any term;
            it is read out as plain data and its repr is shown whole, so a kv
            ref shows what it holds, not its view. Omitted, there is no state
            line.

    Returns:
        A ``Str`` term.
    """
    text = OUTCOME + render(outcome)
    if state is None:
        return text
    return text + STATE + nu.Repr(Extract(state))
