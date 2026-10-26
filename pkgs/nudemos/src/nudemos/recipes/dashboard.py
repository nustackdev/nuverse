"""Dashboard: a night across the network at a glance.

A page header with its actions, a row of stat cards each with a sparkline,
then a bento of charts: one featured chart two columns wide and two rows
tall, two small ones stacked beside it, and a wide bar chart next to a card
of recent frames linking to the instrument they came from.

The page sits in a Container, the kit's page frame, at its dashboard width.
Every node is built as a Ref and put on screen with ``init()``, its look and
its content both props; the charts then take their data with ``set``.
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
    ("hours", "Hours observed", "312", "+8.4%", "up", 101, 10.0, 3.0),
    ("queue", "Requests in queue", "47", "-6", "down", 202, 50.0, 8.0),
    ("clear", "Clear sky", "68%", "+4 pts", "up", 303, 64.0, 9.0),
    ("frames", "Frames captured", "18.2k", "+1.1k", "up", 404, 600.0, 120.0),
)

RECENT = (
    ("m51", "M51, the Whirlpool", "Kestrel 2, 24 x 120 s, L R G B", "4 min ago"),
    ("ngc7000", "NGC 7000, North America", "Osprey, H alpha, 36 x 300 s", "38 min ago"),
    ("hd209458", "HD 209458 transit", "Falcon, photometry, 412 frames", "2 h ago"),
    ("sun", "Active region 3912", "Kite, H alpha, 90 s burst", "Yesterday"),
)


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The dashboard, drawn: every node shown, then the charts' data."""
    to = meridian.links(links)
    shown: list[nu.Nu] = []

    def put(ref_cls: type[ui.Ref], segment: str, parent: ui.Ref | None, **props: object) -> ui.Ref:
        ref = ref_cls(segment, parent_ref=parent, props=props)
        shown.append(ref.init())
        return ref

    nights = meridian.night_labels()
    root = put(ui.ContainerRef, "dashboard", None, size="dashboard", gap=6)

    # --- header ------------------------------------------------------------------------------
    head = put(ui.RowRef, "head", root, align="end", gap=2, wrap=True)
    put(
        ui.HeadingRef,
        "title",
        head,
        label="Tonight",
        level=1,
        size="2xl",
        eyebrow="Meridian network",
        subtitle="Saturday, October 25. Eleven of fourteen sites are open.",
    )
    put(ui.SpacerRef, "push", head)
    put(ui.ButtonRef, "range", head, label="Last 30 nights", variant="secondary", icon="calendar")
    put(ui.ButtonRef, "request", head, label="Request time", icon="plus", href=to["catalog"])

    # --- stats -------------------------------------------------------------------------------
    stats = put(ui.GridRef, "stats", root, columns=4, min_width=140, gap=4)
    data: list[nu.Nu] = []
    for key, label, value, delta, trend, seed, base, swing in STATS:
        card = put(ui.CardRef, key, stats, size="sm")
        put(ui.StatRef, "stat", card, label=label, value=value, delta=delta, trend=trend)
        spark = put(ui.Sparkline, "spark", card, area=True, height=36)
        data.append(spark.set(meridian.night_series(seed, base, swing, n=14)))

    # --- bento -------------------------------------------------------------------------------
    bento = put(
        ui.GridRef,
        "bento",
        root,
        columns=3,
        min_width=280,
        gap=4,
        dense=True,
        spans={"hours": (2, 2)},
    )

    hours = put(ui.CardRef, "hours", bento, title="Observing hours", subtitle="Per night, by site")
    put(ui.BadgeRef, "actions", hours, label="Live", variant="secondary", size="sm")
    curve = put(
        ui.AreaChart,
        "curve",
        hours,
        series=meridian.SITES,
        x_type="category",
        stack=True,
        smooth=True,
        height=440,
        legend=True,
        y_format="{value} h",
    )
    data.append(
        curve.set(
            {
                site: [
                    [n, v]
                    for n, v in zip(
                        nights, meridian.night_series(11 * (k + 1), 2.6, 1.4), strict=True
                    )
                ]
                for k, site in enumerate(meridian.SITES)
            }
        )
    )

    kinds = put(ui.CardRef, "kinds", bento, title="Time by instrument", subtitle="Hours this month")
    donut = put(
        ui.PieChart,
        "donut",
        kinds,
        donut=True,
        total_label="hours",
        labels=False,
        legend=True,
        height=176,
    )
    data.append(donut.set({"Reflector": 1840, "Refractor": 620, "Spectrograph": 910, "Solar": 260}))

    seeing = put(
        ui.CardRef, "seeing", bento, title="Median seeing", subtitle="Arcsec, lower is sharper"
    )
    line = put(
        ui.LineChart,
        "line",
        seeing,
        series=("Atacama", "La Palma"),
        x_type="category",
        smooth=True,
        height=150,
        y_min=0.4,
    )
    data.append(
        line.set(
            {
                "Atacama": [
                    [n, max(0.45, v)]
                    for n, v in zip(
                        nights, meridian.night_series(5, 0.75, 0.25, places=2), strict=True
                    )
                ],
                "La Palma": [
                    [n, max(0.45, v)]
                    for n, v in zip(
                        nights, meridian.night_series(9, 1.0, 0.3, places=2), strict=True
                    )
                ],
            }
        )
    )

    # --- lower row ---------------------------------------------------------------------------
    lower = put(ui.GridRef, "lower", root, columns=3, min_width=280, gap=4, spans={"programs": 2})
    programs = put(
        ui.CardRef,
        "programs",
        lower,
        title="Queue by program",
        subtitle="Requested against scheduled hours",
    )
    bars = put(
        ui.BarChart,
        "bars",
        programs,
        series=("Requested", "Scheduled"),
        height=248,
        legend=True,
        value_format="{value} h",
    )
    data.append(
        bars.set(
            [
                ["Transients", 64, 52],
                ["Exoplanets", 88, 71],
                ["Variable stars", 42, 40],
                ["Deep sky", 120, 64],
                ["Solar", 18, 18],
                ["Outreach", 26, 12],
            ]
        )
    )

    recent = put(ui.CardRef, "recent", lower, title="Recent frames")
    put(
        ui.LinkRef,
        "actions",
        recent,
        label="All frames",
        href=to["detail"],
        variant="muted",
        arrow=True,
    )
    frames = put(ui.ColumnRef, "frames", recent, gap=1)
    for key, title, description, meta in RECENT:
        put(
            ui.PageLinkRef,
            key,
            frames,
            href=to["detail"],
            title=title,
            icon="image",
            description=description,
            meta=meta,
        )

    return nu.Sequential(*shown, *data)
