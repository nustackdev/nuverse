"""The agent page: one Claude Code session, live, steered from here.

A launch makes one per agent, and the agent's job right under it. Every cell
finds the job as the page's child (:func:`~.views.with_job`) and reads the
job's state from there: the page holds no state of its own.

- ``status``: the agent's name, status, what it is doing, and what it cost.
- ``say``: a message for the agent, its next turn; stop or resume.
- ``transcript``: everything it said and did, streamed as it happens, tool calls folded.
- ``sketch``: the board it draws on, when asked to sketch.
"""

from __future__ import annotations

from nuspace import Plane


__all__ = ["PAGE", "SAY", "SKETCH", "STATUS", "TRANSCRIPT"]


_IMPORTS = """\
import nu
import nustd.ui
from nuspace.system.utils import redraws, snap
from nuverse_demos.agents import launch, views
from nuverse_demos.agents.state import Agent, at
from nuverse_demos.agents.views import with_job
"""


def _cell(body: str) -> str:
    return _IMPORTS + "\n\n" + body


STATUS = _cell("""\
class Head(nustd.ui.Row):
    pill = nustd.ui.StatusPillRef.slot()
    doing = nustd.ui.TextRef.slot()


class Tiles(nustd.ui.Grid):
    prompts = nustd.ui.StatRef.slot(label="Prompts")
    calls = nustd.ui.StatRef.slot(label="Tool calls")
    tokens = nustd.ui.StatRef.slot(label="Tokens")
    cost = nustd.ui.StatRef.slot(label="Cost")
    seconds = nustd.ui.StatRef.slot(label="Working time")


class View(nustd.ui.Column):
    head = Head.slot(gap=3, align="center")
    facts = nustd.ui.TextRef.slot()
    tiles = Tiles.slot(columns=5, min_width=120, gap=3)
    error = nustd.ui.AlertRef.slot(variant="danger")


def draw(h):
    t = View.tiles
    failed = nu.IfDo(nu.Str(h["error"]) != "", View.error.set("The last turn failed", body=h["error"]), View.error.erase())
    return (
        View.head.pill.set(h["status"], tone=h["tone"]) >> View.head.doing.set(h["doing"])
        >> View.facts.set(h["facts"])
        >> t.prompts.set_value(h["prompts"]) >> t.calls.set_value(h["calls"]) >> t.tokens.set_value(h["tokens"])
        >> t.cost.set_value(h["cost"]) >> t.seconds.set_value(h["seconds"]) >> failed
    )


def follow(job):
    moves = [at(job, Agent.n.on_change()), at(job, Agent.status.on_change())]
    return redraws(moves, views.head(views.agent_view(job)), draw, every=2.0)


def out(plane):
    return with_job(plane, follow)
""")


SAY = _cell("""\
class Say(nustd.ui.Row):
    text = nustd.ui.InputRef.slot(placeholder="Say something: it is the agent's next turn")
    send = nustd.ui.ButtonRef.slot(label="Say", icon="send")
    stop = nustd.ui.ButtonRef.slot(label="Stop", variant="secondary", icon="square")


class View(nustd.ui.Column):
    say = Say.slot(gap=2, align="end")


S = View.say


def button(label):
    resume = S.stop.set("Resume", variant="primary", icon="play")
    stop = S.stop.set("Stop", variant="secondary", icon="square")
    return nu.IfDo(nu.Str(label) == "Resume", resume, stop)


def sent(job):
    # The box's text into the agent's inbox: it is the next turn, now or after this one.
    typed = snap(nu.Str(S.text).strip())
    return nu.let(typed, lambda t: nu.IfDo(nu.Str(t) != "", launch.say(job, t) >> S.text.set("")))


def press(job):
    status = snap(nu.Dict(views.head(views.agent_view(job)))["button"])
    return nu.let(status, lambda b: nu.IfDo(nu.Str(b) == "Resume", launch.resume(job), launch.stop(job)))


def follow(job):
    status = at(job, Agent.status)
    label = nu.Dict(views.head(views.agent_view(job)))["button"]
    placed = S.text.set("") >> S.send.set("Say") >> S.stop.set("Stop")
    return placed >> nu.ParallelAsync(
        redraws([status.on_change()], label, button, every=3.0),
        nu.ReactForever(S.send.on_click(), sent(job)),
        nu.ReactForever(S.stop.on_click(), press(job)),
    )


def out(plane):
    return with_job(plane, follow)
""")


TRANSCRIPT = _cell("""\
class Tool(nustd.ui.Collapsible):
    call = nustd.ui.CodeRef.slot(wrap=True, max_height=320)
    back = nustd.ui.CodeRef.slot(wrap=True, max_height=320)


class Entry(nustd.ui.Column):
    who = nustd.ui.BadgeRef.slot(variant="info")
    text = nustd.ui.MarkdownRef.slot()
    tool = Tool.slot()
    note = nustd.ui.TextRef.slot()


class View(nustd.ui.Column):
    head = nustd.ui.HeadingRef.slot(level=4)
    log = nustd.ui.ColumnRef.slot(Entry, gap=3)


def entry(e):
    # One transcript entry: what was said, a tool call folded, or the turn's tally.
    at_ = View.log[e["key"]]
    return nu.SwitchDo(nu.Str(e["kind"]), {
        "user": at_.who.set("you", variant="info") >> at_.text.set(e["text"]),
        "text": at_.text.set(e["text"]),
        "tool": at_.tool.set(open=False, title=e["title"]) >> at_.tool.call.set(e["code"]) >> at_.tool.call.set_language(e["lang"]),
        "back": at_.tool.set(title=e["title"]) >> at_.tool.back.set(e["code"]),
        "note": at_.note.set(e["text"]),
    })


def follow(job):
    # Every event past the last one drawn, on every one that lands.
    def drawn(seen):
        i = nu.Dict(seen)["i"]
        new = snap(nu.list(at(job, Agent.log.slice(i, None))))
        each = lambda d: nu.ForEachDo(nu.List(nu.Dict(d)["entries"]), entry) >> seen.set(nu.Dict(d)["seen"])
        behind = snap(at(job, Agent.n.fallback(0))) > i
        step = nu.IfDo(behind, nu.let(views.entries(new, seen), each))
        return nu.ReconcileReactive(snap(at(job, Agent.n.on_change())), step, every=3.0)

    return View.head.set("Transcript") >> nu.let({"i": 0, "titles": {}}, drawn)


def out(plane):
    return with_job(plane, follow)
""")


SKETCH = _cell("""\
class View(nustd.ui.Column):
    hint = nustd.ui.TextRef.slot()
    board = nustd.ui.SketchRef.slot(width=560, height=340, readonly=True, label="What it drew")


def draw(elements):
    # A line until the agent draws something, then the board.
    drawn = View.hint.erase() >> View.board.set(elements)
    return nu.IfDo(nu.List(elements).len() > 0, drawn)


def follow(job):
    sketch = at(job, Agent.sketch)
    hint = View.hint.set("Sketch board: ask the agent to sketch something and it draws here.")
    return hint >> redraws([sketch.on_change()], sketch.fallback([]), draw, every=10.0)


def out(plane):
    return with_job(plane, follow)
""")


PAGE = Plane(
    "agents_page",
    "Agent",
    icon="bot",
    description="One Claude Code session: its transcript streamed live, steered from here.",
    meta={"editable": True, "full_width": True},
    cells=(
        ("status", STATUS),
        ("say", SAY),
        ("transcript", TRANSCRIPT),
        ("sketch", SKETCH),
    ),
    backend="async",
)
