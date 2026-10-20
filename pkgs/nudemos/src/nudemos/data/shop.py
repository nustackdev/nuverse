"""Owlbridge Coffee Roasters, the shop behind the space: its catalog and the names it knows.

Plain data, nothing Nu. A small online roaster: beans by the bag, a monthly
subscription, some brewing gear and merch, sold on its web store, by
subscription, on a marketplace and wholesale to cafes. Every person and cafe
here is made up.
"""

from __future__ import annotations


__all__ = [
    "CATEGORIES",
    "CHANNELS",
    "CITIES",
    "DEVICES",
    "FIRST",
    "KINDS",
    "LAST",
    "PRODUCTS",
    "SKUS",
    "SOURCES",
    "STAGES",
]


#: The catalog, as it opens: sku, name, category, price, unit cost, stock, weight in a web basket.
_ROWS = [
    ("LK-HB", "House Blend", "Blends", 16.0, 6.1, 640, 9.0),
    ("LK-E9", "Espresso No. 9", "Blends", 18.0, 6.8, 410, 6.5),
    ("LK-DC", "Swiss Water Decaf", "Blends", 17.0, 7.0, 180, 2.2),
    ("LK-ET", "Ethiopia Guji", "Single origin", 21.0, 8.4, 260, 4.4),
    ("LK-CO", "Colombia Huila", "Single origin", 19.0, 7.5, 300, 4.0),
    ("LK-KE", "Kenya Nyeri", "Single origin", 23.0, 9.6, 120, 2.4),
    ("LK-GU", "Guatemala Huehuetenango", "Single origin", 20.0, 7.9, 210, 2.8),
    ("SB-01", "Monthly bag", "Subscription", 15.0, 6.2, 0, 0.0),
    ("SB-02", "Two bags a month", "Subscription", 28.0, 12.1, 0, 0.0),
    ("GR-V6", "Pour-over dripper", "Gear", 24.0, 9.0, 85, 1.3),
    ("GR-HG", "Hand grinder", "Gear", 89.0, 41.0, 34, 0.6),
    ("GR-KT", "Gooseneck kettle", "Gear", 64.0, 29.0, 41, 0.7),
    ("GR-PF", "Paper filters, 100", "Gear", 7.0, 1.9, 520, 2.6),
    ("MR-MG", "Enamel mug", "Merch", 14.0, 4.2, 150, 1.1),
    ("MR-TT", "Canvas tote", "Merch", 12.0, 3.6, 95, 0.6),
]

PRODUCTS: list[dict] = [
    dict(zip(("sku", "name", "category", "price", "cost", "stock", "weight"), r, strict=True))
    for r in _ROWS
]

#: Skus in catalog order: a line's ``sku`` column is a position in this list.
SKUS: list[str] = [p["sku"] for p in PRODUCTS]

CATEGORIES = ["Blends", "Single origin", "Subscription", "Gear", "Merch"]

#: Where an order was sold: a line's ``channel`` column. Pop-up sales only come in by import.
CHANNELS = ["Web store", "Subscription", "Marketplace", "Wholesale", "Pop-up"]

#: Where a web session came from, and on what: an event's ``source`` and ``device`` columns.
SOURCES = ["Organic search", "Instagram", "Newsletter", "Paid search", "Referral", "Direct"]
DEVICES = ["Mobile", "Desktop", "Tablet"]

#: The funnel's stages, in order: an event's ``kind`` column.
STAGES = ["Session", "Product view", "Add to cart", "Checkout", "Purchase"]

#: A customer's ``kind``: who they are to the shop.
KINDS = ["Retail", "Subscriber", "Cafe"]

FIRST = (
    "Ada Ben Cleo Dario Elin Farah Gus Hana Ivo Juno Kai Lena Milo Nadia Otis Pia Quinn Rafa Sela Theo "
    "Uma Vik Wren Xan Yara Zeke Ava Bram Cora Dev Esme Finn Gia Hugo Iris Jory Kenji Lior Maren Noor "
    "Odile Pax Rhea Saul Tova Ulla Vera Wim Yusuf Zara Alma Basil Celia Dmitri Edda Felix Greta Hal Ines Joel"
).split()

LAST = (
    "Abara Bellweather Castellan Delacroix Eskew Fairburn Galloway Halvorsen Ibarra Jaskolski Kettering "
    "Lindqvist Marchetti Nakashima Okafor Pemberton Quist Ravensworth Szabo Thorne Underhill Vasquez "
    "Whitlock Yarrow Zielinski Ashby Brannigan Corrigan Dunmore Ellery Ferro Gaskell Hollis Iversen "
    "Juhasz Kowalczyk Larkin Moreau Novak Oyelaran Prentice Rasmussen Sorensen Tamura Voss Wexler"
).split()

#: Where customers are, with a weight: big cities order more.
CITIES: list[tuple[str, float]] = [
    ("Portland, OR", 9),
    ("Seattle, WA", 8),
    ("San Francisco, CA", 7),
    ("Los Angeles, CA", 7),
    ("Denver, CO", 5),
    ("Austin, TX", 5),
    ("Chicago, IL", 6),
    ("Minneapolis, MN", 3),
    ("Brooklyn, NY", 7),
    ("Boston, MA", 4),
    ("Philadelphia, PA", 3),
    ("Atlanta, GA", 3),
    ("Asheville, NC", 2),
    ("Madison, WI", 2),
    ("Salt Lake City, UT", 2),
    ("Burlington, VT", 1),
]

#: Cafes buying wholesale: made up, every one.
CAFES = [
    "Fieldstone Cafe",
    "The Copper Pot",
    "Morning Hollow",
    "Second Shift Coffee",
    "Bramble & Bean",
    "Northside Kiosk",
    "Little Harbor",
    "Cedar Street Bakery",
    "Lantern Row Cafe",
    "Plinth Coffee Bar",
]
