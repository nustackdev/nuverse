"""The content kinds nuverse ships: the primitives any cell keeps its findable data in.

One module each: a schema Shape, its :class:`nuspace.Content`, named on the
class as the class is less ``Content``, and ``CONTENT``, the
:class:`nuspace.ContentSpec` it registers with as ``nuverse.<name>``, eg
``nuverse.Text``. The store keys by that, never by the module.

- :mod:`.text`: :class:`~.text.TextContent`, a string, found by its words.
- :mod:`.number`: :class:`~.number.NumberContent`, a float, found within bounds.
- :mod:`.flag`: :class:`~.flag.FlagContent`, an on or off.
- :mod:`.date`: :class:`~.date.DateContent`, a day, found within bounds.
- :mod:`.row`: :class:`~.row.RowContent`, a table row, found by the words in its cells.

Nothing here imports a kind: a cell's prog imports only the kinds its Cell
keeps. :func:`nuverse.extension` gathers the specs.
"""
