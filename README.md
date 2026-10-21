<div align="center">
  <img width="128" alt="nuverse" src="https://nustack.dev/brand/logo-square-512@2x.png" />
  <h1>
    nuverse - the nu ecosystem
  </h1>
  <p>Ready made spaces and extensions, one install away.</p>

  [![PyPI - Python Version](https://img.shields.io/badge/python-%3E%3D%203.10-blue)](https://pypi.org/project/nuverse/)
  [![PyPI Package](https://img.shields.io/pypi/v/nuverse?color=yellow)](https://pypi.org/project/nuverse/)
  [![License](https://img.shields.io/badge/License-Apache%202.0-orange.svg)](https://opensource.org/licenses/Apache-2.0)

  [![Discord](https://img.shields.io/badge/discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/tCa8YE7XVr)
  [![Twitter Follow](https://img.shields.io/twitter/follow/nustackdev?style=social)](https://twitter.com/nustackdev)

</div>

## About

nuverse is everything you can add to your [nuspace](https://github.com/nustackdev/nuspace): whole spaces to open and use, and the pieces your own spaces are built from.

- **Spaces**: full apps, ready to open. A movie tracker, a team of agents, a live meme market, a model you train and steer mid-run.
- **Extensions**: new kinds of planes and cells. Tables, charts, forms, sliders, jobs, workers.

Install a package and it shows up in your space, nothing to wire up. Build your own and it lives there like everything else.

| Package | What |
| --- | --- |
| [nuverse](pkgs/nuverse) | The everyday planes and cells: runs, jobs and workers planes; tables, lenses, tickers, inputs |
| [nudemos](pkgs/nudemos) | Ready made spaces: a tour, a counter, a film base, MNIST trained live, a live meme market, Claude Code agents |
| [nuagent](pkgs/nuagent) | Agents that answer in Nu: the loop, Claude Code and LLM backends, a Chat plane |
| [nulog](pkgs/nulog) | Serverless logger and metrics store, with Log planes to watch it live |

## Install

nuverse comes with nuspace. Every other package installs on its own and brings nuspace with it.

```bash
pip install nuspace          # a space, with nuverse's everyday planes and cells
pip install nudemos          # demos
pip install "nuagent[space,cc]"  # a Chat plane with LLMs and Claude Code support
pip install "nulog[space]"   # a logger, and planes to watch it
```

Then open one:

```bash
nuspace run --with nudemos.movies
```

`nuspace verse` lists every package installed and the planes it adds, each opened as `pkg.plane`.

## Community

- [Discord](https://discord.gg/tCa8YE7XVr) for questions and what you build
- [X @nustackdev](https://x.com/nustackdev) for releases and demos
- [Issues](https://github.com/nustackdev/nuverse/issues) for bugs and feature requests

## License

Apache-2.0. See [LICENSE.md](LICENSE.md).
