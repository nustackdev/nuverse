"""Dashboard: a night across the network at a glance.

A page header with its actions, a row of stat cards each with a sparkline
in its media, then a placed board: the observing hours chart two rows tall
on the left, the instrument split and the seeing chart stacked beside it,
and under them the queue by program next to a card of recent frames
linking to the instrument they came from.

The page sits in a Container, the kit's page frame, at its dashboard width.
Every child is reached from its container and named with ``.to(Kind)``
where it is placed: ``root["head"]``, ``board[0, 0]``, ``card.actions[0]``.
Its look and its content are slot props, put on screen with ``init()``; the
charts then take their data with ``set``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui as ui
from nudemos.recipes import meridian


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ["page"]


STATS = (
    ("Hours observed", "312", "+8.4%", "up", 101, 10.0, 3.0),
    ("Requests in queue", "47", "-6", "down", 202, 50.0, 8.0),
    ("Clear sky", "68%", "+4 pts", "up", 303, 64.0, 9.0),
    ("Frames captured", "18.2k", "+1.1k", "up", 404, 600.0, 120.0),
)

RECENT = (
    ("M51, the Whirlpool", "Kestrel 2, 24 x 120 s, L R G B", "4 min ago"),
    ("NGC 7000, North America", "Osprey, H alpha, 36 x 300 s", "38 min ago"),
    ("HD 209458 transit", "Falcon, photometry, 412 frames", "2 h ago"),
    ("Active region 3912", "Kite, H alpha, 90 s burst", "Yesterday"),
)

PROGRAMS = [
    ["Transients", 64, 52],
    ["Exoplanets", 88, 71],
    ["Variable stars", 42, 40],
    ["Deep sky", 120, 64],
    ["Solar", 18, 18],
    ["Outreach", 26, 12],
]


def _by_night(series: list[float], floor: float | None = None) -> list[list]:
    nights = meridian.night_labels()
    return [[n, v if floor is None else max(floor, v)] for n, v in zip(nights, series, strict=True)]


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The dashboard, drawn: every child shown, then the charts' data."""
    to = meridian.links(links)
    root = ui.ContainerRef("dashboard", props={"max_width": "dashboard", "gap": 6})

    # --- header ------------------------------------------------------------------------------
    head = root["head"].to(ui.RowRef.slot(align="end", gap=2, wrap=True, grow={"title": 1}))
    shown = [
        root.init(),
        head["title"]
        .to(
            ui.HeadingRef.slot(
                label="Tonight",
                level=1,
                size="2xl",
                eyebrow="Meridian network",
                subtitle="Saturday, October 25. Eleven of fourteen sites are open.",
            )
        )
        .init(),
        head["range"]
        .to(ui.ButtonRef.slot(label="Last 30 nights", variant="secondary", icon="calendar"))
        .init(),
        head["request"]
        .to(ui.ButtonRef.slot(label="Request time", icon="plus", href=to["catalog"]))
        .init(),
    ]

    # --- stats: tiles that wrap by width ------------------------------------------------------
    stats = root["stats"].to(ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=4))
    data: list[nu.Nu] = []
    for i, (label, value, delta, trend, seed, base, swing) in enumerate(STATS):
        card = stats[i].to(ui.CardRef.slot(size="sm"))
        spark = card.media.to(ui.Sparkline.slot(area=True, height=36))
        stat = card[0].to(ui.StatRef.slot(label=label, value=value, delta=delta, trend=trend))
        shown += [spark.init(), stat.init()]
        data.append(spark.set(meridian.night_series(seed, base, swing, n=14)))

    # --- the board: one tall chart beside two stacked ones ------------------------------------
    #
    #   [ hours ][ kinds  ]
    #   [ hours ][ seeing ]
    #   [ programs ][ recent ]
    board = root["board"].to(
        ui.GridRef.slot(cols="2fr 1fr", gap=4, span={(0, 0): {"rows": 2}}, stack_below=800)
    )

    hours = board[0, 0].to(ui.CardRef.slot(title="Observing hours", subtitle="Per night, by site"))
    live = hours.actions[0].to(ui.BadgeRef.slot(label="Live", variant="secondary", size="sm"))
    curve = hours[0].to(
        ui.AreaChart.slot(
            meridian.SITES,
            x_type="category",
            stack=True,
            smooth=True,
            height=440,
            legend=True,
            y_format="{value} h",
        )
    )
    shown.append(live.init())
    data.append(
        curve.set(
            {
                site: _by_night(meridian.night_series(11 * (k + 1), 2.6, 1.4))
                for k, site in enumerate(meridian.SITES)
            }
        )
    )

    kinds = board[0, 1].to(ui.CardRef.slot(title="Time by instrument", subtitle="Hours this month"))
    donut = kinds[0].to(
        ui.PieChart.slot(donut=True, total_label="hours", labels=False, legend=True, height=176)
    )
    data.append(donut.set({"Reflector": 1840, "Refractor": 620, "Spectrograph": 910, "Solar": 260}))

    seeing = board[1, 1].to(
        ui.CardRef.slot(title="Median seeing", subtitle="Arcsec, lower is sharper")
    )
    line = seeing[0].to(
        ui.LineChart.slot(
            ("Atacama", "La Palma"), x_type="category", smooth=True, height=150, y_min=0.4
        )
    )
    data.append(
        line.set(
            {
                "Atacama": _by_night(meridian.night_series(5, 0.75, 0.25, places=2), 0.45),
                "La Palma": _by_night(meridian.night_series(9, 1.0, 0.3, places=2), 0.45),
            }
        )
    )

    programs = board[2, 0].to(
        ui.CardRef.slot(title="Queue by program", subtitle="Requested against scheduled hours")
    )
    bars = programs[0].to(
        ui.BarChart.slot(
            ("Requested", "Scheduled"), height=248, legend=True, value_format="{value} h"
        )
    )
    data.append(bars.set(PROGRAMS))

    recent = board[2, 1].to(ui.CardRef.slot(title="Recent frames"))
    shown.append(
        recent.actions[0]
        .to(ui.LinkRef.slot(label="All frames", href=to["detail"], variant="muted", arrow=True))
        .init()
    )
    frames = recent[0].to(ui.ColumnRef.slot(gap=1))
    shown += [
        frames[i]
        .to(
            ui.PageLinkRef.slot(
                href=to["detail"], title=title, icon="image", description=description, meta=meta
            )
        )
        .init()
        for i, (title, description, meta) in enumerate(RECENT)
    ]

    return nu.Sequential(*shown, *data)
