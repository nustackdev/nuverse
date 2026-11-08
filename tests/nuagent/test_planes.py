"""The Chat plane: found as an extension, its cells loading, and a conversation in a real space.

The space is one for the module, opened the way a host opens one, with
reactions on real workers. A conversation's engine runs on a scripted model
(:data:`SCRIPTED`, a shim the worker imports), so nothing here talks to a
network: every message is two turns, a read and then the end of the run.
The last test runs the real engine shim on settings it cannot build a
backend from.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace

import pytest
import pytest_asyncio
from _support import kernel_envs
from _support.kernel import Kernel, opened
from _support.made import MADE

import nu
import nuagent
import nuspace
import nuspace.devices.web as web
import nustd.kv
from nuagent.planes import PLANE, chat, engine, settings
from nuagent.planes.chat import ANSWER_SPEC, SAID_SPEC
from nuagent.planes.engine import conversation, engine_of
from nuagent.planes.ext import COMPOSER, said_prog
from nuagent.planes.state import ERROR, IDLE, RUNNING, STOPPED, Engine, Run
from nuagent.prompt import TASK, opening, surface
from nuagent.protocol import OK, RUNTIME
from nuspace import Space
from nuspace.devices.web import Conn, Web
from nuspace.devices.web.env import session_env
from nuspace.devices.web.nav import BY as NAV_BY
from nuspace.devices.web.nav import nav
from nuspace.places import inside
from nuspace.system import reactions, reload
from nuspace.system.reactions import Registry


module_loop = pytest.mark.asyncio(loop_scope="module")

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 30.0

#: The model's module head: the Run it ends a run through, and a note in its own cell's state.
HEAD = """\
import nu
import nustd.kv
import nuspace


class Run(nu.Shape):
    done = nustd.kv.BoolRef.slot()


class Note(nu.Shape):
    text = nustd.kv.StrRef.slot()


"""

#: Every message: the first turn reads, the second writes a note and ends the run.
REPLIES = [
    "Let me look.\n```python\n" + HEAD + "def out():\n    return nu.Int(6) * 7\n```",
    "Done.\n```python\n"
    + HEAD
    + "def out():\n    return nuspace.atomic(nuspace.here(Note).text.set('hi'))"
    + " >> nuspace.at.plane.state(Run).done.set(True)\n```",
]

#: The engine on the scripted model, as the worker loads it: the two replies over and over.
SCRIPTED = f"""\
from _support.scripted import Scripted
from nuagent.planes import engine


out = engine.out(backend=Scripted({REPLIES * 8!r}))
"""


class Note(nu.Shape):
    """The note the scripted model writes, read back from the engine's cell."""

    text = nustd.kv.StrRef.slot()


#: A reply whose program takes two minutes.
WAITS = "```python\n" + HEAD + "def out():\n    return nu.Delay(120.0)\n```"

#: The engine on a model whose program does not end soon, for a stop to cut.
HANGS = f"""\
from _support.scripted import Scripted
from nuagent.planes import engine


out = engine.out(backend=Scripted({[WAITS]!r}))
"""

#: An answer cell: a line of Markdown.
CELL = """\
import nustd.ui


def out():
    return nustd.ui.MarkdownRef("answer").set("Six times seven is **42**.")
"""


def answering(cell: str) -> str:
    """A reply whose program adds ``cell`` to the page and ends the run."""
    head = "```python\n" + HEAD + "from nuagent.planes import answer\n\n\n"
    done = "nuspace.at.plane.state(Run).done.set(True)"
    return head + f"def out():\n    return answer({cell!r}) >> {done}\n```"


def scripted(*replies: str) -> str:
    """The engine on a scripted model saying ``replies``, in order."""
    return (
        "from _support.scripted import Scripted\nfrom nuagent.planes import engine\n\n\n"
        f"out = engine.out(backend=Scripted({list(replies)!r}))\n"
    )


#: The engine on a model that answers in its first turn.
ANSWERS = scripted(answering(CELL))

#: The engine on a model that answers and keeps the new cell's id in its own cell's state.
KEEPS = scripted(
    "```python\n"
    + HEAD
    + "from nuagent.planes import answer\n\n\n"
    + f"def out():\n    return answer({CELL!r}, into=nuspace.here(Note).text)"
    + " >> nuspace.at.plane.state(Run).done.set(True)\n```"
)

