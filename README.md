# seachange

seachange runs generational evolutionary algorithms and keeps every individual in a SQLite database. You write each step of a generation (evaluate, select, mutate, retire) as a plain function that takes a population and returns one. The engine runs those functions in order once per generation and saves the result. Because every generation is on disk, you can stop a run, query it afterwards, or restart it from any generation.

It started as the evolution engine of [ARIEL](https://github.com/ci-group/ariel), a robot evolution framework, and holds the parts that have nothing to do with robots: the engine, random generators and mutators for integer and float genomes, crossover operators, and a RevDE optimizer.

## Installation

seachange needs Python 3.13 or later. It is not on PyPI yet, so install it from a local clone:

```bash
git clone <repository URL> seachange
uv add ./seachange
```

## Example

One-max: evolve 20-bit strings until every bit is 1. Each generation adds one mutated child per parent from the better half, scores the new individuals, and retires the worst so twenty stay alive.

```python
from typing import cast

from seachange import (
    EA,
    EAOperation,
    Individual,
    IntegerMutator,
    IntegersGenerator,
    Population,
)

SIZE, LENGTH = 20, 20


def random_individual() -> Individual:
    individual = Individual()
    individual.genotype = IntegersGenerator.integers(
        low=0, high=1, size=LENGTH, endpoint=True
    )
    return individual


def evaluate(population: Population) -> Population:
    for individual in population.unevaluated:
        individual.fitness = sum(cast("list[int]", individual.genotype))
    return population


def reproduce(population: Population) -> Population:
    for parent in population.best(n=SIZE // 2):
        child = Individual()
        child.genotype = IntegerMutator.random_reset(
            cast("list[int]", parent.genotype),
            low=0,
            high=1,
            mutation_probability=1 / LENGTH,
        )
        population.append(child)
    return population


def retire_worst(population: Population) -> Population:
    for individual in population.sort()[SIZE:]:
        individual.alive = False
    return population


first = Population([random_individual() for _ in range(SIZE)])
ea = EA(
    evaluate(first),
    [EAOperation(reproduce), EAOperation(evaluate), EAOperation(retire_worst)],
    num_steps=50,
)
ea.run()
print(ea.get_solution("best").genotype)
```

It prints a progress bar and then the best bit string, all ones after 50 generations. The run is saved in `__data__/database.db` under the current folder; pass `db_file_path=` to `EA` to put it elsewhere. The same example, documented, is in [examples/a1_one_max.py](examples/a1_one_max.py).

To continue a saved run, pass its database to `EA.restart` and give the new run its own file:

```python
from pathlib import Path

ea = EA.restart(
    "__data__/database.db",
    operations,
    db_file_path=Path("__data__/continued.db"),
)
```

Without `db_file_path`, the new run would write to the default `__data__/database.db`, the file you are restarting from, so `EA.restart` raises `ValueError` instead of overwriting it. Pass `generation=` to continue from an earlier generation.

## Documentation

Every public class and function has a NumPy-style docstring. The Sphinx sources are in [docs/](docs/).
