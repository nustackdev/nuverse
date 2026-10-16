"""The interactions: what a Nu program asks the :class:`~.trainer.Trainer` or :class:`~.reader.Reader` it provides.

Each reads the resource bound on the Context by ``nu.Provide`` and calls
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
- :class:`Checkpoint` and :class:`Restore`: everything to resume from, as bytes, and back. Restore yields the step.
- :class:`Weights`: the model alone, as bytes, for reading digits with.

The reader's, over a :class:`~.reader.Reader`:

- :class:`Holds`: whether a model is loaded under a key, using it when it is.
- :class:`Use`: load stored weights under a key and use them.
- :class:`Classify`: a 28x28 field of pixels read: ``{digit, probs, model}``.
- :class:`MnistDigit`: a random MNIST test digit: ``{pixels, label}``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, ClassVar

from nu.lang import ScalarQuery

from .reader import Reader
from .trainer import Trainer


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import BytesArg, FloatArg, IntArg, ListArg, StrArg
    from nu.lang.runtime import Runtime


__all__ = [
    "Checkpoint",
    "Classify",
    "Digits",
    "Evaluate",
    "Histograms",
    "Holds",
    "Info",
    "MnistDigit",
    "Predict",
    "Restore",
    "TrainChunk",
    "Use",
    "Weights",
]


class _Call(ScalarQuery):
    """Calls :attr:`method` on the bound :attr:`resource` with the children's values, off-thread."""

    resource: ClassVar[type] = Trainer
    method: ClassVar[str] = ""

    def _compile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        resource, method = self.resource, self.method

        def thunk(rt: Runtime) -> object:
            held = rt.ctx.fabrics.get(resource)
            return getattr(held, method)(*(c(rt) for c in children))

        return thunk

    def _acompile(self, nid: int, children: tuple[Callable, ...]) -> Callable:
        resource, method = self.resource, self.method

        async def athunk(rt: Runtime) -> object:
            held = rt.ctx.fabrics.get(resource)
            args = [await c(rt) for c in children]
            return await asyncio.to_thread(getattr(held, method), *args)

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


class Checkpoint(_Call):
    """Everything to resume from at ``step``, as bytes."""

    method = "checkpoint"

    def __init__(self, step: IntArg) -> None:
        super().__init__(step)


class Weights(_Call):
    """The model alone at ``step``, as bytes."""

    method = "weights"

    def __init__(self, step: IntArg) -> None:
        super().__init__(step)


class Restore(_Call):
    """Resume from a :class:`Checkpoint`'s bytes. Yields its step, 0 for no bytes."""

    method = "restore"

    def __init__(self, blob: BytesArg) -> None:
        super().__init__(blob)


# --- the reader --------------------------------------------------------------------------------


class _Read(_Call):
    resource = Reader


class Holds(_Read):
    """Whether the reader has the model stored under ``key`` loaded. Uses it when it has."""

    method = "holds"

    def __init__(self, key: StrArg) -> None:
        super().__init__(key)


class Use(_Read):
    """Load ``blob``, stored weights or a whole checkpoint, under ``key`` and use it. Yields the key, ``""`` for no bytes."""

    method = "use"

    def __init__(self, key: StrArg, blob: BytesArg) -> None:
        super().__init__(key, blob)


class Classify(_Read):
    """What the model in use reads in a 28x28 field of pixels in 0..1: ``{digit, probs, model}``, ``{}`` for none."""

    method = "classify"

    def __init__(self, image: ListArg) -> None:
        super().__init__(image)


class MnistDigit(_Read):
    """A random MNIST test digit, as is: ``{pixels, label}``."""

    method = "test_digit"
