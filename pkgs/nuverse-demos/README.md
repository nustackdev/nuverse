# nuverse-demos

The Nu demos as [nuspace](https://github.com/nustackdev/nuspace) Planes `+` creates, under Demos:

- **Counter**: a count ticking once a second, kept in its cell's state.
- **Sampled**: a series that grows forever, charted from a reservoir sample.
- **Movies**: a shelf where every movie is a cell, and a cell that writes them.
- **Nu demos**: all three at once, nested under one plane.

```
pip install nuverse-demos
```

nuspace finds it on install through the `nuspace.extensions` entry point. You don't import it yourself.
