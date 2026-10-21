"""Test: the genotype type parameter, for type checkers and at run time.

The ``assert_type`` lines do nothing at run time; the mypy run over
``tests/`` checks each of them, so they fail the checks if a type is lost.
"""

from pathlib import Path
from typing import assert_type

import numpy as np
import pytest
from numpy.typing import NDArray

from seachange import (
    EA,
    Archive,
    Crossover,
    EAOperation,
    Genotype,
    Individual,
    JSONIterable,
    Population,
)

pytestmark = pytest.mark.usefixtures("dispose_engines")

type Weights = NDArray[np.float32]
PARENT_AND_CHILD = 2


def weights_individual(value: float) -> Individual[Weights]:
    """Return an evaluated individual with a float32 array genotype.

    Parameters
    ----------
    value : float
        Every weight, and the fitness.

    Returns
    -------
    Individual[Weights]
        The individual.
    """
    individual: Individual[Weights] = Individual()
    individual.genotype = np.full(3, value, dtype=np.float32)
    individual.fitness = value
    return individual


def nudge(population: Population[Weights]) -> Population[Weights]:
    """Replace each individual by a child one step higher.

    Parameters
    ----------
    population : Population[Weights]
        The parents.

    Returns
    -------
    Population[Weights]
        The children.
    """
    children: Population[Weights] = Population([])
    for parent in population:
        assert_type(parent.genotype, Weights)
        child = weights_individual(float(parent.genotype[0]) + 1.0)
        children.append(child)
        parent.alive = False
    return population + children


def test_individual_of_a_type_is_individual_at_run_time() -> None:
    """Individual[X] is the same class, so it makes no second table."""
    assert Individual[Weights] is Individual
    individual = Individual[Weights]()
    assert type(individual) is Individual


def test_plain_individual_keeps_the_default_genotype_type() -> None:
    """Code that names no type sees Genotype, as before."""
    individual = Individual()
    individual.genotype = [1.0]
    # Read back through a population: mypy narrows right after assigning
    first = Population([individual])[0]
    assert_type(first.genotype, Genotype)
    assert first.genotype == [1.0]


def test_a_typed_run_keeps_its_genotype_type(tmp_path: Path) -> None:
    """EA, Archive and EA.restart carry the genotype type through."""
    db = tmp_path / "run.db"
    first = Population([weights_individual(v) for v in (1.0, 2.0)])
    with EA(first, [EAOperation(nudge)], num_steps=2, db_file_path=db) as ea:
        assert_type(ea, EA[Weights])
        ea.run()
        best = ea.get_solution("best")
    assert_type(best.genotype, Weights)
    assert best.genotype.tolist() == [4.0, 4.0, 4.0]

    with Archive[Weights](db) as archive:
        stored = archive.hall_of_fame(1, direction="max")[0].genotype
    assert_type(stored, Weights)
    assert stored.dtype == np.float32

    with EA.restart(
        db, [EAOperation(nudge)], db_file_path=tmp_path / "again.db"
    ) as restarted:
        assert_type(restarted, EA[Weights])
        assert restarted.population[0].genotype.dtype == np.float32


def test_eaoperation_accepts_a_typed_population_annotation() -> None:
    """Population[X] passes EAOperation's run-time annotation check."""
    operation = EAOperation(nudge)
    result = operation.run(Population([weights_individual(1.0)]))
    assert_type(result, Population[Weights])
    assert result.size == PARENT_AND_CHILD


def test_crossover_keeps_arrays_as_arrays() -> None:
    """Array parents give array children of the same dtype and shape."""
    parent_i: NDArray[np.float32] = np.zeros((2, 3), dtype=np.float32)
    parent_j: NDArray[np.float32] = np.ones((2, 3), dtype=np.float32)
    for child_i, child_j in (
        Crossover.one_point(parent_i, parent_j),
        Crossover.n_point(parent_i, parent_j, 2),
        Crossover.uniform(parent_i, parent_j),
    ):
        assert_type(child_i, NDArray[np.float32])
        for child in (child_i, child_j):
            assert isinstance(child, np.ndarray)
            assert child.dtype == np.float32
            assert child.shape == (2, 3)
        # Each gene came from one parent: the children add up to all ones
        assert (child_i + child_j).tolist() == [[1.0] * 3] * 2


def test_crossover_still_turns_lists_into_lists() -> None:
    """List parents give nested list children, as before."""
    child_i, _ = Crossover.one_point([0.0, 0.0, 0.0], [1.0, 1.0, 1.0])
    assert_type(child_i, JSONIterable)
    assert isinstance(child_i, list)