#: Cells that do not build: one does not parse, one builds a term that would not run.
BROKEN = {
    "parse": "def out(:\n",
    "validate": "import nu\n\n\ndef out():\n    return nu.Noop() >> nu.Int(1)\n",
}


SOURCES = {
    "composer": COMPOSER,
    "said": nu.run(said_prog(3))[0],
    "engine": engine.SOURCE,
    "settings": settings.SOURCE,
}


# --- No kernel ----------------------------------------------------------------------


def test_discovery_finds_the_chat_plane():
    from nuspace.specs import discover

    ext = discover()["nuagent"]
    assert [p.name for p in ext.planes] == ["nuagent.chat"]
    assert ext.planes == (replace(PLANE, name="nuagent.chat"),)
    assert nuagent.extension().planes == (PLANE,)


def test_the_run_is_shown_with_its_base_and_fabric():
    text = surface(run=Run).render()
    assert "class Run(nu.Shape):\n    done: nustd.kv.BoolRef" in text
    # The engine's prose says where it lives: the running plane's state.
    assert "nuspace.at.plane.state(Run)" in engine.CHAT


def test_the_opening_takes_a_task_known_only_at_run_time():
    parts = engine.parts()
    text = nu.run(nu.let("  hi  ", lambda t: opening(t, parts)))[0]
    assert text == opening("hi", parts)
    assert text.endswith(TASK + "hi\n")
    assert [p.name for p in parts][:2] == ["protocol", "chat"]


@pytest.mark.parametrize("name", list(SOURCES))
async def test_each_cell_loads_through_the_session_rewrite(store, name):
    source = SOURCES[name]
    made = nuspace.plane.add("p", backend="async") >> nuspace.cell.add("p", source, id="c")
    await store.do(made)
    env = session_env("127.0.0.1:9")("s1")
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=env.rewrite)
    term = await store.read(load)
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(inside(term, plane="p", cell="c")))


# --- The space ----------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("chat") / "space")
    envs = {"session": kernel_envs.session}
    k = await opened(path, name="nuagent-chat", spares=2, envs=envs, beside=nav())
    yield k
    await k.close()


def linked(page: str) -> Engine:
    """The page's engine ids, as the page keeps them."""
    return nuspace.at.plane(id=page).state(Engine)


def listed(ids: nu.Nu) -> nu.Nu:
    """A dict's keys as a list, ``[]`` when it was never written."""
    return nu.If(ids.exists(), nu.list(ids.keys()), nu.Literal([]))


def kept(engine_id: str) -> nu.Nu:
    """What a conversation keeps, as plain data."""
    c = conversation(engine_id)
    return nu.Dict.of(
        inbox=c.inbox.extract(),
        cursor=c.cursor.fallback(0),
        status=c.status.fallback(""),
        error=c.error.fallback(""),
        sid=c.sid.fallback(""),
        turns=c.turns.extract(),
        messages=c.messages.extract(),
        done=nuspace.at.plane(id=engine_id).state(Run).done.fallback(None),
    )


def live(plane: str) -> nu.Nu:
    """The plane's live plane runs."""
    return listed(Space.exec.indexes.live.plane_to_plane_runs[plane].ids)


def started(cell: nu.StrArg) -> nu.Nu:
    """Whether each live cell run of ``cell`` has started."""
    ids = Space.exec.indexes.live.cell_to_cell_runs[cell].ids
    each = ids.iter().map(lambda cr: Space.exec.cell_runs[nu.Str(cr)].started_at.exists())
    return nu.If(ids.exists(), each.to_list(), nu.Literal([]))


async def chat_page(space: Kernel, source: str | None = None) -> tuple[str, str]:
    """A Chat plane made as ``+`` makes one, then made sure of as its composer does.

    With ``source``, the engine and its cell are made first, the cell on that
    prog, so the engine never runs anything else.
    """
    page = await space.made(nuspace.specs.add_plane(PLANE, into=MADE))
    if source is not None:
        eid, cid = f"{page}_engine", f"{page}_engine_cell"
        await space.do(linked(page).plane.set(eid) >> linked(page).cell.set(cid))
        plane = nuspace.plane.add(eid, parent=page, name="engine", backend="async")
        await space.do(plane >> nuspace.cell.add(eid, source, id=cid, name="engine", fabrics=[]))
    await space.run(chat.ensure(page))
    await bound(space, page)
    return page, await space.read(engine_of(page))


