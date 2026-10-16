"""Backends behind one interface, a conversation in and text out.

Each is its own module with one class that satisfies
:class:`nuagent.core.Backend`, imported by name so a run pays only for the
backend it uses, and the core imports none of them:

- :mod:`.cc`: Claude Code, stateful. One session for the run, the newest
  message per turn (``nuagent[cc]``).
- :mod:`.llm`: an OpenAI-compatible chat endpoint, stateless. The whole
  conversation every turn (``nuagent[llm]``).
"""
