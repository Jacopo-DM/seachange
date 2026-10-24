"""Test: a generation's rows are saved in batches, with ids as before."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, col, create_engine, select

from seachange import EA, Archive, Individual, Population
from seachange.individual import save_individuals
from tests.ea_helpers import double_pop, make_pop, noop

pytestmark = pytest.mark.usefixtures("dispose_engines")

SIZE = 4
# PRAGMA synchronous reports NORMAL as 1
NORMAL = 1


def _ids(path: Path) -> list[int | None]:
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as session:
        ids = list(
            session.exec(select(Individual.id).order_by(col(Individual.id)))
        )
    engine.dispose()
    return ids


def test_new_individuals_get_ids_in_population_order(tmp_path: Path) -> None:
    """The first population is 1 to n, each later child the next number."""
    population = make_pop(SIZE)
    with EA(
        population,
        [noop],
        db_file_path=tmp_path / "run.db",
        num_steps=1,
        quiet=True,
    ) as ea:
        assert [ind.id for ind in population] == list(range(1, SIZE + 1))
        ea.population = Population(
            ea.population.to_list() + make_pop(SIZE).to_list()
        )
        ea.current_generation += 1
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        assert [ind.id for ind in ea.population] == list(range(1, 2 * SIZE + 1))
    assert _ids(tmp_path / "run.db") == list(range(1, 2 * SIZE + 1))


def test_a_population_holding_one_individual_twice_saves_it_once(
    tmp_path: Path,
) -> None:
    """A doubled population still stores each individual once."""
    with EA(
        make_pop(SIZE),
        [double_pop],
        db_file_path=tmp_path / "run.db",
        num_steps=2,
        quiet=True,
    ) as ea:
        ea.run()
    assert _ids(tmp_path / "run.db") == list(range(1, SIZE + 1))


def _stored_rows(path: Path) -> list[Individual]:
    # Rows read back from a finished run, as the engine reads them
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as session:
        rows = list(
            session.exec(select(Individual).order_by(col(Individual.id)))
        )
    engine.dispose()
    return rows


def test_an_unchanged_stored_individual_writes_nothing(tmp_path: Path) -> None:
    """Saving rows nobody changed leaves the file as it was."""
    EA(
        make_pop(SIZE), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ).close()
    before = (tmp_path / "run.db").read_bytes()
    engine = create_engine(f"sqlite:///{tmp_path / 'run.db'}")
    with engine.begin() as connection:
        save_individuals(connection, _stored_rows(tmp_path / "run.db"))
    engine.dispose()
    assert (tmp_path / "run.db").read_bytes() == before


def test_a_row_from_another_file_is_refused(tmp_path: Path) -> None:
    """An individual read from one run cannot overwrite another's rows."""
    EA(
        make_pop(SIZE), [noop], db_file_path=tmp_path / "big.db", quiet=True
    ).close()
    EA(
        make_pop(1), [noop], db_file_path=tmp_path / "small.db", quiet=True
    ).close()
    stranger = _stored_rows(tmp_path / "big.db")[-1]
    stranger.alive = False
    engine = create_engine(f"sqlite:///{tmp_path / 'small.db'}")
    with (
        pytest.raises(StaleDataError, match="0 were matched"),
        engine.begin() as connection,
    ):
        save_individuals(connection, [stranger])
    engine.dispose()


def test_a_row_from_another_file_assigned_its_own_values_writes_nothing(
    tmp_path: Path,
) -> None:
    """Assigning a column the value it holds is no change, as in the ORM."""
    EA(
        make_pop(SIZE), [noop], db_file_path=tmp_path / "big.db", quiet=True
    ).close()
    EA(
        make_pop(1), [noop], db_file_path=tmp_path / "small.db", quiet=True
    ).close()
    stranger = _stored_rows(tmp_path / "big.db")[-1]
    stranger.time_of_death = stranger.time_of_death
    before = (tmp_path / "small.db").read_bytes()
    engine = create_engine(f"sqlite:///{tmp_path / 'small.db'}")
    with engine.begin() as connection:
        save_individuals(connection, [stranger])
    engine.dispose()
    assert (tmp_path / "small.db").read_bytes() == before


