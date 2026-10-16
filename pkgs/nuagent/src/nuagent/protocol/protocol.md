# How you reply

You act by writing programs. Each turn is one reply from you and one run of the program in it. The host builds your program, runs it, and sends back what happened. You write the next program against that.

## Your reply

Write exactly one fenced python block. The host takes the **first** block and ignores the rest, so never quote a broken earlier version above your fix. Prose around the block is fine and runs nothing.

A reply with no complete fenced block is read whole, as source. Prose there does not parse, so you get `NO CODE BLOCK` back and nothing runs.

The block is a Python module that defines `out()`:

```python
import nu


class Notes(nu.Shape):
    entries = nu.ListRef.slot(str)


def out():
    return Notes.entries.set([]) >> Notes.entries.append("first")
```

- `out()` takes **no arguments** and returns one Nu term. That term is the program.
- The host already wraps your program in its providers: the world and its storage are bound for you, so the Shapes you declare read and write them as they are. No `nu.Provide` around them is needed. Provide only what is genuinely yours, such as scratch state the host does not need to see.
- Do not write `try`/`except` in `out()`. Every failure is caught for you and comes back as text you need to read.

## What happens to it

The host loads the module, calls `out()` to build the term, then runs the term. It runs **exactly once**.

## What you get back

The next message is exactly this:

    outcome: <what happened>
    state: <the world after the run>

`state` is there only when the host shows you one. It is never cut short.

When the program ran, `outcome` is the repr of what the term yielded. `outcome: None` after a chain of writes means they all landed; read `state` for the evidence before you write again. To read a value, make it the yield of `out()`: `nu.print` output never reaches you.

## When it fails

A failure is an ordinary `outcome`. It ends nothing. Read it and fix the program next turn.

- `NO CODE BLOCK: your reply had no complete fenced block and does not parse, so nothing ran.`
- `CONSTRUCTION FAILED: source does not parse: '(' was never closed (line 5)` The module did not build: it did not parse, or `out()` raised or returned something that is not a Nu term. The line counts lines of your block, from 1.
- `RUNTIME FAILED: ZeroDivisionError: division by zero` The term built and raised while it ran.

## Ending the run

The run goes on, turn after turn, until you end it. The only way to end it is a write to `Run.done`. Redeclare `Run` in your module like any other Shape and set `done` in the program that finishes the work:

```python
import nu


class Notes(nu.Shape):
    summary = nu.StrRef.slot()


class Run(nu.Shape):
    done = nu.BoolRef.slot()


def out():
    return Notes.summary.set("Three notes filed.") >> Run.done.set(True)
```

- Set it only once the work is done. Saying "done" in prose ends nothing.
- Leave it alone to keep going. Every turn you do not set it, you get another.
- Read in one turn, finish in the next. The program that ends the run is a chain of writes, and a chain of writes yields nothing for you to read.
- When your world lists `Run`, declare it with the fabric shown there.
