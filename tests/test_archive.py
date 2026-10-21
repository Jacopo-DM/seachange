"""Test: Archive, read-only query interface for a persisted EA database."""

import math
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from seachange import EA, EAOperation
from seachange.archive import Archive, FitnessMode
from seachange.individual import Individual
from seachange.population import Population

pytestmark = pytest.mark.usefixtures("dispose_engines")

MIN_ARCHIVE_SIZE = 20
LAST_GENERATION = 5
FITNESS_LOW = 5.0
FITNESS_HIGH = 10.0
SAMPLE_SIZE = 5
FITNESS_CUTOFF = 5.0
HALL_SIZE = 5
NUM_WINNERS = 4
MAX_WINNER_FITNESS = 19.0
NUM_ALIVE = 20
SAMPLE_LIMIT = 3

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


@EAOperation
def noop(population: Population) -> Population:
    return population


def _make_evaluated_pop(n: int = 20) -> Population:
    """Return n individuals with distinct float fitnesses 0..n-1.

    Returns
    -------
    Population
        The population.
    """
    inds = []
    for i in range(n):
        ind = Individual()
        ind.genotype = [float(i)]
        ind.fitness = float(i)
        inds.append(ind)
    return Population(inds)


def _fitness(ind: Individual) -> float:
    fitness = ind.fitness_
    assert fitness is not None
    return fitness


@pytest.fixture(scope="module")
def archive_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One EA run shared across the whole module.

    20 individuals, fitness 0.0-19.0, run for 5 steps with noop so every
    individual survives to generation 5 (time_of_birth=0, time_of_death=5).

    Returns
    -------
    Path
        The path of the archive database.
    """
    db = tmp_path_factory.mktemp("archive") / "archive.db"
    ea = EA(
        population=_make_evaluated_pop(20),
        operations=[noop],
        db_file_path=db,
        quiet=True,
        num_steps=5,
    )
    ea.run()
    ea.engine.dispose()
    return db


@pytest.fixture
def archive(archive_db: Path) -> Archive:
    return Archive(archive_db)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_archive_opens_existing_db(archive_db: Path) -> None:
    """Archive opens a valid database without error."""
    a = Archive(archive_db)
    assert a.db_path == archive_db


def test_archive_missing_db_raises() -> None:
    """Archive raises FileNotFoundError for a non-existent path."""
    with pytest.raises(FileNotFoundError, match="not found"):
        Archive("/nonexistent/path/db.db")


def test_archive_repr_contains_name(archive: Archive) -> None:
    """__repr__ contains 'Archive'."""
    assert "Archive" in repr(archive)


# ---------------------------------------------------------------------------
# Properties: size, generation_range
# ---------------------------------------------------------------------------


def test_archive_size(archive: Archive) -> None:
    """Size returns the total number of evaluated individuals."""
    assert archive.size >= MIN_ARCHIVE_SIZE


def test_archive_generation_range(archive: Archive) -> None:
    """generation_range returns a (min_birth, max_death) tuple."""
    lo, hi = archive.generation_range
    assert isinstance(lo, int)
    assert isinstance(hi, int)
    assert hi >= lo


def test_archive_generation_range_values(archive: Archive) -> None:
    """Individuals born at gen 0 and alive through gen 5."""
    lo, hi = archive.generation_range
    assert lo == 0
    assert hi == LAST_GENERATION


# ---------------------------------------------------------------------------
# fitness_stats
# ---------------------------------------------------------------------------


def test_fitness_stats_returns_dict(archive: Archive) -> None:
    """fitness_stats returns a dict with the five expected keys."""
    stats = archive.fitness_stats()
    assert set(stats.keys()) == {"min", "max", "mean", "std", "median"}


def test_fitness_stats_min_max(archive: Archive) -> None:
    """Min and max fitness values match the known population range."""
    stats = archive.fitness_stats()
    assert stats["min"] == pytest.approx(0.0)
    assert stats["max"] == pytest.approx(19.0)


def test_fitness_stats_mean(archive: Archive) -> None:
    """Mean fitness of 0..19 is 9.5."""
    stats = archive.fitness_stats()
    assert stats["mean"] == pytest.approx(9.5)


def test_fitness_stats_no_match_returns_nan(archive: Archive) -> None:
    """fitness_stats with an impossible birth_range returns NaN values."""
    stats = archive.fitness_stats(birth_range=(9999, 9999))
    for v in stats.values():
        assert math.isnan(v)


def test_fitness_stats_birth_range_filter(archive: Archive) -> None:
    """birth_range=(0, 0) restricts to individuals born at generation 0."""
    stats = archive.fitness_stats(birth_range=(0, 0))
    assert not math.isnan(stats["min"])


# ---------------------------------------------------------------------------
# random_individual
# ---------------------------------------------------------------------------


def test_random_individual_returns_individual(archive: Archive) -> None:
    """random_individual returns an Individual."""
    ind = archive.random_individual()
    assert isinstance(ind, Individual)


def test_random_individual_is_evaluated(archive: Archive) -> None:
    """random_individual returns an evaluated individual (fitness_ is set)."""
    ind = archive.random_individual()
    assert ind.fitness_ is not None


def test_random_individual_birth_range_filter(archive: Archive) -> None:
    """birth_range limits the birth generation of the result."""
    ind = archive.random_individual(birth_range=(0, 0))
    assert ind.time_of_birth == 0


def test_random_individual_fitness_range_filter(archive: Archive) -> None:
    """fitness_range restricts the returned individual's fitness."""
    ind = archive.random_individual(fitness_range=(FITNESS_LOW, FITNESS_HIGH))
    assert FITNESS_LOW <= _fitness(ind) <= FITNESS_HIGH