def test_a_dict_changed_in_place_after_a_save_is_not_saved(
    tmp_path: Path,
) -> None:
    """A save clears what SQLAlchemy saw assigned, so tags stay as saved."""
    with EA(
        make_pop(1), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ) as ea:
        (ind,) = ea.population
        ind.tags = {"a": 1}
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        ind.tags_["b"] = 2
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
    assert [row.tags for row in _stored_rows(tmp_path / "run.db")] == [{"a": 1}]


def test_a_changed_id_moves_the_row_and_overwrites_none(
    tmp_path: Path,
) -> None:
    """A stored individual given a taken id fails, as the ORM's UPDATE did."""
    with EA(
        make_pop(3), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ) as ea:
        last = ea.population[-1]
        last.id = 1
        last.tags = {"moved": True}
        with pytest.raises(IntegrityError, match="UNIQUE"):
            ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        last.id = 9
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
    rows = _stored_rows(tmp_path / "run.db")
    assert [(row.id, row.tags) for row in rows] == [
        (1, {}),
        (2, {}),
        (9, {"moved": True}),
    ]


def test_an_assignment_that_changed_nothing_is_cleared_by_a_save(
    tmp_path: Path,
) -> None:
    """After a save, a dict changed in place stays unsaved, as in the ORM."""
    with EA(
        make_pop(1), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ) as ea:
        (ind,) = ea.population
        ind.tags = {"a": 1}
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        ind.tags_ = {"a": 1}
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        ind.tags_["b"] = 2
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
    assert [row.tags for row in _stored_rows(tmp_path / "run.db")] == [{"a": 1}]


def test_one_row_held_twice_is_refused(tmp_path: Path) -> None:
    """Two objects for one stored row raise, as the ORM's session did."""
    with EA(
        make_pop(1), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ) as ea:
        (kept,) = ea.population
        ea.fetch_population()
        ea.population = Population([kept, *ea.population])
        with pytest.raises(InvalidRequestError, match="held twice"):
            ea._commit()  # ruff: ignore[private-member-access]  # the commit under test


def test_a_failed_commit_gives_new_individuals_their_ids_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """New individuals of a refused commit are new again, without ids."""
    with EA(
        make_pop(1), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ) as ea:
        fresh = make_pop(2).to_list()
        ea.population = Population([*ea.population, *fresh])

        def refuse(*_args: object) -> None:
            msg = "disk full"
            raise OSError(msg)

        monkeypatch.setattr("seachange.ea.save_genotypes", refuse)
        with pytest.raises(OSError, match="disk full"):
            ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        assert [ind.id for ind in fresh] == [None, None]
        monkeypatch.undo()
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        assert [ind.id for ind in fresh] == [2, 3]
    assert _ids(tmp_path / "run.db") == [1, 2, 3]


def test_archive_draws_are_saved_into_a_new_run_as_new_rows(
    tmp_path: Path,
) -> None:
    """Individuals from Archive get fresh ids and keep their genotypes."""
    EA(
        make_pop(SIZE), [noop], db_file_path=tmp_path / "old.db", quiet=True
    ).close()
    with Archive(tmp_path / "old.db") as archive:
        drawn = archive.random_population(2).to_list()
    genotypes = [ind.genotype for ind in drawn]
    with EA(
        Population([Individual(), *drawn]),
        [noop],
        db_file_path=tmp_path / "new.db",
        quiet=True,
    ):
        pass
    assert _ids(tmp_path / "new.db") == [1, 2, 3]
    with Archive(tmp_path / "new.db") as archive:
        stored = archive.random_population(3).to_list()
    assert sorted(map(repr, genotypes)) == sorted(
        repr(ind.genotype) for ind in stored if not ind.requires_init
    )


