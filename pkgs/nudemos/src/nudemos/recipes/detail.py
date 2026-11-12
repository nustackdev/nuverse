"""Detail: one instrument, everything about it on one page.

A breadcrumb back to the list, then a hero: the instrument's picture held
to 4:3 beside a heading with an eyebrow, its state as a pill and badges, a
grid of key facts and the actions. Under it, tonight's plan as a data table
in a titled section with its own action, the seeing chart beside a strip of
recent frames, and, past a rule, the rest of the network as page tiles.

Every child is reached from its container and named with ``.to(Kind)``
where it is placed; repeated ones (facts, frames, tiles) by position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui as ui
from nudemos.recipes import meridian


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ["page"]


#: The instrument the page is about.
SHOWN = "kestrel"

FACTS = (
    ("Aperture", "0.6 m"),
    ("Focal ratio", "f/6.5"),
    ("Camera", "IMX455 mono"),
    ("Field of view", "1.4 deg"),
    ("Median seeing", "0.7 arcsec"),
    ("Altitude", "2,400 m"),
)

#: How each slot's state reads: its pill tone.
TONES = {"Done": "ok", "Running": "info", "Queued": "neutral"}

PLAN = (
    ("20:41", "Astronomical dusk", "Calibration", "Flats, 30 x 2 s", "Done"),
    ("21:05", "SN 2026xk", "Transients", "12 x 180 s, r", "Running"),
    ("22:10", "WASP-121 b", "Exoplanets", "Transit, 2.5 h", "Queued"),
    ("00:45", "M83", "Deep sky", "24 x 300 s, L R G B", "Queued"),
    ("03:20", "RR Lyrae field 4", "Variable stars", "60 x 60 s, V", "Queued"),
    ("05:52", "Astronomical dawn", "Calibration", "Darks, 20 x 300 s", "Queued"),
)

COLUMNS = [
    {"key": "time", "label": "Time", "width": 80},
    {"key": "target", "label": "Target"},
    {"key": "program", "label": "Program", "hide_below": 640},
    {"key": "exposure", "label": "Exposure", "hide_below": 520},
    {"key": "status", "label": "Status", "cell": ui.StatusPillRef, "align": "end"},
]

#: Recent frames: (seed, hue) for each thumbnail.
FRAMES = ((61, "violet"), (62, "blue"), (63, "rose"), (64, "teal"))


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The detail page of :data:`SHOWN`, drawn."""
    to = meridian.links(links)
    scope = meridian.instrument(SHOWN)
    root = ui.ContainerRef("detail", props={"gap": 10})
    shown = [
        root.init(),
        root["trail"]
        .to(
            ui.BreadcrumbRef.slot(
                items=[
                    {"label": "Network", "href": to["dashboard"]},
                    {"label": "Instruments", "href": to["catalog"]},
                    {"label": scope["name"]},
                ]
            )
        )
        .init(),
    ]

    # --- hero: the picture beside what it is --------------------------------------------------
    hero = root["hero"].to(ui.GridRef.slot(cols=2, gap=10, align="center", stack_below=768))
    about = hero[0, 1].to(ui.ColumnRef.slot(gap=6))
    tags = about["tags"].to(ui.RowRef.slot(gap=2, wrap=True))
    facts = about["facts"].to(ui.GridRef.slot(max_columns=3, min_cell_width=120, gap=5))
    actions = about["actions"].to(ui.RowRef.slot(gap=2, wrap=True))
    shown += [
        hero[0, 0]
        .to(
            ui.ImageRef.slot(
                src=meridian.sky(scope["seed"], scope["hue"], 960, 720),
                alt=f"The sky over {scope['site']} from {scope['name']}",
                fit="cover",
                aspect="4/3",
                radius="lg",
            )
        )
        .init(),
        about["title"]
        .to(
            ui.HeadingRef.slot(
                label=scope["name"],
                level=1,
                size="3xl",
                eyebrow=f"{scope['kind']} at {scope['site']}",
                subtitle=scope["summary"],
            )
        )
        .init(),
        tags[0].to(ui.StatusPillRef.slot(tone="ok", label="Open tonight")).init(),
        tags[1].to(ui.BadgeRef.slot(label="0.6 m aperture")).init(),
        tags[2].to(ui.BadgeRef.slot(label="Transients", variant="secondary")).init(),
    ]
    for k, (label, value) in enumerate(FACTS):
        fact = facts[k].to(ui.ColumnRef.slot(gap=1))
        shown += [
            fact[0].to(ui.TextRef.slot(value=label, size="xs", tone="muted")).init(),
            fact[1].to(ui.TextRef.slot(value=value, weight="semibold")).init(),
        ]
    shown += [
        actions[0].to(ui.ButtonRef.slot(label="Book time", icon="calendar")).init(),
        actions[1]
        .to(ui.ButtonRef.slot(label="Download frames", icon="download", variant="secondary"))
        .init(),
        actions[2].to(ui.ButtonRef.slot(icon="share-2", variant="ghost", tooltip="Share")).init(),
    ]

    # --- tonight -------------------------------------------------------------------------------
    plan = root["plan"].to(
        ui.PageSectionRef.slot(
            title="Tonight's plan",
            description="Six slots from dusk to dawn. Times are local, UTC-3.",
        )
    )
    shown.append(
        plan.actions[0]
        .to(ui.ButtonRef.slot(label="Edit plan", icon="pencil", variant="ghost", size="sm"))
        .init()
    )
    table = plan[0].to(
        ui.DataTableRef.slot(
            columns=COLUMNS, row_key="time", label="Tonight's plan", variant="default"
        )
    )
    rows = [
        {
            "time": time,
            "target": target,
            "program": program,
            "exposure": exposure,
            "status": {"label": status, "tone": TONES[status]},
        }
        for time, target, program, exposure, status in PLAN
    ]

    # --- conditions and frames ------------------------------------------------------------------
    lower = root["lower"].to(ui.GridRef.slot(cols=2, gap=8, stack_below=768))
    seeing = lower[0, 0].to(
        ui.PageSectionRef.slot(title="Seeing", description="Last 30 nights, arcsec")
    )
    chart = seeing[0].to(
        ui.LineChart.slot(
            x_type="category", area=True, smooth=True, height=300, y_min=0.4, y_format="{value}"
        )
    )
    frames = lower[0, 1].to(
        ui.PageSectionRef.slot(title="Recent frames", description="Raw, before calibration")
    )
    shown.append(
        frames.actions[0]
        .to(ui.LinkRef.slot(label="Open archive", href=to["catalog"], variant="muted", arrow=True))
        .init()
    )
    strip = frames[0].to(ui.GridRef.slot(max_columns=2, min_cell_width=120, gap=3))
    shown += [
        strip[i]
        .to(
            ui.ImageRef.slot(
                src=meridian.sky(seed, hue, 480, 300),
                alt="",
                fit="cover",
                aspect="16/10",
                radius="md",
            )
        )
        .init()
        for i, (seed, hue) in enumerate(FRAMES)
    ]

    # --- the rest of the network, past a rule --------------------------------------------------
    shown.append(root["rule"].to(ui.DividerRef).init())
    more = root["more"].to(ui.PageSectionRef.slot(title="More on the network"))
    shown.append(
        more.actions[0]
        .to(
            ui.LinkRef.slot(
                label="Every instrument", href=to["catalog"], variant="muted", arrow=True
            )
        )
        .init()
    )
    tiles = more[0].to(ui.GridRef.slot(max_columns=3, min_cell_width=220, gap=3))
    others = [i for i in meridian.INSTRUMENTS if i["id"] != SHOWN]
    shown += [
        tiles[k]
        .to(
            ui.PageLinkRef.slot(
                href=to["detail"],
                title=other["name"],
                icon="target",
                description=other["summary"],
                meta=f"{other['aperture']} {other['kind'].lower()}, {other['site']}",
                variant="tile",
            )
        )
        .init()
        for k, other in enumerate(others)
    ]
    shown.append(
        tiles[len(others)]
        .to(
            ui.PageLinkRef.slot(
                href=to["settings"],
                title="Observing defaults",
                icon="settings",
                description="What every new request on the network starts with.",
                variant="tile",
            )
        )
        .init()
    )

    data = [
        table.set_rows(rows),
        chart.set(
            [
                [n, max(0.45, v)]
                for n, v in zip(
                    meridian.night_labels(),
                    meridian.night_series(5, 0.75, 0.25, places=2),
                    strict=True,
                )
            ]
        ),
    ]
    return nu.Sequential(*shown, *data)
