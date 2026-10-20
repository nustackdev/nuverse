"""The studio: the team around the system, proposing changes on their own.

A headless job under the Design plane (:data:`STUDIO`, made and supervised
by the root's first open) drops a proposal into the inbox every so often:
who asks, why, and the tokens it would change. Some are good, some fail a
check on purpose, the way real proposals do; Review shows which before
anyone accepts. The inbox holds four at most, so the studio waits for the
team to decide before it sends more.

The people and the studio are fictional.
"""

from __future__ import annotations

import random
import time
from typing import Any

import nu

from . import checks
from . import spec as specs


__all__ = ["PAST", "PEOPLE", "POOL", "STUDIO", "arrive", "history", "job_cell", "job_of", "verdict"]


#: Who is on the team, and what they look after.
PEOPLE = {
    "Mira Okafor": "brand lead",
    "Tomás Rivera": "product, nuspace",
    "Lena Hartmann": "accessibility",
    "Kofi Mensah": "growth",
    "Ines Duarte": "docs",
    "Yuki Tanaka": "motion",
}


def _knob(key: str, value: float) -> dict[str, str]:
    return specs.apply_knob({}, key, value)


#: The proposals, in the order they arrive: ``(who, title, why, changes)``.
POOL: tuple[tuple[str, str, str, dict[str, str]], ...] = (
    (
        "Kofi Mensah",
        "Brighter Afterglow for the launch",
        "The primary button gets lost in the social card at thumbnail size. A lighter violet pops.",
        {
            "dusk:afterglow": "#a77ff0",
            "dawn:afterglow": "#a77ff0",
            "dusk:afterglow-hover": "#9a70e6",
            "dawn:afterglow-hover": "#9a70e6",
        },
    ),
    (
        "Tomás Rivera",
        "Rounder controls in nuspace",
        "Inputs and buttons read a little sharp next to the new cards. One step rounder, cards follow.",
        {"radius.md": "8", "radius.lg": "10"},
    ),
    (
        "Lena Hartmann",
        "Lift ink-3 on Dawn",
        "Labels in the light sidebar sit at 4.9 on ground-deep. A touch darker clears 5.5 without going loud.",
        {"dawn:ink-3": "#5f626a"},
    ),
    (
        "Yuki Tanaka",
        "Snappier menus",
        "Menus at 180ms feel late when you key through them. 150 still reads as motion, dialogs stay calm.",
        {"motion.base": "150", "motion.slow": "260"},
    ),
    (
        "Mira Okafor",
        "Afterglow, a few degrees warmer",
        "Next to Starlight the violet leans blue on most screens. Six degrees warmer keeps the two lights apart.",
        _knob("knob.afterglow", 306),
    ),
    (
        "Ines Duarte",
        "Reading text at 14",
        "Docs pages are long; 13 is right for tools and tight for prose. Base and controls up one step.",
        {"type.base": "14", "type.lg": "15"},
    ),
    (
        "Kofi Mensah",
        "Heavier titles",
        "Hero lines at 600 look polite in screenshots. 700 would carry the page.",
        {"type.title-weight": "700"},
    ),
    (
        "Lena Hartmann",
        "Starlight toward cyan",
        "Starlight and the first chart slot are close in hue. Turning Starlight eight degrees apart fixes it at the source.",
        _knob("knob.starlight", 248),
    ),
    (
        "Tomás Rivera",
        "A 5px grid for the dashboard",
        "The new dashboard packs better on fives. Only the spacing, nothing else moves.",
        {"space.unit": "5"},
    ),
    (
        "Mira Okafor",
        "A larger glyph on the tile",
        "At 32px the glyph looks small inside the tile. 600 of 1024 fills it without touching the edge.",
        {"mark.size": "600"},
    ),
    (
        "Ines Duarte",
        "A bigger hero line",
        "On wide screens the hero line stops short of the window. 64 fills the measure.",
        {"type.hero": "64"},
    ),
    (
        "Yuki Tanaka",
        "A cooler sky",
        "Dusk reads warm under the new violet. Four degrees cooler and a little more tint.",
        {**_knob("knob.sky", 268), "knob.tint": "1"},
    ),
)


