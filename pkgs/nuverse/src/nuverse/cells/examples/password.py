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


__all__ = ["CELL", "Pass", "View", "out"]


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


class Shown(nustd.ui.Row):
    """The password, copied off its own button, and Generate beside it."""

    password = nustd.ui.CodeRef.slot()
    generate = nustd.ui.ButtonRef.slot(icon="refresh-cw", tooltip="Generate", variant="secondary")


class Charset(nustd.ui.Row):
    """Which characters it draws from, beyond the lowercase it always has."""

    upper = nustd.ui.ToggleRef.slot(label="A-Z")
    digits = nustd.ui.ToggleRef.slot(label="0-9")
    symbols = nustd.ui.ToggleRef.slot(label="!@#")


class Characters(nustd.ui.Field):
    charset = Charset.slot(gap=2, wrap=True)


class Body(nustd.ui.Column):
    shown = Shown.slot(gap=2, grow={"password": 1})
    length = nustd.ui.SliderRef.slot(label="Length", min=8, max=64)
    characters = Characters.slot(label="Characters")


class View(nu.Shape):
    """The cell's root: the password on top, its options under it."""

    body = Body.slot(gap=4)


#: The running cell's surface.
Box = View.body
#: Its character toggles.
CHARSET = Box.characters.charset


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
        >> Box.shown.password.set(nu.str(state.password))
        >> Box.length.set(length)
        >> CHARSET.upper.set(upper)
        >> CHARSET.digits.set(digits)
        >> CHARSET.symbols.set(symbols)
        >> nu.ParallelAsync(
            nu.ReactEvery(Box.shown.generate.on_click(), draw),
            nu.ReactEvery(Box.length.on_change(), keep(state.length, nu.ToInt(Box.length))),
            *(
                nu.ReactEvery(toggle.on_change(), keep(slot, nu.ToBool(toggle)))
                for toggle, slot in (
                    (CHARSET.upper, state.upper),
                    (CHARSET.digits, state.digits),
                    (CHARSET.symbols, state.symbols),
                )
            ),
            # Every tab shows the password the store holds.
            nu.ReactEvery(
                state.password.on_change(), Box.shown.password.set(nu.str(state.password))
            ),
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
