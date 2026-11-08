"""What content Cells share: where their item is, their name as their label, kinds by name.

An editor of one item (a text input, a number input, ...) edits its own
cell's :data:`ITEM` by default. Its Config's Item section can point it at
another item of its kind: the scope's level (a cell, a plane, the space),
the scope's id (blank for this cell or this plane) and the item's content
key (blank for :data:`ITEM`). Where it points is the cell's own state
(:class:`Target`), so two editors pointed at one item edit it together, and
a program can point one by writing it
(``nuspace.at.cell(id=c).state(Target).target.set(...)``).

The viewers of any kind (:mod:`.item`, :mod:`.items`, :mod:`.item_picker`)
pick the kind too, by name, from the installed kinds
(:func:`kind_options`, read off the registry where the cell is built), and
build what they draw for it at run time with :class:`ForKind`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nu
import nuspace
import nustd.kv
import nustd.ui
from nu.engine import Declared
from nu.lang import ScalarQuery
from nuspace.places import Here
from nuspace.shapes.content import CELL, PLANE, SPACE, entries
from nuspace.specs import content_spec, content_specs
from nustd.ui.core import Ref as UiRef


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from nu.domains.shape import StructuredRef
    from nu.lang.runtime import Runtime
    from nuspace.shapes.content import Content


__all__ = [
    "DEFAULT_KIND",
    "ITEM",
    "LEVEL_OPTIONS",
    "SECTIONS",
    "TARGET",
    "ForKind",
    "KindField",
    "LevelField",
    "Target",
    "Where",
    "bounded",
    "drawing",
    "editing",
    "editor",
    "kind_of",
    "kind_options",
    "landed",
    "named",
    "pointed",
    "render",
    "render_hit",
    "where",
]


#: The content key of the item an editor edits when its Config names none.
ITEM = "value"

#: The scope levels a Config offers.
LEVEL_OPTIONS = [
    {"value": CELL, "label": "Cell"},
    {"value": PLANE, "label": "Plane"},
    {"value": SPACE, "label": "Space"},
]

#: An editor's Config: its own settings, then where its item is.
SECTIONS = [{"id": "settings", "label": "Config"}, {"id": "item", "label": "Item"}]

#: The kind a viewer of any kind (:mod:`.item`, :mod:`.items`, :mod:`.item_picker`)
#: shows when its Config names none: text.
DEFAULT_KIND = "nuverse.Text"


class Target(nu.Shape):
    """Where the cell's item is, plain data: ``level``, ``scope``, ``key``, and ``kind`` for a viewer.

    A field missing or blank takes its default: a cell, this cell or this
    plane, :data:`ITEM`. Kept in the cell's own state (:data:`TARGET`).
    """

    target = nustd.kv.PrimitiveDictRef.slot()


#: The running cell's :class:`Target`.
TARGET = nuspace.here(Target).target


class LevelField(nustd.ui.Field):
    input = nustd.ui.SelectRef.slot(options=LEVEL_OPTIONS)


class KindField(nustd.ui.Field):
    input = nustd.ui.SelectRef.slot(placeholder="No content kinds registered")


class Where(nustd.ui.Column):
    """An editor's Item section: where the item it edits is."""

    level = LevelField.slot(label="Scope")
    scope = nustd.ui.InputRef.slot(label="Scope id", placeholder="This cell or plane")
    key = nustd.ui.InputRef.slot(label="Item key", placeholder=ITEM)


def _field(ui: nu.Nu, name: str) -> nu.Nu:
    """The input of ``ui``'s field ``name``: a select sits in a Field, an input is one."""
    held = getattr(ui, name)
    return held.input if name in ("level", "kind") else held


def _given(held: nu.Nu, name: str) -> nu.Str:
    """One field of a target, ``""`` when missing."""
    return nu.Str(nu.str(nu.Dict(held).get_item(name, "")))


def kind_of(held: nu.Nu) -> nu.Str:
    """The kind a target names, :data:`DEFAULT_KIND` when it names none."""
    kind = _given(held, "kind")
    return nu.Str(nu.If(kind == "", DEFAULT_KIND, kind))


