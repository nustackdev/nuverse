"""The viewer's knobs: defaults, option sets, bounds, pace.

One place for the numbers you tune. The Config plane saves its own values
for the ones a person changes (the store, the pace, the count, the window);
these are what a plane starts with before anything is saved.
"""

from __future__ import annotations

from ..messages.types import LEVELS


__all__ = [
    "DEFAULT_COUNT",
    "DEFAULT_EVERY",
    "DEFAULT_LEVEL",
    "DEFAULT_MODE",
    "DEFAULT_WINDOW",
    "KEYS_CAP",
    "LEVEL_OPTIONS",
    "LEVEL_VARIANTS",
    "MAX_COUNT",
    "MAX_EVERY",
    "MIN_COUNT",
    "MIN_EVERY",
    "MODE_OPTIONS",
    "MODE_TAIL",
    "MODE_TAKE",
    "OVERVIEW_CAP",
    "SAMPLE_LIMIT",
    "WINDOW_OPTIONS",
]


# ---- messages -------------------------------------------------------------

DEFAULT_LEVEL = "all"
LEVEL_OPTIONS: tuple[str, ...] = (DEFAULT_LEVEL, *LEVELS)

# The badge each level draws as: info is the quiet default, warnings and
# errors stand out.
LEVEL_VARIANTS: dict[str, str] = {
    "debug": "neutral",
    "info": "secondary",
    "warning": "warn",
    "error": "danger",
    "critical": "danger",
}

MODE_TAIL = "tail"
MODE_TAKE = "take"
MODE_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": MODE_TAIL, "label": "Newest"},
    {"value": MODE_TAKE, "label": "Oldest"},
)
DEFAULT_MODE = MODE_TAIL

# How many entries one read takes. The min stops empty reads; the max is a
# cap so a big number in the field can't balloon one repaint. A read costs
# O(count) whatever the stream holds.
MIN_COUNT = 1
MAX_COUNT = 10_000
DEFAULT_COUNT = 200


# ---- metrics --------------------------------------------------------------

# Seconds as strings, so a select round-trips them. "0" is the whole series.
WINDOW_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": "60", "label": "1 min"},
    {"value": "300", "label": "5 min"},
    {"value": "900", "label": "15 min"},
    {"value": "3600", "label": "1 h"},
    {"value": "21600", "label": "6 h"},
    {"value": "86400", "label": "24 h"},
    {"value": "0", "label": "All"},
)
DEFAULT_WINDOW = "300"

# Points drawn per repaint, whatever the window holds: a kh57 sample costs
# about twice this in reads, at a thousand points or a billion.
SAMPLE_LIMIT = 500


# ---- both -----------------------------------------------------------------

# Stream and series names a picker lists at most, read in key order.
KEYS_CAP = 1_000

# Streams and series the overview lists at most: it reads one entry, or a
# small sample, per name on every look.
OVERVIEW_CAP = 50

# Seconds between looks at the store. A secondary only sees the writer's
# commits when it looks, so this is how live the views are.
DEFAULT_EVERY = 1.0
MIN_EVERY = 0.2
MAX_EVERY = 60.0
