"""Catalog: the instruments as a list to act on.

A page header with filters and an add button, then tabs over the list. The
list is a grid of cards, each with its picture in the card's media, its
state on the header's right and its actions in the footer pinned to the
bottom, so a row of cards lines its buttons up whatever each one says.
Under it, saved views as whole-card links, recently viewed pages as page
links, and an empty archive that says what would be there and where to
read more.

Every child is reached from its container and named with ``.to(Kind)``
where it is placed: a tab by its id, a card's parts as ``card.media``,
``card.actions`` and ``card.footer``, repeated items by position.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nustd.ui as ui
from nudemos.recipes import meridian


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ["page"]


#: How each state reads: (pill tone, pill label).
STATES = {"open": ("ok", "Open"), "busy": ("warn", "Busy"), "closed": ("neutral", "Down")}

#: Saved views: (title, what it shows, count, the page it opens).
VIEWS = (
    ("Clear tonight", "Open instruments under a clear forecast", "7 instruments", "dashboard"),
    ("Southern sky", "Everything below the equator", "9 instruments", "dashboard"),
    ("Booked by me", "Your requests, next one first", "3 bookings", "detail"),
)

#: Recently viewed pages: (title, where it is, when, the page it opens).
RECENT = (
    ("Kestrel 2", "Atacama, reflector", "Today", "detail"),
    ("Tonight's plan", "Kestrel 2, six slots", "Today", "detail"),
    ("Members", "Settings, 12 people", "Yesterday", "settings"),
)


def _card(grid: ui.Ref, i: int, item: dict, to: Mapping[str, str]) -> list[nu.Nu]:
    """One instrument's card at position ``i``: picture, state, words, actions."""
    tone, state = STATES[item["status"]]
    queue = f"{item['queue']} in queue" if item["queue"] else "Queue paused"
    card = grid[i].to(
        ui.CardRef.slot(
            title=item["name"],
            subtitle=f"{item['aperture']} {item['kind'].lower()}, {item['site']}",
        )
    )
    footer = card.footer.to(ui.RowRef.slot(gap=2, justify="between"))
    return [
        card.media.to(
            ui.ImageRef.slot(
                src=meridian.sky(item["seed"], item["hue"], 640, 360),
                alt="",
                fit="cover",
                aspect="16/9",
            )
        ).init(),
        card.actions[0].to(ui.StatusPillRef.slot(tone=tone, label=state)).init(),
        card[0].to(ui.TextRef.slot(value=item["summary"], tone="secondary", size="sm")).init(),
        card[1]
        .to(ui.TextRef.slot(value=f"{queue}, seeing {item['seeing']}", tone="muted", size="xs"))
        .init(),
        footer[0]
        .to(ui.ButtonRef.slot(label="Details", variant="secondary", size="sm", href=to["detail"]))
        .init(),
        footer[1]
        .to(
            ui.ButtonRef.slot(
                label="Book", icon="calendar", size="sm", disabled=item["status"] == "closed"
            )
        )
        .init(),
    ]


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The catalog, drawn."""
    to = meridian.links(links)
    root = ui.ContainerRef("catalog", props={"gap": 10})

    # --- header ------------------------------------------------------------------------------
    head = root["head"].to(ui.RowRef.slot(align="end", gap=2, wrap=True, grow={"title": 1}))
    shown = [
        root.init(),
        head["title"]
        .to(
            ui.HeadingRef.slot(
                label="Instruments",
                level=1,
                size="3xl",
                eyebrow="Meridian network",
                subtitle="Every telescope on the network. Book one, or open it for tonight's plan.",
            )
        )
        .init(),
        head["filter"]
        .to(ui.ButtonRef.slot(label="Filters", icon="sliders-horizontal", variant="outline"))
        .init(),
        head["add"].to(ui.ButtonRef.slot(label="Add instrument", icon="plus")).init(),
    ]

    # --- the list, under tabs -----------------------------------------------------------------
    open_now = [i for i in meridian.INSTRUMENTS if i["status"] == "open"]
    tabs = root["views"].to(
        ui.TabsRef.slot(
            tabs=[
                {"id": "all", "label": f"All {len(meridian.INSTRUMENTS)}"},
                {"id": "open", "label": f"Open tonight {len(open_now)}"},
                {"id": "down", "label": "Down 1"},
            ],
            active="all",
            variant="line",
        )
    )
    grid = tabs["all"].to(ui.GridRef.slot(max_columns=3, min_cell_width=260, gap=5))
    for i, item in enumerate(meridian.INSTRUMENTS):
        shown += _card(grid, i, item, to)
    rows = tabs["open"].to(ui.ColumnRef.slot(gap=1))
    shown += [
        rows[i]
        .to(
            ui.PageLinkRef.slot(
                href=to["detail"],
                title=item["name"],
                icon="target",
                description=item["summary"],
                meta=item["site"],
            )
        )
        .init()
        for i, item in enumerate(open_now)
    ]
    shown.append(
        tabs["down"]
        .to(
            ui.EmptyStateRef.slot(
                icon="wrench",
                label="Merlin is down for a mirror recoat",
                description="Back on Friday. Its queue is paused, not dropped.",
            )
        )
        .init()
    )

    # --- saved views: whole cards as links -----------------------------------------------------
    saved = root["saved"].to(
        ui.PageSectionRef.slot(title="Saved views", description="Filters you keep coming back to.")
    )
    shown.append(
        saved.actions[0]
        .to(ui.ButtonRef.slot(label="New view", icon="plus", variant="ghost", size="sm"))
        .init()
    )
    cards = saved[0].to(ui.GridRef.slot(max_columns=3, min_cell_width=220, gap=4))
    for i, (title, what, count, opens) in enumerate(VIEWS):
        card = cards[i].to(
            ui.CardRef.slot(title=title, subtitle=what, href=to[opens], variant="sunken")
        )
        shown.append(card[0].to(ui.TextRef.slot(value=count, weight="medium", size="sm")).init())

    # --- recently viewed and the archive ---------------------------------------------------------
    lower = root["lower"].to(ui.GridRef.slot(cols=2, gap=8, stack_below=768))
    recent = lower[0, 0].to(ui.PageSectionRef.slot(title="Recently viewed", gap=1))
    shown += [
        recent[i]
        .to(
            ui.PageLinkRef.slot(
                href=to[opens], title=title, icon="file-text", description=where, meta=when
            )
        )
        .init()
        for i, (title, where, when, opens) in enumerate(RECENT)
    ]
    archive = lower[0, 1].to(ui.PageSectionRef.slot(title="Archived"))
    box = archive[0].to(ui.CardRef.slot(variant="outline", padding=6))
    shown.append(
        box[0]
        .to(
            ui.EmptyStateRef.slot(
                icon="archive",
                label="Nothing archived yet",
                description="Retired instruments land here, frames and history kept.",
                action="How archiving works",
                action_href=to["landing"],
            )
        )
        .init()
    )

    return nu.Sequential(*shown)
