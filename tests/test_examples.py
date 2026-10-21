"""Run the scripts in examples/ so a change that breaks them fails here."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # runs a repo example with a fixed argv
import sys
from pathlib import Path

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_one_max_finds_all_ones(tmp_path: Path) -> None:
    """The README example reaches full fitness and writes only to cwd.

    A fresh interpreter gives the example its own seeded generator, and
    running it in ``tmp_path`` keeps its ``__data__/`` out of the repo.
    """
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # fixed argv, no outside input
        [sys.executable, str(EXAMPLES / "a1_one_max.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "best fitness 20.0 of 20" in result.stdout
    assert (tmp_path / "__data__" / "database.db").exists()
