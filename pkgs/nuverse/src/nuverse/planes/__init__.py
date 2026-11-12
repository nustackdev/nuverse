"""The Planes ``+`` creates, one module each.

Every module defines ``PLANE``, a :class:`~nuspace.specs.PlaneSpec`: data, seeded as is
when created.

Nothing here imports a plane. A plane's cells import from their own module,
and importing this package pulled in every other one with it, on whichever
thread loaded first. :func:`nuverse.extension` gathers the specs.

A system plane's cells are shims (:func:`shim`): the code lives in its
module, and the stored prog only names it, so a fix ships with the package
and reaches every plane already made.
"""

from __future__ import annotations


__all__ = ["shim"]


def shim(module: str, fn: str) -> str:
    """A cell's prog: ``nuverse.planes.<module>.<fn>(plane)`` on the running page. A plain string."""
    return f"from nuverse.planes import {module}\n\n\ndef out(plane):\n    return {module}.{fn}(plane)\n"
