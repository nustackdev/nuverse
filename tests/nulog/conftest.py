"""Shared test fixtures.

The ``ctx`` fixture builds an in-memory nulog store and binds a
:class:`nu.Context` on it -- same shape as nu's own tests. Each test does
its writes with ``nu.run(nustd.kv.Transaction(cmd), ctx)`` and its reads with
``nu.run(nustd.kv.Snapshot(read_atom), ctx)[0]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from virtuals import Navigator

import nu
import nustd


if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def ctx() -> Generator[nu.Context, None, None]:
    """A fresh in-memory Context bound to a nulog store (per-test isolation).

    Binds both the ``Navigator`` (nustd.kv: persistent messages + metrics) and
    a plain ``dict`` (nustd.mem: transient viewer state).
    """
    with nustd.kv.memory_storage() as storage:
        yield (nu.Context().bind(Navigator, Navigator(storage)).bind(dict, {}))
