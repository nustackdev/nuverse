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


def from_std_logging(tree: nu.Nu) -> nu.Nu:
    """Swap every ``nustd.logging.Log`` in ``tree`` for a persistent write.

    Bottom-up walk. Preserves everything that isn't a ``Log``: other
    atoms, structure, sequence, retries, brackets. The rewritten site
    expects a ``nulog.store(...)`` bracket in scope on the Context.
    """

    def _rewrite(node: nu.Nu) -> nu.Nu:
        if not isinstance(node, nustd.logging.Log):
            return node

        # Log children: [LOGGING, level, logger, msg, *args, extra].
        # Slot 0 is the fabric ref, dropped by the persistent path. Every
        # other child is carried over as a term and runs at write time:
        # never looked into. extra is always last, a DictOf or any Nu.
        children = cast("tuple[nu.Nu, ...]", node._children)
        level, stream, msg = children[1], children[2], children[3]
        args: tuple[nu.Nu, ...] = tuple(children[4:-1])
        return append(stream, level, msg, args, children[-1])

    return nu.tree.map_nodes(tree, _rewrite, order="bottom_up")
