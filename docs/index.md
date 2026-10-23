# seachange

seachange runs generational evolutionary algorithms and keeps every individual in a SQLite database. You write each step of a generation (evaluate, select, mutate, retire) as a plain function that takes a population and returns one; the engine runs those steps once per generation and saves the result, so you can stop a run, query it afterwards with `Archive`, or restart it from any generation. It is for researchers who evolve bit strings, number vectors or neural network weights, stored as lists or numpy arrays, and it holds the evolution engine of the robot framework [ARIEL](https://github.com/ci-group/ariel).

## Quick start

```console
$ uv add seachange
```

One-max: evolve 20-bit strings until every bit is 1. Each generation scores the new individuals, adds one mutated child per parent from the better half, and retires the worst so twenty stay alive. This is `examples/a1_one_max.py`, which the test suite runs:

```{literalinclude} ../examples/a1_one_max.py
:language: python
```

It shows a progress bar, then prints the best individual:

```text
best fitness 20.0 of 20: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
```

The run is saved in `__data__/database.db` under the current folder. [Genotypes and how they are stored](genotypes.md) covers numpy genotypes, type checking and your own genotype types; [How far SQLite storage goes](limits.md) gives the measured limits on genotype size and parallel writes; the reference lists every class and function.

```{toctree}
:maxdepth: 2
:caption: Contents

genotypes
limits
reference
```
