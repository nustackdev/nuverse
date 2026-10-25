"""The Planes ``+`` creates, one module each.

Every module defines ``PLANE``, a :class:`~nuspace.PlaneSpec`: data, seeded as is
when created.

Nothing here imports a plane. A plane's cells import from their own module,
and importing this package pulled in every other one with it, on whichever
thread loaded first. :func:`nuverse.extension` gathers the specs.
"""
