"""nuverse-demos mnist: strokes made into a 28x28 digit, as MNIST made its digits.

The geometry tests are offline and quick. The quality test reads the
hand authored samples with a briefly trained model, and needs MNIST cached
in :func:`~nuverse_demos.mnist.trainer.data_dir`: it is skipped without it.
"""

from __future__ import annotations

import numpy as np
import pytest

from nuverse_demos.mnist.ink import BOX, SAMPLES, SIZE, sample, strokes_of, strokes_to_image
from nuverse_demos.mnist.trainer import MEAN, STD, Trainer, data_dir


def _field(strokes) -> np.ndarray:
    image = np.asarray(strokes_to_image(strokes))
    assert image.shape == (SIZE, SIZE)
    assert image.min() >= 0.0 and image.max() <= 1.0
    return image


def _mass(image: np.ndarray) -> tuple[float, float]:
    ys, xs = np.indices(image.shape)
    return float((ys * image).sum() / image.sum()), float((xs * image).sum() / image.sum())


def _ink(image: np.ndarray) -> tuple[int, int]:
    """Height and width of the ink's bounding box."""
    ys, xs = np.nonzero(image > 0.05)
    return int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)


def test_a_blank_pad_is_a_blank_field():
    assert not _field([]).any()
    assert not _field([[]]).any()


def test_the_ink_lands_centered_by_its_mass():
    # A seven drawn in the top left corner, off center: its mass comes out in the middle.
    seven = [[[0.05, 0.05], [0.3, 0.05], [0.12, 0.35]]]
    cy, cx = _mass(_field(seven))
    assert abs(cy - 13.5) <= 0.6
    assert abs(cx - 13.5) <= 0.6


def test_the_ink_is_scaled_to_fit_twenty_keeping_its_aspect():
    tall = _field([[[0.5, 0.1], [0.5, 0.9]]])
    h, w = _ink(tall)
    assert BOX - 1 <= h <= BOX
    assert w <= 6
    wide = _field([[[0.1, 0.5], [0.9, 0.5]]])
    h, w = _ink(wide)
    assert BOX - 1 <= w <= BOX
    assert h <= 6
    square = _field([[[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8], [0.2, 0.2]]])
    h, w = _ink(square)
    assert abs(h - w) <= 1 and h >= BOX - 1


def test_where_and_how_big_it_was_drawn_does_not_matter():
    _, strokes = sample(3, 0)

    def moved(scale: float, dx: float, dy: float):
        return [[[x * scale + dx, y * scale + dy] for x, y in s] for s in strokes]

    big = _field(moved(1.0, 0.0, 0.0))
    small = _field(moved(0.3, 0.6, 0.05))
    assert np.abs(big - small).mean() < 0.02


def test_the_stroke_weight_is_mnist_like():
    # MNIST's mean pixel is about 0.13: the brush is sized to land near it, whatever the size drawn.
    means = [float(_field(sample(d, s)[1]).mean()) for d in range(10) for s in range(3)]
    assert 0.09 < sum(means) / len(means) < 0.18


def test_a_dot_and_points_outside_are_safe():
    assert _field([[[0.5, 0.5]]]).max() > 0.5
    assert _field([[[0.5, 0.5], [0.5, 0.5]]]).max() > 0.5


def test_a_board_value_reads_as_its_paths_strokes():
    strokes = [[[0.1, 0.2], [0.3, 0.4]], [[0.5, 0.5]]]
    assert strokes_of(strokes) == strokes
    board = [
        {
            "type": "path",
            "points": [[0.1, 0.2, 0.7], [0.3, 0.4, 0.9]],
            "stroke": "#fff",
            "width": 3,
        },
        {"type": "rect", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
        {"type": "path", "points": [[0.5, 0.5]]},
        {"type": "path", "points": []},
    ]
    assert strokes_of(board) == strokes
    assert strokes_of(None) == [] and strokes_of([]) == []


def test_samples_stay_in_the_unit_box():
    for d in SAMPLES:
        digit, strokes = sample(d, 7)
        assert digit == d
        assert all(0.0 <= v <= 1.0 for s in strokes for p in s for v in p)


@pytest.mark.skipif(not (data_dir() / "MNIST" / "raw").exists(), reason="needs MNIST cached")
def test_a_trained_model_reads_the_drawn_samples():
    import torch

    trainer = Trainer(device="cpu", seed=0)
    trainer.setup()
    trainer.train(300, 1e-3)
    trainer.model.eval()
    drawn = [sample(i % 10, i) for i in range(300)]
    x = torch.tensor([strokes_to_image(s) for _, s in drawn]).unsqueeze(1)
    with torch.no_grad():
        read = trainer.model((x - MEAN) / STD).argmax(1).tolist()
    right = sum(r == d for r, (d, _) in zip(read, drawn, strict=True)) / len(drawn)
    print(f"drawn samples read right: {right:.3f}, test set: {trainer.evaluate()['acc']:.3f}")
    assert right >= 0.85
