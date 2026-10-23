"""Test: keep_genotypes decides which genotypes outlive their individual."""

from pathlib import Path

import numpy as np
import pytest
from sqlmodel import Session, create_engine, select

from seachange import (
    EA,
    Direction,
    EAOperation,
    EASettings,
    Genotype,
    Individual,
    Population,
    Rank,
)
from seachange.individual import KeptGenotype
from tests.ea_helpers import make_pop, noop
from tests.misuse import untyped

pytestmark = pytest.mark.usefixtures("dispose_engines")

POPULATION_SIZE = 6
CHILDREN = 3
GENERATIONS = 5
SEED = 3


def replace_worst(rng: np.random.Generator) -> EAOperation[[], Genotype]:
    """Return an operation that replaces the three lowest-fitness members.

    Returns
    -------
    EAOperation
        Retires the three lowest and adds three evaluated children, each
        with a fitness no other individual has (with probability 1).
    """

    def replace(population: Population) -> Population:
        for individual in population.sort(direction="min")[:CHILDREN]:
            individual.alive = False
        for _ in range(CHILDREN):
            child = Individual()
            child.genotype = [float(rng.random())]
            child.fitness = float(rng.random())
            population.append(child)
        return population

    return EAOperation(replace)


def _run(
    path: Path,
    keep: tuple[Rank, ...] | None,
    direction: Direction = "max",
) -> None:
    rng = np.random.default_rng(SEED)
    pop = make_pop(POPULATION_SIZE)
    for individual in pop:
        individual.fitness = float(rng.random())
    with EA(
        pop,
        [replace_worst(rng)],
        db_file_path=path,
        num_steps=GENERATIONS,
        direction=direction,
        keep_genotypes=keep,
        quiet=True,
    ) as ea:
        ea.run()


def _rows(path: Path) -> list[Individual]:
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as session:
        rows = list(session.exec(select(Individual)))
    engine.dispose()
    return rows


def _kept_rows(path: Path) -> list[KeptGenotype]:
    engine = create_engine(f"sqlite:///{path}")
    with Session(engine) as session:
        rows = list(session.exec(select(KeptGenotype)))
    engine.dispose()
    return rows


def _expected(
    rows: list[Individual], ranks: tuple[Rank, ...], direction: Direction
) -> set[int | None]:
    # The living, plus each generation's ranked individuals, from the rows
    keep = {row.id for row in rows if row.alive}
    for generation in range(GENERATIONS + 1):
        present = sorted(
            (
                row
                for row in rows
                if row.time_of_birth <= generation <= row.time_of_death
            ),
            key=lambda row: row.fitness,
            reverse=direction == "max",
        )
        position = {"best": 0, "median": len(present) // 2, "worst": -1}
        keep |= {present[position[rank]].id for rank in ranks}
    return keep


@pytest.mark.parametrize(
    "ranks",
    [(), ("best",), ("worst",), ("median",), ("best", "median", "worst")],
)
@pytest.mark.parametrize("direction", ["max", "min"])
def test_a_run_keeps_the_living_and_the_ranked(
    tmp_path: Path, ranks: tuple[Rank, ...], direction: Direction
) -> None:
    """A genotype stays exactly when its individual lives or was ranked."""
    _run(tmp_path / "run.db", ranks, direction)
    rows = _rows(tmp_path / "run.db")
    expected = _expected(rows, ranks, direction)
    assert {row.id for row in rows if row.genotype_ is not None} == expected
    assert len(_kept_rows(tmp_path / "run.db")) == len(ranks) * (
        GENERATIONS + 1
    )


def test_all_keeps_every_genotype(tmp_path: Path) -> None:
    """The default keeps every genotype and records no ranks."""
    _run(tmp_path / "run.db", None)
    rows = _rows(tmp_path / "run.db")
    assert all(row.genotype_ is not None for row in rows)
    assert _kept_rows(tmp_path / "run.db") == []


def test_a_dropped_genotype_cannot_be_read(tmp_path: Path) -> None:
    """Reading a dropped genotype says it was not kept."""
    _run(tmp_path / "run.db", ())
    dropped = next(row for row in _rows(tmp_path / "run.db") if not row.alive)
    with pytest.raises(ValueError, match="was not kept"):
        _ = dropped.genotype


def test_an_unevaluated_generation_ranks_nobody(tmp_path: Path) -> None:
    """With nobody evaluated, a generation records no rank."""
    pop = Population([Individual() for _ in range(2)])
    for individual in pop:
        individual.genotype = [1.0]
    EA(
        pop,
        [noop],
        db_file_path=tmp_path / "run.db",
        keep_genotypes=["best"],
        quiet=True,
    ).close()
    assert _kept_rows(tmp_path / "run.db") == []


@pytest.mark.parametrize("keep", ["best", ["best", "top"]])
def test_keep_genotypes_must_name_ranks(tmp_path: Path, keep: object) -> None:
    """A string other than "all", or an unknown rank, is refused."""
    with pytest.raises(ValueError, match="keep_genotypes must be"):
        untyped(EA)(
            make_pop(),
            [noop],
            db_file_path=tmp_path / "run.db",
            keep_genotypes=keep,
            quiet=True,
        )


def test_keep_genotypes_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEACHANGE_KEEP_GENOTYPES takes "all" or a JSON list of ranks."""
    monkeypatch.setenv("SEACHANGE_KEEP_GENOTYPES", '["best", "worst"]')
    assert EASettings().keep_genotypes == ("best", "worst")
    monkeypatch.setenv("SEACHANGE_KEEP_GENOTYPES", "all")
    assert EASettings().keep_genotypes == "all"


def test_restart_needs_the_survivors_genotypes(tmp_path: Path) -> None:
    """Only the latest generation can restart a run that dropped genotypes."""
    _run(tmp_path / "run.db", ())
    with pytest.raises(ValueError, match="did not keep the genotypes"):
        EA.restart(
            tmp_path / "run.db",
            [noop],
            generation=1,
            db_file_path=tmp_path / "restarted.db",
            quiet=True,
        )
    EA.restart(
        tmp_path / "run.db",
        [noop],
        db_file_path=tmp_path / "restarted.db",
        quiet=True,
    ).close()


@EAOperation
def retire_all(population: Population) -> Population:
    # Retire everyone, so the next generation is empty
    for individual in population:
        individual.alive = False
    return population


def test_restart_carries_the_kept_records(tmp_path: Path) -> None:
    """A survivor ranked before the restart keeps its genotype after it."""
    _run(tmp_path / "run.db", ("best",))
    ranked = {row.individual_id for row in _kept_rows(tmp_path / "run.db")}
    with EA.restart(
        tmp_path / "run.db",
        [retire_all],
        num_steps=1,
        db_file_path=tmp_path / "restarted.db",
        keep_genotypes=[],
        quiet=True,
    ) as restarted:
        survivors = {ind.id for ind in restarted.population}
        restarted.run()
    rows = {row.id: row for row in _rows(tmp_path / "restarted.db")}
    # The new run ranks nothing, so only the copied records protect
    for key in survivors:
        assert (rows[key].genotype_ is not None) == (key in ranked)
    assert survivors & ranked
    assert survivors - ranked