def pointed(held: nu.Nu, body: Callable[[str, nu.Str, nu.Str], nu.Nu]) -> nu.Nu:
    """``body(level, scope id, key)`` for the item a target names, blanks filled.

    ``level`` is a python str, one of the three, so ``body`` can build a ref
    on it (:func:`~nuspace.shapes.content.entries`); the id and the key are
    terms.

    Args:
        held: A target, plain data (:class:`Target`).
        body: What to do with the item.
    """
    scope_id, key = _given(held, "scope"), _given(held, "key")
    key = nu.Str(nu.If(key == "", ITEM, key))
    level = _given(held, "level")

    def on(at: str, own: nu.StrArg) -> nu.Nu:
        return body(at, nu.Str(nu.If(scope_id == "", own, scope_id)), key)

    return nu.IfDo(
        level == PLANE,
        on(PLANE, Here.plane),
        nu.IfDo(level == SPACE, body(SPACE, nu.Str(""), key), on(CELL, Here.cell)),
    )


def editing(kind: type[Content[Any]], body: Callable[[Any], nu.Nu]) -> nu.Nu:
    """``body(item)`` over the item of ``kind`` the cell points at, started again when it points elsewhere.

    Runs for as long as the cell does. Bare: inside :func:`editor`, or a
    cell's ``nuspace.bracketed``.
    """
    held = nuspace.atomic(TARGET.fallback({}))

    def edit(at: str, scope_id: nu.Str, key: nu.Str) -> nu.Nu:
        return body(entries(kind, at, scope_id)[key])

    return nu.ReactLatest(
        TARGET.on_change(), nu.let(held, lambda t: pointed(t, edit)), initial=True
    )


def where(
    ui: nu.Nu,
    fields: Sequence[str] = ("level", "scope", "key"),
    *,
    shown: Mapping[str, str] | None = None,
) -> tuple[nu.Nu, list[nu.Nu]]:
    """A Config section showing the cell's :class:`Target` and writing it, both ways.

    Args:
        ui: The section: a :class:`Where`, or a Column with ``fields`` of
            the same names (``kind`` and ``level`` in a Field, as selects).
        fields: The target's fields the section asks.
        shown: What a select shows for a field the target leaves blank, by
            field. ``level`` shows :data:`~nuspace.shapes.content.CELL`.

    Returns:
        What draws it, and the reactions keeping it and the target in step.
    """
    blanks = {"level": CELL, **(shown or {})}
    held = nu.Dict(TARGET.fallback({}))

    def given(name: str) -> nu.Nu:
        value = _given(held, name)
        return nu.If(value == "", blanks[name], value) if name in blanks else value

    show = nu.Sequential(*(_field(ui, f).set(given(f)) for f in fields))
    asked = nu.Dict.of(**{f: nu.Str(nu.ToStr(_field(ui, f))).strip() for f in fields})
    keep = TARGET.set(asked)
    reactions = [nu.ReactEvery(_field(ui, f).on_change(), keep) for f in fields]
    return show, [*reactions, nu.ReactEvery(TARGET.on_change(), show)]


def named(entry: nu.Nu, name: nu.Nu) -> tuple[nu.Nu, list[nu.Nu]]:
    """The cell's name as ``entry``'s label and in Config's ``name`` input, renamed from there.

    Returns:
        What draws it, and the reactions keeping it live.
    """
    called = nuspace.Space.cells[Here.cell].name
    show = entry.set_label(called.fallback("")) >> name.set(called.fallback(""))
    renamed = nuspace.atomic(nuspace.cell.rename(Here.cell, nu.Str(name)))
    return show, [
        nu.ReactEvery(name.on_change(), renamed),
        nu.ReactEvery(called.on_change(), show),
    ]


def editor(
    kind: type[Content[Any]],
    box: nu.Nu,
    body: Callable[[Any], nu.Nu],
    *,
    first: nu.Nu | None = None,
    also: Sequence[nu.Nu] = (),
) -> nu.Nu:
    """A whole single item editor: ``body`` over its item, its name and Config, for as long as the cell runs.

    Args:
        kind: The kind it edits.
        box: The cell's surface: ``entry``, a Field, and ``config``, an
            Accordion with ``settings`` (a Column with a ``name`` input) and
            ``item`` (a :class:`Where`), drawn with :data:`SECTIONS`.
        body: The item drawn and edited, both ways. Started again whenever
            the cell is pointed at another item.
        first: Drawn before anything else, eg a seed of the cell's settings.
        also: More reactions, eg the editor's own settings kept live.
    """
    show_name, renames = named(box.entry, box.config.settings.name)
    show_where, points = where(box.config.item)
    head = show_name >> show_where if first is None else first >> show_name >> show_where
    return nuspace.bracketed(
        head >> nu.ParallelAsync(editing(kind, body), *renames, *points, *also)
    )


