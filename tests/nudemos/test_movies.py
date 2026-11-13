"""movies, the cinematheque: its tree built on first run, pages reading one catalog, edits flowing."""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

import pytest

import nu
import nuspace
import nuspace.places
import nuspace.specs
import nuspace.web
from nudemos.movies import PLANE, cells, kit
from nudemos.movies.data import FILMS, slug
from nuspace import Space
from nuspace.web.env import session_env
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.protocol import OP_NOTIFY
from nustd.ui.core.session import Session


if TYPE_CHECKING:
    from collections.abc import Callable


class _Browser(WsSession):
    """A session with no socket. Keeps the frames it is sent, answers reads from ``values``."""

    def __init__(self, values: dict | None = None) -> None:
        super().__init__(ws=None)
        self.frames: list[Frame] = []
        self.values = values or {}

    async def send(self, frame: Frame) -> None:
        self.frames.append(frame)

    async def aread(self, path: tuple[str, ...]) -> object:
        return self.values[path[-1]]

    def drawn(self, name: str) -> list:
        """Every payload sent to the ref ``name``, in order."""
        return [f.payload for f in self.frames if f.ref and f.ref[-1] == name]

    def tile(self, name: str) -> list:
        """Every payload sent to the stat in tile ``name`` (the card's body, ``<name>/0``)."""
        return [
            f.payload for f in self.frames if f.ref and tuple(map(str, f.ref[-2:])) == (name, "0")
        ]

    def touch(self, name: str, value: object, payload: object = None) -> None:
        """The person changes the input ``name`` to ``value``: it reads so, and it notifies a change."""
        (path,) = {f.ref for f in self.frames if f.ref and f.ref[-1] == name}
        self.values[name] = value
        sent = {"event": "change"} if payload is None else payload
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=sent))

    def submit(self, field: str, values: dict, button: str) -> None:
        """The person submits the Form two levels above the input ``field``: one notify, every value in it."""
        (path,) = {f.ref for f in self.frames if f.ref and f.ref[-1] == field}
        payload = {"event": "submit", "values": values, "button": button}
        self._dispatch(Frame(OP_NOTIFY, ref=path[:-2], payload=payload))


async def _until(check: Callable[[], object], timeout: float = 20.0) -> None:
    """Wait until ``check()`` is truthy; a check may return an awaitable, eg a store read."""
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        seen = check()
        if inspect.isawaitable(seen):
            seen = await seen
        if seen:
            return
        assert asyncio.get_running_loop().time() < deadline, "timed out"
        await asyncio.sleep(0.05)


async def _cells(store, plane: str) -> dict:
    """``{cell name: cell id}`` of a plane made from a spec: the ids it keeps in its state."""
    ids = nuspace.at.plane(id=plane).state(nuspace.specs.SpecCells).ids
    return await store.read(ids.extract())


async def _names(store, plane: str) -> list[str]:
    """A plane's cells' names, in order."""
    ids = await store.read(nu.list(Space.planes[plane].cells.keys()))
    return [await store.read(Space.cells[c].name) for c in ids]


async def _run(store, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell's program run as the kernel runs it, inside its ``Here`` frame."""
    env = session_env("127.0.0.1:9")("s1")
    load = Space.cells[cell].prog.load(scope={"plane": plane, "cell": cell}, rewrite=env.rewrite)
    term = nuspace.places.inside(await store.run(nuspace.atomic(load)), plane=plane, cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))


async def _stop(*tasks: asyncio.Task) -> None:
    for task in tasks:
        task.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, asyncio.CancelledError) for r in results), results


async def _films(store, base: str) -> dict:
    return await store.read(kit.catalog(base).films.extract())


async def _pages(store, base: str) -> dict:
    """The plane ids the catalog keeps: ``{film, person, folder}``."""
    return await store.read(kit.catalog(base).planes.extract())


async def _made(store, base: str, kind: str, key: str, n: int) -> bool:
    """The catalog holds the page and the page has ``n`` cells."""
    page = ((await _pages(store, base)) or {}).get(kind, {}).get(key)
    return bool(page) and len(await store.read(nu.list(Space.planes[page].cells.keys()))) == n


@pytest.fixture
async def seeded(store):
    """A cinematheque at ``m``, its ``add`` cell run once: the films, their pages, the people."""
    await store.run(nuspace.specs.add_plane(PLANE, "m"))
    tab = _Browser()
    task = await _run(store, "m", (await _cells(store, "m"))["add"], tab)
    try:
        # The last page the first run makes, with its cells.
        last = slug("Samuel L. Jackson")
        await _until(lambda: _made(store, "m", "person", last, len(cells.PERSON)), timeout=60.0)
    finally:
        await _stop(task)
    return store


