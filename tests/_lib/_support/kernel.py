"""A kernel held open on the test's loop, as nuspace's own tests hold one.

Run ops against it, read the store, and wait until the kernel has made
something true. A trimmed copy of nuspace's ``tests/_lib/_support/kernel.py``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import nu
from _support.made import MADE, MADE_STORE
from nu.lang import ScalarQuery
from nuspace import ops
from nuspace.system.kernel import open_kernel


if TYPE_CHECKING:
    from collections.abc import Callable


class _Hold(ScalarQuery):
    """Hands the host context to ``opened``, then waits for ``done``."""

    def __init__(self, opened: asyncio.Future, done: asyncio.Event) -> None:
        super().__init__()
        self._payload = {"opened": opened, "done": done}

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        opened, done = self._payload["opened"], self._payload["done"]

        async def athunk(rt: object) -> object:
            opened.set_result(rt.ctx)
            await done.wait()

        return athunk


@dataclass
class Kernel:
    """An open kernel: run ops against it, read the store, wait for the kernel."""

    ctx: nu.Context
    done: asyncio.Event
    task: asyncio.Task

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        return await self.run(ops.snapshot(term))

    async def made(self, term: nu.Nu) -> object:
        """Run ``term``, an op given ``into=MADE``, and read what it set there."""
        await self.run(term)
        return await self.run(MADE)

    async def until(
        self, term: nu.Nu, pred: Callable[[object], bool], timeout: float = 4.0
    ) -> object:
        """Read ``term`` until ``pred`` holds on it, or fail with the last value."""
        deadline = time.monotonic() + timeout
        while True:
            value = await self.read(term)
            if pred(value):
                return value
            if time.monotonic() > deadline:
                msg = f"timed out waiting, last read: {value!r}"
                raise AssertionError(msg)
            await asyncio.sleep(0.05)

    async def close(self) -> None:
        if not self.task.done():
            self.done.set()
            await asyncio.wait_for(self.task, 15)


async def opened(name: str = "nuverse-test", **kwargs: object) -> Kernel:
    """A kernel open on this loop, held until :meth:`Kernel.close`."""
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    hold = nu.With(MADE_STORE, body=nu.let(_Hold(ready, done), lambda _: nu.Noop()))
    task = asyncio.create_task(nu.arun(open_kernel(hold, name=name, **kwargs)))
    ctx = await asyncio.wait_for(asyncio.shield(ready), 20)
    return Kernel(ctx, done, task)
