"""Numpy genotypes: evolve 100 float32 weights toward a target vector.

Each genotype is a float32 numpy array. seachange stores it as raw bytes
and gives it back as the same array, dtype and shape included. The
operations are annotated with ``Population[Weights]``, so a type checker
knows ``parent.genotype`` is a float32 array in every step. The run is
stored in ``__data__/numpy.db`` under the current folder.
"""

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from seachange import EA, Archive, EAOperation, Individual, Population

type Weights = NDArray[np.float32]

POPULATION_SIZE = 20
WEIGHTS = 100
GENERATIONS = 60
MUTATION_SCALE = np.float32(0.1)
DATABASE = Path("__data__/numpy.db")

rng = np.random.default_rng(1)
TARGET: Weights = rng.standard_normal(WEIGHTS).astype(np.float32)


def new_individual(weights: Weights) -> Individual[Weights]:
    """Return an unevaluated individual with ``weights`` as its genotype.

    Parameters
    ----------
    weights : Weights
        The genotype. seachange makes the array read-only.

    Returns
    -------
    Individual[Weights]
        The individual.
    """
    individual: Individual[Weights] = Individual()
    individual.genotype = weights
    return individual


def error(weights: Weights) -> float:
    """Return the mean squared distance from ``weights`` to the target.

    Parameters
    ----------
    weights : Weights
        A genotype.

    Returns
    -------
    float
        The error; 0 is a perfect match.
    """
    return float(np.mean((weights - TARGET) ** 2))


def evaluate(population: Population[Weights]) -> Population[Weights]:
    """Score each new individual: higher is better, so the negative error.

    Returns
    -------
    Population[Weights]
        The same population, every member evaluated.
    """
    for individual in population.unevaluated:
        individual.fitness = -error(individual.genotype)
    return population


def reproduce(population: Population[Weights]) -> Population[Weights]:
    """Add one child per parent in the better half: the parent plus noise.

    The child gets a new array; the parent's genotype is read-only and
    stays as it was.

    Returns
    -------
    Population[Weights]
        The population with the children added.
    """
    for parent in population.best(n=POPULATION_SIZE // 2):
        noise = rng.standard_normal(WEIGHTS).astype(np.float32)
        population.append(
            new_individual(parent.genotype + noise * MUTATION_SCALE)
        )
    return population


def retire_worst(population: Population[Weights]) -> Population[Weights]:
    """Mark all but the best ``POPULATION_SIZE`` individuals as dead.

    Returns
    -------
    Population[Weights]
        The same population; the dead stay in the database.
    """
    for individual in population.sort()[POPULATION_SIZE:]:
        individual.alive = False
    return population


def main() -> None:
    """Run the evolution, then read the best genotype back from the file."""
    first = Population([
        new_individual(rng.standard_normal(WEIGHTS).astype(np.float32))
        for _ in range(POPULATION_SIZE)
    ])
    start = -max(individual.fitness for individual in evaluate(first))
    with EA(
        first,
        [
            EAOperation(reproduce),
            EAOperation(evaluate),
            EAOperation(retire_worst),
        ],
        num_steps=GENERATIONS,
        db_file_path=DATABASE,
    ) as ea:
        ea.run()
    with Archive[Weights](DATABASE) as archive:
        best = archive.best_individual(direction="max").genotype
    print(f"error {start:.3f} -> {error(best):.3f}")  # ruff: ignore[print]  # an example shows its result
    print(f"stored genotype: {best.dtype} {best.shape}")  # ruff: ignore[print]  # an example shows its result


if __name__ == "__main__":  # pragma: no cover
    main()
