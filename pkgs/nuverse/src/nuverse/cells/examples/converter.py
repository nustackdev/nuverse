"""A unit converter: two amounts, either one typed, the other worked out.

What the cell keeps is the amount in its kind's base unit (metres,
kilograms, kelvin, seconds), so typing on either side writes the same slot
and both sides are drawn from it. That is the whole trick: one value
stored, two views of it, both editable.
"""

from __future__ import annotations

import nu
import nuspace
import nustd.kv
import nustd.ui
from nuspace.specs import CellSpec

from .. import source


__all__ = ["CELL", "KINDS", "Convert", "View", "out"]


#: Each kind's units as ``unit: [scale, offset]``: ``base = amount * scale + offset``.
KINDS: dict[str, dict[str, list[float]]] = {
    "Length": {
        "m": [1.0, 0.0],
        "km": [1000.0, 0.0],
        "cm": [0.01, 0.0],
        "mi": [1609.344, 0.0],
        "ft": [0.3048, 0.0],
        "in": [0.0254, 0.0],
    },
    "Mass": {
        "kg": [1.0, 0.0],
        "g": [0.001, 0.0],
        "lb": [0.45359237, 0.0],
        "oz": [0.028349523125, 0.0],
    },
    "Temperature": {
        "°C": [1.0, 273.15],
        "°F": [5 / 9, 459.67 * 5 / 9],
        "K": [1.0, 0.0],
    },
    "Time": {
        "s": [1.0, 0.0],
        "min": [60.0, 0.0],
        "h": [3600.0, 0.0],
        "day": [86400.0, 0.0],
    },
}


def _round(x: float) -> float:
    return float(f"{float(x):.6g}")


#: A number cut to six significant digits, so 1 mi reads 1.60934, not 1.6093440000000001.
Rounded = nu.host(_round, name="ConverterRounded")


class Convert(nu.Shape):
    """The converter's own state: the kind, a unit each side, and the amount in the base unit."""

    kind = nustd.kv.StrRef.slot()
    left = nustd.kv.StrRef.slot()
    right = nustd.kv.StrRef.slot()
    base = nustd.kv.FloatRef.slot()


class Side(nustd.ui.Row):
    """One side: an amount and its unit."""

    amount = nustd.ui.NumberInputRef.slot(step=0.1)
    unit = nustd.ui.SelectRef.slot()


class Sides(nustd.ui.Row):
    """The two sides with an equals between, stacked on a narrow cell."""

    left = Side.slot(gap=2, grow={"amount": 1}, basis={"unit": 96})
    equals = nustd.ui.IconRef.slot(name="arrow-left-right", tone="muted")
    right = Side.slot(gap=2, grow={"amount": 1}, basis={"unit": 96})


class Body(nustd.ui.Column):
    kind = nustd.ui.SegmentedControlRef.slot(options=list(KINDS), fill=True)
    sides = Sides.slot(gap=3, grow={"left": 1, "right": 1}, stack_below=440)


class View(nu.Shape):
    """The cell's root: the kind on top, the two sides under it."""

    body = Body.slot(gap=4)


#: The running cell's surface.
Box = View.body
#: Its two sides.
LEFT, RIGHT = Box.sides.left, Box.sides.right


def out() -> nu.Nu:
    """The converter, for as long as the cell runs."""
    state = nuspace.here(Convert)
    kinds = nu.Dict(nu.Literal(KINDS))
    kind = state.kind.fallback("Length")
    units = nu.Dict(kinds[kind])
    names = nu.list(units.keys())

    def held(slot: nu.Nu, at: int) -> nu.Str:
        # A unit of another kind (stored mid switch, or the old pick a
        # select echoes back) reads as the kind's own default.
        stored = nu.str(slot.fallback(nu.str(names[at])))
        return nu.str(nu.If(units.contains(stored), stored, nu.str(names[at])))

    left = held(state.left, 0)
    right = held(state.right, 1)

    def scale(unit: nu.Nu) -> nu.Float:
        return nu.Float(nu.List(units[unit])[0])

    def offset(unit: nu.Nu) -> nu.Float:
        return nu.Float(nu.List(units[unit])[1])

    def amount(unit: nu.Nu) -> nu.Nu:
        return Rounded((state.base.fallback(1.0) - offset(unit)) / scale(unit))

    def typed(side: nu.Nu, unit: nu.Nu) -> nu.Nu:
        return state.base.set(nu.ToFloat(side.amount) * scale(unit) + offset(unit))

    def picked(slot: nu.Nu, select: nu.Nu) -> nu.Nu:
        # Only a unit of the kind shown: options swapping can echo the old one.
        unit = nu.ToStr(select)
        return nu.IfDo(units.contains(unit), slot.set(unit))

    def show() -> nu.Nu:
        return (
            Box.kind.set(kind)
            >> LEFT.unit.set_options(names)
            >> RIGHT.unit.set_options(names)
            >> LEFT.unit.set(left)
            >> RIGHT.unit.set(right)
            >> LEFT.amount.set(amount(left))
            >> RIGHT.amount.set(amount(right))
        )

    def rekind() -> nu.Nu:
        # Another kind: its first two units, one of the left one.
        picked = nu.Str(Box.kind)
        units_of = nu.Dict(kinds[picked])
        first = nu.list(units_of.keys())
        one = nu.List(units_of[first[0]])
        return (
            state.kind.set(picked)
            >> state.left.set(nu.str(first[0]))
            >> state.right.set(nu.str(first[1]))
            >> state.base.set(nu.Float(one[0]) + nu.Float(one[1]))
        )

    # Anything stored changed, here or in another tab: draw it all again.
    stored = (state.kind, state.left, state.right, state.base)
    return nuspace.bracketed(
        show()
        >> nu.ParallelAsync(
            nu.ReactEvery(Box.kind.on_change(), rekind()),
            nu.ReactEvery(LEFT.unit.on_change(), picked(state.left, LEFT.unit)),
            nu.ReactEvery(RIGHT.unit.on_change(), picked(state.right, RIGHT.unit)),
            nu.ReactEvery(LEFT.amount.on_change(), typed(LEFT, left)),
            nu.ReactEvery(RIGHT.amount.on_change(), typed(RIGHT, right)),
            *(nu.ReactEvery(slot.on_change(), show()) for slot in stored),
        )
    )


CELL = CellSpec(
    "converter",
    "Unit converter",
    source(__name__),
    description="Length, mass, temperature and time: type on either side, the other follows.",
    group="Examples",
    icon="calculator",
)
