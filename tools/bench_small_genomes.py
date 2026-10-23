"""Time seachange's own cost per generation for small genomes (goal 13).

The multineat planning session's loop benchmark, kept here as goal 13's
measure. A NEAT-sized run: ``SIZE`` parents each make one child by copying
a small genome (5 nodes, 10 links, about 600 bytes of JSON) and nudging its
weights, every child gets a random fitness, and the worst ``SIZE`` retire.
Fitness is free, so nearly all the time is the engine's. Three variants do
the same work and differ only in where the population lives:

native, in memory
    Python lists, no database.
native and batched SQLite
    The lists, plus one ``executemany`` of the new rows and a commit per
    generation, in WAL mode with ``synchronous=NORMAL``: the floor any
    SQLite-backed engine can reach.
seachange
    ``EA.step()``.

Each variant runs ``REPEATS`` times, each run in a new temporary folder; the
script prints the median of the runs' median milliseconds per generation,
and every run's median. The temporary folders follow ``TMPDIR``; point it at
a folder on disk, as ``/tmp`` can be memory and would hide the commit's disk
sync::

    TMPDIR=/var/tmp uv run --no-sync python tools/bench_small_genomes.py

Run nothing else while it runs.
"""

import json
import operator
import sqlite3
import statistics
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import cast

import numpy as np

from seachange import EA, EAOperation, Genotype, Individual, Population

SIZE = 150
GENERATIONS = 100
REPEATS = 5
SECONDS_TO_MS = 1000
NODES = 5
LINKS = 10
WEIGHT_NOISE = 0.1

type Node = list[int | float]
type Link = list[int | float | bool]
type Genome = dict[str, list[Node] | list[Link]]

BASE: Genome = {
    "nodes": [[i, 1, 0.0] for i in range(NODES)],
    "links": [[i, i % 3, 3 + i % 2, 0.5, True] for i in range(LINKS)],
}

rng = np.random.default_rng(0)


def mutate(genome: Genome) -> Genome:
    """Return a copy of ``genome`` with every link weight nudged.

    Parameters
    ----------
    genome : Genome
        Nodes as ``[id, kind, bias]``, links as
        ``[id, source, target, weight, enabled]``.

    Returns
    -------
    Genome
        A new genome; ``genome`` is unchanged.
    """
    links: list[Link] = [
        [
            *link[:3],
            float(link[3]) + float(rng.normal(0, WEIGHT_NOISE)),
            link[4],
        ]
        for link in genome["links"]
    ]
    nodes: list[Node] = [list(node) for node in genome["nodes"]]
    return {"nodes": nodes, "links": links}


def native(database: sqlite3.Connection | None) -> list[float]:
    """Run the loop on Python lists, optionally writing each generation.

    Parameters
    ----------
    database : sqlite3.Connection or None
        A connection with an ``ind`` table to write each generation's
        children to, or ``None`` for no database.

    Returns
    -------
    list[float]
        Seconds per generation.
    """
    population = [(BASE, float(rng.random())) for _ in range(SIZE)]
    seconds = []
    for _ in range(GENERATIONS):
        start = time.perf_counter()
        children = [
            (mutate(genome), float(rng.random())) for genome, _ in population
        ]
        if database is not None:
            database.executemany(
                "INSERT INTO ind (g, f) VALUES (?, ?)",
                [(json.dumps(genome), fit) for genome, fit in children],
            )
            database.commit()
        population = sorted(
            population + children, key=operator.itemgetter(1), reverse=True
        )[:SIZE]
        seconds.append(time.perf_counter() - start)
    return seconds


def native_batched(folder: Path) -> list[float]:
    """Run the loop on lists with one batched SQLite write per generation.

    Parameters
    ----------
    folder : Path
        An empty folder for the database.

    Returns
    -------
    list[float]
        Seconds per generation.
    """
    with closing(sqlite3.connect(folder / "native.db")) as database:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("PRAGMA synchronous=NORMAL")
        database.execute(
            "CREATE TABLE ind (id INTEGER PRIMARY KEY, g TEXT, f REAL)"
        )
        return native(database)


def reproduce(population: Population) -> Population:
    """Give every living individual one mutated, evaluated child.

    Parameters
    ----------
    population : Population
        This generation's individuals.

    Returns
    -------
    Population
        The same population with the children appended.
    """
    for parent in list(population.alive):
        child = Individual()
        child.genotype = cast(
            "Genotype", mutate(cast("Genome", parent.genotype))
        )
        child.fitness = float(rng.random())
        population.append(child)
    return population


def retire(population: Population) -> Population:
    """Retire every living individual below the best ``SIZE``.

    Parameters
    ----------
    population : Population
        This generation's individuals.

    Returns
    -------
    Population
        The same population, the worst marked dead.
    """
    for individual in population.alive.sort()[SIZE:]:
        individual.alive = False
    return population


def seachange_run(folder: Path) -> list[float]:
    """Run the loop as a seachange ``EA`` and time each ``step()``.

    Parameters
    ----------
    folder : Path
        An empty folder for the database.

    Returns
    -------
    list[float]
        Seconds per generation.
    """
    first = []
    for _ in range(SIZE):
        individual = Individual()
        individual.genotype = cast("Genotype", BASE)
        individual.fitness = float(rng.random())
        first.append(individual)
    seconds = []
    with EA(
        Population(first),
        [EAOperation(reproduce), EAOperation(retire)],
        num_steps=GENERATIONS,
        db_file_path=folder / "seachange.db",
        quiet=True,
    ) as ea:
        for _ in range(GENERATIONS):
            start = time.perf_counter()
            ea.step()
            seconds.append(time.perf_counter() - start)
    return seconds


def report(label: str, runs: list[list[float]]) -> None:
    """Write the median milliseconds per generation of ``runs``.

    Parameters
    ----------
    label : str
        The variant's name.
    runs : list[list[float]]
        Seconds per generation, one list per run.
    """
    medians = [statistics.median(run) * SECONDS_TO_MS for run in runs]
    each = " ".join(f"{median:.2f}" for median in medians)
    sys.stdout.write(
        f"{label:28s} median {statistics.median(medians):7.2f} ms/gen   "
        f"runs {each}\n"
    )


def main() -> None:
    """Run every variant ``REPEATS`` times and write the medians."""
    report("native, in memory", [native(None) for _ in range(REPEATS)])
    batched, engine = [], []
    for _ in range(REPEATS):
        with tempfile.TemporaryDirectory() as folder:
            batched.append(native_batched(Path(folder)))
    report("native + batch SQLite (WAL)", batched)
    for _ in range(REPEATS):
        with tempfile.TemporaryDirectory() as folder:
            engine.append(seachange_run(Path(folder)))
    report("seachange", engine)
    sys.stdout.write(
        f"python {sys.version.split()[0]}, {SIZE} children/gen, "
        f"{GENERATIONS} gens, {REPEATS} runs, temp folders in "
        f"{tempfile.gettempdir()}\n"
    )


if __name__ == "__main__":
    main()
