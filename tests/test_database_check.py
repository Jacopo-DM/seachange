"""Test: rows read back from a database file are checked as they load."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from seachange import EA, Archive
from tests.ea_helpers import make_pop, noop

pytestmark = pytest.mark.usefixtures("dispose_engines")


def _run_with_a_bad_row(
    tmp_path: Path, table: str, column: str, value: str | bytes | int
) -> Path:
    # A finished run whose second row was edited by another tool.
    db = tmp_path / "run.db"
    with EA(make_pop(3), [noop], db_file_path=db, quiet=True):
        pass
    key = "id" if table == "individual" else "individual_id"
    with closing(sqlite3.connect(db)) as connection:
        connection.execute(
            f"UPDATE {table} SET {column} = ? WHERE {key} = 2",  # ruff: ignore[hardcoded-sql-expression]  # names come from the test's own parameters
            (value,),
        )
        connection.commit()
    return db


def test_archive_refuses_a_bad_row(tmp_path: Path) -> None:
    """Both ways Archive loads rows name the bad row."""
    db = _run_with_a_bad_row(tmp_path, "individual", "fitness_", "high")
    with Archive(db) as archive:
        with pytest.raises(ValueError, match="row 2"):
            archive.hall_of_fame(3, direction="max")
        with pytest.raises(ValueError, match="row 2"):
            archive.random_population(3)


BAD_GENOTYPES = [
    '"oops"',
    b"numpy\0not an npy file",
    b"no codec name",
    b"torch\0...",
    7,
]


@pytest.mark.parametrize("value", BAD_GENOTYPES)
def test_archive_names_a_bad_genotype_when_it_is_read(
    tmp_path: Path, value: str | bytes | int
) -> None:
    """Archive reads a genotype when asked for it, and names its row."""
    db = _run_with_a_bad_row(tmp_path, "genotype", "data", value)
    with Archive(db) as archive:
        population = archive.random_population(3)
    with pytest.raises(ValueError, match="row 2 cannot be decoded"):
        _ = [individual.genotype for individual in population]


@pytest.mark.parametrize(
    ("table", "column", "value"),
    [
        ("individual", "fitness_", "high"),
        *(("genotype", "data", value) for value in BAD_GENOTYPES),
    ],
)
def test_restart_refuses_a_bad_row(
    tmp_path: Path, table: str, column: str, value: str | bytes | int
) -> None:
    """EA.restart names the bad row instead of starting from it."""
    db = _run_with_a_bad_row(tmp_path, table, column, value)
    with pytest.raises(ValueError, match="row 2"):
        EA.restart(db, [noop], db_file_path=tmp_path / "again.db", quiet=True)
