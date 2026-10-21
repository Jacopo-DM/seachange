"""Test: rows read back from a database file are checked as they load."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from seachange import EA, Archive
from tests.ea_helpers import make_pop, noop

pytestmark = pytest.mark.usefixtures("dispose_engines")


def _run_with_a_bad_row(tmp_path: Path, column: str, value: str) -> Path:
    # A finished run whose second row was edited by another tool.
    db = tmp_path / "run.db"
    with EA(make_pop(3), [noop], db_file_path=db, quiet=True):
        pass
    with closing(sqlite3.connect(db)) as connection:
        connection.execute(
            f"UPDATE individual SET {column} = ? WHERE id = 2",  # ruff: ignore[hardcoded-sql-expression]  # column comes from the test's own parameters
            (value,),
        )
        connection.commit()
    return db


@pytest.mark.parametrize(
    ("column", "value"), [("fitness_", "high"), ("genotype_", '"oops"')]
)
def test_archive_refuses_a_bad_row(
    tmp_path: Path, column: str, value: str
) -> None:
    """Both ways Archive loads rows name the bad row."""
    db = _run_with_a_bad_row(tmp_path, column, value)
    with Archive(db) as archive:
        with pytest.raises(ValueError, match="row 2"):
            archive.hall_of_fame(3, direction="max")
        with pytest.raises(ValueError, match="row 2"):
            archive.random_population(3)


def test_restart_refuses_a_bad_row(tmp_path: Path) -> None:
    """EA.restart names the bad row instead of starting from it."""
    db = _run_with_a_bad_row(tmp_path, "fitness_", "high")
    with pytest.raises(ValueError, match="row 2"):
        EA.restart(db, [noop], db_file_path=tmp_path / "again.db", quiet=True)
