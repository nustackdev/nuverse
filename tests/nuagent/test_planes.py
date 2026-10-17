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
import nustd.kv
from nuagent.planes import PLANE, chat, engine, settings
from nuagent.planes.chat import ANSWER_BY, SAID_BY
from nuagent.planes.ext import COMPOSER, said_prog
from nuagent.planes.state import ERROR, IDLE, RUNNING, STOPPED, Chat, Run
from nuagent.prompt import TASK, opening, surface
from nuagent.protocol import OK, RUNTIME
from nuspace import CellState, ops
from nuspace.ops.utils import atomic
from nuspace.shapes import Reroot, Space
from nuspace.system.devices.web.env import session_env
from nuspace.system.kernel import store
from nuspace.system.kernel.body import Rewrites
from nuspace.system.services import ensure_system, init, nav, reactions
from nuspace.system.settings import ensure_settings
from nustd.kv import Snapshot


module_loop = pytest.mark.asyncio(loop_scope="module")

#: A deadline for waits a loaded machine stretches. Met early, it costs nothing.
SLOW = 30.0

#: The model's module head: the Run it ends a run through, and a note in its own cell's state.
HEAD = """\
import nu
import nustd.kv
import nuspace
from nuspace import ops


class Run(nuspace.PlaneState):
    done = nustd.kv.BoolRef.slot()


class Note(nuspace.CellState):
    text = nustd.kv.StrRef.slot()


"""

#: Every message: the first turn reads, the second writes a note and ends the run.
REPLIES = [
    "Let me look.\n```python\n" + HEAD + "def out():\n    return nu.Int(6) * 7\n```",
    "Done.\n```python\n"
    + HEAD
    + "def out():\n    return ops.atomic_state(Note.text.set('hi')) >> Run.done.set(True)\n```",
]

#: The engine on the scripted model, as the worker loads it: the two replies over and over.
SCRIPTED = f"""\
from _support.scripted import Scripted
from nuagent.planes import engine


out = engine.out(backend=Scripted({REPLIES * 8!r}))
"""


class Note(CellState):
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
    return head + f"def out():\n    return answer({cell!r}) >> Run.done.set(True)\n```"


def scripted(*replies: str) -> str:
    """The engine on a scripted model saying ``replies``, in order."""
    return (
        "from _support.scripted import Scripted\nfrom nuagent.planes import engine\n\n\n"
        f"out = engine.out(backend=Scripted({list(replies)!r}))\n"
    )


#: The engine on a model that answers in its first turn.
ANSWERS = scripted(answering(CELL))

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
    from nuspace.ext import discover

    (ext,) = [e for e in discover() if e.name == "nuagent"]
    assert [p.name for p in ext.planes] == ["nuagent.chat"]
    assert ext.planes == (replace(PLANE, name="nuagent.chat"),)
    assert nuagent.extension().planes == (PLANE,)


def test_the_run_is_shown_with_its_base_and_fabric():
    text = surface(run=Run).render()
    assert "class Run(nuspace.PlaneState):\n    done: nustd.kv.BoolRef" in text


def test_the_opening_takes_a_task_known_only_at_run_time():
    parts = engine.parts()
    text = nu.run(nu.let("  hi  ", lambda t: opening(t, parts)))[0]
    assert text == opening("hi", parts)
    assert text.endswith(TASK + "hi\n")
    assert [p.name for p in parts][:2] == ["protocol", "chat"]


@pytest.mark.parametrize("name", list(SOURCES))
async def test_each_cell_loads_through_the_kernel_rewrites(store, name):
    source = SOURCES[name]
    await store.run(ops.add_plane("p", backend="async") >> ops.add_cell("p", source, cell_id="c"))
    env = session_env("127.0.0.1:9")("s1")
    rewrite = Rewrites(Reroot("p", "c"), env.rewrite)
    load = Space.cells["c"].prog.load(scope={"plane": "p", "cell": "c"}, rewrite=rewrite)
    term = await store.run(Snapshot(load, scope=Space))
    assert isinstance(term, nu.Nu)
    nu.validate(nu.compile(term))


# --- The space ----------------------------------------------------------------------


