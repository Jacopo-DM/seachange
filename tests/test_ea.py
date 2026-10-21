"""Test: the EA class."""

import subprocess  # ruff: ignore[suspicious-subprocess-import]  # runs a fixed import check
import sys
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from seachange import EA, Archive, EAOperation, config
from seachange.individual import Individual
from seachange.population import Population
from tests.ea_helpers import (
    ALIVE_COUNT,
    FIRST_GENERATION_ID,
    INITIAL_POP_SIZE,
    NUM_STEPS_RUN,
    STEPS_TAKEN,
    make_ea,
    make_pop,
    noop,
)
from tests.misuse import assign, untyped

pytestmark = pytest.mark.usefixtures("dispose_engines")


def test_ea_initializes(tmp_path: Path) -> None:
    """EA initializes without error given population and ops."""
    ea = make_ea(tmp_path)
    assert ea.current_generation == 0


def test_ea_requires_population_and_operations(tmp_path: Path) -> None:
    """Both are required: a restart goes through EA.restart instead."""
    with pytest.raises(TypeError, match="operations"):
        untyped(EA)(population=make_pop(), db_file_path=tmp_path / "db.db")
    with pytest.raises(TypeError, match="population"):
        untyped(EA)(operations=[noop], db_file_path=tmp_path / "db.db")


def test_ea_creates_database_file(tmp_path: Path) -> None:
    """EA creates the SQLite database file on disk."""
    db = tmp_path / "ea.db"
    make_ea(tmp_path, ops=[noop])
    assert db.exists() or (tmp_path / "test.db").exists()


def test_ea_db_handling_halt_raises(tmp_path: Path) -> None:
    """db_handling='halt' raises FileExistsError when db already exists."""
    db = tmp_path / "existing.db"
    db.touch()
    with pytest.raises(FileExistsError):
        EA(
            population=make_pop(),
            operations=[noop],
            db_file_path=db,
            quiet=True,
            db_handling="halt",
        )


def test_ea_db_handling_delete_overwrites(tmp_path: Path) -> None:
    """db_handling='delete' recreates the db without raising."""
    db = tmp_path / "run.db"
    ea1 = EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=db,
        quiet=True,
        db_handling="delete",
    )
    # Explicitly dispose the engine so Windows releases the file lock
    ea1.engine.dispose()
    del ea1
    # Second run on same path: should succeed
    EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=db,
        quiet=True,
        db_handling="delete",
    )


def test_ea_population_stored(tmp_path: Path) -> None:
    """EA stores the initial population."""
    pop = make_pop(INITIAL_POP_SIZE)
    ea = make_ea(tmp_path, pop=pop)
    assert len(ea.population) == INITIAL_POP_SIZE


def test_ea_custom_first_generation(tmp_path: Path) -> None:
    """first_generation_id is stored on the EA."""
    ea = make_ea(tmp_path, first_generation_id=FIRST_GENERATION_ID)
    assert ea.current_generation == FIRST_GENERATION_ID


def test_ea_commit_sets_time_of_birth(tmp_path: Path) -> None:
    """_commit assigns time_of_birth=-1 individuals the current generation."""
    ea = make_ea(tmp_path)
    # Fetch fresh from DB so SQLAlchemy session context is active
    ea.fetch_population()
    for ind in ea.population:
        assert ind.time_of_birth == 0


def test_ea_fetch_returns_population(tmp_path: Path) -> None:
    """fetch_population stores a Population."""
    ea = make_ea(tmp_path)
    ea.fetch_population()
    assert isinstance(ea.population, Population)


def test_ea_fetch_only_alive(tmp_path: Path) -> None:
    """fetch_population(only_alive=True) keeps only alive individuals."""
    ea = make_ea(tmp_path)
    ea.fetch_population(only_alive=True)
    assert all(ind.alive for ind in ea.population)


def _solution_fitnesses(ea: EA) -> tuple[float, float, float]:
    best = ea.get_solution(mode="best").fitness_
    median = ea.get_solution(mode="median").fitness_
    worst = ea.get_solution(mode="worst").fitness_
    assert best is not None
    assert median is not None
    assert worst is not None
    return best, median, worst


def test_ea_solutions_descend_when_maximising(tmp_path: Path) -> None:
    """Maximising: best, median and worst come in falling fitness."""
    best, median, worst = _solution_fitnesses(make_ea(tmp_path))
    assert best >= median >= worst


def test_ea_solutions_ascend_when_minimising(tmp_path: Path) -> None:
    """Minimising: best, median and worst come in rising fitness."""
    ea = EA(
        population=make_pop(),
        operations=[noop],
        db_file_path=tmp_path / "test.db",
        quiet=True,
        direction="min",
    )
    best, median, worst = _solution_fitnesses(ea)
    assert best <= median <= worst


def test_ea_fetch_requires_eval_false(tmp_path: Path) -> None:
    """fetch_population(requires_eval=False) keeps evaluated individuals."""
    ea = make_ea(tmp_path)
    ea.fetch_population(requires_eval=False)
    assert all(not ind.requires_eval for ind in ea.population)


def test_ea_fetch_population_updates_self(tmp_path: Path) -> None:
    """fetch_population() updates self.population from the database."""
    ea = make_ea(tmp_path)
    original_len = len(ea.population)
    ea.fetch_population()
    assert len(ea.population) == original_len


