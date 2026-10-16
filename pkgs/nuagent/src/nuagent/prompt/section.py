"""One named piece of the prompt, and the three edits a caller makes to a tuple of them."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple


if TYPE_CHECKING:
    from collections.abc import Callable


__all__ = ["Section", "inserted", "replaced", "without"]


class Section(NamedTuple):
    """One named piece of the prompt. ``text`` is called on render, so generated parts are live."""

    name: str
    text: Callable[[], str]

    def render(self) -> str:
        """The section's text, without the blank lines around it."""
        return self.text().strip("\n")


def without(parts: tuple[Section, ...], *names: str) -> tuple[Section, ...]:
    """``parts`` minus every section named in ``names``."""
    return tuple(s for s in parts if s.name not in names)


def replaced(parts: tuple[Section, ...], section: Section) -> tuple[Section, ...]:
    """``parts`` with the section of the same name swapped for ``section``."""
    return tuple(section if s.name == section.name else s for s in parts)


def inserted(
    parts: tuple[Section, ...],
    section: Section,
    *,
    before: str | None = None,
    after: str | None = None,
) -> tuple[Section, ...]:
    """``parts`` with ``section`` spliced in next to an anchor, or at the end without one.

    Raises:
        KeyError: when the anchor names no section.
    """
    anchor = before or after
    if anchor is None:
        return (*parts, section)
    names = [s.name for s in parts]
    if anchor not in names:
        msg = f"no section named {anchor!r}"
        raise KeyError(msg)
    at = names.index(anchor) + (0 if before else 1)
    return (*parts[:at], section, *parts[at:])
