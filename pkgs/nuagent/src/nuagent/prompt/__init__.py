"""The opening prompt: ordered sections, then the task.

A prompt is a tuple of named :class:`Section` s, rendered in order and joined,
with the task last under ``# Task``. The order is the argument: how to reply
(:mod:`nuagent.protocol`), what Nu is and how to write it (nuskills pieces),
what exists (the :func:`catalogue`, generated), what the world holds (the
:func:`surface`, generated, when the caller has one), then what to do. The
task goes last because it is the one part that changes per run and a model
attends hardest to the end of what it reads.

Which sections a run needs depends on the run, so the set is data: a caller
adds or drops nuskills pieces by id, or edits the tuple with :func:`without`,
:func:`replaced` and :func:`inserted`::

    from nuagent import prompt

    text = prompt.opening(task)                                # protocol, nu, catalogue
    text = prompt.opening(task, prompt.sections(add=prompt.NUSPACE))
    text = prompt.opening(task, prompt.sections(app=(Board, Task)))

The text lives in three places and is written in none of them here:
``protocol/`` holds the agent's own part, nuskills the Nu prose, and
``nu.inspect`` the catalogue and the surface, read live on every render so a
rename in nu is a rename in the next prompt. Nothing is a format string: the
prose is full of dict literals, so sections join by concatenation only.

The prompt is built in Python before the run, then handed to
:func:`nuagent.core.seed` as plain text. It is not a Nu term.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

import nu
import nuskills
from nuagent import protocol
from nuagent.core import Run
from nuskills.skills import SKILLS

from .catalogue import MODULES, catalogue
from .section import Section, inserted, replaced, without
from .surface import surface


if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import ModuleType

    from nu.lang import Nu


__all__ = [
    "MODULES",
    "NU",
    "NUSPACE",
    "TASK",
    "Section",
    "catalogue",
    "inserted",
    "opening",
    "piece",
    "protocol_section",
    "replaced",
    "sections",
    "skill",
    "surface",
    "without",
]


#: Heads the task, the last thing in every prompt.
TASK = "# Task\n\n"


def skill(name: str) -> tuple[str, ...]:
    """The piece ids a nuskills skill loads up front (its ``inline`` pieces), in its order.

    Args:
        name: a skill in ``nuskills.skills.SKILLS``, eg ``"nu"`` or ``"nuspace"``.
    """
    for found in SKILLS:
        if found.name == name:
            return found.inline
    msg = f"no nuskills skill {name!r}"
    raise KeyError(msg)


#: The Nu pieces every run gets: what the ``nu`` skill loads up front.
NU: tuple[str, ...] = skill("nu")

#: The pieces for a run inside a nuspace: what the ``nuspace`` skill loads up front.
NUSPACE: tuple[str, ...] = skill("nuspace")


def piece(piece_id: str) -> Section:
    """A nuskills piece as a section named by its id (``"nu/crashcourse"``).

    Raises:
        KeyError: when nuskills has no such piece. Checked here, not on render,
            so a typo fails where the prompt is put together.
    """
    nuskills.load(piece_id)
    return Section(piece_id, lambda: nuskills.read(piece_id))


def protocol_section() -> Section:
    """The agent's own text: how to reply, what comes back, how the run ends."""
    return Section("protocol", protocol.prompt)


def sections(
    pieces: Iterable[str] = NU,
    *,
    add: Iterable[str] = (),
    drop: Iterable[str] = (),
    modules: Iterable[str | ModuleType] = MODULES,
    app: Iterable[ModuleType | type] = (),
    run: type | None = Run,
) -> tuple[Section, ...]:
    """The default sections: protocol, pieces, catalogue, then the surface when there is an app.

    Args:
        pieces: nuskills piece ids, in order. Defaults to :data:`NU`.
        add: more piece ids, after ``pieces``. A piece named twice is kept once,
            where it first appears, so ``add=NUSPACE`` is safe over ``NU``.
        drop: piece ids to leave out.
        modules: what the catalogue lists. Add a fabric the run binds
            (``"nustd.kv"``); empty leaves the catalogue out.
        app: the caller's Shapes and Services, or modules holding them. Empty
            leaves the surface out.
        run: the Shape the model ends the run through, shown on the surface.
            One other than the mem :class:`~nuagent.core.Run` is shown even
            with no ``app``: the model cannot guess its fabric or its base.

    Returns:
        A tuple of sections for :func:`opening`.
    """
    dropped = set(drop)
    ids = [p for p in dict.fromkeys([*pieces, *add]) if p not in dropped]
    found = [protocol_section(), *(piece(p) for p in ids)]
    modules = tuple(modules)
    if modules:
        found.append(catalogue(*modules))
    app = tuple(app)
    # A run Shape of the caller's own is shown even with no app: the model has to copy it.
    if app or run not in (Run, None):
        found.append(surface(*app, run=run))
    return tuple(found)


@overload
def opening(task: str, parts: Iterable[Section] | None = None) -> str: ...


@overload
def opening(task: Nu, parts: Iterable[Section] | None = None) -> Nu: ...


def opening(task: str | Nu, parts: Iterable[Section] | None = None) -> str | Nu:
    """The opening prompt: every section in order, then the task.

    Args:
        task: what the run is for. Last, under ``# Task``. A str, or a Str
            term for a task known only when the run is under way (a message
            read off state): the sections are rendered here either way.
        parts: the sections. Defaults to :func:`sections` with no arguments.

    Returns:
        The text for :func:`nuagent.core.seed`: a str for a str task, else a
        ``Str`` term.
    """
    rendered = [s.render() for s in (sections() if parts is None else parts)]
    head = "\n\n".join([*rendered, TASK])
    if isinstance(task, str):
        return head + task.strip() + "\n"
    return head + nu.Str(task).strip() + "\n"
