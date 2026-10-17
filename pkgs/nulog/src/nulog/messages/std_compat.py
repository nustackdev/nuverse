"""Tree rewrites that swap ``nustd.logging`` atoms for persistent ``nulog`` writes.

:func:`from_std_logging` walks a Nu tree and replaces every
``nustd.logging.Log`` with the equivalent persistent-write subtree.
App code stays written in ``nustd.logging`` style -- ``log.info(...)`` -- and the
*deployment* picks whether logs go to Python's ``logging`` (default -- no
rewrite) or persist into nulog (wrap the tree in :func:`from_std_logging`).

Usage::

    import nustd
    import nulog

    log = nustd.logging.getLogger("app")

    body = (
        log.info("started")
        >> log.warning("slow: %s ms", latency)
        >> log.error("failed", extra={"code": 500})
    )

    tree = nu.With(nulog.store("logs.db"), body=nustd.kv.Transaction(nulog.from_std_logging(body)))
    nu.run(tree)  # every log.* call now persists
"""

from __future__ import annotations

from typing import cast

import nu
import nustd

from .ops import append


__all__ = [
    "from_std_logging",
]


def _literal_value(term: nu.Nu) -> object | nu.Nu:
    """Return the Python value if ``term`` is a ``Literal``, else the term."""
    if isinstance(term, nu.Literal):
        return term._payload.get("value")
    return term


def from_std_logging(tree: nu.Nu) -> nu.Nu:
    """Swap every ``nustd.logging.Log`` in ``tree`` for a persistent write.

    Bottom-up walk. Preserves everything that isn't a ``Log``: other
    atoms, structure, sequence, retries, brackets. The rewritten site
    expects a ``nulog.store(...)`` bracket in scope on the Context.
    """

    def _rewrite(node: nu.Nu) -> nu.Nu:
        if not isinstance(node, nustd.logging.Log):
            return node

        # Log children: [LOGGING, level, logger, msg, *args].
        # Slot 0 is the fabric ref -- dropped by the persistent path.
        children = cast("tuple[nu.Nu, ...]", node._children)
        level = _literal_value(children[1])
        stream = _literal_value(children[2])
        msg: object | nu.Nu = _literal_value(children[3])
        args: tuple[nu.Nu, ...] = tuple(children[4:])
        extra = cast("dict[str, object] | None", node._payload.get("extra")) or None

        return append(stream, level, msg, args, extra)

    return nu.tree.map_nodes(tree, _rewrite, order="bottom_up")
