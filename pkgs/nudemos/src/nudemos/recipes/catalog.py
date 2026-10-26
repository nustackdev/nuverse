"""Catalog: the instruments as a list to act on.

A page header with search and an add button, then tabs over the list. The
list is a grid of cards, each with its picture on top, its state on the
header's right and its actions in a footer pinned to the bottom, so a row
of cards lines its buttons up whatever each one says. Under it, saved views
as whole-card links, recently viewed pages as page links, and an empty
archive that says what would be there and where to read more.
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

#: Saved views: (key, title, what it shows, count, the page it opens).
VIEWS = (
    (
        "clear",
        "Clear tonight",
        "Open instruments under a clear forecast",
        "7 instruments",
        "dashboard",
    ),
    ("south", "Southern sky", "Everything below the equator", "9 instruments", "dashboard"),
    ("mine", "Booked by me", "Your requests, next one first", "3 bookings", "detail"),
)

#: Recently viewed pages: (key, title, where it is, when, the page it opens).
RECENT = (
    ("kestrel", "Kestrel 2", "Atacama, reflector", "Today", "detail"),
    ("plan", "Tonight's plan", "Kestrel 2, six slots", "Today", "detail"),
    ("members", "Members", "Settings, 12 people", "Yesterday", "settings"),
)


def page(links: Mapping[str, str] | None = None) -> nu.Nu:
    """The catalog, drawn."""
    to = meridian.links(links)
    shown: list[nu.Nu] = []

    def put(ref_cls: type[ui.Ref], segment: str, parent: ui.Ref | None, **props: object) -> ui.Ref:
        ref = ref_cls(segment, parent_ref=parent, props=props)
        shown.append(ref.init())
        return ref

    root = put(ui.ContainerRef, "catalog", None, size="main", gap=10)

    # --- header ------------------------------------------------------------------------------
    head = put(ui.RowRef, "head", root, align="end", gap=2, wrap=True)
    put(
        ui.HeadingRef,
        "title",
        head,
        label="Instruments",
        level=1,
        size="3xl",
        eyebrow="Meridian network",
        subtitle="Every telescope on the network. Book one, or open it for tonight's plan.",
    )
    put(ui.SpacerRef, "push", head)
    put(ui.ButtonRef, "filter", head, label="Filters", icon="sliders-horizontal", variant="outline")
    put(ui.ButtonRef, "add", head, label="Add instrument", icon="plus")

    # --- the list, under tabs -----------------------------------------------------------------
    open_now = [i for i in meridian.INSTRUMENTS if i["status"] == "open"]
    tabs = put(
        ui.TabsRef,
        "views",
        root,
        tabs=[
            {"id": "all", "label": f"All {len(meridian.INSTRUMENTS)}"},
            {"id": "open", "label": f"Open tonight {len(open_now)}"},
            {"id": "down", "label": "Down 1"},
        ],
        active="all",
        variant="line",
    )
    grid = put(ui.GridRef, "all", tabs, columns=3, min_width=260, gap=5)
    for item in meridian.INSTRUMENTS:
        tone, state = STATES[item["status"]]
        card = put(
            ui.CardRef,
            item["id"],
            grid,
            title=item["name"],
            subtitle=f"{item['aperture']} {item['kind'].lower()}, {item['site']}",
        )
        put(
            ui.ImageRef,
            "media",
            card,
            src=meridian.sky(item["seed"], item["hue"], 640, 360),
            alt="",
            fit="cover",
            aspect="16/9",
        )
        put(ui.StatusPillRef, "actions", card, tone=tone, label=state)
        put(ui.TextRef, "summary", card, value=item["summary"], tone="secondary", size="sm")
        queue = f"{item['queue']} in queue" if item["queue"] else "Queue paused"
        put(
            ui.TextRef,
            "meta",
            card,
            value=f"{queue}, seeing {item['seeing']}",
            tone="muted",
            size="xs",
        )
        footer = put(ui.RowRef, "footer", card, gap=2)
        put(
            ui.ButtonRef,
            "open",
            footer,
            label="Details",
            variant="secondary",
            size="sm",
            href=to["detail"],
        )
        put(ui.SpacerRef, "push", footer)
        put(
            ui.ButtonRef,
            "book",
            footer,
            label="Book",
            icon="calendar",
            size="sm",
            disabled=item["status"] == "closed",
        )
    rows = put(ui.ColumnRef, "open", tabs, gap=1)
    for item in open_now:
        put(
            ui.PageLinkRef,
            item["id"],
            rows,
            href=to["detail"],
            title=item["name"],
            icon="target",
            description=item["summary"],
            meta=item["site"],
        )
    put(
        ui.EmptyStateRef,
        "down",
        tabs,
        icon="wrench",
        label="Merlin is down for a mirror recoat",
        description="Back on Friday. Its queue is paused, not dropped.",
    )

    # --- saved views: whole cards as links -----------------------------------------------------
    saved = put(
        ui.PageSectionRef,
        "saved",
        root,
        title="Saved views",
        description="Filters you keep coming back to.",
    )
    put(
        ui.ButtonRef,
        "new",
        saved.actions,
        label="New view",
        icon="plus",
        variant="ghost",
        size="sm",
    )
    cards = put(ui.GridRef, "cards", saved, columns=3, min_width=220, gap=4)
    for key, title, what, count, opens in VIEWS:
        card = put(
            ui.CardRef, key, cards, title=title, subtitle=what, href=to[opens], variant="sunken"
        )
        put(ui.TextRef, "count", card, value=count, weight="medium", size="sm")

    # --- recently viewed and the archive ---------------------------------------------------------
    lower = put(ui.GridRef, "lower", root, columns=2, min_width=300, gap=8)
    recent = put(ui.PageSectionRef, "recent", lower, title="Recently viewed")
    for key, title, where, when, opens in RECENT:
        put(
            ui.PageLinkRef,
            key,
            recent,
            href=to[opens],
            title=title,
            icon="file-text",
            description=where,
            meta=when,
        )
    archive = put(ui.PageSectionRef, "archive", lower, title="Archived")
    box = put(ui.BoxRef, "box", archive, border="hairline", padding="lg")
    put(
        ui.EmptyStateRef,
        "empty",
        box,
        icon="archive",
        label="Nothing archived yet",
        description="Retired instruments land here, frames and history kept.",
        action="How archiving works",
        action_href=to["landing"],
    )

    return nu.Sequential(*shown)
