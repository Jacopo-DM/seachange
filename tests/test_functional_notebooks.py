"""Hold the coverage table in tests/functional/README.md to the package.

Every public module of seachange has a row, and every notebook a row names
exists. The notebooks themselves run through ``tools/run_notebooks.py``.
"""

import pkgutil
import re
from pathlib import Path

import seachange

FUNCTIONAL = Path(__file__).parent / "functional"
ROW = re.compile(r"^\| `(?P<module>\w+)` \|.*\| (?P<notebook>[^|]+?) \|$")
NONE_YET = "none yet"


def table_rows() -> dict[str, str]:
    """Read the coverage table.

    Returns
    -------
    dict[str, str]
        Each module named in the table, with its notebook cell.
    """
    text = (FUNCTIONAL / "README.md").read_text(encoding="utf-8")
    matches = (ROW.match(line) for line in text.splitlines())
    return {m["module"]: m["notebook"] for m in matches if m is not None}


def test_every_public_module_has_a_row() -> None:
    """A public module missing from the table fails, and so does a stale row."""
    public = {
        module.name
        for module in pkgutil.iter_modules(seachange.__path__)
        if not module.name.startswith("_")
    }
    assert set(table_rows()) == public


def test_every_named_notebook_exists() -> None:
    """A row names a notebook in tests/functional, or says none yet."""
    for notebook in table_rows().values():
        name = notebook.strip("[]()").split("](")[0]
        assert notebook == NONE_YET or (FUNCTIONAL / name).is_file(), notebook