def bounded(state: nu.Shape, entry: nu.Nu, settings: nu.Nu) -> tuple[nu.Nu, list[nu.Nu]]:
    """``state``'s min, max and step on ``entry`` and in Config, both ways.

    What a number input and a slider configure: their bounds or range, and step.
    ``state`` is the cell's own, eg ``nuspace.here(Range)``.

    Returns:
        What draws them, and the reactions keeping them live.
    """
    held = {"min": 0.0, "max": 100.0, "step": 1.0}
    setters = {"min": entry.set_min, "max": entry.set_max, "step": entry.set_step}

    def show(name: str) -> nu.Nu:
        value = getattr(state, name).fallback(held[name])
        return setters[name](value) >> getattr(settings, name).set_value(value)

    reactions = []
    for name in held:
        typed = getattr(settings, name)
        reactions += [
            nu.ReactEvery(typed.on_change(), getattr(state, name).set(nu.ToFloat(typed))),
            nu.ReactEvery(getattr(state, name).on_change(), show(name)),
        ]
    return nu.Sequential(*(show(name) for name in held)), reactions


def kind_options() -> list[dict[str, str]]:
    """The installed kinds as select options, ``{value: name, label}``, off the registry where the cell is built."""
    return [{"value": name, "label": spec.label} for name, spec in content_specs().items()]


def _ui(ref: StructuredRef) -> bool:
    """A ``rooted`` predicate: every chain but a bare ui one stays where it is."""
    return not isinstance(ref, UiRef)


def landed(term: nu.Nu, under: nu.Nu) -> nu.Nu:
    """``term`` with its bare ui chains spliced under ``under``, eg a kind's ``render`` under a column."""
    return nu.shape.reroot(term, under, rooted=_ui)


class ForKind(ScalarQuery):
    """The term ``build(kind, *args)`` makes for a kind known only at run time. Run it with ``nu.Eval``.

    The kind is found by name, through its installed spec
    (:func:`~nuspace.specs.content_spec`), and ``build`` called with it and
    the arguments' values, plain python, so it can use the kind's own
    behaviors (``find``, ``render``) and build refs on it
    (:func:`~nuspace.shapes.content.entries`). What it builds is a program of
    its own: its bare ui chains land under ``under``, and each of its store
    accesses is bracketed (``nuspace.bracketed``). Places in it resolve as
    the cell's own do.

    ``under`` is a ui ref the program names bare like any of its ui refs: it
    sits in a structural slot, never read, so the program's own rewrites
    land it first and what is built lands where it does.

    Args:
        kind: The kind's name.
        under: A ui ref what is built lands under.
        *args: More values ``build`` is given, evaluated first.
        build: A module level function, ``(kind, *args) -> nu.Nu``.

    Raises:
        LookupError: When it runs, no installed kind has the name
            (:func:`~nuspace.specs.content_spec`).
    """

    _structural = Declared(value=frozenset({1}), name="structural")

    def __init__(
        self,
        kind: nu.StrArg,
        under: nu.Nu,
        *args: nu.Arg,
        build: Callable[..., nu.Nu],
    ) -> None:
        super().__init__(kind, under, *args)
        self._payload["build"] = build

    def _term(self, kind: object, args: Sequence[object]) -> nu.Nu:
        made = self._payload["build"](content_spec(str(kind)).kind, *args)
        return nuspace.bracketed(landed(made, self._children[1]))

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, rest = children[0], children[2:]

        def thunk(rt: Runtime) -> object:
            return self._term(kind(rt), [arg(rt) for arg in rest])

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        kind, rest = children[0], children[2:]

        async def athunk(rt: Runtime) -> object:
            return self._term(await kind(rt), [await arg(rt) for arg in rest])

        return athunk


def render(kind: type[Content[Any]], level: str, scope_id: str, key: str) -> nu.Nu:
    """One item drawn in full by its kind's ``render``: a :class:`ForKind` build."""
    return kind.render(entries(kind, level, scope_id)[key])


def render_hit(kind: type[Content[Any]], level: str, scope_id: str, key: str) -> nu.Nu:
    """One item drawn as a search hit by its kind's ``render_hit``: a :class:`ForKind` build."""
    return kind.render_hit(entries(kind, level, scope_id)[key])


def drawing(
    kind: nu.StrArg,
    level: nu.StrArg,
    scope_id: nu.StrArg,
    key: nu.StrArg,
    under: nu.Nu,
    *,
    hit: bool = False,
) -> nu.Nu:
    """The item at an address, all four known only at run time, drawn under ``under``. Brackets itself.

    Raises:
        LookupError: When it runs, no installed kind has the name.
    """
    built = ForKind(kind, under, level, scope_id, key, build=render_hit if hit else render)
    return nu.Eval(built)
