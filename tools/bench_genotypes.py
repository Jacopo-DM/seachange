"""Time how long an EA run spends storing large genotypes (goal 8).

A neuro-evolution sized run: ``POPULATION`` individuals, each a genotype of
``WEIGHTS`` float32 weights. Every generation replaces each parent by a
mutated child, so every individual is new. The script times each
``EA.step()`` and subtracts the time spent inside the mutation, which leaves
the database work: fetching the population and saving it. It runs
``REPEATS`` times in a temporary folder and prints the median::

    uv run --no-sync python tools/bench_genotypes.py

Genotypes are lists of floats, stored as JSON text, the only kind seachange
stores before goal 8's codecs. Run nothing else while it runs.
"""

import statistics
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

import numpy as np
from numpy.typing import NDArray

from seachange import EA, EAOperation, Individual, Population, seed

POPULATION = 100
WEIGHTS = 10_000
GENERATIONS = 20
REPEATS = 3
MUTATION_SCALE = 0.01
BYTES_PER_MB = 1e6

rng = np.random.default_rng(1)
# Seconds spent inside the mutation since the last reset.
mutation_seconds: list[float] = [0.0]


def make_individual(weights: list[float]) -> Individual:
    """Return an evaluated individual with ``weights`` as its genotype.

    Parameters
    ----------
    weights : list of float
        The genotype.

    Returns
    -------
    Individual
        The individual, with a cheap stand-in fitness.
    """
    individual = Individual()
    individual.genotype = weights
    individual.fitness = sum(weights[:10])
    return individual


def as_list(weights: NDArray[np.float32]) -> list[float]:
    """Return ``weights`` as a list of Python floats.

    Parameters
    ----------
    weights : NDArray[np.float32]
        A one-dimensional array.

    Returns
    -------
    list of float
        The same values.
    """
    # numpy types tolist() as returning Any; a 1-D float array gives floats
    return cast("list[float]", weights.tolist())


def random_weights() -> list[float]:
    """Return ``WEIGHTS`` random float32 weights as a list.

    Returns
    -------
    list of float
        The weights.
    """
    return as_list(rng.standard_normal(WEIGHTS).astype(np.float32))


@EAOperation
def mutate_all(population: Population) -> Population:
    """Retire every parent and add one mutated child per parent.

    Parameters
    ----------
    population : Population
        The living parents.

    Returns
    -------
    Population
        The retired parents and their children.
    """
    start = time.perf_counter()
    children = []
    for parent in population:
        weights = np.asarray(parent.genotype, dtype=np.float32)
        noise = rng.standard_normal(WEIGHTS).astype(np.float32)
        child = as_list(weights + noise * MUTATION_SCALE)
        children.append(make_individual(child))
        parent.alive = False
    mutation_seconds[0] += time.perf_counter() - start
    return Population(population.to_list() + children)


def one_run(folder: Path) -> tuple[float, float]:
    """Run once and return storage seconds per generation and database MB.

    Parameters
    ----------
    folder : Path
        An empty folder for the database.

    Returns
    -------
    tuple of float
        Seconds of database work per generation, and the file size in MB.
    """
    seed(1)
    database = folder / "bench.db"
    population = Population([
        make_individual(random_weights()) for _ in range(POPULATION)
    ])
    storage = 0.0
    with EA(
        population,
        [mutate_all],
        num_steps=GENERATIONS,
        db_file_path=database,
        quiet=True,
    ) as ea:
        for _ in range(GENERATIONS):
            mutation_seconds[0] = 0.0
            start = time.perf_counter()
            ea.step()
            storage += time.perf_counter() - start - mutation_seconds[0]
    return storage / GENERATIONS, database.stat().st_size / BYTES_PER_MB


def main() -> None:
    """Run the benchmark ``REPEATS`` times and print each run and the median."""
    sys.stdout.write(
        f"{POPULATION} individuals x {WEIGHTS:,} float32 weights, "
        f"{GENERATIONS} generations, list genotypes (JSON)\n"
    )
    seconds: list[float] = []
    sizes: list[float] = []
    for repeat in range(REPEATS):
        with tempfile.TemporaryDirectory() as folder:
            per_generation, size = one_run(Path(folder))
        seconds.append(per_generation)
        sizes.append(size)
        sys.stdout.write(
            f"  run {repeat + 1}: {per_generation:.3f} s storage per "
            f"generation, database {size:.0f} MB\n"
        )
    sys.stdout.write(
        f"median: {statistics.median(seconds):.3f} s per generation, "
        f"{statistics.median(sizes):.0f} MB\n"
    )


if __name__ == "__main__":
    main()