def test_random_individual_no_match_raises(archive: Archive) -> None:
    """random_individual raises ValueError when no match exists."""
    with pytest.raises(ValueError, match="No individuals"):
        archive.random_individual(fitness_range=(9999.0, 9999.0))


# ---------------------------------------------------------------------------
# best_individual
# ---------------------------------------------------------------------------


def test_best_individual_min_mode(archive: Archive) -> None:
    """best_individual('min') returns the individual with the lowest fitness."""
    ind = archive.best_individual(fitness_mode="min")
    assert ind.fitness_ == pytest.approx(0.0)


def test_best_individual_max_mode(archive: Archive) -> None:
    """best_individual('max') returns the individual with highest fitness."""
    ind = archive.best_individual(fitness_mode="max")
    assert ind.fitness_ == pytest.approx(19.0)


def test_best_individual_birth_range(archive: Archive) -> None:
    """best_individual respects birth_range."""
    ind = archive.best_individual(fitness_mode="min", birth_range=(0, 0))
    assert ind.time_of_birth == 0


# ---------------------------------------------------------------------------
# random_population
# ---------------------------------------------------------------------------


def test_random_population_returns_population(archive: Archive) -> None:
    """random_population returns a Population."""
    pop = archive.random_population(5)
    assert isinstance(pop, Population)


def test_random_population_respects_n(archive: Archive) -> None:
    """random_population returns at most n individuals."""
    pop = archive.random_population(SAMPLE_SIZE)
    assert len(pop) <= SAMPLE_SIZE


def test_random_population_all_evaluated(archive: Archive) -> None:
    """All individuals in the random population are evaluated."""
    pop = archive.random_population(10)
    for ind in pop:
        assert ind.fitness_ is not None


def test_random_population_fitness_range(archive: Archive) -> None:
    """fitness_range filter works for random_population."""
    pop = archive.random_population(20, fitness_range=(0.0, FITNESS_CUTOFF))
    for ind in pop:
        assert 0.0 <= _fitness(ind) <= FITNESS_CUTOFF


def test_random_population_n_larger_than_archive(archive: Archive) -> None:
    """Requesting more than the archive size returns what's available."""
    pop = archive.random_population(10000)
    assert len(pop) <= archive.size


# ---------------------------------------------------------------------------
# hall_of_fame
# ---------------------------------------------------------------------------