async def bound(space: Kernel, page: str) -> None:
    """Wait until the engine's reaction listens: its cell run live and started, its subscription bound."""
    reaction = await space.until(linked(page).reaction.fallback(""), bool, SLOW)
    await space.until(started(reaction), lambda runs: any(runs), SLOW)
    # The cell run is live a moment before its subscription binds.
    await asyncio.sleep(0.3)


async def handled(space: Kernel, eid: str, n: int) -> dict:
    """The conversation once ``n`` messages are handled and no run of the engine is live."""
    await space.until(kept(eid), lambda k: k["cursor"] >= n and k["status"] != "thinking", SLOW)
    await space.until(live(eid), lambda rs: rs == [], SLOW)
    return await space.read(kept(eid))


async def cells_of(space: Kernel, page: str) -> list[dict]:
    """The page's cells in order, each its row with its ``id``."""
    ids = await space.read(nu.list(Space.planes[page].cells.keys()))
    return [{"id": c, **await space.read(Space.cells[c].extract())} for c in ids]


@module_loop
async def test_a_chat_makes_its_engine_reaction_and_settings_once(space):
    page, eid = await chat_page(space)
    await space.run(chat.ensure(page))
    assert await space.read(nu.list(Space.planes[page].children.keys())) == [eid]
    row = await space.read(Space.planes[eid].extract())
    assert (row["spec"], row["backend"], row["name"]) == (engine.SPEC, "async", "engine")
    assert await space.read(Web.planes.contains(eid)) is False
    cid = await space.read(linked(page).cell)
    assert await space.read(nu.list(Space.planes[eid].cells.keys())) == [cid]
    assert (await space.read(Space.cells[cid].extract()))["prog"] == engine.SOURCE
    agent = await space.read(Space.indexes.cell_keys[settings.KEY])
    assert (await space.read(Space.cells[agent].extract()))["plane"] == settings.PLANE
    assert (await space.read(Space.cells[agent].extract()))["prog"] == settings.SOURCE
    reaction = await space.read(linked(page).reaction)
    by_plane = nuspace.at.plane(id=reactions.PLANE).state(Registry).by_plane[eid].ids
    assert await space.read(by_plane.extract()) == {reaction: True}
    # Nothing was waiting, so nothing ran it.
    await space.until(live(eid), lambda rs: rs == [], SLOW)
    assert (await space.read(kept(eid)))["cursor"] == 0


@module_loop
async def test_two_tabs_making_sure_of_a_new_chat_agree_on_one_engine(space):
    page = await space.made(nuspace.specs.add_plane(PLANE, into=MADE))
    both = nu.ParallelAsync(chat.ensure(page), chat.ensure(page))
    await nu.arun(both, space.ctx, max_parallel=2)
    eid = await space.read(engine_of(page))
    assert await space.read(nu.list(Space.planes[page].children.keys())) == [eid]
    # The agent settings stay one cell, under its key.
    on_settings = await cells_of(space, settings.PLANE)
    assert [r["key"] for r in on_settings].count(settings.KEY) == 1


@module_loop
async def test_a_message_runs_the_engine_through_the_loop_and_ends(space):
    page, eid = await chat_page(space, SCRIPTED)
    await space.run(chat.say(eid, "hi"))
    k = await handled(space, eid, 1)
    assert (k["cursor"], k["status"], k["error"]) == (1, IDLE, "")
    assert [(t["at"], t["kind"]) for t in k["turns"]] == [(0, OK), (0, OK)]
    assert k["turns"][0]["observation"] == "outcome: 42"
    assert k["turns"][0]["reply"] == REPLIES[0]
    assert "return nu.Int(6) * 7" in k["turns"][0]["program"]
    assert k["done"] is True
    opening = k["messages"][0]
    assert opening["role"] == "user"
    assert opening["content"].startswith("# How you reply")
    assert opening["content"].endswith(TASK + "hi\n")
    assert [m["role"] for m in k["messages"]] == ["user", "assistant", "user", "assistant", "user"]
    assert k["sid"] != ""
    # The program's own state landed under the engine's cell.
    cid = await space.read(linked(page).cell)
    assert await space.read(nuspace.at.cell(id=cid).state(Note).text.fallback("")) == "hi"
    # What the page draws.
    shown = await space.read(chat._shown(conversation(eid)))
    assert shown == {"status": IDLE, "tone": "neutral", "error": ""}
    trace = await space.read(chat._trace(conversation(eid), 0))
    assert (trace["text"], trace["done"]) == ("hi", True)
    assert [(t["key"], t["kind"], t["variant"]) for t in trace["steps"]] == [
        ("t0", OK, "ok"),
        ("t1", OK, "ok"),
    ]
    title = chat._title(nu.List(trace["steps"]), trace["done"])
    assert nu.run(title)[0] == "2 steps · ok"