def verdict(spec: dict[str, str], changes: dict[str, str]) -> str:
    """What the checks say about ``changes`` on ``spec``: ``clean``, ``1 fails``, ``2 under target``."""
    before = {r["key"]: r["verdict"] for r in checks.run(spec)["pairs"] + checks.run(spec)["rules"]}
    after = checks.run({**spec, **changes})
    fails = sum(
        1
        for r in after["pairs"] + after["rules"]
        if r["verdict"] == "fail" and before.get(r["key"]) != "fail"
    )
    under = sum(
        1
        for r in after["pairs"] + after["rules"]
        if r["verdict"] == "under target" and before.get(r["key"]) == "pass"
    )
    if fails:
        return f"{fails} fails"
    if under:
        return f"{under} under target"
    return "clean"


@nu.host
def arrive(inbox: list, cursor: int, now: float) -> list:
    """The inbox with the next proposal from :data:`POOL` on the end."""
    who, title, why, changes = POOL[cursor % len(POOL)]
    pid = f"p{cursor:03d}"
    return [
        *list(inbox or []),
        {
            "id": pid,
            "who": who,
            "role": PEOPLE[who],
            "title": title,
            "why": why,
            "changes": changes,
            "at": now,
        },
    ]


@nu.host
def wait(pace: float, first: bool) -> float:
    """Seconds until the next arrival: soon on a fresh start, then about ``pace``, never on the beat."""
    return 6.0 if first else max(4.0, pace * random.uniform(0.8, 1.2))  # noqa: S311


def job_of(root: nu.StrArg) -> nu.Str:
    """The studio's plane id: fixed under the root."""
    return nu.Str(root) + ".studio"


def job_cell(job: nu.StrArg) -> nu.Str:
    """The studio's one cell."""
    return nu.Str(job) + "_main"


#: Arrivals the studio starts with, seconds apart, before it settles into its pace.
PACE = 24.0


STUDIO = """\
import nu
import nustd.time
from nuspace import ops
from nuspace.system.utils import snap
from nudemos.design.kit import System, root_of
from nudemos.design.studio import PACE, arrive, wait

#: The inbox holds this many at most: past it the studio waits for decisions.
FULL = 4


@nu.host
def roomy(inbox):
    return len(inbox or []) < FULL


def deliver(root):
    def put():
        room = roomy(System.inbox.fallback([]))
        ready = System.paused.fallback(False).not_().and_(room)
        land = (
            System.inbox.set(arrive(System.inbox.fallback([]), System.cursor.fallback(0), nustd.time.time()))
            >> System.cursor.set(System.cursor.fallback(0) + 1)
            >> System.mail.set(System.mail.fallback(0) + 1)
        )
        return nu.IfDo(ready, land)

    return ops.atomic_state(ops.plane_state(root, put()))


def out(plane):
    def run(root):
        pace = snap(ops.plane_state(root, System.pace.fallback(PACE)))
        first = nu.Delay(wait(PACE, True)) >> deliver(root)
        return first >> nu.ForeverDo(nu.Delay(wait(pace, False)) >> deliver(root))

    return nu.let(snap(root_of(plane)), lambda root: run(nu.Str(root)))
"""


#: Decisions the team made before the space was opened: ``(who, title, verdict, days ago)``.
PAST = (
    ("Lena Hartmann", "One focus ring, in Afterglow", "accepted", 6.2),
    ("Kofi Mensah", "A glow behind the hero", "declined", 4.8),
    ("Ines Duarte", "Figures in tables in the mono voice", "accepted", 3.1),
    ("Tomás Rivera", "Sidebar on ground-deep in both themes", "accepted", 1.7),
    ("Yuki Tanaka", "A spring on the dialog", "declined", 0.9),
)


@nu.host
def history(now: float) -> list[dict[str, Any]]:
    """:data:`PAST` as decided proposals, dated back from ``now``."""
    return [
        {
            "id": f"h{i}",
            "who": who,
            "role": PEOPLE[who],
            "title": title,
            "why": "",
            "changes": {},
            "verdict": verdict,
            "at": now - days * 86400,
        }
        for i, (who, title, verdict, days) in enumerate(PAST)
    ]


def now() -> float:
    """Wall seconds, for plain callers."""
    return time.time()


def proposal_line(p: dict[str, Any]) -> str:
    """A proposal in one line, for lists."""
    return f"{p['who']}: {p['title']}"
