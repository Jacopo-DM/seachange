"""Small individuals, populations and EAs shared by the EA tests."""

from collections.abc import Sequence
from pathlib import Path

from seachange import EA, EAOperation
from seachange.ea_operation import Operation
from seachange.individual import Individual
from seachange.population import Population

DEFAULT_NUM_STEPS = 100
DEFAULT_POPULATION_SIZE = 100
CUSTOM_NUM_STEPS = 50
SIZE_BEFORE_DOUBLING = 3
SIZE_AFTER_DOUBLING = 2 * SIZE_BEFORE_DOUBLING
INITIAL_POP_SIZE = 5
FIRST_GENERATION_ID = 10
ALIVE_COUNT = 6
STEPS_TAKEN = 2
NUM_STEPS_RUN = 5


def make_ind(i: int) -> Individual:
    ind = Individual()
    ind.genotype = [float(i)]
    ind.fitness = float(i)
    return ind


def make_pop(n: int = 4) -> Population:
    return Population([make_ind(i) for i in range(n)])


@EAOperation
def noop(population: Population) -> Population:
    return population


@EAOperation
def double_pop(population: Population) -> Population:
    return Population(population.to_list() + population.to_list())


def make_ea(
    tmp_path: Path,
    pop: Population | None = None,
    ops: Sequence[Operation] | None = None,
    *,
    num_steps: int | None = None,
    first_generation_id: int | None = None,
) -> EA:
    return EA(
        population=pop or make_pop(),
        operations=ops or [noop],
        db_file_path=tmp_path / "test.db",
        quiet=True,
        num_steps=num_steps,
        first_generation_id=first_generation_id,
    )
