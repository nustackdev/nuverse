"""Landing: the product page, one column down the middle of the window.

A top bar of nav links with the sign in and the call to action at its end,
then the hero: a display heading with an eyebrow, a line under it, two
calls to action as buttons that are links, and a wide picture. A
strip of numbers, a grid of features each marked by a framed icon, a
closing call on an accent card, and a quiet footer.

Every child is reached from its container and named with ``.to(Kind)``
where it is placed; repeated ones (numbers, features) by position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui as ui
from nudemos.recipes import meridian


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ["page"]


NUMBERS = (
    ("Sites", "14"),
    ("Hours observed this year", "38,400"),
    ("Frames in the archive", "2.1 M"),
    ("Clear night uptime", "99.2%"),
)

#: Features: (icon, tone, title, line).
FEATURES = (
    (
        "calendar",
        "accent",
        "One queue, every site",
        "Ask for time once. The queue finds the site with the clearest sky and the right instrument.",
    ),
    (
        "activity",
        "info",
        "Watch it live",
        "Frames land as they are taken, with seeing, focus and guiding beside them.",
    ),
    (
        "database",
        "accent",
        "Keep every frame",
        "Raw and calibrated, searchable by target, night and filter. Nothing expires while you need it.",
    ),
    (
        "workflow",
        "info",
        "Pipelines you own",
        "Calibrate, stack and measure in Python, on the same data the scopes write.",
    ),
    (
        "users",
        "accent",
        "Built for small teams",
        "Share instruments, split hours fairly, see who booked what and why.",
    ),
    (
        "shield-check",
        "info",
        "Open by default",
        "Your data leaves with you. Every format is plain, every API is documented.",
    ),
)


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The landing page, drawn."""
    to = meridian.links(links)
    root = ui.ContainerRef("landing", props={"gap": 16})

    # --- top bar -------------------------------------------------------------------------------
    # Mark and name straight in the bar: a Row nested in a Row fills and gives
    # way first, and a squeezed one lets the name run under the links.
    bar = root["bar"].to(ui.RowRef.slot(gap=3, grow={"nav": 1}))
    nav = bar["nav"].to(ui.NavListRef.slot(variant="horizontal", label="Main"))
    shown = [
        root.init(),
        bar["mark"].to(ui.IconRef.slot(name="compass", size="lg", tone="accent")).init(),
        bar["name"].to(ui.TextRef.slot(value="Meridian", weight="semibold", size="lg")).init(),
        nav[0].to(ui.NavItemRef.slot(label="Instruments", href=to["catalog"], active=False)).init(),
        nav[1].to(ui.NavItemRef.slot(label="Network", href=to["dashboard"], active=False)).init(),
        nav[2].to(ui.NavItemRef.slot(label="Pricing", href=to["landing"], active=False)).init(),
        bar["signin"]
        .to(ui.ButtonRef.slot(label="Sign in", href=to["settings"], variant="ghost", size="sm"))
        .init(),
        bar["start"]
        .to(ui.ButtonRef.slot(label="Start observing", href=to["dashboard"], size="sm"))
        .init(),
    ]

    # --- hero ----------------------------------------------------------------------------------
    hero = root["hero"].to(ui.ColumnRef.slot(gap=8))
    words = hero["words"].to(ui.ColumnRef.slot(gap=6, max_width="panel", align="start"))
    ctas = words["ctas"].to(ui.RowRef.slot(gap=3, wrap=True))
    shown += [
        words["news"]
        .to(ui.BadgeRef.slot(label="New: Harrier spectrograph in Namibia", variant="secondary"))
        .init(),
        words["title"]
        .to(
            ui.HeadingRef.slot(
                label="A shared sky for small observatories",
                level=1,
                size="display",
                subtitle="Book time on fourteen remote telescopes from one queue. Keep every frame.",
            )
        )
        .init(),
        ctas[0]
        .to(ui.ButtonRef.slot(label="Start observing", href=to["dashboard"], size="lg"))
        .init(),
        ctas[1]
        .to(
            ui.ButtonRef.slot(
                label="Browse instruments", href=to["catalog"], variant="outline", size="lg"
            )
        )
        .init(),
        hero["picture"]
        .to(
            ui.ImageRef.slot(
                src=meridian.sky(3, "violet", 1600, 640),
                alt="The southern sky over the Atacama site",
                fit="cover",
                aspect="5/2",
                radius="lg",
            )
        )
        .init(),
    ]

    # --- numbers -------------------------------------------------------------------------------
    numbers = root["numbers"].to(ui.GridRef.slot(max_columns=4, min_cell_width=160, gap=6))
    shown += [
        numbers[i].to(ui.StatRef.slot(label=label, value=value)).init()
        for i, (label, value) in enumerate(NUMBERS)
    ]

    # --- features ------------------------------------------------------------------------------
    features = root["features"].to(
        ui.PageSectionRef.slot(
            title="Everything a night needs",
            description="From the request to the published light curve, in one place.",
            size="lg",
            gap=8,
        )
    )
    grid = features[0].to(ui.GridRef.slot(max_columns=3, min_cell_width=240, gap=10))
    for i, (icon, tone, title, line) in enumerate(FEATURES):
        cell = grid[i].to(ui.ColumnRef.slot(gap=3))
        shown += [
            cell[0].to(ui.IconRef.slot(name=icon, tone=tone, framed=True, size="lg")).init(),
            # The line rides the heading as its subtitle, so the pair keeps the
            # heading's own tight spacing rather than the column's gap.
            cell[1].to(ui.HeadingRef.slot(label=title, level=3, size="xl", subtitle=line)).init(),
        ]

    # --- closing call --------------------------------------------------------------------------
    close = root["close"].to(ui.CardRef.slot(variant="accent", padding=8, gap=5, align="center"))
    row = close["row"].to(ui.RowRef.slot(gap=3, justify="center", wrap=True))
    shown += [
        close["title"]
        .to(
            ui.HeadingRef.slot(
                label="Your first night is on us",
                level=2,
                size="2xl",
                align="center",
                subtitle="Ten hours on any open instrument, no card needed.",
            )
        )
        .init(),
        row[0]
        .to(ui.ButtonRef.slot(label="Request time", href=to["catalog"], icon="calendar"))
        .init(),
        row[1].to(ui.LinkRef.slot(label="See a live night", href=to["detail"], arrow=True)).init(),
    ]

    # --- footer --------------------------------------------------------------------------------
    foot = root["foot"].to(ui.ColumnRef.slot(gap=4))
    line = foot["line"].to(ui.RowRef.slot(gap=4, wrap=True, grow={"made": 1}))
    shown += [
        foot["rule"].to(ui.DividerRef).init(),
        line["made"]
        .to(ui.TextRef.slot(value="Meridian, 2026. Run by observers.", tone="muted", size="sm"))
        .init(),
        line["status"]
        .to(ui.LinkRef.slot(label="Status", href=to["dashboard"], variant="muted"))
        .init(),
        line["settings"]
        .to(ui.LinkRef.slot(label="Settings", href=to["settings"], variant="muted"))
        .init(),
    ]

    return nu.Sequential(*shown)
