"""A space held open on the test's loop, as a host opens one: headless, with real workers.

Run terms against it, read the stores, and wait until the kernel has made
something true. The space is made first with the web device's planes
(Settings among them), then opened headless: the kernel, the system planes
and a worker pool run, no device driver does. A test that needs one runs it
``beside`` the hold, eg the web device's nav.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import nu
import nuspace
import nuspace.host
from _support.made import MADE, MADE_STORE
from nu.lang import ScalarQuery


if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from nuspace.kernel import EnvFactory


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
    """An open space: run terms against it, read the stores, wait for the kernel."""

    ctx: nu.Context
    done: asyncio.Event
    task: asyncio.Task

    async def run(self, term: nu.Nu) -> object:
        value, _ = await nu.arun(term, self.ctx)
        return value

    async def read(self, term: nu.Nu) -> object:
        """``term`` read in ``nuspace.atomic``: a snapshot of each store it reads."""
        return await self.run(nuspace.atomic(term))

    async def do(self, term: nu.Nu) -> object:
        """``term`` in one commit: ``nuspace.atomic``."""
        return await self.run(nuspace.atomic(term))

    async def made(self, term: nu.Nu) -> object:
        """Run ``term``, a term given ``into=MADE``, and read what it set there."""
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
            await asyncio.wait_for(self.task, 30)


async def opened(
    path: str,
    *,
    name: str = "nuverse-test",
    spares: int = 2,
    envs: Mapping[str, EnvFactory] | None = None,
    beside: nu.Nu | None = None,
) -> Kernel:
    """The space at ``path`` made with the web planes, then open headless on this loop until :meth:`Kernel.close`.

    Args:
        path: The space's root.
        name: The workers' process name prefix.
        spares: Idle workers to keep up.
        envs: Env factories of the test's own.
        beside: A term run beside the hold, cancelled at close, eg a driver.
    """
    await nu.arun(nuspace.host.make_space(path, devices=("web",)))
    loop = asyncio.get_running_loop()
    ready, done = loop.create_future(), asyncio.Event()
    hold = nu.With(MADE_STORE, body=nu.let(_Hold(ready, done), lambda _: nu.Noop()))
    body = hold if beside is None else nu.Race(beside, hold)
    space = nuspace.host.open_space(
        path, devices=(), spares=spares, envs=envs, body=body, name=name
    )
    task = asyncio.create_task(nu.arun(space))
    await asyncio.wait({task, ready}, timeout=30, return_when=asyncio.FIRST_COMPLETED)
    if task.done():
        task.result()  # the open failed: say why
    return Kernel(await asyncio.wait_for(ready, 1), done, task)