def test_hall_of_fame_returns_population(archive: Archive) -> None:
    """hall_of_fame returns a Population."""
    hof = archive.hall_of_fame(n=5)
    assert isinstance(hof, Population)


def test_hall_of_fame_size(archive: Archive) -> None:
    """hall_of_fame returns at most n individuals."""
    hof = archive.hall_of_fame(n=HALL_SIZE)
    assert len(hof) <= HALL_SIZE


def test_hall_of_fame_min_sorted(archive: Archive) -> None:
    """hall_of_fame('min') is sorted ascending by fitness."""
    hof = archive.hall_of_fame(n=5, fitness_mode="min")
    fitnesses = [_fitness(ind) for ind in hof]
    assert fitnesses == sorted(fitnesses)


def test_hall_of_fame_max_sorted(archive: Archive) -> None:
    """hall_of_fame('max') is sorted descending by fitness."""
    hof = archive.hall_of_fame(n=5, fitness_mode="max")
    fitnesses = [_fitness(ind) for ind in hof]
    assert fitnesses == sorted(fitnesses, reverse=True)


def test_hall_of_fame_min_best_is_lowest(archive: Archive) -> None:
    """The first entry in a min hall of fame has the lowest fitness."""
    hof = archive.hall_of_fame(n=3, fitness_mode="min")
    assert hof[0].fitness_ == pytest.approx(0.0)


def test_hall_of_fame_max_best_is_highest(archive: Archive) -> None:
    """The first entry in a max hall of fame has the highest fitness."""
    hof = archive.hall_of_fame(n=3, fitness_mode="max")
    assert hof[0].fitness_ == pytest.approx(19.0)


def test_hall_of_fame_birth_range(archive: Archive) -> None:
    """hall_of_fame respects birth_range."""
    hof = archive.hall_of_fame(n=5, birth_range=(0, 0))
    for ind in hof:
        assert ind.time_of_birth == 0


# ---------------------------------------------------------------------------
# tournament_population
# ---------------------------------------------------------------------------


def test_tournament_population_returns_population(archive: Archive) -> None:
    """tournament_population returns a Population."""
    pop = archive.tournament_population(n=3, tournament_size=2)
    assert isinstance(pop, Population)


def test_tournament_population_size(archive: Archive) -> None:
    """tournament_population returns exactly n individuals."""
    pop = archive.tournament_population(n=NUM_WINNERS, tournament_size=2)
    assert len(pop) == NUM_WINNERS


def test_tournament_population_min_winners_are_low_fitness(
    archive: Archive,
) -> None:
    """In min mode, tournament winners have low fitness."""
    pop = archive.tournament_population(
        n=5, tournament_size=3, fitness_mode="min"
    )
    for ind in pop:
        assert _fitness(ind) <= MAX_WINNER_FITNESS


def test_tournament_population_max_mode(archive: Archive) -> None:
    """In max mode, tournament winners have high fitness."""
    pop = archive.tournament_population(
        n=5, tournament_size=3, fitness_mode="max"
    )
    for ind in pop:
        assert _fitness(ind) >= 0.0


def test_tournament_size_exceeds_pool_raises(archive: Archive) -> None:
    """tournament_size larger than the pool raises AssertionError."""
    with pytest.raises(AssertionError, match="tournament_size"):
        archive.tournament_population(
            n=1, tournament_size=9999, pool_multiplier=1
        )


# ---------------------------------------------------------------------------
# by_generation
# ---------------------------------------------------------------------------


def test_by_generation_returns_population(archive: Archive) -> None:
    """by_generation returns a Population."""
    pop = archive.by_generation(0)
    assert isinstance(pop, Population)


def test_by_generation_correct_count(archive: Archive) -> None:
    """All 20 individuals were alive at generation 0."""
    pop = archive.by_generation(0)
    assert len(pop) == NUM_ALIVE


def test_by_generation_mid_run(archive: Archive) -> None:
    """All individuals alive through generation 3 (born=0, died=5)."""
    pop = archive.by_generation(3)
    assert len(pop) == NUM_ALIVE


def test_by_generation_out_of_range_empty(archive: Archive) -> None:
    """A generation beyond the run returns no individuals."""
    pop = archive.by_generation(9999)
    assert len(pop) == 0


