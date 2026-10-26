"""Settings: a sidebar of nav items beside sections of form fields.

Two nav lists down the side, the page you are on marked active, and a way
back. Beside them the page: a heading, then one titled section per group
of settings, each with its own action in the header (save, reset), its
fields in a grid that stacks on a phone, switches and a slider, and a
bordered danger zone at the end.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui as ui
from nudemos.recipes import meridian


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ["page"]


#: The sidebar: (list label, [(key, label, icon, meta), ...]). The first item is this page.
NAV = (
    (
        "Workspace",
        (
            ("general", "General", "settings", ""),
            ("members", "Members", "users", "12"),
            ("observing", "Observing", "target", ""),
            ("notifications", "Notifications", "bell", "3"),
            ("billing", "Billing", "package", ""),
            ("keys", "API keys", "lock", ""),
        ),
    ),
    ("Account", (("profile", "Profile", "user", ""), ("security", "Security", "shield", ""))),
)

ZONES = ["America/Santiago", "Atlantic/Canary", "Africa/Windhoek", "Australia/Sydney", "UTC"]


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The settings page, drawn."""
    to = meridian.links(links)
    shown: list[nu.Nu] = []

    def put(ref_cls: type[ui.Ref], segment: str, parent: ui.Ref | None, **props: object) -> ui.Ref:
        ref = ref_cls(segment, parent_ref=parent, props=props)
        shown.append(ref.init())
        return ref

    def field(
        parent: ui.Ref, key: str, label: str, control: type[ui.Ref], help: str = "", **props: object
    ) -> None:
        box = put(ui.FieldRef, key, parent, label=label, help=help)
        put(control, "control", box, **props)

    root = put(ui.ContainerRef, "settings", None, size="main")
    layout = put(
        ui.GridRef,
        "layout",
        root,
        columns=4,
        min_width=200,
        gap=10,
        align="start",
        spans={"main": 3},
    )

    # --- the sidebar ---------------------------------------------------------------------------
    side = put(ui.ColumnRef, "side", layout, gap=6)
    put(
        ui.LinkRef,
        "back",
        side,
        label="Dashboard",
        href=to["dashboard"],
        icon="arrow-left",
        variant="muted",
    )
    for k, (label, items) in enumerate(NAV):
        nav = put(ui.NavListRef, f"nav{k}", side, label=label)
        for key, text, icon, meta in items:
            # Pinned, every one: the items share the page's route, so following
            # the tab would light them all.
            put(
                ui.NavItemRef,
                key,
                nav,
                label=text,
                href=to["settings"],
                icon=icon,
                meta=meta,
                active=key == "general",
            )

    # --- the page ------------------------------------------------------------------------------
    main = put(ui.ColumnRef, "main", layout, gap=10, max_width="panel", center=False)
    put(
        ui.HeadingRef,
        "title",
        main,
        label="General",
        level=1,
        size="3xl",
        subtitle="How the workspace looks to the people in it.",
    )

    workspace = put(
        ui.PageSectionRef,
        "workspace",
        main,
        title="Workspace",
        description="Shown on every page and in every email.",
    )
    put(ui.ButtonRef, "save", workspace.actions, label="Save changes", size="sm")
    pair = put(ui.GridRef, "pair", workspace, columns=2, min_width=220, gap=4)
    field(pair, "name", "Name", ui.InputRef, value="Meridian Atacama")
    field(
        pair,
        "address",
        "Address",
        ui.InputRef,
        help="Where members sign in.",
        value="meridian.network/atacama",
        mono=True,
    )
    field(
        pair,
        "zone",
        "Time zone",
        ui.SelectRef,
        help="Plans and reports use it.",
        options=ZONES,
        selected="America/Santiago",
    )
    field(
        pair,
        "units",
        "Coordinates",
        ui.SelectRef,
        options=["Sexagesimal", "Decimal degrees"],
        selected="Sexagesimal",
    )
    field(
        workspace,
        "about",
        "About",
        ui.TextAreaRef,
        help="A line or two for the sign-in page.",
        value="Two reflectors and a spectrograph at 2,400 m, run for the southern transient programs.",
        rows=3,
    )

    observing = put(
        ui.PageSectionRef,
        "observing",
        main,
        title="Observing defaults",
        description="What a new request starts with. Each request can change them.",
        bordered=True,
    )
    put(
        ui.ButtonRef,
        "reset",
        observing.actions,
        label="Reset",
        icon="rotate-ccw",
        variant="ghost",
        size="sm",
    )
    put(ui.SwitchRef, "auto", observing, label="Book clear nights on their own", default=True)
    put(ui.SwitchRef, "report", observing, label="Email the morning report", default=True)
    put(ui.SwitchRef, "moon", observing, label="Skip nights within three days of full moon")
    field(
        observing,
        "airmass",
        "Highest airmass",
        ui.SliderRef,
        help="Lower keeps targets higher in the sky.",
        min=1.0,
        max=3.0,
        step=0.1,
        value=2.0,
    )

    danger = put(ui.PageSectionRef, "danger", main, title="Danger zone", bordered=True)
    box = put(ui.BoxRef, "box", danger, border="hairline", padding="md")
    row = put(ui.RowRef, "row", box, gap=4, wrap=True)
    words = put(ui.ColumnRef, "words", row, gap=1)
    put(ui.TextRef, "what", words, value="Delete this workspace", weight="semibold")
    put(
        ui.TextRef,
        "why",
        words,
        value="Frames stay in the archive for 30 days, then go for good.",
        tone="secondary",
        size="sm",
    )
    put(ui.SpacerRef, "push", row)
    put(ui.ButtonRef, "delete", row, label="Delete workspace", icon="trash-2", variant="danger")

    return nu.Sequential(*shown)
