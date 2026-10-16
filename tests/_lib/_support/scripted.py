"""nuagent's test harness: a scripted model, and stores the tests can look into.

``Scripted`` is the test backend: ``ask`` hands out the next canned reply and
keeps the conversation it was asked with, ``wrap`` is the identity. ``Mem``
and ``KV`` run a term over their store and leave the session and the world
behind as plain dicts the test reads afterwards: ``Mem`` binds two dicts,
``KV`` one sqlite file it reads back after the run.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import nu
import nustd.kv
from nu.domains.shape.interactions import Extract
from nu.lang import ScalarQuery
from nuagent.presets.store.kv import KVSession, KVStore
from nuagent.presets.store.mem import MemSession, MemStore


if TYPE_CHECKING:
    from collections.abc import Callable


class _Next(ScalarQuery):
    """The script's next reply. Keeps the messages it was asked with."""

    def __init__(self, script: Scripted, messages: nu.Nu) -> None:
        super().__init__(messages)
        self._payload["script"] = script

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (messages,) = children
        script = self._payload["script"]

        def thunk(rt: object) -> object:
            script.seen.append(copy.deepcopy(list(messages(rt))))
            return script.replies[len(script.seen) - 1]

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        (messages,) = children
        script = self._payload["script"]

        async def athunk(rt: object) -> object:
            script.seen.append(copy.deepcopy(list(await messages(rt))))
            return script.replies[len(script.seen) - 1]

        return athunk


@dataclass
class Scripted:
    """A model that says what it is told to, in order."""

    replies: list[str]
    seen: list[list[dict]] = field(default_factory=list)
    wraps: int = 0

    def ask(self, messages: nu.Nu) -> nu.Nu:
        return _Next(self, messages)

    def wrap(self, body: nu.Nu) -> nu.Nu:
        self.wraps += 1
        return body


@dataclass
class Mem:
    """The session's dict and the world's, kept after the run."""

    session: dict = field(default_factory=dict)
    world: dict = field(default_factory=dict)
    store: MemStore = field(default_factory=MemStore)

    #: The world's ``log``, for a state line.
    log = nu.ListRef[str]("log")

    #: The fabric the model's Shapes are declared on.
    fabric = "nu"

    def program(self, out: str) -> str:
        return program(out, self.fabric)

    def context(self) -> nu.Context:
        return nu.Context().bind(dict, self.session, MemSession).bind(dict, self.world)

    def run(self, term: nu.Nu) -> object:
        value, _ = nu.run(term, self.context())
        return value


class KVWorld(nu.Shape):
    """Every world slot the tests write, on kv."""

    done = nustd.kv.BoolRef.slot()
    log = nustd.kv.ListRef.slot(str)
    title = nustd.kv.StrRef.slot()
    nums = nustd.kv.ListRef.slot(int)
    even_sum = nustd.kv.IntRef.slot()


#: KVWorld's slots, read back after a run.
WORLD = ("done", "log", "title", "nums", "even_sum")

#: The session's slots, read back after a run.
SESSION = ("messages", "reply", "program", "outcome")


@dataclass
class KV:
    """A kv store on one sqlite file, session and world both, read back after each run.

    ``session`` and ``world`` are seeded into the file before the first run,
    then refreshed from it after every run.
    """

    path: str
    session: dict = field(default_factory=dict)
    world: dict = field(default_factory=dict)

    #: The world's ``log``, for a state line.
    log = KVWorld.log

    #: The fabric the model's Shapes are declared on.
    fabric = "nustd.kv"

    def program(self, out: str) -> str:
        return program(out, self.fabric)

    def __post_init__(self) -> None:
        self.store = KVStore.sqlite(self.path)
        seeds = [
            *(self.store.bracket(getattr(KVSession, k).set(v)) for k, v in self.session.items()),
            *(self.store.rewrite(getattr(KVWorld, k).set(v)) for k, v in self.world.items()),
        ]
        if seeds:
            nu.run(self.store.bound(nu.Sequential(*seeds)))

    def run(self, term: nu.Nu) -> object:
        value, _ = nu.run(self.store.bound(term))
        self.session = self._read(KVSession, SESSION, self.store.bracket)
        self.world = self._read(KVWorld, WORLD, self.store.rewrite)
        return value

    def _read(self, shape: type[nu.Shape], slots: tuple[str, ...], bracket) -> dict:
        """The slots that hold something, as plain data. An empty kv list reads as absent."""
        refs = {k: getattr(shape, k) for k in slots}
        read = nu.Dict.of(**{k: nu.If(r.exists(), Extract(r), None) for k, r in refs.items()})
        held = nu.run(self.store.bound(bracket(read)))[0]
        return {k: v for k, v in held.items() if v is not None and v != []}


def block(body: str) -> str:
    """A reply holding one python block around ``body``, with prose either side."""
    return f"Here it goes.\n```python\n{body.strip()}\n```\nThat should do it."


def head(fabric: str = "nu") -> str:
    """Model module bits the tests compose replies from: Run and World on ``fabric``."""
    return (
        "import nu\nimport nustd.kv\n\n\n"
        f"class Run(nu.Shape):\n    done = {fabric}.BoolRef.slot()\n\n\n"
        f"class World(nu.Shape):\n    log = {fabric}.ListRef.slot(str)\n\n\n"
    )


#: The mem head.
HEAD = head()


def program(out: str, fabric: str = "nu") -> str:
    """A reply whose module declares Run and World on ``fabric`` and returns ``out``."""
    return block(head(fabric) + f"def out():\n    return {out}\n")
