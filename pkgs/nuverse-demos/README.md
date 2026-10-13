# nuverse-demos

The Nu demos as [nuspace](https://github.com/nustackdev/nuspace) Planes `+` creates, under Demos:

- **Counter**: a count ticking once a second, kept in its cell's state.
- **Sampled**: a series that grows forever, charted from a reservoir sample.
- **Movies**: a film base where every film and person is its own live page.
- **MNIST**: train a small CNN, steer it while it trains, and track every run. Needs the `mnist` extra.
- **Nu demos**: all three at once, nested under one plane.

```
pip install nuverse-demos
```

nuspace finds it on install through the `nuspace.extensions` entry point. You don't import it yourself.

## MNIST

Launch picks the knobs (optimizer, learning rate, batch size, channels, epochs, dropout) and starts a run: a page, and a headless job under it that trains in its own process. A run page shows the curves, twelve test digits and what the model reads in each, and every layer's weights and gradients over training. Drag the learning rate while it trains, stop it, resume it. Compare lines the runs up. Read puts a run's model to work: pick a run and its latest or best checkpoint, draw a digit, and it reads it on every stroke, showing the 28x28 image the model sees. Pick a run that is still training, or just launch one (the page follows the newest run until you pick), and the same drawing is read again as each checkpoint lands.

Nu owns the loop, torch owns the step: the job cell is a Nu loop over a trainer resource, reading its learning rate from state each chunk. Close the space mid run and open it again: the run carries on from its last checkpoint.

Models live in the space, not in files: each run keeps its latest checkpoint (what it resumes from) and the weights at its best test score, in its own state.

```
pip install "nuverse-demos[mnist]"
```

MNIST downloads once, on the first run, into `~/.cache/nuverse-mnist` (`$NUVERSE_MNIST_DATA` to move it). Runs train on cuda, or mps on Apple silicon, else the cpu (`$NUVERSE_MNIST_DEVICE` to pick). Three epochs take about a minute on a laptop cpu.
