"""Test: a generation's rows are saved in batches, with ids as before."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel import Session, col, create_engine, select

from seachange import EA, Archive, EAOperation, Individual, Population
from seachange.individual import save_genotypes, save_individuals
from tests.ea_helpers import double_pop, make_ind, make_pop, noop

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


def test_archive_draws_join_a_new_run_alive_and_newborn(
    tmp_path: Path,
) -> None:
    """Dead draws of a late generation are alive and born at the start."""
    old = tmp_path / "old.db"
    with EA(make_pop(SIZE), [noop], db_file_path=old, quiet=True) as ea:
        ea.current_generation = 50
        for ind in ea.population:
            ind.alive = False
        ea._commit()  # ruff: ignore[private-member-access]  # dead rows to draw
    with Archive(old) as archive:
        drawn = archive.random_population(2, only_dead=True).to_list()
    assert [(ind.alive, ind.time_of_birth) for ind in drawn] == [
        (False, 0),
        (False, 0),
    ]
    with EA(
        Population(drawn), [noop], db_file_path=tmp_path / "new.db", quiet=True
    ) as ea:
        ea.current_generation = 3
        ea.fetch_population()
        assert len(ea.population) == 2  # ruff: ignore[magic-value-comparison]
    rows = _stored_rows(tmp_path / "new.db")
    assert [(r.alive, r.time_of_birth, r.time_of_death) for r in rows] == [
        (True, 0, 0),
        (True, 0, 0),
    ]


def _dead_draws(path: Path, count: int) -> list[Individual]:
    # Individuals that died in generation 5 of a finished run at path
    with EA(make_pop(SIZE), [noop], db_file_path=path, quiet=True) as ea:
        ea.current_generation = 5
        for ind in ea.population:
            ind.alive = False
        ea._commit()  # ruff: ignore[private-member-access]  # dead rows to draw
    with Archive(path) as archive:
        return archive.random_population(count, only_dead=True).to_list()


def test_a_draw_given_a_new_genotype_still_starts_alive(
    tmp_path: Path,
) -> None:
    """Draw, mutate, seed: a new genotype does not hide where it came from."""
    (draw,) = _dead_draws(tmp_path / "old.db", 1)
    draw.genotype = [99.0]
    EA(
        Population([draw]), [noop], db_file_path=tmp_path / "new.db", quiet=True
    ).close()
    (row,) = _stored_rows(tmp_path / "new.db")
    assert (row.alive, row.time_of_birth) == (True, 0)
    with Archive(tmp_path / "new.db") as archive:
        (stored,) = archive.random_population(1)
        assert stored.genotype == [99.0]


def test_a_draw_an_operation_adds_dead_stays_dead(tmp_path: Path) -> None:
    """Only a seeding draw is revived; an operation's choice stands."""
    (draw,) = _dead_draws(tmp_path / "old.db", 1)

    @EAOperation
    def add_dead(population: Population) -> Population:
        draw.alive = False
        return Population([*population, draw])

    with EA(
        make_pop(1),
        [add_dead],
        db_file_path=tmp_path / "new.db",
        num_steps=1,
        quiet=True,
    ) as ea:
        ea.step()
    rows = _stored_rows(tmp_path / "new.db")
    assert [(r.id, r.alive, r.time_of_birth) for r in rows] == [
        (1, True, 0),
        (2, False, 1),
    ]


def test_a_draw_from_a_replaced_file_refuses_to_read(tmp_path: Path) -> None:
    """A run written over the file later makes the draw's genotype fail."""
    path = tmp_path / "run.db"
    (draw,) = _dead_draws(path, 1)
    EA(make_pop(SIZE), [noop], db_file_path=path, quiet=True).close()
    with pytest.raises(ValueError, match="another run has replaced"):
        _ = draw.genotype


def test_a_draw_from_a_deleted_file_names_the_file(tmp_path: Path) -> None:
    """Reading a genotype whose file is gone says which file it was."""
    path = tmp_path / "run.db"
    (draw,) = _dead_draws(path, 1)
    path.unlink()
    with pytest.raises(FileNotFoundError, match="which no longer exists"):
        _ = draw.genotype


def test_archive_draws_survive_a_new_run_replacing_their_file(
    tmp_path: Path,
) -> None:
    """A run written over the archive's own file reads the genotypes first."""
    path = tmp_path / "run.db"
    EA(make_pop(SIZE), [noop], db_file_path=path, quiet=True).close()
    with Archive(path) as archive:
        drawn = archive.random_population(2).to_list()
    with Archive(path) as archive:
        expected = sorted(
            repr(ind.genotype) for ind in archive.random_population(SIZE)
        )
    with EA(Population(drawn), [noop], db_file_path=path, quiet=True):
        pass
    with Archive(path) as archive:
        stored = [repr(ind.genotype) for ind in archive.random_population(2)]
    assert set(stored) <= set(expected)
    assert len(stored) == 2  # ruff: ignore[magic-value-comparison]


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


def _fail_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # save_genotypes does its work, then the commit fails, as a failed
    # COMMIT would
    real = save_genotypes

    def save_then_fail(
        connection: Connection,
        individuals: list[Individual],
        moved: list[Individual],
    ) -> None:
        real(connection, individuals, moved)
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr("seachange.ea.save_genotypes", save_then_fail)