def test_ea_size_property(tmp_path: Path) -> None:
    """Size returns the number of alive individuals."""
    ea = make_ea(tmp_path, pop=make_pop(ALIVE_COUNT))
    assert ea.size == ALIVE_COUNT


def test_ea_get_solution_best(tmp_path: Path) -> None:
    """get_solution('best') returns an Individual."""
    ea = make_ea(tmp_path)
    sol = ea.get_solution(mode="best")
    assert isinstance(sol, Individual)


def test_ea_get_solution_median(tmp_path: Path) -> None:
    """get_solution('median') returns an Individual."""
    ea = make_ea(tmp_path)
    sol = ea.get_solution(mode="median")
    assert isinstance(sol, Individual)


def test_ea_get_solution_worst(tmp_path: Path) -> None:
    """get_solution('worst') returns an Individual."""
    ea = make_ea(tmp_path)
    sol = ea.get_solution(mode="worst")
    assert isinstance(sol, Individual)


def test_ea_step_increments_generation(tmp_path: Path) -> None:
    """step() increments current_generation by 1."""
    ea = make_ea(tmp_path)
    ea.step()
    assert ea.current_generation == 1


def test_ea_step_applies_operations(tmp_path: Path) -> None:
    """step() applies all operations and the result is committed to the DB."""
    called = []

    @EAOperation
    def recording_op(population: Population) -> Population:
        called.append(True)
        return population

    ea = make_ea(tmp_path, pop=make_pop(3), ops=[recording_op])
    ea.step()
    assert len(called) == 1


def test_ea_step_twice(tmp_path: Path) -> None:
    """Two steps advance generation to 2."""
    ea = make_ea(tmp_path)
    ea.step()
    ea.step()
    assert ea.current_generation == STEPS_TAKEN


def test_ea_run_executes_num_steps(tmp_path: Path) -> None:
    """run() executes exactly num_steps generations."""
    ea = make_ea(tmp_path, num_steps=NUM_STEPS_RUN)
    ea.run()
    assert ea.current_generation == NUM_STEPS_RUN


def test_ea_run_zero_steps(tmp_path: Path) -> None:
    """run() with num_steps=0 leaves generation unchanged."""
    ea = make_ea(tmp_path, num_steps=0)
    ea.run()
    assert ea.current_generation == 0


def test_default_database_follows_the_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default path is decided when read, not when seachange loads."""
    monkeypatch.chdir(tmp_path)
    assert config.db_file_path == tmp_path / "__data__" / "database.db"


def test_settings_are_read_only() -> None:
    """Assigning to config raises; a run takes its value as an argument."""
    with pytest.raises(ValidationError, match="frozen"):
        assign(config, "direction", value="min")
    assert config.direction == "max"


def test_ea_writes_under_the_working_directory_at_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An EA created after a chdir writes its run under the new folder."""
    monkeypatch.chdir(tmp_path)
    EA(population=make_pop(), operations=[noop], quiet=True)
    assert (tmp_path / "__data__" / "database.db").exists()


def test_importing_seachange_leaves_the_traceback_printer_alone(
    tmp_path: Path,
) -> None:
    """A library import must not replace the program's sys.excepthook."""
    check = (
        "import sys; hook = sys.excepthook; import seachange; "
        "assert sys.excepthook is hook, 'excepthook replaced'"
    )
    subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]  # fixed argv, no outside input
        [sys.executable, "-c", check],
        cwd=tmp_path,
        check=True,
    )


def test_population_is_readable_right_after_creation(tmp_path: Path) -> None:
    """Saving the first generation keeps each individual's values."""
    ea = make_ea(tmp_path)
    first = ea.population[0]
    assert first.genotype == make_pop()[0].genotype
    assert first.time_of_birth == 0
    assert first.id is not None


@EAOperation
def replace_genotypes(population: Population) -> Population:
    # Give every saved individual a new array, as a repair step might
    for individual in population:
        individual.genotype = np.full(2, individual.fitness)
    return population


def test_a_saved_numpy_genotype_can_be_replaced(tmp_path: Path) -> None:
    """Replacing a stored array saves the new one."""
    pop = Population([])
    for value in (1.0, 2.0):
        individual = Individual()
        individual.genotype = np.zeros(2)
        individual.fitness = value
        pop.append(individual)
    with EA(
        pop,
        [replace_genotypes],
        num_steps=2,
        db_file_path=tmp_path / "run.db",
        quiet=True,
    ) as ea:
        ea.run()
    with Archive(tmp_path / "run.db") as archive:
        stored = archive.hall_of_fame(2, direction="max")
    assert [np.asarray(i.genotype).tolist() for i in stored] == [
        [2.0, 2.0],
        [1.0, 1.0],
    ]


def test_an_individual_without_a_genotype_is_saved(tmp_path: Path) -> None:
    """A missing genotype is stored as NULL and read back as missing."""
    with EA(
        Population([Individual()]),
        [noop],
        db_file_path=tmp_path / "run.db",
        quiet=True,
    ) as ea:
        ea.fetch_population(only_alive=False, requires_eval=None)
        assert ea.population[0].genotype_ is None
