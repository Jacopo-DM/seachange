"""Test: restarting an EA and its edge cases."""

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Literal, cast

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from seachange import (
    EA,
    Archive,
    DBHandlingMode,
    EAOperation,
    Individual,
    Population,
    config,
)
from tests.ea_helpers import (
    FIRST_GENERATION_ID,
    make_ea,
    make_pop,
    noop,
)

pytestmark = pytest.mark.usefixtures("dispose_engines")

RESTART_STEPS = 3
RESTART_GENERATION = 1
# retire_two over 2 generations: 6 start, 4 survive generation 1, 2 the end
RETIRE_POP_SIZE = 6
SURVIVORS_AFTER_FIRST = 4
SURVIVORS_AT_END = 2


def _finished_run(tmp_path: Path) -> Path:
    # Run a few generations and return the database that was written.
    ea = make_ea(tmp_path, num_steps=RESTART_STEPS)
    ea.run()
    return tmp_path / "test.db"


def _restart(
    tmp_path: Path,
    source: Path,
    *,
    generation: int | None = None,
    name: str = "restarted.db",
) -> EA:
    return EA.restart(
        source,
        [noop],
        generation=generation,
        db_file_path=tmp_path / name,
        quiet=True,
    )


def test_restart_continues_after_the_last_generation(tmp_path: Path) -> None:
    """Restarting from a path alone resumes after the latest generation."""
    source = _finished_run(tmp_path / "first")
    ea = _restart(tmp_path / "second", source)
    assert ea.current_generation >= RESTART_STEPS
    assert ea.size > 0


def test_restart_from_a_chosen_generation(tmp_path: Path) -> None:
    """generation= restarts from that generation."""
    source = _finished_run(tmp_path / "first")
    ea = _restart(tmp_path / "second", source, generation=RESTART_GENERATION)
    assert ea.current_generation == RESTART_GENERATION


def test_restart_from_a_string_path(tmp_path: Path) -> None:
    """A path may be given as a string."""
    source = _finished_run(tmp_path / "first")
    ea = EA.restart(
        str(source),
        [noop],
        db_file_path=tmp_path / "second" / "restarted.db",
        quiet=True,
    )
    assert ea.size > 0


def test_restart_database_must_exist(tmp_path: Path) -> None:
    """A missing source database is an error."""
    with pytest.raises(FileNotFoundError, match="Restart database not found"):
        _restart(tmp_path, tmp_path / "missing.db")


def test_restart_from_an_empty_database_fails(tmp_path: Path) -> None:
    """A database without individuals cannot be restarted from."""
    empty = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{empty}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()
    with pytest.raises(ValueError, match="contains no individuals"):
        _restart(tmp_path, empty)


def test_restart_from_a_generation_without_individuals(tmp_path: Path) -> None:
    """A generation that no evaluated individual lived through is an error."""
    source = _finished_run(tmp_path / "first")
    with pytest.raises(ValueError, match="No evaluated individuals"):
        _restart(tmp_path / "second", source, generation=RESTART_STEPS * 100)


def test_unknown_db_handling_keeps_the_existing_file(tmp_path: Path) -> None:
    """A handling mode that is neither delete nor halt changes nothing."""
    first = make_ea(tmp_path)
    del first
    second = EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=tmp_path / "test.db",
        db_handling=cast("DBHandlingMode", "keep"),
        quiet=True,
    )
    # Both populations are in the file: the old one was not deleted.
    assert second.size == 2 * len(make_pop())


def test_get_solution_with_an_unknown_mode_raises(tmp_path: Path) -> None:
    """A typo in the mode fails at once and names the valid modes."""
    ea = make_ea(tmp_path)
    mode = cast("Literal['best']", "bset")
    with pytest.raises(ValueError, match="'best', 'median' or 'worst'"):
        ea.get_solution(mode)


def test_fetch_population_can_include_dead_and_unevaluated(
    tmp_path: Path,
) -> None:
    """The filters of fetch_population are optional."""
    ea = make_ea(tmp_path)
    ea.fetch_population(only_alive=False, requires_eval=None)
    assert ea.population.size == len(make_pop())
    ea.fetch_population(only_alive=True, requires_eval=True)
    assert ea.population.size == 0


def test_restart_keeps_an_explicit_first_generation(tmp_path: Path) -> None:
    """first_generation_id overrides the generation derived from the restart."""
    source = _finished_run(tmp_path / "first")
    ea = EA.restart(
        source,
        [noop],
        db_file_path=tmp_path / "second" / "restarted.db",
        first_generation_id=FIRST_GENERATION_ID,
        quiet=True,
    )
    assert ea.current_generation == FIRST_GENERATION_ID


@pytest.mark.parametrize("db_handling", ["delete", "halt"])
def test_restart_onto_its_own_default_file_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_handling: DBHandlingMode,
) -> None:
    """Without db_file_path the default file is the source: refuse."""
    monkeypatch.chdir(tmp_path)
    run = _finished_run(tmp_path / "__data__")
    source = run.rename(config.db_file_path)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="same file"):
        EA.restart(
            source,
            [noop],
            db_handling=db_handling,
            quiet=True,
        )
    assert source.read_bytes() == before


