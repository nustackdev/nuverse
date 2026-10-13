"""The trainer's interactions: what a Nu program asks the :class:`~.trainer.Trainer` it provides.

Each reads the ``Trainer`` bound on the Context by ``nu.Provide`` and calls
one of its methods off-thread, so a chunk of training never stalls the event
loop the program runs on: its reads, writes and subscriptions go on. Their
arguments are ordinary children, so any of them may be a ref read at run
time, eg the learning rate a slider just wrote.

- :class:`TrainChunk`: ``n`` steps at ``lr``: ``{loss, acc, steps, seconds, lr}``.
- :class:`Evaluate`: the test set, or its first ``limit`` images: ``{loss, acc}``.
- :class:`Predict`: the fixed sample digits: ``[[label, prob, probs], ...]``.
- :class:`Digits`: the sample digits themselves: ``[{src, label}, ...]``.
- :class:`Histograms`: weights and grads per layer, binned, as JSON.
- :class:`Info`: device, steps per epoch, data sizes, parameter count.
- :class:`Save` and :class:`Load`: a checkpoint, by path. Load yields the step.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

from nu.lang import ScalarQuery

from .trainer import Trainer


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import FloatArg, IntArg, StrArg
    from nu.lang.runtime import Runtime


__all__ = ["Digits", "Evaluate", "Histograms", "Info", "Load", "Predict", "Save", "TrainChunk"]


class _Call(ScalarQuery):
    """Calls :attr:`method` on the bound ``Trainer`` with the children's values, off-thread."""

    method: ClassVar[str] = ""

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self.method

        def thunk(rt: Runtime) -> object:
            trainer = rt.ctx.fabrics.get(Trainer)
            return getattr(trainer, method)(*(c(rt) for c in children))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        method = self.method

        async def athunk(rt: Runtime) -> object:
            trainer = rt.ctx.fabrics.get(Trainer)
            args = [await c(rt) for c in children]
            return await asyncio.to_thread(getattr(trainer, method), *args)

        return athunk


class TrainChunk(_Call):
    """``n`` training steps at learning rate ``lr``: ``{loss, acc, steps, seconds, lr}``, means over the chunk."""

    method = "train"

    def __init__(self, n: IntArg, lr: FloatArg) -> None:
        super().__init__(n, lr)


class Evaluate(_Call):
    """Loss and accuracy on the test set, or on its first ``limit`` images: ``{loss, acc}``."""

    method = "evaluate"

    def __init__(self, limit: IntArg = 0) -> None:
        super().__init__(limit)


class Predict(_Call):
    """Per sample digit, ``[label, prob, probs]``: what the model says it is, how sure, and all ten."""

    method = "predict"


class Digits(_Call):
    """The fixed sample digits, ``[{src, label}, ...]``: a ``data:`` PNG and the true label each."""

    method = "digits"


class Histograms(_Call):
    """Each layer's weights and last grads, binned on fixed ranges, as a JSON string."""

    method = "histograms"


class Info(_Call):
    """``{device, per_epoch, train, test, params}``."""

    method = "info"


class Save(_Call):
    """Write a checkpoint to ``path``, recording ``step``. Yields the path."""

    method = "save"

    def __init__(self, path: StrArg, step: IntArg) -> None:
        super().__init__(path, step)


class Load(_Call):
    """Restore from the checkpoint at ``path``. Yields its step, 0 when there is none."""

    method = "load"

    def __init__(self, path: StrArg) -> None:
        super().__init__(path)