# --- the spec --------------------------------------------------------------------------------


def test_the_root_holds_the_cinematheque_cells():
    assert [name for name, _ in PLANE.cells] == ["welcome", "stats", "add", "films", "wall"]
    assert PLANE.children == ()


def test_the_opening_films_connect():
    people = kit.people_of({slug(f["title"]): f for f in FILMS})
    assert len(FILMS) == 20
    assert len(people["Michael Caine"]["films"]) == 3
    assert len(people["Leonardo DiCaprio"]["films"]) == 3
    assert people["Harrison Ford"]["films"] == ["blade-runner", "blade-runner-2049"]
    assert kit.has_page(people["Bong Joon-ho"])
    assert not kit.has_page(people["Amy Adams"])


@pytest.mark.parametrize(
    "source",
    [
        s
        for group in (
            cells.ROOT,
            cells.FILM,
            cells.PERSON,
            cells.PEOPLE,
            cells.TIMELINE,
            cells.ATLAS,
        )
        for _, s in group
    ],
    ids=lambda s: s.split("class ", 1)[-1][:12],
)
async def test_every_page_cell_loads_and_draws(store, source):
    await store.do(nuspace.plane.add("p", backend="async"))
    await store.do(nuspace.cell.add("p", source, id="c"))
    assert await store.read(Space.cells["c"].fabrics) == ["ui"]
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"})
    nu.validate(nu.compile(await store.run(nuspace.atomic(load))))


def test_typed_film_reads_a_year():
    assert nu.run(kit.typed_film("Oppenheimer (2023)"))[0]["year"] == 2023
    assert nu.run(kit.typed_film("  Heat "))[0] == {
        **nu.run(kit.typed_film("Heat"))[0],
        "title": "Heat",
    }


def test_every_film_gets_a_poster():
    url = kit.poster_url(FILMS[0])
    assert url.startswith("data:image/svg+xml")
    assert "GODFATHER" in url


# --- the first run ---------------------------------------------------------------------------


async def test_the_first_run_builds_the_tree(seeded):
    store = seeded
    films = await _films(store, "m")
    assert len(films) == 20
    assert films["dune"]["director"] == "Denis Villeneuve"
    pages = await _pages(store, "m")
    kids = await store.read(nu.list(Space.planes["m"].children.keys()))
    folders = pages["folder"]
    assert kids[:3] == [folders["people"], folders["timeline"], folders["atlas"]]
    assert set(pages["film"]) == {slug(f["title"]) for f in FILMS}
    assert set(pages["film"].values()) <= set(kids)
    people = await store.read(nu.list(Space.planes[folders["people"]].children.keys()))
    assert pages["person"]["christopher-nolan"] in people
    assert "amy-adams" not in pages["person"]
    dune, caine = pages["film"]["dune"], pages["person"]["michael-caine"]
    assert await store.read(Space.planes[dune].meta.extract()) == {"film": "dune"}
    # Each page records its cinematheque in its own plane state, read back checked.
    assert await store.read(kit.base_of(dune)) == "m"
    assert await store.read(kit.base_of(folders["people"])) == "m"
    assert await store.read(kit.base_of("m")) == "m"
    assert await store.read(Space.planes[caine].meta["person"]) == "Michael Caine"
    assert await store.read(Space.planes[dune].icon) == "emoji:🚀"
    assert await store.read(nuspace.web.Web.planes[dune].width) == "page"
    for page, spec in ((dune, cells.FILM), (caine, cells.PERSON)):
        assert await _names(store, page) == [name for name, _ in spec]
        for c in (await _cells(store, page)).values():
            assert await store.read(Space.cells[c].fabrics) == ["ui"]


async def test_a_page_of_a_removed_cinematheque_raises_never_reads_another(seeded):
    store = seeded
    dune = (await _pages(store, "m"))["film"]["dune"]
    # A plane the cinematheque never made recorded no base.
    await store.do(nuspace.plane.add("stray", backend="async"))
    with pytest.raises(nuspace.errors.Missing):
        await store.read(kit.base_of("stray"))
    await store.do(nuspace.plane.remove("m"))
    with pytest.raises(nuspace.errors.Removed):
        await store.read(kit.base_of(dune))


async def test_the_first_run_happens_once(seeded):
    store = seeded
    tab = _Browser()
    task = await _run(store, "m", (await _cells(store, "m"))["add"], tab)
    try:
        await _until(lambda: tab.drawn("add"))
        await asyncio.sleep(0.3)
    finally:
        await _stop(task)
    assert len(await store.read(nu.list(Space.planes["m"].children.keys()))) == 23
    dune = (await _pages(store, "m"))["film"]["dune"]
    assert len(await store.read(nu.list(Space.planes[dune].cells.keys()))) == len(cells.FILM)


