"""What content Cells share: where their item is, their name as their label, kinds by name.

An editor of one item (a text input, a number input, ...) edits its own
cell's :data:`ITEM` by default. Its Config's Item section can point it at
another item of its kind: the scope's level (a cell, a plane, the space),
the scope's id or key (blank for this cell or this plane; an inline switch
says which the input holds, id by default) and the item's content key
(blank for :data:`ITEM`). Where it points is the cell's own state
(:class:`Target`), so two editors pointed at one item edit it together, and
a program can point one by writing it
(``nuspace.at.cell(id=c).state(Target).target.set(...)``).

Every editor draws on one surface, :class:`Editor`: its control in a Field
labelled with the cell's name, then Config. An editor names only its
control's kind and its own settings; :func:`editor` runs the rest.

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
    "BOUNDS",
    "BY_ID",
    "BY_KEY",
    "BY_OPTIONS",
    "DEFAULT_KIND",
    "ENTRY",
    "ITEM",
    "KIND",
    "LEVEL",
    "LEVEL_OPTIONS",
    "NAME",
    "SECTIONS",
    "SETTINGS",
    "TARGET",
    "Editing",
    "Editor",
    "ForKind",
    "Scope",
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
    "scoped",
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

#: A Config names the scope by its id (the default) or by its key. See identity.md.
BY_ID = "id"
BY_KEY = "key"

#: The switch beside the scope input: what the input holds.
BY_OPTIONS = [{"value": BY_ID, "label": "ID"}, {"value": BY_KEY, "label": "Key"}]

#: An editor's Config: its own settings, then where its item is.
SECTIONS = [{"id": "settings", "label": "Config"}, {"id": "item", "label": "Item"}]

#: The kind a viewer of any kind (:mod:`.item`, :mod:`.items`, :mod:`.item_picker`)
#: shows when its Config names none: text.
DEFAULT_KIND = "nuverse.Text"


class Target(nu.Shape):
    """Where the cell's item is, plain data: ``level``, ``scope``, ``by``, ``key``, and ``kind`` for a viewer.

    ``by`` says what ``scope`` holds: :data:`BY_ID` or :data:`BY_KEY`. A
    part missing or blank takes its default: a cell, this cell or this
    plane, by id, :data:`ITEM`. Kept in the cell's own state (:data:`TARGET`).
    """

    target = nustd.kv.PrimitiveDictRef.slot()


#: The running cell's :class:`Target`.
TARGET = nuspace.here(Target).target


#: The select a Config picks the scope level with, the control of a "Scope" Field.
LEVEL = nustd.ui.SelectRef.slot(options=LEVEL_OPTIONS)

#: The select a viewer's Config picks the kind with, the control of a "Kind" Field.
KIND = nustd.ui.SelectRef.slot(placeholder="No content kinds registered")


class Scope(nustd.ui.Row):
    """The scope's id or key, with the switch saying which, inline."""

    value = nustd.ui.InputRef.slot(label="Scope identity", placeholder="This cell or plane")
    by = nustd.ui.RadioGroupRef.slot(options=BY_OPTIONS, selected=BY_ID, orientation="horizontal")


class Where(nustd.ui.Column):
    """An editor's Item section: where the item it edits is."""

    level = nustd.ui.FieldRef.slot(label="Scope")
    scope = Scope.slot(gap=3, align="end", grow={"value": 1})
    key = nustd.ui.InputRef.slot(label="Item key", placeholder=ITEM)


class Config(nustd.ui.Accordion):
    """An editor's Config: its own settings, then where its item is (:data:`SECTIONS`)."""

    settings = nustd.ui.ColumnRef.slot(gap=3)
    item = Where.slot(gap=3)


class Editor(nustd.ui.Column):
    """Every single item editor's surface: the control in a Field labelled with the cell's name, then Config.

    An editor names its control's kind at the use site,
    ``ENTRY.control.to(nustd.ui.SliderRef.slot())``, and adds its
    own settings under :data:`SETTINGS` by name, after the cell's name.
    """

    entry = nustd.ui.FieldRef.slot()
    config = Config.slot(sections=SECTIONS)


class Editing(nu.Shape):
    """An editor cell's root: the :class:`Editor`, its parts spaced apart."""

    editor = Editor.slot(gap=3)


#: The Field an editor's control sits in: its label is the cell's name, its error why nothing is edited.
ENTRY = Editing.editor.entry

