"""Settings: a sidebar of nav items beside sections of form fields.

A placed grid of two columns, a narrow side and the page, that stacks on a
phone. Down the side, two nav lists with the page you are on marked active,
and a way back. Beside them the page: a heading, then one titled section
per group of settings, hairlines between them, each with its own action in
the header (save, reset), its fields in a grid that stacks on a phone,
switches and a slider, and a danger zone at the end.

Every child is reached from its container and named with ``.to(Kind)``
where it is placed; a field's input as ``field.control``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui as ui
from nudemos.recipes import meridian


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ["page"]


#: The sidebar: (list label, [(label, icon, meta), ...]). The first item is this page.
NAV = (
    (
        "Workspace",
        (
            ("General", "settings", ""),
            ("Members", "users", "12"),
            ("Observing", "target", ""),
            ("Notifications", "bell", "3"),
            ("Billing", "package", ""),
            ("API keys", "lock", ""),
        ),
    ),
    ("Account", (("Profile", "user", ""), ("Security", "shield", ""))),
)

ZONES = ["America/Santiago", "Atlantic/Canary", "Africa/Windhoek", "Australia/Sydney", "UTC"]


def _field(parent: ui.Ref, key: object, control: ui.Ref, label: str, help: str = "") -> nu.Nu:
    """A labelled field at ``parent[key]`` holding ``control``, a slot spec."""
    return parent[key].to(ui.FieldRef.slot(label=label, help=help)).control.to(control).init()


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The settings page, drawn."""
    to = meridian.links(links)
    root = ui.ContainerRef("settings", props={})
    layout = root["layout"].to(
        ui.GridRef.slot(cols="240px 1fr", gap=10, align="start", stack_below=768)
    )
    shown = [root.init()]

    # --- the sidebar ---------------------------------------------------------------------------
    side = layout[0, 0].to(ui.ColumnRef.slot(gap=6))
    shown.append(
        side[0]
        .to(
            ui.LinkRef.slot(
                label="Dashboard", href=to["dashboard"], icon="arrow-left", variant="muted"
            )
        )
        .init()
    )
    for k, (label, items) in enumerate(NAV):
        nav = side[k + 1].to(ui.NavListRef.slot(label=label))
        # Pinned, every one: the items share the page's route, so following
        # the tab would light them all.
        shown += [
            nav[i]
            .to(
                ui.NavItemRef.slot(
                    label=text,
                    href=to["settings"],
                    icon=icon,
                    meta=meta,
                    active=k == 0 and i == 0,
                )
            )
            .init()
            for i, (text, icon, meta) in enumerate(items)
        ]

    # --- the page ------------------------------------------------------------------------------
    main = layout[0, 1].to(ui.ColumnRef.slot(gap=10, max_width="panel", divided=True))
    shown.append(
        main["title"]
        .to(
            ui.HeadingRef.slot(
                label="General",
                level=1,
                size="3xl",
                subtitle="How the workspace looks to the people in it.",
            )
        )
        .init()
    )

    workspace = main["workspace"].to(
        ui.PageSectionRef.slot(
            title="Workspace", description="Shown on every page and in every email."
        )
    )
    shown.append(workspace.actions[0].to(ui.ButtonRef.slot(label="Save changes", size="sm")).init())
    pair = workspace[0].to(ui.GridRef.slot(max_columns=2, min_cell_width=220, gap=4))
    shown += [
        _field(pair, 0, ui.InputRef.slot(value="Meridian Atacama"), "Name"),
        _field(
            pair,
            1,
            ui.InputRef.slot(value="meridian.network/atacama", mono=True),
            "Address",
            "Where members sign in.",
        ),
        _field(
            pair,
            2,
            ui.SelectRef.slot(options=ZONES, selected="America/Santiago"),
            "Time zone",
            "Plans and reports use it.",
        ),
        _field(
            pair,
            3,
            ui.SelectRef.slot(options=["Sexagesimal", "Decimal degrees"], selected="Sexagesimal"),
            "Coordinates",
        ),
        _field(
            workspace,
            1,
            ui.TextAreaRef.slot(
                value="Two reflectors and a spectrograph at 2,400 m, run for the southern transient programs.",
                rows=3,
            ),
            "About",
            "A line or two for the sign-in page.",
        ),
    ]

    observing = main["observing"].to(
        ui.PageSectionRef.slot(
            title="Observing defaults",
            description="What a new request starts with. Each request can change them.",
        )
    )
    shown += [
        observing.actions[0]
        .to(ui.ButtonRef.slot(label="Reset", icon="rotate-ccw", variant="ghost", size="sm"))
        .init(),
        observing[0]
        .to(ui.SwitchRef.slot(label="Book clear nights on their own", default=True))
        .init(),
        observing[1].to(ui.SwitchRef.slot(label="Email the morning report", default=True)).init(),
        observing[2]
        .to(ui.SwitchRef.slot(label="Skip nights within three days of full moon"))
        .init(),
        _field(
            observing,
            3,
            ui.SliderRef.slot(min=1.0, max=3.0, step=0.1, value=2.0),
            "Highest airmass",
            "Lower keeps targets higher in the sky.",
        ),
    ]

    danger = main["danger"].to(ui.PageSectionRef.slot(title="Danger zone"))
    box = danger[0].to(ui.CardRef.slot(variant="outline", padding=4))
    row = box[0].to(ui.RowRef.slot(gap=4, wrap=True, grow={0: 1}))
    words = row[0].to(ui.ColumnRef.slot(gap=1))
    shown += [
        words[0].to(ui.TextRef.slot(value="Delete this workspace", weight="semibold")).init(),
        words[1]
        .to(
            ui.TextRef.slot(
                value="Frames stay in the archive for 30 days, then go for good.",
                tone="secondary",
                size="sm",
            )
        )
        .init(),
        row[1]
        .to(ui.ButtonRef.slot(label="Delete workspace", icon="trash-2", variant="danger"))
        .init(),
    ]

    return nu.Sequential(*shown)
