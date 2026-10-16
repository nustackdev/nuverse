"""The model's program: taken out of the reply, built, run once, and told as an outcome.

Two terms, both evaluated inside the turn. A Python helper here would be a
hole in the tree, and a tree with a hole runs nowhere but the host process.

**Extract** takes the first fenced block. A model correcting itself quotes
the broken version first, and a model adding an illustration puts it last,
so neither choice is always right. First is the safer one: re-reading broken
code costs a turn, running an illustration does something nobody asked for.
A reply with no complete block is used whole, which is right for bare source
and wrong for prose. Extract cannot tell the two apart. Attempt can.

**Attempt** builds the program with ``LoadNu`` and runs it with ``Eval``,
once. The store's ``rewrite`` lands the built term on the world (on kv it
brackets it), and the yield is read out as plain data and repr'd inside that
landing, while the store is still open. Its own yield is the outcome record, and the error type picks the branch
that writes it: a ``ConstructionError`` is ``construct`` (or ``no_code``,
when the reply had no fence to begin with), anything else ``runtime``.
Nothing downstream reads labels out of text. The repr sits inside the inner
catch, so a failure is never repr'd and never arrives quoted.

A failure is the model's input, not the loop's crash. Source that builds and
then raises is as much the model's mistake as source that does not parse,
so both are caught and both become the next thing it reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import nu
import nu.prog
from nu.domains.shape.interactions import Extract
from nuagent.protocol import CONSTRUCT, NO_CODE, OK, RUNTIME


if TYPE_CHECKING:
    from collections.abc import Callable

    from nu.lang import Nu, StrArg


__all__ = ["FENCE", "Shown", "attempt", "extract", "fenced"]


#: What opens and closes a block. Code sits at the odd indices of the split.
FENCE = "```"


def fenced(reply: StrArg) -> Nu:
    """Whether the reply holds a complete block: a Bool term, three chunks or more."""
    return nu.Str(reply).split(FENCE).len() >= 3


def extract(reply: StrArg) -> Nu:
    """The source in the reply's first fenced block, or the whole reply when there is none.

    Args:
        reply: the model's text, a str or any Str-yielding term.

    Returns:
        A ``Str`` term: the block's body with its ``python``/``py`` tag gone,
        stripped. Fewer than three chunks means no complete block, and then
        it is the reply itself, stripped.
    """
    text = nu.Str(reply)
    chunks = text.split(FENCE)
    block = nu.Str(chunks[1]).removeprefix("python").removeprefix("py").strip()
    return nu.Str(nu.If(fenced(reply), block, text.strip()))


class Shown:
    """A ``LoadNu`` rewrite: the program's yield as plain data, repr'd, then landed.

    A class rather than a closure so a load carrying it pickles.

    Args:
        landing: the store's ``rewrite``. None leaves the term where it is.

    Notes:
        - The repr sits inside the landing, so a kv view the program yields
          is read out while its bracket is open. Outside it, a view is a
          lazy handle and its repr says nothing.
    """

    __slots__ = ("landing",)

    def __init__(self, landing: Callable[[Nu], Nu] | None = None) -> None:
        self.landing = landing

    def __call__(self, term: Nu) -> Nu:
        """The term's yield, materialised and repr'd, on the world."""
        shown = nu.Repr(Extract(term))
        return shown if self.landing is None else self.landing(shown)


def attempt(
    program: Nu, *, reply: StrArg | None = None, rewrite: Callable[[Nu], Nu] | None = None
) -> Nu:
    """Build the program, run it once, and yield what happened as an outcome record.

    Args:
        program: the source, a ``ProgramRef`` or any Str-yielding term.
        reply: the raw reply the source came from. Given, a construction
            failure on a reply with no complete fence is ``no_code``, so a
            model is never handed a parser error about its own English.
        rewrite: the store's ``rewrite``, applied to the built term before
            it runs. Omitted, the term runs as it was built.

    Returns:
        A dict term, one of:
        ``{kind: ok, value}``, ``{kind: no_code}``,
        ``{kind: construct, message, line}`` (``line`` is None when the
        failure has no source position), ``{kind: runtime, message}``.
    """
    ran = nu.Dict.of(kind=OK, value=nu.Eval(nu.LoadNu(program, rewrite=Shown(rewrite))))

    def built(err: Nu) -> Nu:
        """The construction failure, off the Diagnostic the error carries."""
        diagnostic = err.exception.diagnostic
        failed = nu.Dict.of(kind=CONSTRUCT, message=diagnostic.message, line=diagnostic.lineno)
        if reply is None:
            return failed
        return nu.If(fenced(reply), failed, nu.Dict.of(kind=NO_CODE))

    def raised(err: Nu) -> Nu:
        """The runtime failure: the error's type, then its text."""
        typed = nu.Str(nu.GetAttr(nu.Type(err.exception), "__name__"))
        return nu.Dict.of(kind=RUNTIME, message=typed + ": " + err)

    return nu.TryCatch(
        nu.TryCatch(ran, catch=built, errors=nu.prog.ConstructionError),
        catch=raised,
    )
