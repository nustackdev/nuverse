"""The trainer: a small CNN on MNIST, held by a resource, stepped from outside.

:class:`Trainer` owns what torch owns: the model, the optimizer, the data in
memory and the random state. It never loops on its own. A Nu program
provides it with ``nu.Provide(Trainer, hparams, body)`` and steps it through
the interactions in :mod:`nuverse_demos.mnist.interactions`, a chunk of batches at
a time, so the loop, the logging, the steering and the stopping stay in Nu.

Everything here is plain sync Python. ``asetup`` and ``acleanup`` run the
blocking parts off the event loop, the way ``nustd.mp.MpWorker`` does, and
the interactions call every method off-thread too.

The data is MNIST through torchvision, downloaded once into
:func:`data_dir`. ``data="synthetic"`` swaps it for a few hundred random
images, for tests and for a machine with no network.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import math
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable

    import torch


__all__ = ["LAYERS", "Trainer", "checkpoint_dir", "data_dir", "pick_device"]


#: The layers whose weights and grads are binned, in model order.
LAYERS = ("conv1", "conv2", "fc1", "fc2")

#: MNIST's pixel mean and std, what the images are normalized by.
MEAN, STD = 0.1307, 0.3081

#: Bins per histogram.
BINS = 32


def data_dir() -> Path:
    """Where MNIST is cached: ``$NUVERSE_MNIST_DATA``, else ``~/.cache/nuverse-mnist``."""
    return Path(os.environ.get("NUVERSE_MNIST_DATA") or Path.home() / ".cache" / "nuverse-mnist")


def checkpoint_dir() -> Path:
    """Where runs keep their checkpoints: ``checkpoints`` under :func:`data_dir`."""
    return data_dir() / "checkpoints"


def pick_device(asked: str = "auto") -> str:
    """``asked``, or for ``auto`` the first of cuda, mps and cpu this machine has.

    An Intel Mac's mps (an AMD GPU) runs this small net at half the cpu's
    pace, so ``auto`` takes mps on Apple silicon only.
    ``$NUVERSE_MNIST_DEVICE`` overrides ``auto``.
    """
    import platform

    import torch

    asked = asked if asked != "auto" else os.environ.get("NUVERSE_MNIST_DEVICE", "auto")
    if asked != "auto":
        return asked
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available() and platform.machine() == "arm64":
        return "mps"
    return "cpu"


def _model(channels: int, dropout: float) -> torch.nn.Module:
    """Two conv blocks and two dense layers, named as :data:`LAYERS`."""
    from collections import OrderedDict

    from torch import nn

    c = channels
    return nn.Sequential(
        OrderedDict(
            conv1=nn.Conv2d(1, c, 3, padding=1),
            act1=nn.ReLU(),
            pool1=nn.MaxPool2d(2),
            conv2=nn.Conv2d(c, 2 * c, 3, padding=1),
            act2=nn.ReLU(),
            pool2=nn.MaxPool2d(2),
            flat=nn.Flatten(),
            drop1=nn.Dropout(dropout),
            fc1=nn.Linear(2 * c * 49, 128),
            act3=nn.ReLU(),
            drop2=nn.Dropout(dropout),
            fc2=nn.Linear(128, 10),
        )
    )


def _optimizer(name: str, params: Iterable[torch.nn.Parameter], lr: float) -> torch.optim.Optimizer:
    import torch

    if name == "sgd":
        return torch.optim.SGD(params, lr=lr, momentum=0.9)
    if name == "adamw":
        return torch.optim.AdamW(params, lr=lr, weight_decay=0.01)
    return torch.optim.Adam(params, lr=lr)


#: The ink a sample digit is drawn in: a blue that reads on a dark ground and a light one.
INK = (96, 140, 255)


def _png(image: torch.Tensor, scale: int = 4) -> str:
    """A 28x28 grey image as a ``data:`` PNG: :data:`INK` on clear, scaled up with hard pixel edges."""
    import torch
    from PIL import Image

    alpha = Image.fromarray((image.clamp(0, 1) * 255).to(dtype=torch.uint8).cpu().numpy(), mode="L")
    img = Image.new("RGBA", alpha.size, (*INK, 0))
    img.putalpha(alpha)
    img = img.resize((28 * scale, 28 * scale), Image.NEAREST)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class Trainer:
    """A CNN, its optimizer and MNIST in memory, stepped a chunk at a time.

    Args:
        lr: The learning rate it starts with. Every :meth:`train` call may
            pass another.
        batch_size: Images per step.
        channels: Filters in the first conv layer, twice that in the second.
        dropout: Dropout before each dense layer.
        optimizer: ``adam``, ``adamw`` or ``sgd`` (with momentum).
        seed: Seeds the init, the batches and the pick of sample digits.
        data: ``mnist``, or ``synthetic`` for random images (tests).
        samples: How many fixed test digits :meth:`predict` reports on.
        device: ``auto`` (see :func:`pick_device`), ``cpu``, ``mps`` or ``cuda``.
    """

    def __init__(
        self,
        *,
        lr: float = 1e-3,
        batch_size: int = 64,
        channels: int = 16,
        dropout: float = 0.25,
        optimizer: str = "adam",
        seed: int = 0,
        data: str = "mnist",
        samples: int = 12,
        device: str = "auto",
        **_: object,
    ) -> None:
        self.hp = {
            "lr": float(lr),
            "batch_size": int(batch_size),
            "channels": int(channels),
            "dropout": float(dropout),
            "optimizer": str(optimizer),
            "seed": int(seed),
        }
        self.data = data
        self.n_samples = int(samples)
        self.asked_device = device
        self.ranges: dict[str, float] = {}
        self.steps = 0

    # -- lifecycle -----------------------------------------------------------------

    def setup(self, ctx: object = None) -> None:
        """Load the data into memory and build the model and the optimizer."""
        import torch

        torch.manual_seed(self.hp["seed"])
        self.device = pick_device(self.asked_device)
        self.gen = torch.Generator().manual_seed(self.hp["seed"])
        (self.x, self.y), (self.tx, self.ty) = self._load()
        self.model = _model(self.hp["channels"], self.hp["dropout"]).to(self.device)
        self.opt = _optimizer(self.hp["optimizer"], self.model.parameters(), self.hp["lr"])
        self.x, self.y = self.x.to(self.device), self.y.to(self.device)
        self.tx, self.ty = self.tx.to(self.device), self.ty.to(self.device)
        picks = torch.randperm(len(self.ty), generator=self.gen)[: self.n_samples]
        self.picks = picks.to(self.device)

    def cleanup(self) -> None:
        """Let the model and the data go."""
        for name in ("model", "opt", "x", "y", "tx", "ty"):
            self.__dict__.pop(name, None)

    async def asetup(self, ctx: object = None) -> None:
        """Async lifecycle: :meth:`setup` off-thread."""
        await asyncio.to_thread(self.setup, ctx)

    async def acleanup(self) -> None:
        """Async lifecycle: :meth:`cleanup` off-thread."""
        await asyncio.to_thread(self.cleanup)

    def _load(self) -> tuple[tuple[torch.Tensor, torch.Tensor], tuple[torch.Tensor, torch.Tensor]]:
        import torch

        if self.data == "synthetic":
            g = torch.Generator().manual_seed(1)
            x = torch.rand(256, 1, 28, 28, generator=g)
            y = torch.randint(0, 10, (256,), generator=g)
            return (x[:192], y[:192]), (x[192:], y[192:])
        from torchvision import datasets

        root = str(data_dir())
        train = datasets.MNIST(root, train=True, download=True)
        test = datasets.MNIST(root, train=False, download=True)

        def norm(ds: datasets.MNIST) -> tuple[torch.Tensor, torch.Tensor]:
            return (ds.data.float() / 255.0).unsqueeze(1), ds.targets.clone()

        return norm(train), norm(test)

    # -- facts ---------------------------------------------------------------------

    @property
    def per_epoch(self) -> int:
        """Steps in one pass over the training set."""
        return math.ceil(len(self.y) / self.hp["batch_size"])

    def info(self) -> dict:
        """What a run shows before its first step: device, sizes, parameter count."""
        params = sum(p.numel() for p in self.model.parameters())
        return {
            "device": self.device,
            "per_epoch": self.per_epoch,
            "train": len(self.y),
            "test": len(self.ty),
            "params": params,
        }

    # -- steps ---------------------------------------------------------------------

    def train(self, n: int, lr: float | None = None) -> dict:
        """Run ``n`` steps at ``lr`` (or the current one): the chunk's mean loss and accuracy, ``{loss, acc, steps, seconds, lr}``."""
        import torch
        from torch.nn import functional

        if lr is not None and lr > 0:
            for group in self.opt.param_groups:
                group["lr"] = float(lr)
        self.model.train()
        started = time.perf_counter()
        losses, right, seen = 0.0, 0, 0
        for _ in range(int(n)):
            idx = torch.randint(0, len(self.y), (self.hp["batch_size"],), generator=self.gen)
            idx = idx.to(self.device)
            x, y = (self.x[idx] - MEAN) / STD, self.y[idx]
            logits = self.model(x)
            loss = functional.cross_entropy(logits, y)
            self.opt.zero_grad(set_to_none=True)
            loss.backward()
            self.opt.step()
            losses += loss.detach() * len(y)
            right += (logits.argmax(1) == y).sum()
            seen += len(y)
        self.steps += int(n)
        seconds = time.perf_counter() - started
        return {
            "loss": float(losses) / max(seen, 1),
            "acc": float(right) / max(seen, 1),
            "steps": int(n),
            "seconds": seconds,
            "lr": self.opt.param_groups[0]["lr"],
        }

    def evaluate(self, limit: int = 0) -> dict:
        """Loss and accuracy on the test set, its first ``limit`` images when given."""
        import torch
        from torch.nn import functional

        self.model.eval()
        n = len(self.ty) if not limit else min(int(limit), len(self.ty))
        loss, right = 0.0, 0
        with torch.no_grad():
            for i in range(0, n, 1000):
                x, y = (self.tx[i : min(i + 1000, n)] - MEAN) / STD, self.ty[i : min(i + 1000, n)]
                logits = self.model(x)
                loss += float(functional.cross_entropy(logits, y, reduction="sum"))
                right += int((logits.argmax(1) == y).sum())
        return {"loss": loss / max(n, 1), "acc": right / max(n, 1)}

    def digits(self) -> list[dict]:
        """The fixed sample digits: each as a ``data:`` PNG and its true label."""
        return [{"src": _png(self.tx[i, 0]), "label": int(self.ty[i])} for i in self.picks.tolist()]

    def predict(self) -> list[list]:
        """Per sample digit: the predicted label, its probability, and all ten probabilities."""
        import torch

        self.model.eval()
        with torch.no_grad():
            probs = torch.softmax(self.model((self.tx[self.picks] - MEAN) / STD), 1).cpu()
        conf, pred = probs.max(1)
        return [
            [int(p), round(float(c), 4), [round(float(v), 3) for v in row]]
            for p, c, row in zip(pred, conf, probs, strict=True)
        ]

    def histograms(self) -> str:
        """Each layer's weights and last grads binned, as JSON: ``{layer: {w, g, wr, gr}}``.

        A layer's bins span a fixed range, worked out at the first call and
        kept, so the bins of every call line up as rows of one heatmap.
        """
        import torch

        out = {}
        for name in LAYERS:
            layer = getattr(self.model, name)
            w = layer.weight.detach().float().cpu().flatten()
            wr = self.ranges.setdefault(name + ".w", 2.0 * float(w.abs().max()) or 1.0)
            # Before the first step there are no grads: an empty row, and no range fixed from it.
            g = layer.weight.grad
            if g is None:
                gr, gs = self.ranges.get(name + ".g", 1e-3), [0] * BINS
            else:
                g = g.detach().float().cpu().flatten()
                gr = self.ranges.setdefault(name + ".g", 4.0 * float(g.std()) or 1e-3)
                gs = torch.histc(g.clamp(-gr, gr), BINS, -gr, gr).int().tolist()
            out[name] = {
                "w": torch.histc(w.clamp(-wr, wr), BINS, -wr, wr).int().tolist(),
                "g": gs,
                "wr": wr,
                "gr": gr,
            }
        return json.dumps(out)

    # -- checkpoints ---------------------------------------------------------------

    def save(self, path: str, step: int) -> str:
        """Model, optimizer, random state and histogram ranges to ``path``, at ``step``."""
        import torch

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        tmp = path + ".tmp"
        torch.save(
            {
                "model": self.model.state_dict(),
                "opt": self.opt.state_dict(),
                "gen": self.gen.get_state(),
                "ranges": self.ranges,
                "step": int(step),
            },
            tmp,
        )
        Path(tmp).replace(path)
        return path

    def load(self, path: str) -> int:
        """Restore from ``path``. The step it was saved at, 0 when there is no file."""
        import torch

        if not path or not Path(path).exists():
            return 0
        saved = torch.load(path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(saved["model"])
        self.opt.load_state_dict(saved["opt"])
        self.gen.set_state(saved["gen"])
        self.ranges = dict(saved.get("ranges") or {})
        self.steps = int(saved["step"])
        return self.steps