# --- reactions -------------------------------------------------------------------------------


async def test_a_rating_on_a_film_page_moves_the_shelf(seeded):
    store = seeded
    page, shelf = _Browser(), _Browser()
    parasite = (await _pages(store, "m"))["film"]["parasite"]
    film = await _cells(store, parasite)
    root = await _cells(store, "m")
    tasks = [
        await _run(store, parasite, film["ours"], page),
        await _run(store, "m", root["films"], shelf),
        await _run(store, "m", root["stats"], shelf),
    ]
    try:
        await _until(lambda: page.drawn("rating") and shelf.drawn("table") and shelf.tile("best"))
        assert page.drawn("rank")[-1]["value"] == "unrated"
        page.touch("rating", 10.0)
        await _until(lambda: shelf.tile("best")[-1].get("value") == "Parasite")

        def parasite() -> dict:
            rows = shelf.drawn("table")[-1]["rows"]
            return next(r for r in rows if r["key"] == "parasite")

        await _until(lambda: parasite()["rating"] == 10.0)
        await _until(lambda: page.drawn("rank")[-1]["value"] == "#1 of 20")
    finally:
        await _stop(*tasks)
    assert (await _films(store, "m"))["parasite"]["rating"] == 10.0


async def test_an_edit_in_the_table_moves_the_film_page(seeded):
    store = seeded
    page, shelf = _Browser(), _Browser()
    root = await _cells(store, "m")
    heat = (await _pages(store, "m"))["film"]["heat"]
    film = await _cells(store, heat)
    tasks = [
        await _run(store, "m", root["films"], shelf),
        await _run(store, heat, film["ours"], page),
    ]
    try:
        await _until(lambda: shelf.drawn("table") and page.drawn("rating"))
        edit = {
            "event": "edit",
            "key": "heat",
            "row_index": 0,
            "column": "rating",
            "value": 6.5,
            "previous": 9.0,
        }
        shelf.touch("table", None, edit)
        await _until(lambda: page.drawn("rating")[-1] == 6.5)
    finally:
        await _stop(*tasks)


async def test_notes_are_kept_as_typed(seeded):
    store = seeded
    page = _Browser()
    alien = (await _pages(store, "m"))["film"]["alien"]
    film = await _cells(store, alien)
    task = await _run(store, alien, film["notes"], page)
    try:
        await _until(lambda: page.drawn("notes"))
        text = "In space **no one** can hear you scream."
        page.touch("notes", text)

        async def kept() -> bool:
            return (await _films(store, "m"))["alien"]["notes"] == text

        await _until(kept)
    finally:
        await _stop(task)


async def test_adding_a_film_makes_its_page(seeded):
    store = seeded
    tab = _Browser()
    task = await _run(store, "m", (await _cells(store, "m"))["add"], tab)
    try:
        await _until(lambda: tab.drawn("add"))
        tab.submit("title", {"line": {"title": "Oppenheimer (2023)"}}, "add")
        await _until(lambda: _made(store, "m", "film", "oppenheimer", len(cells.FILM)))
    finally:
        await _stop(task)
    film = (await _films(store, "m"))["oppenheimer"]
    assert (film["title"], film["year"]) == ("Oppenheimer", 2023)
    page = (await _pages(store, "m"))["film"]["oppenheimer"]
    assert await _names(store, page) == [n for n, _ in cells.FILM]


async def test_facts_saved_credit_a_new_person(seeded):
    store = seeded
    page = _Browser()
    parasite = (await _pages(store, "m"))["film"]["parasite"]
    film = await _cells(store, parasite)
    task = await _run(store, parasite, film["facts"], page)
    try:
        await _until(lambda: page.drawn("save"))
        page.values.update(
            year=2019,
            runtime=132,
            director="Bong Joon-ho",
            cast=["Song Kang-ho", "Lee Sun-kyun"],
            genres=["Thriller"],
        )
        page.touch("save", None, {"event": "click"})

        async def saved() -> bool:
            return (await _films(store, "m"))["parasite"]["cast"] == [
                "Song Kang-ho",
                "Lee Sun-kyun",
            ]

        await _until(saved)
    finally:
        await _stop(task)
    assert (await _films(store, "m"))["parasite"]["genres"] == ["Thriller"]
    # Song Kang-ho is in one film only: no page. Bong Joon-ho directs: a page, already there.
    people = (await _pages(store, "m"))["person"]
    assert "song-kang-ho" not in people
    assert await store.read(nuspace.plane.exists(people["bong-joon-ho"]))
    # The genre picked the page's icon.
    assert await store.read(Space.planes[parasite].icon) == "emoji:🗝️"
