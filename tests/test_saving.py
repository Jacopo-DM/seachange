"""Test: a generation's rows are saved in batches, with ids as before."""

from pathlib import Path

import pytest
from sqlmodel import Session, col, create_engine, select

from seachange import EA, Individual, Population
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
        pytest.raises(ValueError, match="not in this run's database"),
        engine.begin() as connection,
    ):
        save_individuals(connection, [stranger])
    engine.dispose()


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