@module_loop
async def test_a_later_message_carries_the_conversation_on(space):
    _, eid = await chat_page(space, SCRIPTED)
    await space.run(chat.say(eid, "hi"))
    first = await handled(space, eid, 1)
    await space.run(chat.say(eid, "  and again  "))
    k = await handled(space, eid, 2)
    assert k["messages"][:5] == first["messages"]
    assert k["messages"][5] == {"role": "user", "content": "  and again  "}
    assert len(k["messages"]) == 10
    assert [t["at"] for t in k["turns"]] == [0, 0, 1, 1]
    assert k["sid"] == first["sid"]
    assert k["done"] is True


@module_loop
async def test_messages_sent_together_are_handled_in_one_go(space):
    _, eid = await chat_page(space, SCRIPTED)
    await space.run(chat.say(eid, "one") >> chat.say(eid, "two") >> chat.say(eid, "three"))
    k = await handled(space, eid, 3)
    assert [t["at"] for t in k["turns"]] == [0, 0, 1, 1, 2, 2]
    said = [m["content"] for m in k["messages"] if m["role"] == "user"]
    assert said[0].endswith(TASK + "one\n")
    assert "two" in said and "three" in said


@module_loop
async def test_stop_cuts_the_run_under_way(space):
    _, eid = await chat_page(space, HANGS)
    await space.run(chat.say(eid, "wait") >> chat.say(eid, "and this"))
    shown = chat._shown(conversation(eid))
    await space.until(shown, lambda s: s["status"] == RUNNING, SLOW)
    await space.run(chat.stop(eid))
    await space.until(live(eid), lambda rs: rs == [], SLOW)
    k = await space.read(kept(eid))
    assert (k["cursor"], k["status"]) == (2, STOPPED)
    assert (await space.read(shown))["status"] == STOPPED


@module_loop
async def test_settings_it_cannot_build_from_fail_the_message_and_move_on(space):
    _, eid = await chat_page(space)
    await space.do(settings.kept().backend.set(settings.LLM))
    try:
        await space.run(chat.say(eid, "hi"))
        k = await handled(space, eid, 1)
        assert k["status"] == ERROR
        assert "needs an endpoint" in k["error"]
        assert k["messages"] == []
    finally:
        await space.do(settings.kept().backend.set(settings.CC))


def names(rows: list[dict]) -> list[tuple[str, str]]:
    """A page's cells as ``(name, spec)``, in order."""
    return [(r["name"], r["spec"]) for r in rows]


@module_loop
async def test_a_message_is_a_said_cell_above_the_composer(space):
    page, eid = await chat_page(space, SCRIPTED)
    (box,) = [r["id"] for r in await cells_of(space, page)]
    await space.run(chat.tell(page, "hi") >> chat.tell(page, "and again"))
    k = await handled(space, eid, 2)
    assert k["inbox"] == ["hi", "and again"]
    rows = await cells_of(space, page)
    assert names(rows)[:2] == [("said", SAID_SPEC), ("said", SAID_SPEC)]
    assert rows[2]["id"] == box
    assert [r["prog"] for r in rows[:2]] == [nu.run(said_prog(i))[0] for i in (0, 1)]
    trace = await space.read(chat._trace(conversation(eid), 1))
    assert (trace["text"], trace["done"], len(trace["steps"])) == ("and again", True, 2)