@pytest_asyncio.fixture(loop_scope="module", scope="module")
async def space(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("chat") / "space")
    await nu.arun(nu.With(store(path), body=ensure_system() >> ensure_settings()))
    envs = {"session": kernel_envs.session}
    k = await opened("nuagent-chat", path=path, spares=2, envs=envs, init=init.PLANE)
    yield k
    await k.close()


def kept(engine_id: str) -> nu.Nu:
    """What a conversation keeps, as plain data."""
    return ops.plane_state(
        engine_id,
        nu.Dict.of(
            inbox=Chat.inbox.extract(),
            cursor=Chat.cursor.fallback(0),
            status=Chat.status.fallback(""),
            error=Chat.error.fallback(""),
            sid=Chat.sid.fallback(""),
            turns=Chat.turns.extract(),
            messages=Chat.messages.extract(),
            done=Run.done.fallback(None),
        ),
    )


def live(plane: str) -> nu.Nu:
    return nu.list(Space.kernel.planes_running[plane].runs)


async def chat_page(space: Kernel, source: str | None = None) -> tuple[str, str]:
    """A Chat plane made as ``+`` makes one, then made sure of as its composer does.

    With ``source``, the engine and its cell are made first, the cell on that
    prog, so the engine never runs anything else.
    """
    page = await space.made(ops.create_plane(PLANE, into=MADE))
    eid = f"{page}_engine"
    if source is not None:
        made = ops.add_plane(eid, backend="async", parent=page, made_by=engine.MADE_BY)
        await space.run(made >> ops.add_cell(eid, source, cell_id=f"{eid}_cell"))
    await space.run(chat.ensure(page))
    return page, eid


async def handled(space: Kernel, eid: str, n: int) -> dict:
    """The conversation once ``n`` messages are handled and no run of the engine is live."""
    await space.until(kept(eid), lambda k: k["cursor"] >= n and k["status"] != "thinking", SLOW)
    await space.until(live(eid), lambda rs: rs == [], SLOW)
    return await space.read(kept(eid))


@module_loop
async def test_a_chat_makes_its_engine_reaction_and_settings_once(space):
    page, eid = await chat_page(space)
    await space.run(chat.ensure(page))
    assert await space.read(ops.children(page)) == [eid]
    row = await space.read(Space.planes[eid].props.extract())
    assert (row["ui"], row["made_by"], row["backend"]) == (False, engine.MADE_BY, "async")
    assert await space.read(ops.cells(eid)) == [f"{eid}_cell"]
    assert await space.read(ops.prog(f"{eid}_cell")) == engine.SOURCE
    assert await space.read(ops.cell_plane(settings.CELL)) == settings.PLANE
    assert await space.read(ops.prog(settings.CELL)) == settings.SOURCE
    change = f"ops.plane_state({eid!r}, Chat.inbox.on_change())"
    assert await space.read(reactions.reaction_of(change, eid)) != ""
    # Its first fire found nothing to handle and ended.
    await space.until(live(eid), lambda rs: rs == [], SLOW)
    assert (await space.read(kept(eid)))["cursor"] == 0


@module_loop
async def test_a_message_runs_the_engine_through_the_loop_and_ends(space):
    _, eid = await chat_page(space, SCRIPTED)
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
    assert await space.read(ops.cell_state(f"{eid}_cell", Note.text.fallback(""))) == "hi"
    # What the page draws.
    shown = await space.read(ops.plane_state(eid, chat._shown()))
    assert shown == {"status": IDLE, "tone": "neutral", "error": ""}
    trace = await space.read(ops.plane_state(eid, chat._trace(0)))
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
    shown = ops.plane_state(eid, chat._shown())
    await space.until(shown, lambda s: s["status"] == RUNNING, SLOW)
    await space.run(chat.stop(eid))
    await space.until(live(eid), lambda rs: rs == [], SLOW)
    k = await space.read(kept(eid))
    assert (k["cursor"], k["status"]) == (2, STOPPED)
    assert (await space.read(shown))["status"] == STOPPED


@module_loop
async def test_settings_it_cannot_build_from_fail_the_message_and_move_on(space):
    _, eid = await chat_page(space)
    bad = settings.Config.backend.set(settings.LLM)
    await space.run(ops.atomic_state(ops.cell_state(settings.CELL, bad)))
    try:
        await space.run(chat.say(eid, "hi"))
        k = await handled(space, eid, 1)
        assert k["status"] == ERROR
        assert "needs an endpoint" in k["error"]
        assert k["messages"] == []
    finally:
        await space.run(
            ops.atomic_state(
                ops.cell_state(settings.CELL, settings.Config.backend.set(settings.CC))
            )
        )


