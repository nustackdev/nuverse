"""movies, the cinematheque: its tree built on first run, pages reading one catalog, edits flowing."""

from __future__ import annotations

import asyncio
import inspect
from typing import TYPE_CHECKING

import pytest

import nu
import nustd.kv
from nuspace import ops
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel.body import Rewrites
from nustd.ui.core import Frame, WsSession
from nustd.ui.core.protocol import OP_NOTIFY
from nustd.ui.core.session import Session
from nuverse_demos.movies import PLANE, cells, kit
from nuverse_demos.movies.data import FILMS, slug


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

    def touch(self, name: str, value: object, payload: object = None) -> None:
        """The person changes the input ``name`` to ``value``: it reads so, and it notifies."""
        (path,) = {f.ref for f in self.frames if f.ref and f.ref[-1] == name}
        self.values[name] = value
        self._dispatch(Frame(OP_NOTIFY, ref=path, payload=value if payload is None else payload))


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
    """``{cell name: cell id}`` of a plane."""
    return {c["name"]: c["id"] for c in await store.read(ops.cell_rows(plane))}


async def _run(store, plane: str, cell: str, browser: _Browser) -> asyncio.Task:
    """The cell's program run as the kernel runs it, inside its ``Here`` frame."""
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot(plane, cell), env.rewrite)
    load = Space.cells[cell].prog.load(scope={"plane": plane, "cell": cell}, rewrite=rewrite)
    term = await store.run(nustd.kv.Snapshot(load, scope=Space))
    term = nu.Frame(ops.Here, term, plane=plane, cell=cell)
    return asyncio.create_task(nu.arun(term, store.ctx.bind(Session, browser)))


async def _stop(*tasks: asyncio.Task) -> None:
    for task in tasks:
        task.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert all(isinstance(r, asyncio.CancelledError) for r in results), results


async def _films(store, base: str) -> dict:
    return await store.read(ops.plane_state(base, kit.Catalog.films.extract()))


async def _made(store, page: str, n: int) -> bool:
    return len(await store.read(ops.cells(page))) == n


@pytest.fixture
async def seeded(store):
    """A cinematheque at ``m``, its ``add`` cell run once: the films, their pages, the people."""
    await store.run(ops.create_plane(PLANE, plane_id="m"))
    tab = _Browser()
    task = await _run(store, "m", (await _cells(store, "m"))["add"], tab)
    try:
        # The last page the first run makes, with its cells.
        last = "m.person." + slug("Samuel L. Jackson")
        await _until(lambda: _made(store, last, len(cells.PERSON)), timeout=60.0)
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
        for group in (cells.FILM, cells.PERSON, cells.PEOPLE, cells.TIMELINE, cells.ATLAS)
        for _, s in group
    ],
    ids=lambda s: s.split("class ", 1)[-1][:12],
)
async def test_every_page_cell_loads_and_draws(store, source):
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    (row,) = await store.read(ops.cell_rows("p"))
    assert row["props"]["has_ui"]
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=Reroot("p", "c"))
    nu.validate(nu.compile(await store.run(nustd.kv.Snapshot(load, scope=Space))))


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
    kids = await store.read(ops.children("m"))
    assert kids[:3] == ["m.people", "m.timeline", "m.atlas"]
    assert {f"m.film.{slug(f['title'])}" for f in FILMS} <= set(kids)
    people = await store.read(ops.children("m.people"))
    assert "m.person.christopher-nolan" in people
    assert "m.person.amy-adams" not in people
    rows = {r["id"]: r for r in await store.read(ops.plane_rows())}
    assert rows["m.film.dune"]["meta"]["film"] == "dune"
    assert rows["m.film.dune"]["meta"]["base"] == "m"
    assert rows["m.person.michael-caine"]["meta"]["person"] == "Michael Caine"
    for page, spec in (("m.film.dune", cells.FILM), ("m.person.michael-caine", cells.PERSON)):
        made = await store.read(ops.cell_rows(page))
        assert [c["name"] for c in made] == [name for name, _ in spec]
        assert all(c["props"]["has_ui"] for c in made)


async def test_the_first_run_happens_once(seeded):
    store = seeded
    tab = _Browser()
    task = await _run(store, "m", (await _cells(store, "m"))["add"], tab)
    try:
        await _until(lambda: tab.drawn("add"))
        await asyncio.sleep(0.3)
    finally:
        await _stop(task)
    assert len(await store.read(ops.children("m"))) == 23
    assert len(await store.read(ops.cells("m.film.dune"))) == len(cells.FILM)


# --- reactions -------------------------------------------------------------------------------


async def test_a_rating_on_a_film_page_moves_the_shelf(seeded):
    store = seeded
    page, shelf = _Browser(), _Browser()
    film = await _cells(store, "m.film.parasite")
    root = await _cells(store, "m")
    tasks = [
        await _run(store, "m.film.parasite", film["ours"], page),
        await _run(store, "m", root["films"], shelf),
        await _run(store, "m", root["stats"], shelf),
    ]
    try:
        await _until(lambda: page.drawn("rating") and shelf.drawn("table") and shelf.drawn("best"))
        assert page.drawn("rank")[-1]["value"] == "unrated"
        page.touch("rating", 10.0)
        await _until(lambda: shelf.drawn("best")[-1].get("value") == "Parasite")

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
    film = await _cells(store, "m.film.heat")
    tasks = [
        await _run(store, "m", root["films"], shelf),
        await _run(store, "m.film.heat", film["ours"], page),
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
        await _until(lambda: page.drawn("rating")[-1].get("value") == 6.5)
    finally:
        await _stop(*tasks)


async def test_notes_are_kept_as_typed(seeded):
    store = seeded
    page = _Browser()
    film = await _cells(store, "m.film.alien")
    task = await _run(store, "m.film.alien", film["notes"], page)
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
        tab.values["title"] = "Oppenheimer (2023)"
        tab.touch("add", None, {})
        await _until(lambda: store.read(ops.plane_exists("m.film.oppenheimer")))
    finally:
        await _stop(task)
    film = (await _films(store, "m"))["oppenheimer"]
    assert (film["title"], film["year"]) == ("Oppenheimer", 2023)
    assert [c["name"] for c in await store.read(ops.cell_rows("m.film.oppenheimer"))] == [
        n for n, _ in cells.FILM
    ]


async def test_facts_saved_credit_a_new_person(seeded):
    store = seeded
    page = _Browser()
    film = await _cells(store, "m.film.parasite")
    task = await _run(store, "m.film.parasite", film["facts"], page)
    try:
        await _until(lambda: page.drawn("save"))
        page.values.update(
            year=2019,
            runtime=132,
            director="Bong Joon-ho",
            cast=["Song Kang-ho", "Lee Sun-kyun"],
            genres=["Thriller"],
        )
        page.touch("save", None, {})

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
    assert not await store.read(ops.plane_exists("m.person.song-kang-ho"))
    assert await store.read(ops.plane_exists("m.person.bong-joon-ho"))
