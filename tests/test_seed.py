"""Test: after seed(n) a whole run, and every random draw, repeats."""

import random
from pathlib import Path
from typing import cast

import pytest

from seachange import (
    EA,
    Archive,
    EAOperation,
    FloatMutator,
    Individual,
    Population,
    seed,
)
from tests.ea_helpers import make_pop, noop

pytestmark = pytest.mark.usefixtures("dispose_engines")

POPULATION_SIZE = 20
GENERATIONS = 5


@EAOperation
def sample_and_mutate(population: Population) -> Population:
    # Random parents (Python draws), mutated children (numpy draws).
    for parent in population.sample(POPULATION_SIZE // 2):
        child = Individual()
        child.genotype = FloatMutator.gaussian(
            cast("list[float]", parent.genotype),
            std=0.1,
            mutation_probability=1.0,
        )
        child.fitness = sum(cast("list[float]", child.genotype))
        population.append(child)
    for loser in population.shuffle().sort(direction="max")[POPULATION_SIZE:]:
        loser.alive = False
    return population


def _run(tmp_path: Path, name: str, value: int) -> list[list[float]]:
    seed(value)
    pop = make_pop(POPULATION_SIZE)
    with EA(
        pop,
        [sample_and_mutate],
        db_file_path=tmp_path / name,
        num_steps=GENERATIONS,
        quiet=True,
    ) as ea:
        ea.run()
        ea.fetch_population()
        return sorted(cast("list[float]", i.genotype) for i in ea.population)


def test_a_whole_run_repeats_after_the_same_seed(tmp_path: Path) -> None:
    """Same seed, same final population; another seed, another one."""
    first = _run(tmp_path, "a.db", 5)
    again = _run(tmp_path, "b.db", 5)
    other = _run(tmp_path, "c.db", 6)
    assert first == again
    assert first != other


def test_population_draws_follow_the_seed() -> None:
    """Population.sample and shuffle repeat after the same seed."""
    pop = make_pop(POPULATION_SIZE)

    def draw() -> tuple[list[object], list[object]]:
        return (
            [i.genotype for i in pop.sample(5)],
            [i.genotype for i in pop.shuffle()],
        )

    seed(5)
    first = draw()
    seed(5)
    assert draw() == first
    seed(6)
    assert draw() != first


def test_archive_draws_follow_the_seed(tmp_path: Path) -> None:
    """All four random Archive queries repeat after the same seed."""
    db = tmp_path / "run.db"
    with EA(
        make_pop(POPULATION_SIZE),
        [noop],
        db_file_path=db,
        num_steps=2,
        quiet=True,
    ):
        pass

    def draw(archive: Archive) -> list[list[object]]:
        # Archive clears ids, so individuals are told apart by genotype.
        return [
            [archive.random_individual().genotype],
            [i.genotype for i in archive.random_population(5)],
            [
                i.genotype
                for i in archive.tournament_population(5, direction="max")
            ],
            [
                i.genotype
                for i in archive.fitness_percentile_population(0.0, 100.0, n=5)
            ],
        ]

    with Archive(db) as archive:
        seed(5)
        first = draw(archive)
        seed(5)
        assert draw(archive) == first
        seed(6)
        assert draw(archive) != first


def test_seed_leaves_pythons_global_random_alone() -> None:
    """The package draws from its own generator, not the global one."""
    random.seed(1)
    expected = random.random()  # ruff: ignore[suspicious-non-cryptographic-random-usage]  # reads the global generator on purpose
    random.seed(1)
    seed(5)
    make_pop(POPULATION_SIZE).sample(5)
    assert random.random() == expected  # ruff: ignore[suspicious-non-cryptographic-random-usage]  # reads the global generator on purpose
