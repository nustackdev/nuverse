"""Detail: one instrument, everything about it on one page.

A breadcrumb back to the list, then a hero: the instrument's picture held
to 4:3 beside a heading with an eyebrow, its state as a pill and badges, a
grid of key facts and the actions. Under it, tonight's plan as a table in a
titled section with its own action, the seeing chart beside a strip of
recent frames, and the rest of the network as page tiles.
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

PLAN = (
    ["20:41", "Astronomical dusk", "Calibration", "Flats, 30 x 2 s", "Done"],
    ["21:05", "SN 2026xk", "Transients", "12 x 180 s, r", "Running"],
    ["22:10", "WASP-121 b", "Exoplanets", "Transit, 2.5 h", "Queued"],
    ["00:45", "M83", "Deep sky", "24 x 300 s, L R G B", "Queued"],
    ["03:20", "RR Lyrae field 4", "Variable stars", "60 x 60 s, V", "Queued"],
    ["05:52", "Astronomical dawn", "Calibration", "Darks, 20 x 300 s", "Queued"],
)

#: Recent frames: (key, seed, hue) for each thumbnail.
FRAMES = (("f1", 61, "violet"), ("f2", 62, "blue"), ("f3", 63, "rose"), ("f4", 64, "teal"))


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The detail page of :data:`SHOWN`, drawn."""
    to = meridian.links(links)
    scope = meridian.instrument(SHOWN)
    shown: list[nu.Nu] = []

    def put(ref_cls: type[ui.Ref], segment: str, parent: ui.Ref | None, **props: object) -> ui.Ref:
        ref = ref_cls(segment, parent_ref=parent, props=props)
        shown.append(ref.init())
        return ref

    root = put(ui.ContainerRef, "detail", None, size="main", gap=10)
    put(
        ui.BreadcrumbRef,
        "trail",
        root,
        items=[
            {"label": "Network", "href": to["dashboard"]},
            {"label": "Instruments", "href": to["catalog"]},
            {"label": scope["name"]},
        ],
    )

    # --- hero: the picture beside what it is --------------------------------------------------
    hero = put(ui.GridRef, "hero", root, columns=2, min_width=320, gap=10, align="center")
    put(
        ui.ImageRef,
        "picture",
        hero,
        src=meridian.sky(scope["seed"], scope["hue"], 960, 720),
        alt=f"The sky over {scope['site']} from {scope['name']}",
        fit="cover",
        aspect="4/3",
        radius="lg",
    )
    about = put(ui.ColumnRef, "about", hero, gap=6)
    put(
        ui.HeadingRef,
        "title",
        about,
        label=scope["name"],
        level=1,
        size="3xl",
        eyebrow=f"{scope['kind']} at {scope['site']}",
        subtitle=scope["summary"],
    )
    tags = put(ui.RowRef, "tags", about, gap=2, wrap=True)
    put(ui.StatusPillRef, "state", tags, tone="ok", label="Open tonight")
    put(ui.BadgeRef, "aperture", tags, label="0.6 m aperture")
    put(ui.BadgeRef, "program", tags, label="Transients", variant="secondary")
    facts = put(ui.GridRef, "facts", about, columns=3, min_width=120, gap=5)
    for k, (label, value) in enumerate(FACTS):
        fact = put(ui.ColumnRef, f"fact{k}", facts, gap=1)
        put(ui.TextRef, "label", fact, value=label, size="xs", tone="muted")
        put(ui.TextRef, "value", fact, value=value, weight="semibold")
    actions = put(ui.RowRef, "actions", about, gap=2, wrap=True)
    put(ui.ButtonRef, "book", actions, label="Book time", icon="calendar")
    put(
        ui.ButtonRef,
        "download",
        actions,
        label="Download frames",
        icon="download",
        variant="secondary",
    )
    put(ui.ButtonRef, "share", actions, icon="share-2", variant="ghost", tooltip="Share")

    # --- tonight -------------------------------------------------------------------------------
    plan = put(
        ui.PageSectionRef,
        "plan",
        root,
        title="Tonight's plan",
        description="Six slots from dusk to dawn. Times are local, UTC-3.",
    )
    put(
        ui.ButtonRef,
        "edit",
        plan.actions,
        label="Edit plan",
        icon="pencil",
        variant="ghost",
        size="sm",
    )
    table = put(
        ui.TableRef,
        "slots",
        plan,
        columns=["Time", "Target", "Program", "Exposure", "Status"],
        label="Tonight's plan",
        striped=False,
    )

    # --- conditions and frames ------------------------------------------------------------------
    lower = put(ui.GridRef, "lower", root, columns=2, min_width=320, gap=8)
    seeing = put(
        ui.PageSectionRef, "seeing", lower, title="Seeing", description="Last 30 nights, arcsec"
    )
    chart = put(
        ui.LineChart,
        "chart",
        seeing,
        x_type="category",
        area=True,
        smooth=True,
        height=300,
        y_min=0.4,
        y_format="{value}",
    )
    frames = put(
        ui.PageSectionRef,
        "frames",
        lower,
        title="Recent frames",
        description="Raw, before calibration",
    )
    put(
        ui.LinkRef,
        "all",
        frames.actions,
        label="Open archive",
        href=to["catalog"],
        variant="muted",
        arrow=True,
    )
    strip = put(ui.GridRef, "strip", frames, columns=2, min_width=120, gap=3)
    for key, seed, hue in FRAMES:
        put(
            ui.ImageRef,
            key,
            strip,
            src=meridian.sky(seed, hue, 480, 300),
            alt="",
            fit="cover",
            aspect="16/10",
            radius="md",
        )

    # --- the rest of the network ---------------------------------------------------------------
    more = put(ui.PageSectionRef, "more", root, title="More on the network", bordered=True)
    put(
        ui.LinkRef,
        "all",
        more.actions,
        label="Every instrument",
        href=to["catalog"],
        variant="muted",
        arrow=True,
    )
    tiles = put(ui.GridRef, "tiles", more, columns=3, min_width=220, gap=3)
    for other in meridian.INSTRUMENTS:
        if other["id"] != SHOWN:
            put(
                ui.PageLinkRef,
                other["id"],
                tiles,
                href=to["detail"],
                title=other["name"],
                icon="target",
                description=other["summary"],
                meta=f"{other['aperture']} {other['kind'].lower()}, {other['site']}",
                variant="tile",
            )
    put(
        ui.PageLinkRef,
        "settings",
        tiles,
        href=to["settings"],
        title="Observing defaults",
        icon="settings",
        description="What every new request on the network starts with.",
        variant="tile",
    )

    data = [
        table.set_rows([list(row) for row in PLAN]),
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
