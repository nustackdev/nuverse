"""Content Cells: views and editors over content items (:mod:`nuverse.contents`).

A single item editor (text, inputs) edits its own cell's ``value`` item by
default, and its Config can point it at another item of its kind, so two
editors can edit one item. :mod:`.item`, :mod:`.items` and
:mod:`.item_picker` show, list and link items of any kind; :mod:`.table`
edits a cell's rows. What they share lives in :mod:`._editing`.
"""