def names(rows: list[dict]) -> list[tuple[str, str]]:
    """A page's cells as ``(name, made_by)``, in order."""
    return [(r["name"], r["props"]["made_by"]) for r in rows]


@module_loop
async def test_a_message_is_a_said_cell_above_the_composer(space):
    page, eid = await chat_page(space, SCRIPTED)
    (box,) = await space.read(ops.cells(page))
    await space.run(chat.tell(page, "hi") >> chat.tell(page, "and again"))
    k = await handled(space, eid, 2)
    assert k["inbox"] == ["hi", "and again"]
    rows = await space.read(ops.cell_rows(page))
    assert names(rows)[:2] == [("said", SAID_BY), ("said", SAID_BY)]
    assert rows[2]["id"] == box
    assert [r["prog"] for r in rows[:2]] == [nu.run(said_prog(i))[0] for i in (0, 1)]
    trace = await space.read(ops.plane_state(eid, chat._trace(1)))
    assert (trace["text"], trace["done"], len(trace["steps"])) == ("and again", True, 2)


@module_loop
async def test_the_agent_answers_with_a_cell_above_the_composer(space):
    page, eid = await chat_page(space, ANSWERS)
    await space.run(chat.tell(page, "six times seven?"))
    k = await handled(space, eid, 1)
    assert [(t["at"], t["kind"]) for t in k["turns"]] == [(0, OK)]
    rows = await space.read(ops.cell_rows(page))
    assert [n for n, _ in names(rows)] == ["said", "answer", "composer"]
    said, answered, _ = rows
    assert said["props"]["made_by"] == SAID_BY
    assert (answered["prog"], answered["props"]["made_by"]) == (CELL, ANSWER_BY)
    assert answered["props"]["has_ui"] is True
    trace = await space.read(ops.plane_state(eid, chat._trace(0)))
    assert [(t["kind"], t["variant"]) for t in trace["steps"]] == [(OK, "ok")]
    assert nu.run(chat._title(nu.List(trace["steps"]), trace["done"]))[0] == "1 step · ok"


@pytest.mark.parametrize("how", list(BROKEN))
@module_loop
async def test_an_answer_that_does_not_build_fails_the_program_and_adds_nothing(space, how):
    page, eid = await chat_page(space, scripted(answering(BROKEN[how]), REPLIES[1]))
    await space.run(chat.tell(page, "hi"))
    k = await handled(space, eid, 1)
    assert [t["kind"] for t in k["turns"]] == [RUNTIME, OK]
    assert "ValueError: the answer" in k["turns"][0]["observation"]
    assert [n for n, _ in names(await space.read(ops.cell_rows(page)))] == ["said", "composer"]


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
    """The cell run nav started for ``cell`` in the tab's run of the page, once there is one."""
    deadline = time.monotonic() + SLOW
    while True:
        rid = await space.read(nav.pane_run(sid, page))
        rows = (await space.read(ops.run(rid)))["cells"] if rid else []
        mine = [c for c in rows if c["cell"] == cell and c.get("started_at") is not None]
        if mine:
            return mine[-1]
        assert time.monotonic() < deadline, f"{cell} never started on {page}, last: {rows!r}"
        await asyncio.sleep(0.05)


@module_loop
async def test_an_answer_starts_on_a_page_open_in_a_tab(space):
    page, eid = await chat_page(space, ANSWERS)
    sid = "tab-answer"
    tab = Space.connections[sid]
    await space.run(atomic(tab.routes.set([page]) >> tab.opened.set(time.time())))
    try:
        await space.until(nav.pane_run(sid, page), bool, SLOW)
        await space.run(chat.tell(page, "six times seven?"))
        await handled(space, eid, 1)
        said, answered, _ = await space.read(ops.cells(page))
        assert (await started_on_the_page(space, sid, page, said))["by"] == nav.BY
        assert (await started_on_the_page(space, sid, page, answered))["by"] == nav.BY
    finally:
        await space.run(atomic(Space.connections.del_item(sid)))
