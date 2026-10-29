"""nuverse's cell and plane packages import nothing until asked.

A cell's prog imports one Cell or one plane module. When importing the
package pulled in every sibling with it, two cells loading on two threads met
inside the package's ``__init__`` and the import system raised a deadlock.
"""

from __future__ import annotations

import subprocess
import sys


def _loaded(code: str) -> list[str]:
    script = (
        "import sys\n"
        f"{code}\n"
        "print(sorted(m for m in sys.modules"
        " if m.startswith(('nuverse.cells.', 'nuverse.planes.', 'nuverse.contents.'))))\n"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60, check=True
    )
    return eval(done.stdout)  # noqa: S307 -- our own print of a list of names


def test_importing_the_packages_loads_no_member():
    assert _loaded("import nuverse.cells, nuverse.planes, nuverse.contents") == []


def test_a_cell_prog_loads_only_its_own_module():
    loaded = _loaded("from nuverse.cells.content.table import out")
    cells = [m for m in loaded if m.startswith("nuverse.cells.")]
    assert cells == ["nuverse.cells.content", "nuverse.cells.content.table"]
    # Its rows' kind, and the text kind whose word matching a row shares.
    kinds = [m for m in loaded if m.startswith("nuverse.contents.")]
    assert kinds == ["nuverse.contents.row", "nuverse.contents.text"]


def test_an_editor_loads_its_kind_and_what_editors_share():
    loaded = _loaded("from nuverse.cells.content.slider import out")
    assert [m for m in loaded if m.startswith(("nuverse.cells.", "nuverse.contents."))] == [
        "nuverse.cells.content",
        "nuverse.cells.content._editing",
        "nuverse.cells.content.slider",
        "nuverse.contents.number",
    ]


def test_the_extension_gathers_every_spec_in_order():
    import nuverse

    ext = nuverse.extension()
    assert [s.name for s in ext.cells][:3] == ["text", "table", "item"]
    assert ext.planes[0].name == "quickstart"
    assert [s.name for s in ext.contents] == ["Text", "Number", "Flag", "Date", "Row"]