#: An editor's own settings, by name: ``SETTINGS["min"].to(nustd.ui.NumberInputRef.slot(...))``.
SETTINGS = Editing.editor.config.settings

#: The cell's name, the first of an editor's settings.
NAME = SETTINGS["name"].to(nustd.ui.InputRef.slot(label="Name"))


def scoped(level: nustd.ui.FieldRef, scope: nu.Nu) -> dict[str, nu.Nu]:
    """The scope's controls for :func:`where`: the level select in ``level``, the identity and its switch in a :class:`Scope`."""
    return {"level": level.control.to(LEVEL), "scope": scope.value, "by": scope.by}


def _given(held: nu.Nu, name: str) -> nu.Str:
    """One part of a target, ``""`` when missing."""
    return nu.Str(nu.str(nu.Dict(held).get_item(name, "")))


def kind_of(held: nu.Nu) -> nu.Str:
    """The kind a target names, :data:`DEFAULT_KIND` when it names none."""
    kind = _given(held, "kind")
    return nu.Str(nu.If(kind == "", DEFAULT_KIND, kind))


def pointed(
    held: nu.Nu,
    body: Callable[[str, nu.Str, nu.Str], nu.Nu],
    *,
    missing: Callable[[nu.Str], nu.Nu] | None = None,
) -> nu.Nu:
    """``body(level, scope id, key)`` for the item a target names, blanks filled.

    ``level`` is a python str, one of the three, so ``body`` can build a ref
    on it (:func:`~nuspace.shapes.content.entries`); the id and the key are
    terms.

    Named by key, the scope is resolved to its id in one read of the key
    index, the read ``nuspace.at.cell(key)`` and ``nuspace.at.plane(key)``
    make, then everything goes by that id. Resolved again, ``body`` started
    over, whenever that key's entry changes (set, moved, removed). A key no
    live row holds addresses nothing: ``missing(why)`` runs instead of
    ``body``. A blank key is this cell or this plane, as a blank id is.

    Args:
        held: A target, plain data (:class:`Target`).
        body: What to do with the item.
        missing: What to do while the key finds no row, given why. Nothing
            when left out.
    """
    scope, key = _given(held, "scope"), _given(held, "key")
    key = nu.Str(nu.If(key == "", ITEM, key))
    level = _given(held, "level")
    by_key = (_given(held, "by") == BY_KEY).and_(scope != "")

    def on(at: str, own: nu.StrArg, index: nustd.kv.DictRef) -> nu.Nu:
        by_id = body(at, nu.Str(nu.If(scope == "", own, scope)), key)
        gone = nu.Noop() if missing is None else missing(nu.Str(f"No {at} has the key ") + scope)

        def found(id: nu.Nu) -> nu.Nu:
            return nu.IfDo(nu.Str(id) == "", gone, body(at, nu.Str(id), key))

        resolved = nu.let(nuspace.atomic(index.get_item(scope, "")), found)
        keyed = nu.ReactLatest(index[scope].on_change(), resolved, initial=True)
        return nu.IfDo(by_key, keyed, by_id)

    keys = nuspace.Space.indexes
    return nu.IfDo(
        level == PLANE,
        on(PLANE, Here.plane, keys.plane_keys),
        nu.IfDo(level == SPACE, body(SPACE, nu.Str(""), key), on(CELL, Here.cell, keys.cell_keys)),
    )


def editing(
    kind: type[Content[Any]],
    body: Callable[[Any], nu.Nu],
    *,
    missing: Callable[[nu.Str], nu.Nu] | None = None,
) -> nu.Nu:
    """``body(item)`` over the item of ``kind`` the cell points at, started again when it points elsewhere.

    Runs for as long as the cell does. Bare: inside :func:`editor`, or a
    cell's ``nuspace.bracketed``. ``missing(why)`` runs instead while the
    cell points at a key no row holds (:func:`pointed`).
    """
    held = nuspace.atomic(TARGET.fallback({}))

    def edit(at: str, scope_id: nu.Str, key: nu.Str) -> nu.Nu:
        return body(entries(kind, at, scope_id)[key])

    return nu.ReactLatest(
        TARGET.on_change(), nu.let(held, lambda t: pointed(t, edit, missing=missing)), initial=True
    )


