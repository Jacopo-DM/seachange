"""One-max: evolve 20-bit strings until every bit is 1.

Each generation runs three steps on the population: give every new
individual a fitness, add one mutated child per parent from the better
half, and retire the worst so twenty stay alive. The run is stored in
``__data__/database.db`` under the current folder.
"""

from typing import cast

from seachange import (
    EA,
    EAOperation,
    Individual,
    IntegerMutator,
    IntegersGenerator,
    Population,
)

POPULATION_SIZE = 20
GENOME_LENGTH = 20


def random_individual() -> Individual:
    """Return an individual with a random bit string.

    Returns
    -------
    Individual
        A new, unevaluated individual.
    """
    individual = Individual()
    individual.genotype = IntegersGenerator.integers(
        low=0, high=1, size=GENOME_LENGTH, endpoint=True
    )
    return individual


def evaluate(population: Population) -> Population:
    """Score each new individual by its number of ones.

    Returns
    -------
    Population
        The same population, every member evaluated.
    """
    for individual in population.unevaluated:
        individual.fitness = sum(cast("list[int]", individual.genotype))
    return population


def reproduce(population: Population) -> Population:
    """Add one mutated child for each individual in the better half.

    Returns
    -------
    Population
        The population with the children added.
    """
    for parent in population.best(n=POPULATION_SIZE // 2):
        child = Individual()
        child.genotype = IntegerMutator.random_reset(
            cast("list[int]", parent.genotype),
            low=0,
            high=1,
            mutation_probability=1 / GENOME_LENGTH,
        )
        population.append(child)
    return population


def retire_worst(population: Population) -> Population:
    """Mark all but the best ``POPULATION_SIZE`` individuals as dead.

    Returns
    -------
    Population
        The same population; the dead stay in the database.
    """
    for individual in population.sort()[POPULATION_SIZE:]:
        individual.alive = False
    return population


def main() -> None:
    """Run fifty generations and print the best bit string."""
    first = Population([random_individual() for _ in range(POPULATION_SIZE)])
    ea = EA(
        evaluate(first),
        [
            EAOperation(reproduce),
            EAOperation(evaluate),
            EAOperation(retire_worst),
        ],
        num_steps=50,
    )
    ea.run()

    best = ea.get_solution("best")
    print(f"best fitness {best.fitness} of {GENOME_LENGTH}: {best.genotype}")  # ruff: ignore[print]  # an example shows its result


if __name__ == "__main__":  # pragma: no cover
    main()