def test_a_closed_run_reads_in_a_read_only_folder(tmp_path: Path) -> None:
    """Closing leaves WAL mode, which needs a writable folder to read."""
    folder = tmp_path / "run"
    with EA(make_pop(SIZE), [noop], db_file_path=folder / "run.db", quiet=True):
        pass
    folder.chmod(0o555)
    try:
        with Archive(folder / "run.db") as archive:
            assert len(archive.random_population(2)) == 2  # ruff: ignore[magic-value-comparison]
    finally:
        folder.chmod(0o755)


def test_closing_a_run_while_it_is_read_keeps_it_in_wal_mode(
    tmp_path: Path,
) -> None:
    """close() neither fails nor waits while an Archive is reading."""
    path = tmp_path / "run.db"
    ea = EA(make_pop(SIZE), [noop], db_file_path=path, quiet=True)
    with Archive(path) as archive, archive.engine.connect() as reader:
        reader.exec_driver_sql("BEGIN")
        reader.exec_driver_sql("SELECT count(*) FROM individual").all()
        ea.close()
        reader.exec_driver_sql("ROLLBACK")
    with closing(sqlite3.connect(path)) as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()
    assert mode == ("wal",)


def test_closing_a_run_with_a_read_only_file_keeps_it_in_wal_mode(
    tmp_path: Path,
) -> None:
    """close() does not fail when it may not write the file."""
    path = tmp_path / "run.db"
    ea = EA(make_pop(SIZE), [noop], db_file_path=path, quiet=True)
    ea.engine.dispose()
    path.chmod(0o444)
    try:
        ea.close()
    finally:
        path.chmod(0o644)
    with closing(sqlite3.connect(path)) as connection:
        mode = connection.execute("PRAGMA journal_mode").fetchone()
    assert mode == ("wal",)


class _FailingConnection:
    # Stands in for sqlite3.Connection: its one statement fails
    @staticmethod
    def execute(_sql: str) -> None:
        msg = "disk I/O error"
        raise sqlite3.OperationalError(msg)

    def close(self) -> None:
        pass


def test_closing_a_run_raises_any_other_sqlite_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only a lock or a read-only file is passed over."""
    ea = EA(make_pop(1), [noop], db_file_path=tmp_path / "run.db", quiet=True)
    monkeypatch.setattr(
        "seachange.ea_database.sqlite3.connect",
        lambda *_a, **_k: _FailingConnection(),
    )
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        ea.close()
    monkeypatch.undo()
    ea.close()


def test_closing_a_run_whose_file_is_gone_does_nothing(
    tmp_path: Path,
) -> None:
    """close() creates no file where the run's file was removed."""
    path = tmp_path / "run.db"
    ea = EA(make_pop(1), [noop], db_file_path=path, quiet=True)
    ea.engine.dispose()
    path.unlink()
    ea.close()
    assert not path.exists()


def test_a_run_writes_ahead_without_waiting_for_the_disk(
    tmp_path: Path,
) -> None:
    """A run's connections use WAL with synchronous=NORMAL."""
    with (
        EA(
            make_pop(SIZE), [noop], db_file_path=tmp_path / "run.db", quiet=True
        ) as ea,
        ea.engine.connect() as connection,
    ):
        mode = connection.exec_driver_sql("PRAGMA journal_mode").scalar()
        sync = connection.exec_driver_sql("PRAGMA synchronous").scalar()
    assert (mode, sync) == ("wal", NORMAL)


def test_replacing_a_database_drops_its_old_journal(tmp_path: Path) -> None:
    """db_handling='delete' removes a live run's -wal with the file."""
    live = tmp_path / "live.db"
    path = tmp_path / "run.db"
    with EA(make_pop(3 * SIZE), [noop], db_file_path=live, quiet=True):
        # Copied while open: its rows are still in the -wal file
        for suffix in ("", "-wal", "-shm"):
            Path(f"{path}{suffix}").write_bytes(
                Path(f"{live}{suffix}").read_bytes()
            )
    EA(make_pop(SIZE), [noop], db_file_path=path, quiet=True).close()
    assert _ids(path) == list(range(1, SIZE + 1))
