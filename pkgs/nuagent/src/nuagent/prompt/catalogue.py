"""The catalogue: every name the model can write against, one line each, read off ``nu.inspect``.

Generated on every render, never stored. A hand-written vocabulary rots, and
a stale line in a prompt is worse than none: the model takes it as fact and
follows a wrong name off a cliff. These are the records the ``Inspect`` atom
and the docs read, so a rename in nu is a rename in the next prompt.

The default is the flat ``nu`` namespace, the kernel and the mem fabric,
because that is how a program spells them (``nu.ForEachDo``, ``nu.IntRef``).
Fabrics outside it are left out unless the caller binds one and names its
module (``"nustd.kv"``): listing a fabric the run cannot resolve spends
context on Refs the model must not use. The nu/inspect piece teaches how to
read the rest.

Host-side names are left out: the kind bases, the runners and the renderers
under ``nu.lang`` (:data:`HOST`). A program never names them, and a model
that sees ``nu.run`` in a list of things to write calls it inside ``out()``.

Each line is the name as a program writes it (``nu.Sum``, never bare
``Sum``: a model read a bare list under a ``## nu`` heading as names in
scope) and its summary only. Args, notes and examples are one
``nu.inspect.Inspect("<path>")`` away, and the prose says so.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING

from nu.inspect import (
    catalogue_builders,
    catalogue_calls,
    catalogue_interactions,
    catalogue_services,
    catalogue_shapes,
)

from .section import Section


if TYPE_CHECKING:
    from nu.inspect import Record


__all__ = ["HEAD", "HOST", "MODULES", "catalogue", "render"]


#: What the catalogue lists by default: the flat kernel and the mem fabric.
MODULES: tuple[str, ...] = ("nu",)

#: Modules whose names a program never writes: the kinds, the runners, the renderers.
HOST: tuple[str, ...] = ("nu.lang", "nu.factory.core")

#: Heads the section, and says where the rest of each record is.
HEAD = (
    "# Catalogue\n\n"
    "Every name you can write against, one line each, generated from the installed "
    "version. For args, notes and examples, return "
    '`nu.inspect.Inspect("<the name>")` from `out()` and read it next turn.'
)

#: The groups each module is listed in, in this order.
GROUPS = (
    ("forms and refs", catalogue_builders),
    ("interactions", catalogue_interactions),
    ("functions", catalogue_calls),
    ("shapes", catalogue_shapes),
    ("services", catalogue_services),
)


def catalogue(*modules: str | ModuleType) -> Section:
    """The catalogue as a section named ``catalogue``.

    Args:
        *modules: dotted names or modules to list. Defaults to :data:`MODULES`.
    """
    listed = modules or MODULES
    return Section("catalogue", lambda: render(*listed))


def render(*modules: str | ModuleType) -> str:
    """:data:`HEAD`, then per module a heading and one ``name  summary`` line per subject."""
    return "\n\n".join([HEAD, *(_module(m) for m in modules or MODULES)])


def _module(module: str | ModuleType) -> str:
    found = module if isinstance(module, ModuleType) else importlib.import_module(module)
    lines = [f"## {found.__name__}"]
    for title, listed in GROUPS:
        records = [r for r in listed(found) if not _host(r)]
        if records:
            lines.append(f"\n{title}:")
            lines.extend(_line(found.__name__, r) for r in records)
    return "\n".join(lines)


def _host(record: Record) -> bool:
    module = getattr(record.target, "__module__", None) or ""
    return any(module == m or module.startswith(m + ".") for m in HOST)


def _line(module: str, record: Record) -> str:
    """The name as a program writes it, then its summary."""
    summary = (record.summary or "-").rstrip(".")
    return f"  {module + '.' + record.name:<28} {summary}"
