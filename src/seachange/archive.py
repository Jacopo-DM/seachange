"""Archive: read-only query interface for a persisted EA database."""

from pathlib import Path
from types import TracebackType
from typing import Self, cast

import numpy as np
from sqlalchemy import Engine, create_engine, func
from sqlalchemy.orm import make_transient
from sqlmodel import Session, col, select
from sqlmodel.sql.expression import SelectOfScalar

from seachange._rng import py_rng
from seachange.codecs import Genotype
from seachange.ea_database import file_identity
from seachange.ea_settings import Direction
from seachange.individual import (
    GenotypeSource,
    Individual,
    check_rows,
    genotype_layout,
)
from seachange.model import Model
from seachange.population import Population

type AgeRange = tuple[int, int] | None
type FitnessRange = tuple[float, float] | None


class GenerationRange(Model):
    """The generations a run's archive spans.

    Attributes
    ----------
    first : int
        Earliest ``time_of_birth`` in the archive.
    last : int
        Latest ``time_of_death`` in the archive.
    """

    first: int
    last: int


class FitnessStats(Model):
    """Summary statistics of the fitness of archived individuals.

    Every field is ``NaN`` when no individual matched.

    Attributes
    ----------
    min, max, mean, std, median : float
        The statistic of the matching individuals' fitness.
    """

    min: float
    max: float
    mean: float
    std: float
    median: float


