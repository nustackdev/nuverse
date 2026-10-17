<div align="center">
  <h1>nulog</h1>
  <h3>Fast, serverless logger built on <a href="https://github.com/nustackdev/nu">Nu</a>, for infinite-scale streams</h3>

  [![Powered by Nu](https://img.shields.io/badge/powered%20by-Nu-5865F2)](https://github.com/nustackdev/nu)
  [![PyPI - Python Version](https://img.shields.io/badge/python-%3E%3D%203.10-blue)](https://pypi.org/project/nulog/)
  [![PyPI Package](https://img.shields.io/pypi/v/nulog?color=yellow)](https://pypi.org/project/nulog/)
</div>

<br/>

- Append-only logs and metric series in one library.
- Serverless and in-process: no daemon, no extra service to run.
- Billions of entries per stream, reads stay fast at any size.
- Watch any store live from a [nuspace](https://github.com/nustackdev/nuspace) space: one Log plane per store, as many as you like.

## Installation

Requires Python 3.10+.

```bash
pip install nulog            # the logger
pip install "nulog[space]"   # and the Log planes, to watch it in nuspace
```

## Usage

Two flavors of the same store, pick whichever fits the call site. A store is a RocksDB directory on disk.

### Plain Python

```python
import nulog

log = nulog.init("logs.db")  # `with nulog.init("logs.db") as log:` works too.

log.info("server started", stream="app", extra={"port": 8080})
log.warning("cache miss", stream="app", extra={"key": "user:42"})
log.error("request failed", stream="app", extra={"path": "/checkout"})
log.observe("cpu_load", 0.42)

print(log.tail("app", 3))
print(log.sample("cpu_load", 10))

log.close()
```

### Native Nu

```python
import nu, nustd, nulog

app = nulog.getLogger("app")

tree = nu.With(
    nulog.store("logs.db"),
    body=nustd.kv.Transaction(
        app.info("server started", extra={"port": 8080})
        >> app.warning("cache miss", extra={"key": "user:42"})
        >> app.error("request failed", extra={"path": "/checkout"})
        >> nulog.observe("cpu_load", 0.42),
    )
    >> nustd.kv.Snapshot(nu.print("tail:", nulog.messages.tail("app", 3)))
    >> nustd.kv.Snapshot(nu.print("cpu:", nulog.metrics.sample("cpu_load", 10))),
)

nu.run(tree)
```

Read atoms both flavors expose:

- Messages: `tail(stream, n)`, `slice(stream, start, stop, step=1)`.
- Metrics: `range(name, begin_us, end_us)`, `sample(name, n, begin_us=None, end_us=None)`.

Log rows: `{"ts_us": int, "level": str, "msg": str, "fields": dict}`.
Metric rows: `{"ts_us": int, "ts": float, "value": float}`.

## Watch it live

Install `nulog[space]` and open a space: **Log** shows under **+**. Each Log plane reads one store, set on its own **Config** plane, so one space can watch many stores side by side.

| Plane | What |
| --- | --- |
| Log | Every stream with its newest entry, every series with its latest point |
| Messages | One stream, newest or oldest first, filtered by level and text. Click a row to see the entry whole |
| Metrics | One series over a window, charted from a kh57 sample: the same cost at a thousand points or a billion |
| Config | The store's path, how often to read it, how much. A save takes effect at once, no restart |

The planes open the store read only, as a RocksDB secondary, so they are safe on a store your program is still writing. See [examples/nu_live.py](examples/nu_live.py) for a program that keeps writing one.
