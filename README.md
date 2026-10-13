# nuverse

Extensions for [nuspace](https://github.com/nustackdev/nuspace): the Planes `+` creates and the snippets `/` inserts. One repo, many packages, each its own distribution.

| Package | What |
| --- | --- |
| [nuverse](pkgs/nuverse) | std: the Planes and snippets every space ships with. `pip install nuspace` pulls it |
| [nuverse-demos](pkgs/nuverse-demos) | The Nu demos as Planes: a counter, a sampled series, a film base, MNIST trained live, a live meme market, Claude Code agents |

`nuverse` is std and has no suffix. Everything else is `nuverse-<name>`, installed when you want it:

```
pip install nuverse-demos
```

nuspace finds every package through the `nuspace.extensions` entry point. You never import one yourself.

## Layout

```
nuverse/
  pkgs/
    nuverse/        std, import name nuverse
    nuverse-demos/  import name nuverse_demos
  tests/
    _lib/_support/  shared harness, on sys.path for spawned workers too
    nuverse/        one directory per package
    nuverse_demos/
```

## Develop

Checked out beside `nuspace` and `nu`, which the workspace installs editable:

```
~/Projects/nustackdev/{nu,nuspace,nuverse}
make sync
make test
```

A new package: `pkgs/nuverse-<name>/` with its own `pyproject.toml` and a `nuspace.extensions` entry point, plus `tests/nuverse_<name>/`.

## Release

Each package ships on its own tag, `<dist>@X.Y.Z`. See `.github/workflows/publish.yml`.

## License

Apache-2.0.