def where(
    controls: Mapping[str, nu.Nu],
    *,
    shown: Mapping[str, str] | None = None,
) -> tuple[nu.Nu, list[nu.Nu]]:
    """A Config section showing the cell's :class:`Target` and writing it, both ways.

    Args:
        controls: The control asking each part of the target it asks, by
            name, in the order they draw: ``kind`` and ``level`` selects
            (:data:`KIND`, :data:`LEVEL`), ``scope`` and ``by`` from
            :func:`scoped`, ``key`` an input.
        shown: What a select shows for a part the target leaves blank, by
            name. ``level`` shows :data:`~nuspace.shapes.content.CELL`,
            ``by`` :data:`BY_ID`.

    Returns:
        What draws it, and the reactions keeping it and the target in step.
    """
    blanks = {"level": CELL, "by": BY_ID, **(shown or {})}
    held = nu.Dict(TARGET.fallback({}))

    def given(name: str) -> nu.Nu:
        value = _given(held, name)
        return nu.If(value == "", blanks[name], value) if name in blanks else value

    show = nu.Sequential(*(control.set(given(f)) for f, control in controls.items()))
    asked = nu.Dict.of(**{f: nu.Str(nu.ToStr(control)).strip() for f, control in controls.items()})
    keep = TARGET.set(asked)
    reactions = [nu.ReactEvery(control.on_change(), keep) for control in controls.values()]
    return show, [*reactions, nu.ReactEvery(TARGET.on_change(), show)]


def named() -> tuple[nu.Nu, list[nu.Nu]]:
    """The cell's name as the :data:`ENTRY` label and in the :data:`NAME` setting, renamed from there.

    Returns:
        What draws it, and the reactions keeping it live.
    """
    called = nuspace.Space.cells[Here.cell].name
    show = ENTRY.set_label(called.fallback("")) >> NAME.set(called.fallback(""))
    renamed = nuspace.atomic(nuspace.cell.rename(Here.cell, nu.Str(NAME)))
    return show, [
        nu.ReactEvery(NAME.on_change(), renamed),
        nu.ReactEvery(called.on_change(), show),
    ]


def editor(
    kind: type[Content[Any]],
    body: Callable[[Any], nu.Nu],
    *,
    first: nu.Nu | None = None,
    also: Sequence[nu.Nu] = (),
) -> nu.Nu:
    """A whole single item editor on :class:`Editor`: ``body`` over its item, its name and Config, for as long as the cell runs.

    Args:
        kind: The kind it edits.
        body: The item drawn and edited, both ways, on the editor's control.
            Started again whenever the cell is pointed at another item.
        first: Drawn right after the cell's name, eg a seed of the cell's
            settings: what it writes under :data:`SETTINGS` draws after the name.
        also: More reactions, eg the editor's own settings kept live.
    """
    item = Editing.editor.config.item
    show_name, renames = named()
    show_where, points = where({**scoped(item.level, item.scope), "key": item.key})
    head = nu.Sequential(show_name, *([] if first is None else [first]), show_where)

    def found(held: nu.Nu) -> nu.Nu:
        return ENTRY.set_error("") >> body(held)

    # A key that finds no row: said on the entry, nothing edited until it does.
    edits = editing(kind, found, missing=ENTRY.set_error)
    return nuspace.bracketed(head >> nu.ParallelAsync(edits, *renames, *points, *also))


#: The settings a number input and a slider share: min, max and step, under :data:`SETTINGS`.
BOUNDS = {
    "min": SETTINGS["min"].to(nustd.ui.NumberInputRef.slot(label="Min")),
    "max": SETTINGS["max"].to(nustd.ui.NumberInputRef.slot(label="Max", default=100)),
    "step": SETTINGS["step"].to(
        nustd.ui.NumberInputRef.slot(label="Step", min=0, step=0.1, default=1)
    ),
}


def bounded(state: nu.Shape, control: nu.Nu) -> tuple[nu.Nu, list[nu.Nu]]:
    """``state``'s min, max and step on ``control`` and in :data:`BOUNDS`, both ways.

    What a number input and a slider configure: their bounds or range, and step.
    ``state`` is the cell's own, eg ``nuspace.here(Range)``.

    Returns:
        What draws them, and the reactions keeping them live.
    """
    held = {"min": 0.0, "max": 100.0, "step": 1.0}
    setters = {"min": control.set_min, "max": control.set_max, "step": control.set_step}

    def show(name: str) -> nu.Nu:
        value = getattr(state, name).fallback(held[name])
        return setters[name](value) >> BOUNDS[name].set_value(value)

    reactions = []
    for name in held:
        typed = BOUNDS[name]
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
