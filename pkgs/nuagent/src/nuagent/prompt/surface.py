"""The surface: the caller's Shapes and Services, the world the task is about, read off ``nu.inspect``.

The catalogue is the language; this is the world. A model shown only the
language spends its first turns finding out that a ``Board`` exists and what
a task record holds, and both facts are already on the caller's classes. So
they are rendered here, generated on every render like the catalogue.

**A Shape is shown as the declaration the model repeats.** The model's module
is loaded on its own, so it redeclares every Shape it touches, and the
cheapest way to get that right is to copy it. Each Shape renders as a class
in annotation form, the Ref named from its fabric (``nu.ListRef[int]`` is
mem, ``nustd.kv.IntRef`` is kv), which builds as it is. A plain list of
``name  type`` lines was tried first: a model copied ``nums = nu.ListRef[int]``
off it, an assignment, not a slot. Slot config the annotation cannot carry
follows as a comment. A Service is one line per method.

One level, never deeper: the verbs a slot carries are one ``Inspect`` away.

The run Shape comes last on its own: it is not the caller's, it is how the
model ends the run, and the protocol tells the model to declare it with the
fabric listed here.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING

from nu import Shape
from nu.inspect import (
    ShapeRecord,
    catalogue_services,
    catalogue_shapes,
    parse_service,
    parse_shape,
)
from nu.inspect.entry import is_service, is_shape

from .section import Section


if TYPE_CHECKING:
    from nu.inspect import Record


__all__ = ["HEAD", "RUN", "records", "render", "surface"]


#: Heads the section. The facts that have to land: these are the task's world,
#: they are already bound, and you redeclare what you touch. Binding nothing
#: of your own is the protocol's rule, not repeated here.
HEAD = """\
# Your world

The Shapes and Services below are the world the task is about. They are not
examples, and their fabrics are already bound around your program.

- Declare each Shape you touch in your module, at module level, by copying its
  declaration below as it is. Addressing is by slot name, so a matching
  declaration reaches this world.
- The verbs a slot or method carries are not listed here. Return
  `nu.inspect.Inspect("<the path on its heading>.<name>")` to read them."""


#: The run Shape's prose. Its docstring is written for the host, this for the model.
RUN = "How you end the run: set `done` to True in the program that finishes the task."


def surface(*app: ModuleType | type, run: type | None = None) -> Section:
    """The surface as a section named ``surface``.

    Args:
        *app: Shapes and Services, or modules holding them. A module adds every
            Shape and Service it declares, in its order.
        run: the Shape the model ends the run through, rendered last.

    Raises:
        TypeError: for anything that is not a module, a Shape or a Service.
            Checked here, so a wrong argument fails where the prompt is put
            together, not mid-render.
    """
    records(app)
    return Section("surface", lambda: render(*app, run=run))


def render(*app: ModuleType | type, run: type | None = None) -> str:
    """:data:`HEAD`, one block per class, then ``run``."""
    blocks = [_block(r) for r in records(app)]
    if run is not None:
        blocks.append(_block(parse_shape(run), prose=RUN))
    return "\n\n".join([HEAD, *blocks])


def records(app: tuple[ModuleType | type, ...]) -> tuple[Record, ...]:
    """A ShapeRecord or ServiceRecord per class, in order, each once."""
    found: dict[str, Record] = {}
    for item in app:
        if isinstance(item, ModuleType):
            listed = (*catalogue_shapes(item), *catalogue_services(item))
        elif is_shape(item):
            listed = (parse_shape(item),)
        elif is_service(item):
            listed = (parse_service(item),)
        else:
            msg = f"not a module, Shape or Service: {item!r}"
            raise TypeError(msg)
        for record in listed:
            found.setdefault(record.path, record)
    return tuple(found.values())


def _block(record: Record, *, prose: str | None = None) -> str:
    """Heading, prose (the record's own, or ``prose`` in its place), then the entries."""
    shape = isinstance(record, ShapeRecord)
    lines = [f"## {'shape' if shape else 'service'} {record.target.__name__}  ({record.path})"]
    if prose is not None:
        lines.append(prose)
    else:
        if record.summary:
            lines.append(record.summary)
        lines.extend(f"- {note}" for note in record.notes)
    lines.append("")
    if shape:
        lines.extend(["```python", *_declaration(record), "```"])
    else:
        lines.extend(f"  {e.name:<18} {e.kind:<7} {e.type}" for e in record.entries)
    return "\n".join(lines)


def _declaration(record: Record) -> list[str]:
    """The Shape as a class in annotation form, slot config as a trailing comment."""
    owner = record.target
    lines = [f"class {owner.__name__}({_base(owner)}):"]
    for entry in record.entries:
        ref = _spelled(owner._slots[entry.name].ref_cls)
        typed = f"{ref}[{entry.type}]" if entry.kind == "shape" else _qualified(ref, entry.type)
        line = f"    {entry.name}: {typed}"
        lines.append(f"{line}  # {entry.config}" if entry.config else line)
    return lines


def _base(owner: type) -> str:
    """The Shape class ``owner`` derives from, spelled from its package: ``nuspace.PlaneState``.

    The base is part of what the model copies: a nuspace ``PlaneState`` lands
    in the space's store, a bare ``nu.Shape`` of kv Refs lands nowhere.
    """
    base = owner.__bases__[0]
    if base is Shape:
        return "nu.Shape"
    top = base.__module__.partition(".")[0]
    if getattr(importlib.import_module(top), base.__name__, None) is base:
        return f"{top}.{base.__name__}"
    return f"{base.__module__}.{base.__name__}"


def _qualified(ref: str, shown: str) -> str:
    """``ListRef[int]`` spelled from where ``ref`` lives: ``nu.ListRef[int]``."""
    head, _, _ = ref.rpartition(".")
    return f"{head}.{shown}" if head else shown


def _spelled(ref_cls: type) -> str:
    """How a module writes a Ref class: ``nu.ListRef`` for mem, ``nustd.<fabric>.X`` else."""
    parts = ref_cls.__module__.split(".")
    if parts[0] == "nu":
        return f"nu.{ref_cls.__name__}"
    if parts[0] == "nustd" and len(parts) > 1:
        return f"nustd.{parts[1]}.{ref_cls.__name__}"
    return f"{ref_cls.__module__}.{ref_cls.__name__}"
