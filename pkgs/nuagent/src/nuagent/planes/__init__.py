"""nuagent in a space: planes a person talks to an agent through.

Imports nuspace, so nothing in :mod:`nuagent` imports this: nuspace finds
it through the ``nuspace.extensions`` entry point (:func:`nuagent.extension`).

One conversation is two planes. The Chat page (:mod:`.chat`) is what a person
sees, run while a tab has it open: its cells are the conversation, a cell per
message and a cell per answer, the agent adding its answers itself
(:func:`answer`). Its engine (:mod:`.engine`), a headless
child, is what works: a reaction on its inbox runs it, it handles every
message past its cursor through the nuagent loop, and returns. Everything the
conversation is lives in the engine's plane state (:mod:`.state`), which the
loop reaches through :class:`~.store.SpaceStore`. The agent's backend is set
once for the space, in a Settings cell (:mod:`.settings`).

- :mod:`.ext`: the Chat plane spec, :data:`PLANE`.
- :mod:`.chat`, :mod:`.engine`, :mod:`.settings`: the cells' code, and the
  terms that drive a chat (:func:`~.chat.tell`, :func:`~.chat.stop`).
- :func:`answer`: what the agent's program calls to answer the person, a
  cell on the page.
- :mod:`.state`, :mod:`.store`: what a conversation keeps, and the loop's store over it.
"""

from __future__ import annotations

from .chat import answer
from .ext import PLANE


__all__ = ["PLANE", "answer"]
