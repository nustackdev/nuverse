"""The ``log`` Plane: nulog entries and metrics. Empty for now."""

from __future__ import annotations

from nuspace import Plane


__all__ = ["PLANE"]


PLANE = Plane(
    "log",
    "Log",
    description="Entries and metrics from nulog.",
    meta={"editable": True, "full_width": True},
    group="Observe",
    backend="async",
)
