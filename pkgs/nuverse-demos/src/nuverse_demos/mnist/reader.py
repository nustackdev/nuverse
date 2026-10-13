"""The reader: a run's stored weights, loaded once, reading digits. Held by a resource, like the trainer.

:class:`Reader` keeps a few models in memory, each under a key a Nu program
makes from the run, the slot and the step it was stored at
(``<job>/<slot>/<step>``). The program asks :meth:`Reader.holds` first and
reads the weights out of the run's state only when the reader does not have
them: a new step is a new key, so a run that stores a fresh checkpoint is
reloaded, and one that does not is never read twice. The bytes go from the
store to here and nowhere else.

Models load on the cpu in eval mode. Every method is plain sync Python, called
off-thread by the interactions in :mod:`.interactions`.

:meth:`Reader.test_digit` hands out MNIST test digits, as they are, for a
page to read without drawing.
"""

from __future__ import annotations

import random
from collections import OrderedDict
from typing import TYPE_CHECKING

from .trainer import MEAN, STD, _png, build, data_dir, load


if TYPE_CHECKING:
    import torch


__all__ = ["KEEP", "Reader", "image_png"]


#: Models a reader keeps loaded, newest used first.
KEEP = 4


def image_png(pixels: list | None) -> str:
    """A 28x28 field of pixels in 0..1 as a ``data:`` PNG, the way the run page draws its digits."""
    import torch

    if not pixels:
        pixels = [[0.0] * 28 for _ in range(28)]
    return _png(torch.tensor(pixels, dtype=torch.float32))


class Reader:
    """Models read out of runs' states, kept by key, and the one in use.

    Args:
        data: ``mnist``, or ``synthetic`` for random test digits (tests).
    """

    def __init__(self, *, data: str = "mnist", **_: object) -> None:
        self.data = data
        self.models: OrderedDict[str, torch.nn.Module] = OrderedDict()
        self.current = ""
        self.tests: tuple[torch.Tensor, torch.Tensor] | None = None
        self.loads = 0

    # -- lifecycle -----------------------------------------------------------------

    def setup(self, ctx: object = None) -> None:
        """Nothing up front: torch loads with the first model."""

    def cleanup(self) -> None:
        """Let the models and the test digits go."""
        self.models.clear()
        self.tests = None

    async def asetup(self, ctx: object = None) -> None:
        """Async lifecycle: :meth:`setup`."""
        self.setup(ctx)

    async def acleanup(self) -> None:
        """Async lifecycle: :meth:`cleanup`."""
        self.cleanup()

    # -- models --------------------------------------------------------------------

    def holds(self, key: str) -> bool:
        """Whether the model stored under ``key`` is loaded. Makes it the one in use when it is."""
        if key in self.models:
            self.models.move_to_end(key)
            self.current = key
            return True
        return False

    def use(self, key: str, blob: bytes) -> str:
        """Load ``blob`` (weights or a whole checkpoint) under ``key`` and use it. ``""`` for no bytes."""
        if not blob:
            self.current = ""
            return ""
        if not self.holds(key):
            saved = load(blob)
            arch = saved.get("arch") or {"channels": 16, "dropout": 0.25}
            model = build(int(arch["channels"]), float(arch["dropout"]))
            model.load_state_dict(saved["model"])
            model.eval()
            self.models[key] = model
            self.loads += 1
            while len(self.models) > KEEP:
                self.models.popitem(last=False)
            self.current = key
        return key

    def classify(self, pixels: list | None) -> dict:
        """What the model in use reads in a 28x28 field: ``{digit, probs, model}``, probs for 0 to 9.

        ``{}`` with no model in use, or a blank field.
        """
        import torch

        model = self.models.get(self.current)
        if model is None or not pixels or not any(any(row) for row in pixels):
            return {}
        x = torch.tensor(pixels, dtype=torch.float32).reshape(1, 1, 28, 28)
        with torch.no_grad():
            probs = torch.softmax(model((x - MEAN) / STD), 1)[0]
        return {
            "digit": int(probs.argmax()),
            "probs": [round(float(p), 4) for p in probs],
            "model": self.current,
        }

    # -- test digits ---------------------------------------------------------------

    def _tests(self) -> tuple[torch.Tensor, torch.Tensor]:
        import torch

        if self.tests is None:
            if self.data == "synthetic":
                g = torch.Generator().manual_seed(2)
                self.tests = (
                    torch.rand(64, 28, 28, generator=g),
                    torch.randint(0, 10, (64,), generator=g),
                )
            else:
                from torchvision import datasets

                test = datasets.MNIST(str(data_dir()), train=False, download=True)
                self.tests = test.data.float() / 255.0, test.targets.clone()
        return self.tests

    def test_digit(self, seed: int | None = None) -> dict:
        """A random MNIST test digit as is: ``{pixels, label}``."""
        x, y = self._tests()
        i = random.Random(seed).randrange(len(y))  # noqa: S311 - a pick, not a secret
        return {"pixels": [[round(float(v), 4) for v in row] for row in x[i]], "label": int(y[i])}