@module_loop
async def test_the_agent_answers_with_a_cell_above_the_composer(space):
    page, eid = await chat_page(space, ANSWERS)
    await space.run(chat.tell(page, "six times seven?"))
    k = await handled(space, eid, 1)
    assert [(t["at"], t["kind"]) for t in k["turns"]] == [(0, OK)]
    rows = await cells_of(space, page)
    assert [n for n, _ in names(rows)] == ["said", "answer", "composer"]
    said, answered, _ = rows
    assert said["spec"] == SAID_SPEC
    assert (answered["prog"], answered["spec"]) == (CELL, ANSWER_SPEC)
    assert answered["fabrics"] == ["ui"]
    trace = await space.read(chat._trace(conversation(eid), 0))
    assert [(t["kind"], t["variant"]) for t in trace["steps"]] == [(OK, "ok")]
    assert nu.run(chat._title(nu.List(trace["steps"]), trace["done"]))[0] == "1 step · ok"


@module_loop
async def test_a_message_goes_at_the_end_once_the_composer_is_gone(space):
    page, eid = await chat_page(space, SCRIPTED)
    (box,) = [r["id"] for r in await cells_of(space, page)]
    await space.do(nuspace.cell.remove(box))
    await space.run(chat.tell(page, "hi"))
    await handled(space, eid, 1)
    assert [n for n, _ in names(await cells_of(space, page))] == ["said"]


@module_loop
async def test_an_answer_hands_its_id_to_a_ref_in_another_store(space):
    page, eid = await chat_page(space, KEEPS)
    await space.run(chat.tell(page, "six times seven?"))
    await handled(space, eid, 1)
    _, answered, _ = await cells_of(space, page)
    cid = await space.read(linked(page).cell)
    assert await space.read(nuspace.at.cell(id=cid).state(Note).text) == answered["id"]


@pytest.mark.parametrize("how", list(BROKEN))
@module_loop
async def test_an_answer_that_does_not_build_fails_the_program_and_adds_nothing(space, how):
    page, eid = await chat_page(space, scripted(answering(BROKEN[how]), REPLIES[1]))
    await space.run(chat.tell(page, "hi"))
    k = await handled(space, eid, 1)
    assert [t["kind"] for t in k["turns"]] == [RUNTIME, OK]
    assert "ValueError: the answer" in k["turns"][0]["observation"]
    assert [n for n, _ in names(await cells_of(space, page))] == ["said", "composer"]


@pytest.mark.parametrize(
    ("steps", "done", "title"),
    [
        ([], False, "working..."),
        ([{"kind": OK}], False, "1 step · working..."),
        ([{"kind": OK}, {"kind": RUNTIME}], True, "2 steps · runtime"),
        ([], True, "no steps"),
    ],
)
def test_the_trace_title_counts_the_steps_and_names_the_last(steps, done, title):
    assert nu.run(chat._title(nu.List(steps), done))[0] == title


async def started_on_the_page(space: Kernel, sid: str, page: str, cell: str) -> dict:
    """The cell run of ``cell`` in the tab's run of the page, once one has started."""
    pane = Conn.connections[sid].panes[page]
    deadline = time.monotonic() + SLOW
    while True:
        rid = await space.read(pane.plane_run.fallback(""))
        rows: list[dict] = []
        if rid:
            node = Space.exec.indexes.history.plane_to_plane_runs[page].runs[rid]
            ids = await space.read(listed(node.cell_to_cell_runs[cell].ids))
            rows = [await space.read(Space.exec.cell_runs[cr].extract()) for cr in ids]
        mine = [c for c in rows if c.get("started_at") is not None]
        if mine:
            return mine[-1]
        assert time.monotonic() < deadline, f"{cell} never started on {page}, last: {rows!r}"
        await asyncio.sleep(0.05)


@module_loop
async def test_an_answer_starts_on_a_page_open_in_a_tab(space):
    page, eid = await chat_page(space, ANSWERS)
    sid = "tab-answer"
    await space.do(web.open_tab(sid))
    try:
        await space.do(web.set_panes(sid, [page]))
        pane = Conn.connections[sid].panes[page]
        await space.until(pane.plane_run.fallback(""), bool, SLOW)
        await space.run(chat.tell(page, "six times seven?"))
        await handled(space, eid, 1)
        said, answered, _ = [r["id"] for r in await cells_of(space, page)]
        # The pane's run gives each new cell a run: the kernel, or reload once the run is up.
        by = {NAV_BY, reload.BY}
        assert (await started_on_the_page(space, sid, page, said))["by"] in by
        assert (await started_on_the_page(space, sid, page, answered))["by"] in by
    finally:
        await space.do(web.close_tab(sid))
