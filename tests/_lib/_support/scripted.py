"""nuagent's test harness: a scripted model, and a mem store the tests can look into.

``Scripted`` is the test backend: ``ask`` hands out the next canned reply and
keeps the conversation it was asked with, ``wrap`` is the identity. ``Mem``
runs a term over a :class:`MemSession` and an untagged world, both plain
dicts the test reads afterwards.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import nu
from nu.lang import ScalarQuery
from nuagent.presets.store.mem import MemSession


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

    def run(self, term: nu.Nu) -> object:
        ctx = nu.Context().bind(dict, self.session, MemSession).bind(dict, self.world)
        value, _ = nu.run(term, ctx)
        return value


def block(body: str) -> str:
    """A reply holding one python block around ``body``, with prose either side."""
    return f"Here it goes.\n```python\n{body.strip()}\n```\nThat should do it."


#: Model module bits the tests compose replies from.
HEAD = "import nu\n\n\nclass Run(nu.Shape):\n    done = nu.BoolRef.slot()\n\n\nclass World(nu.Shape):\n    log = nu.ListRef.slot(str)\n\n\n"


def program(out: str) -> str:
    """A reply whose module declares Run and World and returns ``out``."""
    return block(HEAD + f"def out():\n    return {out}\n")
