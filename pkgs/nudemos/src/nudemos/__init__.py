"""nudemos: the Nu demos as nuspace Planes.

- :mod:`.counter`: a count ticking once a second, in its cell's state.
- :mod:`.sampled`: a kh57 series growing forever, charted from a sample.
- :mod:`.tour`: the two above, nested under one plane.
- :mod:`.movies`: a film base, every film and person its own live page.
- :mod:`.mnist`: a CNN trained on MNIST, steered live, every run tracked. Needs the ``mnist`` extra.
- :mod:`.memes`: a live terminal over a meme market, synced from Solana.
- :mod:`.agents`: Claude Code sessions, run, steered and orchestrated from a space.
- :mod:`.design`: the nustack design system as one live spec, every mock, check and asset drawn from it. Needs the ``design`` extra.
- :mod:`.ops`: a storefront run from a space: real jobs, logs, deploys, incidents and alert rules. Needs the ``ops`` extra.
- :mod:`.data`: a coffee roaster's books as live dashboards over a million rows, fed by a stream and an importer. Needs the ``data`` extra.
- :mod:`.research`: an LLM research desk: papers weighed against claims, our own evals on Claude beside them. Needs the ``research`` extra.
- :mod:`.recipes`: the kit's page recipes, each a live, editable page, linked to each other.
- :mod:`.knowledge`: a team wiki and handbook where pages query the base and facts are cited everywhere. Needs the ``knowledge`` extra.

nuspace finds this package through the ``nuspace.extensions`` entry point,
which names :func:`extension`. Nothing is imported here at module scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from nuspace import Extension


__all__ = ["extension"]


def extension() -> Extension:
    """The tour and the demo planes, as one extension."""
    from nuspace import Extension

    from . import (
        agents,
        counter,
        data,
        design,
        knowledge,
        memes,
        mnist,
        movies,
        ops,
        recipes,
        research,
        sampled,
        tour,
    )

    return Extension(
        planes=(
            tour.PLANE,
            counter.PLANE,
            sampled.PLANE,
            movies.PLANE,
            mnist.PLANE,
            memes.PLANE,
            agents.PLANE,
            knowledge.PLANE,
            research.PLANE,
            design.PLANE,
            data.PLANE,
            ops.PLANE,
            recipes.PLANE,
        )
    )