def test_a_failed_commit_saves_the_genotypes_at_the_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A genotype is marked saved only once its commit succeeds."""
    with EA(
        make_pop(1), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ) as ea:
        child = make_ind(7)
        ea.population = Population([*ea.population, child])
        _fail_after(monkeypatch)
        with pytest.raises(OSError, match="disk full"):
            ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        monkeypatch.undo()
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
    with Archive(tmp_path / "run.db") as archive:
        stored = sorted(
            repr(ind.genotype) for ind in archive.random_population(2)
        )
    assert stored == ["[0.0]", "[7.0]"]


def test_a_failed_commit_keeps_the_genotypes_it_would_drop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """keep_genotypes drops a genotype from memory only once committed."""
    with EA(
        make_pop(2),
        [noop],
        db_file_path=tmp_path / "run.db",
        keep_genotypes=[],
        quiet=True,
    ) as ea:
        dying = ea.population[0]
        dying.alive = False
        _fail_after(monkeypatch)
        with pytest.raises(OSError, match="disk full"):
            ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        assert dying.genotype == [0.0]
        monkeypatch.undo()
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
        with pytest.raises(ValueError, match="was not kept"):
            _ = dying.genotype


def test_individuals_of_one_run_are_saved_into_another(
    tmp_path: Path,
) -> None:
    """Saved by run A, put in run B: B stores them as new rows."""
    with EA(
        make_pop(2), [noop], db_file_path=tmp_path / "a.db", quiet=True
    ) as first:
        moved = first.population.to_list()
    with EA(
        Population([make_ind(9), *moved]),
        [noop],
        db_file_path=tmp_path / "b.db",
        quiet=True,
    ) as second:
        assert [ind.id for ind in second.population] == [1, 2, 3]
    with Archive(tmp_path / "b.db") as archive:
        stored = sorted(
            repr(ind.genotype) for ind in archive.random_population(3)
        )
    assert stored == ["[0.0]", "[1.0]", "[9.0]"]
    assert _ids(tmp_path / "a.db") == [1, 2]


def test_a_fetched_row_stays_in_its_own_run(tmp_path: Path) -> None:
    """A run's own rows are updated, not copied, after a fetch."""
    with EA(
        make_pop(2), [noop], db_file_path=tmp_path / "run.db", quiet=True
    ) as ea:
        ea.fetch_population()
        ea.population[0].tags = {"seen": True}
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
    rows = _stored_rows(tmp_path / "run.db")
    assert [(r.id, r.tags) for r in rows] == [(1, {"seen": True}), (2, {})]


def test_a_draw_whose_genotype_was_dropped_says_where(tmp_path: Path) -> None:
    """The error of a dropped genotype names the run it was drawn from."""
    old = tmp_path / "old.db"
    with EA(
        make_pop(SIZE), [noop], db_file_path=old, keep_genotypes=[], quiet=True
    ) as ea:
        for ind in ea.population:
            ind.alive = False
        ea._commit()  # ruff: ignore[private-member-access]  # dead rows to draw
    with Archive(old) as archive:
        (draw,) = archive.random_population(1, only_dead=True)
    with EA(
        Population([draw]), [noop], db_file_path=tmp_path / "new.db", quiet=True
    ):
        pass
    with (
        Archive(tmp_path / "new.db") as archive,
        pytest.raises(ValueError, match="the run it was drawn from"),
    ):
        _ = archive.random_population(1)[0].genotype


def test_a_child_retired_at_birth_keeps_no_genotype(tmp_path: Path) -> None:
    """keep_genotypes drops a genotype that was never stored, too."""
    with EA(
        make_pop(2),
        [noop],
        db_file_path=tmp_path / "run.db",
        keep_genotypes=["best"],
        quiet=True,
    ) as ea:
        stillborn = make_ind(-5)
        stillborn.alive = False
        ea.population = Population([*ea.population, stillborn])
        ea._commit()  # ruff: ignore[private-member-access]  # the commit under test
    with closing(sqlite3.connect(tmp_path / "run.db")) as connection:
        kept = connection.execute(
            "SELECT individual_id FROM genotype ORDER BY individual_id"
        ).fetchall()
    assert kept == [(1,), (2,)]


def test_a_failed_commit_leaves_a_moved_individual_in_its_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Moving to another run happens only when that run's commit succeeds."""
    with EA(
        make_pop(1), [noop], db_file_path=tmp_path / "a.db", quiet=True
    ) as first:
        (ind,) = first.population
    with EA(
        make_pop(1), [noop], db_file_path=tmp_path / "b.db", quiet=True
    ) as second:
        second.population = Population([*second.population, ind])
        _fail_after(monkeypatch)
        with pytest.raises(OSError, match="disk full"):
            second._commit()  # ruff: ignore[private-member-access]  # the commit under test
        monkeypatch.undo()
    assert (ind.id, ind.time_of_birth) == (1, 0)
    first.population = Population([ind])
    first.current_generation = 1
    first._commit()  # ruff: ignore[private-member-access]  # back in its own run
    assert _ids(tmp_path / "a.db") == [1]
    first.close()