def test_restart_onto_its_own_file_by_another_path_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative and an absolute path to the same file are caught."""
    source = _finished_run(tmp_path)
    before = source.read_bytes()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="same file"):
        EA.restart(
            source.name,
            [noop],
            db_file_path=source.resolve(),
            quiet=True,
        )
    assert source.read_bytes() == before


@EAOperation
def retire_two(population: Population) -> Population:
    # Mark the two lowest-fitness individuals dead each generation.
    for individual in population.sort(direction="min")[:2]:
        individual.alive = False
    return population


@pytest.mark.parametrize(
    ("generation", "survivors"),
    [(None, SURVIVORS_AT_END), (1, SURVIVORS_AFTER_FIRST)],
)
def test_restart_takes_only_the_survivors_of_the_generation(
    tmp_path: Path, generation: int | None, survivors: int
) -> None:
    """Individuals retired during the chosen generation stay out."""
    first = EA(
        make_pop(RETIRE_POP_SIZE),
        [retire_two],
        db_file_path=tmp_path / "first.db",
        num_steps=2,
        quiet=True,
    )
    first.run()
    ea = EA.restart(
        tmp_path / "first.db",
        [noop],
        generation=generation,
        db_file_path=tmp_path / "second.db",
        quiet=True,
    )
    assert ea.size == survivors


def test_restart_numbers_generations_as_the_source(tmp_path: Path) -> None:
    """A restart from g for n steps stores g's survivors as g, ends at g + n."""
    first = EA(
        make_pop(RETIRE_POP_SIZE),
        [retire_two],
        db_file_path=tmp_path / "first.db",
        num_steps=2,
        quiet=True,
    )
    first.run()
    with EA.restart(
        tmp_path / "first.db",
        [noop],
        generation=1,
        num_steps=2,
        db_file_path=tmp_path / "second.db",
        quiet=True,
    ) as ea:
        ea.run()
        assert ea.current_generation == 1 + 2
    with Archive(tmp_path / "second.db") as archive:
        assert archive.generation_range.last == 1 + 2


# Eight individuals, two retired in each of generations 1 and 2
SURVIVORS_AT_RESTART = 4


def _contents(archive: Archive, generation: int) -> list[tuple[float, str]]:
    # Fitness and genotype of everyone present, in a stable order
    return sorted(
        (ind.fitness, repr(ind.genotype))
        for ind in archive.by_generation(generation)
    )


def test_restart_copies_the_history_before_the_generation(
    tmp_path: Path,
) -> None:
    """The new file answers by_generation up to the restart as the source."""
    restart_from = 2
    first = EA(
        make_pop(RETIRE_POP_SIZE + 2),
        [retire_two],
        db_file_path=tmp_path / "first.db",
        num_steps=3,
        quiet=True,
    )
    first.run()
    first.close()
    with EA.restart(
        tmp_path / "first.db",
        [noop],
        generation=restart_from,
        db_file_path=tmp_path / "second.db",
        quiet=True,
    ) as restarted:
        # The copied history is retired: only the survivors carry on
        assert restarted.size == SURVIVORS_AT_RESTART
    with (
        Archive(tmp_path / "first.db") as source,
        Archive(tmp_path / "second.db") as copy,
    ):
        assert copy.generation_range.first == 0
        for generation in range(restart_from + 1):
            assert _contents(copy, generation) == _contents(source, generation)
        # All eight were born in generation 0, so all are copied
        assert copy.size == source.size


def _rows(path: Path) -> dict[int, Individual]:
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as session:
        rows = {ind.id: ind for ind in session.exec(select(Individual))}
    engine.dispose()
    return {key: row for key, row in rows.items() if key is not None}


def _genotype_bytes(path: Path) -> dict[int, bytes]:
    # The genotype table as stored: id to codec name and bytes
    with closing(sqlite3.connect(path)) as connection:
        return dict(
            connection.execute("SELECT individual_id, data FROM genotype")
        )


@EAOperation
def add_unevaluated_child(population: Population) -> Population:
    # One new child per generation, left for a later evaluation
    child = Individual()
    child.genotype = [0.5]
    population.append(child)
    return population


def test_restart_keeps_ids_and_caps_the_copied_lifetimes(
    tmp_path: Path,
) -> None:
    """Copied rows keep their ids; nobody copied lives past the restart."""
    restart_from = 1
    with EA(
        make_pop(RETIRE_POP_SIZE),
        [retire_two, add_unevaluated_child],
        db_file_path=tmp_path / "first.db",
        num_steps=3,
        quiet=True,
    ) as first:
        first.run()
    EA.restart(
        tmp_path / "first.db",
        [noop],
        generation=restart_from,
        db_file_path=tmp_path / "second.db",
        quiet=True,
    ).close()
    source = _rows(tmp_path / "first.db")
    copy = _rows(tmp_path / "second.db")
    born_by_then = {
        key for key, ind in source.items() if ind.time_of_birth <= restart_from
    }
    assert set(copy) == born_by_then
    for key, ind in copy.items():
        assert ind.time_of_birth == source[key].time_of_birth
        assert ind.time_of_death == min(source[key].time_of_death, restart_from)
    source_bytes = _genotype_bytes(tmp_path / "first.db")
    assert _genotype_bytes(tmp_path / "second.db") == {
        key: source_bytes[key] for key in born_by_then
    }
    # The child born in generation 1 was never evaluated: copied, retired
    child = next(ind for ind in copy.values() if ind.requires_eval)
    assert not child.alive