class Archive[G = Genotype]:
    """Read-only interface to a persisted EA database.

    Opens a SQLite database written by the EA engine and exposes targeted
    query methods for retrieving archived individuals. Particularly useful
    for injecting historically successful individuals back into a
    stagnating population.

    ``G`` is the genotype type of the run, for type checkers:
    ``Archive[NDArray[np.float32]](path)`` returns individuals whose
    ``genotype`` is a float32 array. Plain ``Archive(path)`` means
    ``Genotype``.

    Parameters
    ----------
    db_path : Path or str
        Path to the SQLite ``.db`` file produced by an EA run.

    Examples
    --------
    >>> archive = Archive("__data__/run_1/database.db")
    >>> ind = archive.random_individual(birth_range=(0, 30))
    >>> pop = archive.tournament_population(n=10, direction="max")
    >>> hall = archive.hall_of_fame(n=5, direction="min")
    """

    def __init__(self, db_path: Path | str) -> None:
        """Open the archive database at `db_path`; raise if it is missing.

        Raises
        ------
        FileNotFoundError
            If the database file does not exist.
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            msg = f"Archive database not found: {self.db_path}"
            raise FileNotFoundError(msg)
        self.engine: Engine = create_engine(f"sqlite:///{self.db_path}")
        with self.engine.connect() as connection:
            self._layout = genotype_layout(connection)
            self._identity = file_identity(connection)

    # -- Internal helpers ------------------------------------------------------

    @staticmethod
    def _base_query(
        *,
        birth_range: AgeRange = None,
        death_range: AgeRange = None,
        fitness_range: FitnessRange = None,
        alive_filter: bool | None = None,
    ) -> SelectOfScalar[Individual]:
        """Construct a base SQL query with optional filters.

        Parameters
        ----------
        birth_range : (int, int) or None, optional
            Inclusive ``(low, high)`` filter on ``time_of_birth``.
        death_range : (int, int) or None, optional
            Inclusive ``(low, high)`` filter on ``time_of_death``.
        fitness_range : (float, float) or None, optional
            Inclusive ``(low, high)`` filter on raw ``fitness_``.
        alive_filter : bool or None, optional
            ``True`` restricts to living individuals, ``False`` to dead ones,
            ``None`` applies no filter. Default is ``None``.

        Returns
        -------
        SelectOfScalar[Individual]
            SQLModel Select statement with the specified filters applied.
        """
        statement = select(Individual)

        if alive_filter is not None:
            statement = statement.where(
                Individual.alive == alive_filter,
            )
        statement = statement.where(Individual.requires_eval == False)  # ruff: ignore[true-false-comparison]
        if birth_range is not None:
            lo, hi = birth_range
            statement = statement.where(Individual.time_of_birth >= lo).where(
                Individual.time_of_birth <= hi,
            )
        if death_range is not None:
            lo, hi = death_range
            statement = statement.where(Individual.time_of_death >= lo).where(
                Individual.time_of_death <= hi,
            )
        if fitness_range is not None:
            fit_lo, fit_hi = fitness_range
            statement = statement.where(
                col(Individual.fitness_) >= fit_lo
            ).where(
                col(Individual.fitness_) <= fit_hi,
            )

        return statement

    def _fetch_all(
        self, statement: SelectOfScalar[Individual]
    ) -> list[Individual[G]]:
        with Session(self.engine) as session:
            rows = check_rows(session.exec(statement).all())
        self._read_genotypes_later(rows)
        # The run stored these rows, so their genotypes are of G
        return cast("list[Individual[G]]", rows)

    def _draw(
        self, statement: SelectOfScalar[Individual], n: int
    ) -> list[Individual[G]]:
        # Pick up to n matching rows with py_rng, so seed() repeats the draw.
        # Ids are read in a fixed order; only the picked rows are loaded.
        id_column = col(Individual.id)
        with Session(self.engine) as session:
            ids: list[int | None] = list(
                session.scalars(
                    statement.with_only_columns(id_column).order_by(id_column)
                ).all()
            )
            picked = py_rng.sample(ids, min(n, len(ids)))
            by_id = {
                row.id: row
                for row in check_rows(
                    session.exec(
                        select(Individual).where(id_column.in_(picked))
                    ).all()
                )
            }
        drawn = [by_id[row_id] for row_id in picked]
        self._read_genotypes_later(drawn)
        return cast("list[Individual[G]]", drawn)

    def _read_genotypes_later(self, rows: list[Individual]) -> None:
        # Each genotype is read from the file when first asked for. The ids
        # go, and with them SQLAlchemy's key for this file's row, so
        # callers may add these to a new run as new rows.
        path = self.db_path.resolve()
        for ind in rows:
            ind.read_genotype_from(
                GenotypeSource(
                    path=path,
                    row_id=cast("int", ind.id),
                    layout=self._layout,
                    identity=self._identity,
                )
            )
            make_transient(ind)
            ind.id = None

    # -- Single-individual queries ---------------------------------------------

    def random_individual(
        self,
        *,
        birth_range: AgeRange = None,
        death_range: AgeRange = None,
        fitness_range: FitnessRange = None,
        only_dead: bool = False,
    ) -> Individual[G]:
        """Return a single uniformly-random archived individual.

        Parameters
        ----------
        birth_range : (int, int) or None, optional
            Inclusive ``(lo, hi)`` filter on ``time_of_birth``.
        death_range : (int, int) or None, optional
            Inclusive ``(lo, hi)`` filter on ``time_of_death``.
        fitness_range : (float, float) or None, optional
            Inclusive ``(lo, hi)`` filter on raw ``fitness_``.
        only_dead : bool, optional
            Restrict to individuals that are no longer alive. Default ``False``.

        Returns
        -------
        Individual

        Raises
        ------
        ValueError
            If no individuals match the supplied filters.
        """
        statement = self._base_query(
            birth_range=birth_range,
            death_range=death_range,
            fitness_range=fitness_range,
            alive_filter=False if only_dead else None,
        )

        results = self._draw(statement, 1)
        if not results:
            msg = "No individuals match the given filters."
            raise ValueError(msg)
        return results[0]

    def best_individual(
        self,
        *,
        direction: Direction,
        birth_range: AgeRange = None,
        death_range: AgeRange = None,
    ) -> Individual[G]:
        """Return the single best individual in the archive.

        Parameters
        ----------
        direction : {"max", "min"}
            ``"min"`` returns the lowest-fitness individual (minimisation);
            ``"max"`` returns the highest (maximisation). Required: the
            archive does not know which way the run optimised.
        birth_range : (int, int) or None, optional
        death_range : (int, int) or None, optional

        Returns
        -------
        Individual

        Raises
        ------
        ValueError
            If the archive contains no evaluated individuals.
        """
        statement = self._base_query(
            birth_range=birth_range,
            death_range=death_range,
        )
        match direction:
            case "min":
                statement = statement.order_by(col(Individual.fitness_).asc())
            case "max":
                statement = statement.order_by(col(Individual.fitness_).desc())
        statement = statement.limit(1)

        results = self._fetch_all(statement)
        if not results:
            msg = "No evaluated individuals found in the archive."
            raise ValueError(msg)
        return results[0]

    # -- Population queries ----------------------------------------------------

    def random_population(
        self,
        n: int,
        *,
        birth_range: AgeRange = None,
        death_range: AgeRange = None,
        fitness_range: FitnessRange = None,
        only_dead: bool = False,
    ) -> Population[G]:
        """Return a uniformly-random sample of up to ``n`` archived individuals.

        Parameters
        ----------
        n : int
            Number of individuals to return.
        birth_range : (int, int) or None, optional
        death_range : (int, int) or None, optional
        fitness_range : (float, float) or None, optional
        only_dead : bool, optional

        Returns
        -------
        Population
            May be smaller than ``n`` if fewer matching individuals exist.
        """
        statement = self._base_query(
            birth_range=birth_range,
            death_range=death_range,
            fitness_range=fitness_range,
            alive_filter=False if only_dead else None,
        )

        return Population(self._draw(statement, n))

    def hall_of_fame(
        self,
        n: int = 10,
        *,
        direction: Direction,
        birth_range: AgeRange = None,
        death_range: AgeRange = None,
    ) -> Population[G]:
        """Return the all-time ``n`` best individuals from the archive.

        Parameters
        ----------
        n : int, optional
            Size of the hall of fame. Default is ``10``.
        direction : {"max", "min"}
            Optimisation direction. Required.
        birth_range : (int, int) or None, optional
        death_range : (int, int) or None, optional

        Returns
        -------
        Population
        """
        statement = self._base_query(
            birth_range=birth_range,
            death_range=death_range,
        )
        match direction:
            case "min":
                statement = statement.order_by(col(Individual.fitness_).asc())
            case "max":
                statement = statement.order_by(col(Individual.fitness_).desc())
        statement = statement.limit(n)

        return Population(self._fetch_all(statement))

    def tournament_population(  # ruff: ignore[too-many-arguments]  # signature kept as copied from ARIEL
        self,
        n: int,
        tournament_size: int = 3,
        *,
        direction: Direction,
        birth_range: AgeRange = None,
        death_range: AgeRange = None,
        pool_multiplier: int = 4,
    ) -> Population[G]:
        """Select ``n`` individuals via repeated tournament selection.

        Fetches a candidate pool of ``n * pool_multiplier`` individuals from
        the database at random, then runs ``n`` tournaments of
        ``tournament_size`` over that pool. This is the core mechanism
        behind the J.E.S.U.S. strategy.

        Parameters
        ----------
        n : int
            Number of tournament winners to return.
        tournament_size : int, optional
            Number of competitors drawn per tournament. Default is ``3``.
        direction : {"max", "min"}
            ``"min"`` picks the lowest-fitness contestant as the winner
            (minimisation problem). ``"max"`` picks the highest. Required.
        birth_range : (int, int) or None, optional
        death_range : (int, int) or None, optional
        pool_multiplier : int, optional
            Pool size relative to ``n``; larger values increase draw
            diversity at the cost of a bigger DB fetch. Default is ``4``.

        Returns
        -------
        Population
            A population of ``n`` tournament winners.

        Raises
        ------
        ValueError
            If the fetched pool is empty.
        AssertionError
            If ``tournament_size`` exceeds the pool size.
        """
        pool = self.random_population(
            n * pool_multiplier,
            birth_range=birth_range,
            death_range=death_range,
        )
        pool_list = pool.to_list()

        if not pool_list:
            msg = "No individuals match the given filters."
            raise ValueError(msg)

        if tournament_size > len(pool_list):
            msg = (
                f"tournament_size={tournament_size} "
                f"exceeds pool size={len(pool_list)}."
            )
            raise AssertionError(msg)

        def _key(ind: Individual[G]) -> float:
            return ind.fitness_ if ind.fitness_ is not None else float("inf")

        sample_size = min(tournament_size, len(pool_list))
        if direction == "min":
            winners = [
                min(py_rng.sample(pool_list, sample_size), key=_key)
                for _ in range(n)
            ]
        else:
            winners = [
                max(py_rng.sample(pool_list, sample_size), key=_key)
                for _ in range(n)
            ]
        return Population(winners)

    def by_generation(self, generation: int) -> Population[G]:
        """Return all individuals present at a given generation.

        An individual was alive at ``generation`` if it was born at or
        before it and died at or after it.

        Parameters
        ----------
        generation : int
            The generation index to query.

        Returns
        -------
        Population
        """
        statement = (
            select(Individual)
            .where(Individual.requires_eval == False)  # ruff: ignore[true-false-comparison]
            .where(Individual.time_of_birth <= generation)
            .where(Individual.time_of_death >= generation)
        )
        return Population(self._fetch_all(statement))

    def fitness_percentile_population(
        self,
        lo_pct: float = 25.0,
        hi_pct: float = 75.0,
        n: int | None = None,
        *,
        birth_range: AgeRange = None,
    ) -> Population[G]:
        """Return individuals whose fitness falls within a percentile band.

        Useful for sampling "mediocre-but-interesting" individuals rather
        than always drawing from the elite tail, which can help preserve
        morphological diversity in the resurrected pool.

        Parameters
        ----------
        lo_pct : float, optional
            Lower percentile bound (0-100). Default is ``25.0``.
        hi_pct : float, optional
            Upper percentile bound (0-100). Default is ``75.0``.
        n : int or None, optional
            If given, randomly sample ``n`` individuals from the band.
            When ``None`` all matching individuals are returned.
        birth_range : (int, int) or None, optional

        Returns
        -------
        Population
        """
        all_inds = self._fetch_all(self._base_query(birth_range=birth_range))
        if not all_inds:
            return Population([])

        fitnesses = np.array([ind.fitness_ for ind in all_inds], dtype=float)
        lo_val = float(np.percentile(fitnesses, lo_pct))
        hi_val = float(np.percentile(fitnesses, hi_pct))

        band = [
            ind
            for ind in all_inds
            if ind.fitness_ is not None and lo_val <= ind.fitness_ <= hi_val
        ]
        if n is not None:
            band = py_rng.sample(band, min(n, len(band)))
        return Population(band)

    # -- Statistics / introspection --------------------------------------------

    @property
    def size(self) -> int:
        """Total number of evaluated individuals stored in the archive."""
        with Session(self.engine) as session:
            return session.exec(
                select(func.count(col(Individual.id))).where(
                    Individual.requires_eval == False,  # ruff: ignore[true-false-comparison]
                ),
            ).one()

    @property
    def generation_range(self) -> GenerationRange:
        """The earliest birth and latest death in the archive.

        Returns
        -------
        GenerationRange
            ``first`` and ``last`` generation; both ``0`` when empty.
        """
        with Session(self.engine) as session:
            min_birth = session.exec(
                select(func.min(Individual.time_of_birth)),
            ).one()
            max_death = session.exec(
                select(func.max(Individual.time_of_death)),
            ).one()
        return GenerationRange(first=min_birth or 0, last=max_death or 0)

    def fitness_stats(self, birth_range: AgeRange = None) -> FitnessStats:
        """Return summary fitness statistics for archived individuals.

        Parameters
        ----------
        birth_range : (int, int) or None, optional
            Restrict statistics to individuals born in this range.

        Returns
        -------
        FitnessStats
            ``min``, ``max``, ``mean``, ``std`` and ``median``; all ``NaN``
            when no matching individuals exist.
        """
        inds = self._fetch_all(self._base_query(birth_range=birth_range))
        if not inds:
            nan = float("nan")
            return FitnessStats(min=nan, max=nan, mean=nan, std=nan, median=nan)

        fitnesses = np.array([ind.fitness_ for ind in inds], dtype=float)
        return FitnessStats(
            min=float(np.min(fitnesses)),
            max=float(np.max(fitnesses)),
            mean=float(np.mean(fitnesses)),
            std=float(np.std(fitnesses)),
            median=float(np.median(fitnesses)),
        )

    def close(self) -> None:
        """Release the database connection.

        The archive can still be read afterwards; the next query opens a new
        connection, which ``close`` releases again.
        """
        self.engine.dispose()

    def __enter__(self) -> Self:
        """Return this archive, to be closed when the ``with`` block ends.

        Returns
        -------
        Self
            This archive.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the archive when the ``with`` block ends."""
        self.close()

    def __repr__(self) -> str:
        """Return a string representation of the archive.

        Returns
        -------
        str
            A string representation of the archive.
        """
        return f"Archive(path={self.db_path!r}, size={self.size})"
