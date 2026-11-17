"""Media Cells: an image, a video, a sound or any file, dropped in place, a gallery of them, and a mic and a camera recording in place.

Each keeps what it shows as :class:`~nuverse.contents.file.FileContent`
items, the bytes in the space's blob store. The single file Cells share
:mod:`._media`; the mic and camera Cells, whose takes read as uploads,
share :mod:`._capture` on top of it.
"""
