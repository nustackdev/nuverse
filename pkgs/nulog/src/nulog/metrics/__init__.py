"""nulog.metrics -- metric time-series store: shapes + write/read primitives.

Module layout:
- :mod:`.shapes` -- store layout (``Metrics`` / ``MetricSeries`` / ``MetricPoint``).
- :mod:`.ops`    -- write + read primitives (``observe`` / ``range`` / ``sample``).

Writes are one op (``nulog.observe(name, value)``); reads are two primitives
(``range``, ``sample``) that ride kh57's shifted-key substrate.
"""

from __future__ import annotations

from .ops import observe, range, sample
from .shapes import MetricPoint, Metrics, MetricSeries


__all__ = [
    "MetricPoint",
    "MetricSeries",
    "Metrics",
    "observe",
    "range",
    "sample",
]
