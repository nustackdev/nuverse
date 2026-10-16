"""Session memory as Shapes: mem for one-off runs, kv for durable ones.

Every store has the same slots under the same names, so the loop runs on
either unchanged:

- ``messages``: the conversation, ``{role, content}`` dicts.
- ``reply``: the latest reply, as the model sent it.
- ``program``: the source taken out of it.
- ``outcome``: how it went, ``{kind, value, message, line}``.

Each store is its own module with one class that satisfies
:class:`nuagent.core.Store` (its Shapes, its two brackets, and ``bound``),
imported by name (``nuagent.presets.store.mem``), so a run pays only for the
store it uses.
"""