# ---------------------------------------------------------------------------
# fitness_percentile_population
# ---------------------------------------------------------------------------


def test_fitness_percentile_returns_population(archive: Archive) -> None:
    """fitness_percentile_population returns a Population."""
    pop = archive.fitness_percentile_population(25.0, 75.0)
    assert isinstance(pop, Population)


def test_fitness_percentile_in_band(archive: Archive) -> None:
    """All returned individuals fall within the percentile band."""
    pop = archive.fitness_percentile_population(0.0, 50.0)
    assert len(pop) > 0
    fitnesses = [_fitness(ind) for ind in pop]
    everyone = archive.hall_of_fame(n=archive.size, fitness_mode="max")
    all_fitnesses = [_fitness(ind) for ind in everyone]
    lo = float(np.percentile(all_fitnesses, 0.0))
    hi = float(np.percentile(all_fitnesses, 50.0))
    for f in fitnesses:
        assert lo <= f <= hi


def test_fitness_percentile_with_n_sampling(archive: Archive) -> None:
    """N parameter limits the number of returned individuals."""
    pop = archive.fitness_percentile_population(0.0, 100.0, n=SAMPLE_LIMIT)
    assert len(pop) <= SAMPLE_LIMIT


def test_fitness_percentile_impossible_birth_range_empty(
    archive: Archive,
) -> None:
    """Impossible birth_range returns an empty population."""
    pop = archive.fitness_percentile_population(
        0.0, 100.0, birth_range=(9999, 9999)
    )
    assert len(pop) == 0


# ---------------------------------------------------------------------------
# Maximisation, death ranges and empty selections
# ---------------------------------------------------------------------------

NOBODY = (100, 200)
BEST_FITNESS = 19.0
EVERYONE = (0, 1000)
TOP_N = 3


def test_best_individual_maximising(archive: Archive) -> None:
    """In max mode the highest fitness wins."""
    best = archive.best_individual("max")
    assert _fitness(best) == pytest.approx(BEST_FITNESS)


def test_hall_of_fame_maximising(archive: Archive) -> None:
    """In max mode the hall of fame holds the highest fitnesses first."""
    hof = archive.hall_of_fame(n=TOP_N, fitness_mode="max")
    fitnesses = [_fitness(ind) for ind in hof]
    assert fitnesses == sorted(fitnesses, reverse=True)
    assert fitnesses[0] == pytest.approx(BEST_FITNESS)


def test_death_range_filters_the_hall_of_fame(archive: Archive) -> None:
    """A death range that covers everyone keeps everyone; none keeps nobody."""
    everyone = archive.hall_of_fame(n=NUM_ALIVE, death_range=EVERYONE)
    nobody = archive.hall_of_fame(n=NUM_ALIVE, death_range=NOBODY)
    assert len(everyone) == NUM_ALIVE
    assert len(nobody) == 0


def test_best_individual_of_an_empty_selection_fails(
    archive: Archive,
) -> None:
    """No evaluated individual in range is an error."""
    with pytest.raises(ValueError, match="No evaluated individuals"):
        archive.best_individual(birth_range=NOBODY)


def test_random_individual_among_the_dead_fails(archive: Archive) -> None:
    """Everyone is still alive after the run, so no dead one can be drawn."""
    with pytest.raises(ValueError, match="No individuals match"):
        archive.random_individual(only_dead=True)


def test_tournament_of_an_empty_pool_fails(archive: Archive) -> None:
    """A birth range without individuals gives an empty pool."""
    with pytest.raises(ValueError, match="No individuals match"):
        archive.tournament_population(n=2, birth_range=NOBODY)


def test_unknown_fitness_mode_leaves_the_order_to_the_database(
    archive: Archive,
) -> None:
    """A mode that is neither min nor max applies no ordering."""
    mode = cast("FitnessMode", "unsorted")
    assert isinstance(archive.best_individual(mode), Individual)
    assert len(archive.hall_of_fame(n=TOP_N, fitness_mode=mode)) == TOP_N
