"""The ``research`` Plane: a research desk on LLMs, where papers, claims and our own evals meet.

A three-person desk on what is new in large language models, and what of it
holds up. Opened the first time, its ``welcome`` cell builds the tree under
it, all of it pages it writes itself:

- Reading list: the papers, a page each with its summary, our notes, and
  the claims it bears on; a form links it to one more.
- Claims: the board, every claim scored live from the evidence for and
  against it, a page each with the score's history.
- Models: the models as their reports give them; their tokens per
  parameter weigh in on a claim.
- Evals: our own small suite run on Claude, a run a job in its own process,
  its answers landing one by one on the leaderboard, its page, and the
  claims they bear on.
- Watch: a probe that asks Claude a question every few minutes, on its own.
- Notebook: dated entries, the newest written from live numbers.

Every page reads and writes one desk in this plane's state
(:class:`.kit.Desk`), so a source linked to a claim moves the board, the
week's digest and the notebook at once.

- :mod:`.data`, :mod:`.baked`: the opening desk, and the opening runs (real answers, kept).
- :mod:`.evals`, :mod:`.views`: the suite and its grading; scores, digests, the leaderboard.
- :mod:`.kit`, :mod:`.job`, :mod:`.claude`: the store, the ops that make pages, the jobs.
- :mod:`.cells`: every cell's source.
"""

from __future__ import annotations

from nuspace import Plane

from . import cells


__all__ = ["PLANE"]


PLANE = Plane(
    "research",
    "Research",
    icon="atom",
    description="A research desk on LLMs: papers, claims and our own evals, all live.",
    meta={"editable": True, "full_width": True},
    cells=cells.ROOT,
    group="Demos",
    backend="async",
)
