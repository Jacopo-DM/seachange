"""Run the scripts in examples/ so a change that breaks them fails here."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # runs a repo example with a fixed argv
import sys
from pathlib import Path

EXAMPLES = Path(__file__).parent.parent / "examples"
# The numpy example must cut its error by at least a third
ERROR_KEPT_AT_MOST = 2 / 3


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


def test_revde_demo_prints_three_children(tmp_path: Path) -> None:
    """The RevDE demo mutates three parents into three children."""
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # fixed argv, no outside input
        [sys.executable, str(EXAMPLES / "a2_revde.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert [line.split(":")[0] for line in result.stdout.splitlines()] == [
        "parent 0",
        "parent 1",
        "parent 2",
        "child 0",
        "child 1",
        "child 2",
    ]


def test_numpy_example_lowers_the_error_and_keeps_float32(
    tmp_path: Path,
) -> None:
    """The numpy example improves and reads its genotype back as float32."""
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # fixed argv, no outside input
        [sys.executable, str(EXAMPLES / "a3_numpy_genotypes.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.splitlines()
    # "error 1.274 -> 0.804" on Linux; compared loosely, as float32 sums
    # may differ in the last bits on other platforms
    start, end = (float(word) for word in lines[-2].split()[1::2])
    assert end < start * ERROR_KEPT_AT_MOST
    assert lines[-1] == "stored genotype: float32 (100,)"
    assert (tmp_path / "__data__" / "numpy.db").exists()
