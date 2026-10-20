# nudemos

The Nu demos as [nuspace](https://github.com/nustackdev/nuspace) Planes `+` creates, under Demos:

- **Counter**: a count ticking once a second, kept in its cell's state.
- **Sampled**: a series that grows forever, charted from a reservoir sample.
- **Movies**: a film base where every film and person is its own live page.
- **MNIST**: train a small CNN, steer it while it trains, and track every run. Needs the `mnist` extra.
- **Memes**: a live terminal over the meme market on Solana: launches, trades and every coin's page, synced from public mainnet. Needs the `memes` extra.
- **Agents**: Claude Code sessions run, watched, steered and orchestrated from a space. One agent is one Claude Code session in a page, driven by a short Nu loop; fan-out with a judge, chains and task boards are a few lines of Nu each. Needs the `agents` extra and a logged-in `claude` CLI, no API key.
- **Design**: the nustack design system as one live spec: tokens, the mark, a component gallery, mocks and contrast checks all drawn from it, teammates proposing changes, and releases cut by a job that draws the assets. Needs the `design` extra.
- **Ops**: a storefront run from a space: a real HTTP server and shoppers, scheduled jobs, logs, deploys, incidents, runbooks and alert rules written in a few lines. Needs the `ops` extra.
- **Data**: a coffee roaster's books as live dashboards: orders streaming in, a million web events queried in milliseconds, exports loaded by a job, a forecast that follows every price. Needs the `data` extra.
- **Research**: an LLM research desk: real papers weighed against claims, our own small evals on Claude, and a probe that keeps asking. Needs the `research` extra and a logged-in `claude` CLI.
- **Knowledge**: a team wiki and handbook where pages query the base, facts are cited everywhere, meeting notes write themselves and Claude answers from the whole base. Needs the `knowledge` extra and a logged-in `claude` CLI.
- **Nu demos**: all three at once, nested under one plane.

```
pip install nudemos
```

nuspace finds it on install through the `nuspace.extensions` entry point. You don't import it yourself.

## MNIST

Launch picks the knobs (optimizer, learning rate, batch size, channels, epochs, dropout) and starts a run: a page, and a headless job under it that trains in its own process. A run page shows the curves, twelve test digits and what the model reads in each, and every layer's weights and gradients over training. Drag the learning rate while it trains, stop it, resume it. Compare lines the runs up. Read puts a run's model to work: pick a run and its latest or best checkpoint, draw a digit, and it reads it on every stroke, showing the 28x28 image the model sees. Pick a run that is still training, or just launch one (the page follows the newest run until you pick), and the same drawing is read again as each checkpoint lands.

Nu owns the loop, torch owns the step: the job cell is a Nu loop over a trainer resource, reading its learning rate from state each chunk. Close the space mid run and open it again: the run carries on from its last checkpoint.

Models live in the space, not in files: each run keeps its latest checkpoint (what it resumes from) and the weights at its best test score, in its own state.

```
pip install "nudemos[mnist]"
```

MNIST downloads once, on the first run, into `~/.cache/nuverse-mnist` (`$NUVERSE_MNIST_DATA` to move it). Runs train on cuda, or mps on Apple silicon, else the cpu (`$NUVERSE_MNIST_DEVICE` to pick). Three epochs take about a minute on a laptop cpu.
