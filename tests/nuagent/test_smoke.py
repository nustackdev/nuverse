import re
from pathlib import Path

import nuagent


PYPROJECT = Path(__file__).parents[2] / "pkgs" / "nuagent" / "pyproject.toml"


def test_version_matches_pyproject():
    declared = re.search(r'^version = "([^"]+)"', PYPROJECT.read_text(), re.M)
    assert declared is not None
    assert nuagent.__version__ == declared.group(1)


def test_subpackages_import():
    import nuagent.core
    import nuagent.presets.backends
    import nuagent.presets.store
    import nuagent.protocol  # noqa: F401
