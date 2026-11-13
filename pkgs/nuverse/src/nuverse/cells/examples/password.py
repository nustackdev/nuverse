"""A password generator: a length, three switches, and a fresh password whenever one changes.

The options and the password live in the cell's state, so the last password
is still there when the plane opens again. Drawn with :mod:`secrets`, not
:mod:`random`: it is meant to be used.
"""

from __future__ import annotations

import secrets
import string

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.specs import CellSpec

from .. import source


__all__ = ["CELL", "Pass", "out"]


def _draw(alphabet: str, length: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(int(length)))


#: ``length`` characters drawn from ``alphabet``, each from the OS's secure source.
Draw = nu.host(_draw, name="PasswordDraw")


class Pass(nu.Shape):
    """The generator's state: its options, and the password they made last."""

    length = nustd.kv.IntRef.slot()
    upper = nustd.kv.BoolRef.slot()
    digits = nustd.kv.BoolRef.slot()
    symbols = nustd.kv.BoolRef.slot()
    password = nustd.kv.StrRef.slot()


class Options(nustd.ui.Row):
    upper = nustd.ui.SwitchRef.slot(label="A-Z")
    digits = nustd.ui.SwitchRef.slot(label="0-9")
    symbols = nustd.ui.SwitchRef.slot(label="!@#")
    generate = nustd.ui.ButtonRef.slot(label="Generate", variant="secondary")


class Box(nustd.ui.Column):
    password = nustd.ui.CodeRef.slot()
    length = nustd.ui.SliderRef.slot(label="Length", min=8, max=64)
    options = Options.slot(gap=4, wrap=True)


def out() -> nu.Nu:
    """The generator, for as long as the cell runs: an option changed, or Generate, draws again."""
    state = nuspace.here(Pass)
    length = state.length.fallback(20)
    upper, digits, symbols = (s.fallback(True) for s in (state.upper, state.digits, state.symbols))
    alphabet = (
        nu.Str(string.ascii_lowercase)
        + nu.If(upper, string.ascii_uppercase, "")
        + nu.If(digits, string.digits, "")
        + nu.If(symbols, "!@#$%^&*-_=+?", "")
    )
    draw = state.password.set(Draw(alphabet, length))

    def keep(slot: nu.Nu, value: nu.Nu) -> nu.Nu:
        # The option first, then a password made with it, in one commit.
        return slot.set(value) >> draw

    first = nu.IfDo(state.password.is_null(), draw)
    return nuspace.bracketed(
        first
        >> Box.password.set(nu.str(state.password))
        >> Box.length.set(length)
        >> Box.options.upper.set(upper)
        >> Box.options.digits.set(digits)
        >> Box.options.symbols.set(symbols)
        >> nu.ParallelAsync(
            nu.ReactEvery(Box.options.generate.on_click(), draw),
            nu.ReactEvery(Box.length.on_change(), keep(state.length, nu.ToInt(Box.length))),
            nu.ReactEvery(
                Box.options.upper.on_change(), keep(state.upper, nu.ToBool(Box.options.upper))
            ),
            nu.ReactEvery(
                Box.options.digits.on_change(), keep(state.digits, nu.ToBool(Box.options.digits))
            ),
            nu.ReactEvery(
                Box.options.symbols.on_change(), keep(state.symbols, nu.ToBool(Box.options.symbols))
            ),
            # Every tab shows the password the store holds.
            nu.ReactEvery(state.password.on_change(), Box.password.set(nu.str(state.password))),
        )
    )


CELL = CellSpec(
    "password",
    "Password generator",
    source(__name__),
    description="A strong password, drawn again whenever its length or characters change.",
    group="Examples",
    icon="key",
)
