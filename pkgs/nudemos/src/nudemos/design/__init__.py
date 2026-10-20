"""The ``design`` Plane: the nustack design system as one live spec, and everything drawn from it.

One spec in the Design plane's state (:class:`.kit.System`): every color in
both themes, the type ladder, the grid, the radii, the durations and the
mark's own settings. Every page draws from it as it stands, so one change
anywhere moves the swatches, the mark, the kit's controls, the mocks and the
checks at once:

- Tokens: four knobs that turn the palette as one, every token in a table,
  the history; under it Color, Type, Shape and Motion, each with its own
  levers and drawings.
- Mark: the Nu mark built from the spec (a port of the brand's logo build),
  a size ladder on both grounds, six variants one step away, its live SVG.
- Components: the kit's controls drawn in the current tokens.
- Mocks: the nustack.dev hero, a nuspace screen, the social card, the README.
- Checks: WCAG contrast for every pair that must read, both themes, and the
  language's rules, flagged live.
- Review: the team's proposals, arriving on their own from a headless studio
  job, each checked before anyone accepts.
- Export: a release is a page and a job in its own process that writes the
  tokens, SVGs, PNGs drawn with Pillow, and a favicon into its state.
- Principles: the foundations, in the language's words.

- :mod:`.spec`, :mod:`.color`, :mod:`.checks`: the tokens and their math, plain Python.
- :mod:`.logo`, :mod:`.glyph`, :mod:`.raster`, :mod:`.draw`, :mod:`.fonts`: the drawings.
- :mod:`.kit`, :mod:`.studio`, :mod:`.job`: the state, the studio, the export job.
- :mod:`.cells`, :mod:`.principles`: every cell's source.
"""

from __future__ import annotations

from nuspace import Plane

from . import cells


__all__ = ["PLANE"]


_WIDE = {"editable": True, "full_width": True, "compact": True}


def _page(
    name: str, label: str, icon: str, page_cells: tuple[tuple[str, str], ...], *children: Plane
) -> Plane:
    return Plane(
        f"design_{name}",
        label,
        icon=icon,
        meta=_WIDE,
        cells=page_cells,
        children=children,
        backend="async",
    )


PLANE = Plane(
    "design",
    "Design",
    icon="palette",
    description="The nustack design system: one live spec, and every swatch, control, mock and asset drawn from it.",
    meta=_WIDE,
    cells=cells.ROOT,
    children=(
        _page(
            "tokens",
            "Tokens",
            "layers",
            cells.TOKENS,
            _page("color", "Color", "sun", cells.COLOR),
            _page("type", "Type", "type", cells.TYPE),
            _page("shape", "Shape", "box", cells.SHAPE),
            _page("motion", "Motion", "activity", cells.MOTION),
        ),
        _page("mark", "Mark", "hexagon", cells.MARK),
        _page("components", "Components", "puzzle", cells.COMPONENTS),
        _page("mocks", "Mocks", "image", cells.MOCKS),
        _page("checks", "Checks", "shield", cells.CHECKS),
        _page("review", "Review", "inbox", cells.REVIEW),
        _page("export", "Export", "package", cells.EXPORT),
        _page("principles", "Principles", "book-open", cells.PRINCIPLES),
    ),
    group="Demos",
    backend="async",
)
