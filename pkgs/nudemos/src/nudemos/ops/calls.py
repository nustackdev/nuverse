"""The ops resources' methods as Nu terms: each calls one method on the resource ``nu.Provide`` bound.

- :class:`Open`, :class:`Drain`: the :class:`~.gateway.Gateway`, started on a port and
  release, and what it saw since the last drain.
- :class:`Read`: the :class:`~.machine.Machine` and the jobs' processes, now.
- :class:`Shop`: the :class:`~.work.Shoppers`, one second of shopping.
- :class:`Work`: a scheduled job's one run (:class:`~.work.Worker`).

The resource is child 0, read through a ``FabricRef``: it is what the call
changes, so it sits in the mutation slot. A method that is a coroutine is
awaited; any other runs inline.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, ClassVar

import nu
from nu.engine.structure import Declared
from nu.lang import ScalarAction

from .gateway import Gateway
from .machine import Machine
from .work import Shoppers, Worker


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang.runtime import Runtime


__all__ = ["Drain", "Open", "Read", "Shop", "Work"]


class _Call(ScalarAction):
    """Calls :attr:`method` on the bound :attr:`resource` with the other children's values."""

    resource: ClassVar[type] = Gateway
    method: ClassVar[str] = ""
    _mutates = Declared(value=frozenset({0}), name="mutates")

    def __init__(self, *args: object) -> None:
        super().__init__(nu.FabricRef(self.resource), *args)

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self.method

        def thunk(rt: Runtime) -> object:
            obj, *args = (c(rt) for c in children)
            return getattr(obj, method)(*args)

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self.method

        async def athunk(rt: Runtime) -> object:
            obj, *args = [await c(rt) for c in children]
            out = getattr(obj, method)(*args)
            return await out if inspect.isawaitable(out) else out

        return athunk


class Open(_Call):
    """Start serving on ``port`` as ``release`` does, the orders store in ``data``: the first drain."""

    method = "open"

    def __init__(self, port: object, release: object, data: object) -> None:
        super().__init__(port, release, data)


class Drain(_Call):
    """What the gateway saw since the last drain: ``{lines, gw, point}``. Raises once it is out of memory."""

    method = "drain"


class Read(_Call):
    """The machine now and each job's process: see :meth:`.Machine.read`."""

    resource = Machine
    method = "read"

    def __init__(self, pids: object, disk: object) -> None:
        super().__init__(pids, disk)


class Shop(_Call):
    """One second of shoppers on the gateway at ``port``: see :meth:`.Shoppers.shop`."""

    resource = Shoppers
    method = "shop"

    def __init__(self, port: object, users: object) -> None:
        super().__init__(port, users)


class Work(_Call):
    """One run of the scheduled job ``name``: see :meth:`.Worker.run`."""

    resource = Worker
    method = "run"

    def __init__(self, name: object, ask: object) -> None:
        super().__init__(name, ask)
