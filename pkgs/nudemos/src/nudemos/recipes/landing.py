"""Landing: the product page, one column down the middle of the window.

A top bar of nav links with the sign in and the call to action at its end,
then the hero: a display heading with an eyebrow, a line under it, two
calls to action as buttons that are links, and a wide picture. A
strip of numbers, a grid of features each marked by a framed icon, a
closing call in a tinted box, and a quiet footer.
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
    ("sites", "Sites", "14"),
    ("hours", "Hours observed this year", "38,400"),
    ("frames", "Frames in the archive", "2.1 M"),
    ("uptime", "Clear night uptime", "99.2%"),
)

#: Features: (key, icon, tone, title, line).
FEATURES = (
    (
        "queue",
        "calendar",
        "accent",
        "One queue, every site",
        "Ask for time once. The queue finds the site with the clearest sky and the right instrument.",
    ),
    (
        "live",
        "activity",
        "info",
        "Watch it live",
        "Frames land as they are taken, with seeing, focus and guiding beside them.",
    ),
    (
        "archive",
        "database",
        "accent",
        "Keep every frame",
        "Raw and calibrated, searchable by target, night and filter. Nothing expires while you need it.",
    ),
    (
        "pipelines",
        "workflow",
        "info",
        "Pipelines you own",
        "Calibrate, stack and measure in Python, on the same data the scopes write.",
    ),
    (
        "teams",
        "users",
        "accent",
        "Built for small teams",
        "Share instruments, split hours fairly, see who booked what and why.",
    ),
    (
        "open",
        "shield-check",
        "info",
        "Open by default",
        "Your data leaves with you. Every format is plain, every API is documented.",
    ),
)


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The landing page, drawn."""
    to = meridian.links(links)
    shown: list[nu.Nu] = []

    def put(ref_cls: type[ui.Ref], segment: str, parent: ui.Ref | None, **props: object) -> ui.Ref:
        ref = ref_cls(segment, parent_ref=parent, props=props)
        shown.append(ref.init())
        return ref

    root = put(ui.ContainerRef, "landing", None, size="main", gap=16)

    # --- top bar -------------------------------------------------------------------------------
    bar = put(ui.RowRef, "bar", root, gap=3)
    # Mark and name straight in the bar: a Row nested in a Row fills and gives
    # way first, and a squeezed one lets the name run under the links.
    put(ui.IconRef, "mark", bar, name="compass", size="lg", tone="accent")
    put(ui.TextRef, "name", bar, value="Meridian", weight="semibold", size="lg")
    nav = put(ui.NavListRef, "nav", bar, variant="horizontal", label="Main")
    put(ui.NavItemRef, "instruments", nav, label="Instruments", href=to["catalog"], active=False)
    put(ui.NavItemRef, "network", nav, label="Network", href=to["dashboard"], active=False)
    put(ui.NavItemRef, "pricing", nav, label="Pricing", href=to["landing"], active=False)
    put(ui.SpacerRef, "push", bar)
    put(
        ui.ButtonRef,
        "signin",
        bar,
        label="Sign in",
        href=to["settings"],
        variant="ghost",
        size="sm",
    )
    put(ui.ButtonRef, "start", bar, label="Start observing", href=to["dashboard"], size="sm")

    # --- hero ----------------------------------------------------------------------------------
    hero = put(ui.ColumnRef, "hero", root, gap=8)
    words = put(ui.ColumnRef, "words", hero, gap=6, max_width="panel", center=False, align="start")
    put(
        ui.BadgeRef,
        "news",
        words,
        label="New: Harrier spectrograph in Namibia",
        variant="secondary",
    )
    put(
        ui.HeadingRef,
        "title",
        words,
        label="A shared sky for small observatories",
        level=1,
        size="display",
        subtitle="Book time on fourteen remote telescopes from one queue. Keep every frame.",
    )
    ctas = put(ui.RowRef, "ctas", words, gap=3, wrap=True)
    put(ui.ButtonRef, "start", ctas, label="Start observing", href=to["dashboard"], size="lg")
    put(
        ui.ButtonRef,
        "browse",
        ctas,
        label="Browse instruments",
        href=to["catalog"],
        variant="outline",
        size="lg",
    )
    put(
        ui.ImageRef,
        "picture",
        hero,
        src=meridian.sky(3, "violet", 1600, 640),
        alt="The southern sky over the Atacama site",
        fit="cover",
        aspect="5/2",
        radius="lg",
    )

    # --- numbers -------------------------------------------------------------------------------
    numbers = put(ui.GridRef, "numbers", root, columns=4, min_width=120, gap=6)
    for key, label, value in NUMBERS:
        put(ui.StatRef, key, numbers, label=label, value=value)

    # --- features ------------------------------------------------------------------------------
    features = put(
        ui.PageSectionRef,
        "features",
        root,
        title="Everything a night needs",
        description="From the request to the published light curve, in one place.",
        size="lg",
        gap=8,
    )
    grid = put(ui.GridRef, "grid", features, columns=3, min_width=240, gap=10)
    for key, icon, tone, title, line in FEATURES:
        cell = put(ui.ColumnRef, key, grid, gap=3)
        put(ui.IconRef, "icon", cell, name=icon, tone=tone, framed=True, size="lg")
        # The line rides the heading as its subtitle, so the pair keeps the
        # heading's own tight spacing rather than the column's gap.
        put(ui.HeadingRef, "title", cell, label=title, level=3, size="xl", subtitle=line)

    # --- closing call --------------------------------------------------------------------------
    close = put(ui.BoxRef, "close", root, background="accent", padding="lg", border="none")
    inner = put(ui.ColumnRef, "inner", close, gap=5, align="center", padding=8)
    put(
        ui.HeadingRef,
        "title",
        inner,
        label="Your first night is on us",
        level=2,
        size="2xl",
        align="center",
        subtitle="Ten hours on any open instrument, no card needed.",
    )
    row = put(ui.RowRef, "row", inner, gap=3, justify="center", wrap=True)
    put(ui.ButtonRef, "start", row, label="Request time", href=to["catalog"], icon="calendar")
    put(ui.LinkRef, "tour", row, label="See a live night", href=to["detail"], arrow=True)

    # --- footer --------------------------------------------------------------------------------
    foot = put(ui.ColumnRef, "foot", root, gap=4)
    put(ui.DividerRef, "rule", foot)
    line = put(ui.RowRef, "line", foot, gap=4, wrap=True)
    put(
        ui.TextRef, "made", line, value="Meridian, 2026. Run by observers.", tone="muted", size="sm"
    )
    put(ui.SpacerRef, "push", line)
    put(ui.LinkRef, "status", line, label="Status", href=to["dashboard"], variant="muted")
    put(ui.LinkRef, "settings", line, label="Settings", href=to["settings"], variant="muted")

    return nu.Sequential(*shown)
