"""Test: files from before codecs, and files stored with a user codec."""

import json
import sqlite3
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

import pytest

from seachange import EA, Archive, Individual, Population, register_codec
from seachange import codecs as codecs_module
from tests.ea_helpers import noop
from tests.test_codecs import FrozensetCodec

pytestmark = pytest.mark.usefixtures("dispose_engines")

# The table as seachange wrote it before codecs, and as ARIEL writes it:
# genotype_ is a JSON column holding JSON text
OLD_TABLE = """
CREATE TABLE individual (
    id INTEGER NOT NULL,
    alive BOOLEAN NOT NULL,
    time_of_birth INTEGER NOT NULL,
    time_of_death INTEGER NOT NULL,
    requires_eval BOOLEAN NOT NULL,
    fitness_ FLOAT,
    requires_init BOOLEAN NOT NULL,
    genotype_ JSON,
    tags_ JSON,
    PRIMARY KEY (id)
)
"""
OLD_GENOTYPES = [[0.5, 1.5], {"w": [1, 2]}, [[1, 2], [3, 4]]]


def _old_database(path: Path) -> Path:
    # One generation of three living individuals, written as before codecs
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(OLD_TABLE)
        for row_id, genotype in enumerate(OLD_GENOTYPES, start=1):
            connection.execute(
                "INSERT INTO individual VALUES (?, 1, 0, 0, 0, ?, 0, ?, ?)",
                (row_id, float(row_id), json.dumps(genotype), "{}"),
            )
        connection.commit()
    return path


def _sorted_json(genotypes: Sequence[object]) -> list[str]:
    # Genotypes of mixed shape, comparable regardless of order
    return sorted(json.dumps(genotype) for genotype in genotypes)


def test_a_database_from_before_codecs_opens_in_archive(tmp_path: Path) -> None:
    """JSON text genotypes read back equal through Archive."""
    db = _old_database(tmp_path / "old.db")
    with Archive(db) as archive:
        best = archive.hall_of_fame(3, direction="max")
    assert _sorted_json([i.genotype for i in best]) == _sorted_json(
        OLD_GENOTYPES
    )


def test_a_database_from_before_codecs_restarts(tmp_path: Path) -> None:
    """A restart from an old file continues with equal genotypes."""
    db = _old_database(tmp_path / "old.db")
    with EA.restart(
        db, [noop], db_file_path=tmp_path / "new.db", quiet=True
    ) as ea:
        restarted = [i.genotype for i in ea.population]
    assert _sorted_json(restarted) == _sorted_json(OLD_GENOTYPES)


@pytest.fixture
def frozenset_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Store a run with FrozensetCodec, then unregister the codec.

    Returns
    -------
    Path
        The run's database file.
    """
    monkeypatch.setattr(codecs_module, "_registered", [])
    register_codec(FrozensetCodec())
    individual = Individual()
    individual.genotype_ = frozenset({"a", "b"})
    individual.requires_init = False
    individual.fitness = 1.0
    db = tmp_path / "run.db"
    with EA(Population([individual]), [noop], db_file_path=db, quiet=True):
        pass
    # A new program that reads the file starts without the user codec
    monkeypatch.setattr(codecs_module, "_registered", [])
    return db


def test_a_user_codec_must_be_registered_to_read(frozenset_run: Path) -> None:
    """Without the codec, reading the genotype names it and its row."""
    with Archive(frozenset_run) as archive:
        stored = archive.random_individual()
    with pytest.raises(
        ValueError, match=r"row 1 .* no codec named 'frozenset'"
    ):
        _ = stored.genotype


def test_a_registered_user_codec_reads_its_file(frozenset_run: Path) -> None:
    """Registering the codec again reads the genotype back equal."""
    register_codec(FrozensetCodec())
    with Archive(frozenset_run) as archive:
        stored = archive.random_individual()
    assert stored.genotype_ == frozenset({"a", "b"})
