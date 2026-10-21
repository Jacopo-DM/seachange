"""The EA class."""

from collections.abc import Sequence
from pathlib import Path
from types import TracebackType
from typing import Literal, Self, cast

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
)
from sqlalchemy import Engine, create_engine, func
from sqlmodel import Session, col, or_, select

from seachange.codecs import Genotype
from seachange.ea_database import setup_database
from seachange.ea_operation import Operation
from seachange.ea_settings import DBHandlingMode, Direction, config
from seachange.individual import Individual, check_rows
from seachange.population import Population


class EA[G = Genotype]:
    """
    Generational evolutionary algorithm engine.

    ``G`` is the genotype type of the run, for type checkers. It is read
    from the population and operations, so ``EA(population, ops)`` with a
    ``Population[NDArray[np.float32]]`` is an ``EA[NDArray[np.float32]]``.

    Each call to ``step()`` / ``run()`` executes the ordered list of
    ``EAOperation`` operations against the current population, then persists
    the result to a SQLite database via SQLModel.

    Parameters
    ----------
    population : Population
        Initial population.
    operations : Sequence[Operation]
        Ordered pipeline of operations executed once per generation.
    num_steps : int or None, optional
        Total number of generational steps to run. Falls back to
        ``config.num_steps`` when ``None``. Default is ``None``.
    first_generation_id : int or None, optional
        Starting value of the internal generation counter. Falls back to
        ``config.first_generation_id`` when ``None``. Default is ``None``.
    direction : {"max", "min"} or None, optional
        ``"max"`` when higher fitness is better, ``"min"`` when lower is.
        Determines the ranking used by ``get_solution``. Falls back to
        ``config.direction`` when ``None``. Default is ``None``.
    quiet : bool or None, optional
        Suppress Rich console output. Falls back to ``config.quiet`` when
        ``None``. Default is ``None``.
    db_file_path : Path or None, optional
        Path at which the SQLite database is created. Falls back to
        ``config.db_file_path`` when ``None``. Default is ``None``.
    db_handling : DBHandlingMode or None, optional
        Behaviour when a database already exists at ``db_file_path``. Falls
        back to ``config.db_handling`` when ``None``. Default is ``None``.

    Examples
    --------
    Fresh run:

    >>> ops = [EAOperation(evaluate), EAOperation(survivor_selection)]
    >>> ea = EA(Population(initial_individuals), ops, num_steps=200)
    >>> ea.run()

    Continue a recorded run from its latest generation, in a new file:

    >>> ea = EA.restart(
    ...     "__data__/run_1/database.db",
    ...     ops,
    ...     db_file_path=Path("__data__/run_2/database.db"),
    ... )
    >>> ea.run()

    Continue from a specific generation:

    >>> ea = EA.restart("__data__/run_1/database.db", ops, generation=50, ...)
    """

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        population: Population[G],
        operations: Sequence[Operation[G]],
        *,
        num_steps: int | None = None,
        first_generation_id: int | None = None,
        direction: Direction | None = None,
        quiet: bool | None = None,
        db_file_path: Path | None = None,
        db_handling: DBHandlingMode | None = None,
    ) -> None:
        """Start a new run from ``population``."""
        self.operations: Sequence[Operation[G]] = operations
        self.direction: Direction = (
            direction if direction is not None else config.direction
        )
        self.current_generation: int = (
            first_generation_id
            if first_generation_id is not None
            else config.first_generation_id
        )
        self.num_steps: int = (
            num_steps if num_steps is not None else config.num_steps
        )
        self.console: Console = Console(
            quiet=quiet if quiet is not None else config.quiet,
        )
        self.engine: Engine = setup_database(
            db_file_path=db_file_path or config.db_file_path,
            db_handling=db_handling or config.db_handling,
            console=self.console,
        )
        self.population: Population[G] = population
        self._commit()
        self.console.rule("[blue]EA Initialized")

    # A static method with its own H: on the bare class, ty would fill a
    # class method's G with its default instead of reading the operations
    @staticmethod
    def restart[H](  # ruff: ignore[too-many-arguments]
        source: Path | str,
        operations: Sequence[Operation[H]],
        *,
        generation: int | None = None,
        num_steps: int | None = None,
        first_generation_id: int | None = None,
        direction: Direction | None = None,
        quiet: bool | None = None,
        db_file_path: Path | None = None,
        db_handling: DBHandlingMode | None = None,
    ) -> "EA[H]":
        """Continue a recorded run in a new database.

        Reads the evaluated individuals that survived ``generation`` in
        ``source`` (born by then and not retired during or before it) and
        starts a new run with them. The other keywords are
        those of ``EA``.

        Parameters
        ----------
        source : Path or str
            Database of the run to continue. It is only read.
        operations : Sequence[Operation]
            Ordered pipeline of operations executed once per generation.
        generation : int or None, optional
            Generation to continue from. Default is ``None``: the latest
            recorded generation.
        num_steps : int or None, optional
            As for ``EA``.
        first_generation_id : int or None, optional
            As for ``EA``, but defaults to ``generation + 1``.
        direction : {"max", "min"} or None, optional
            As for ``EA``.
        quiet : bool or None, optional
            As for ``EA``.
        db_file_path : Path or None, optional
            As for ``EA``. Must not be ``source``.
        db_handling : DBHandlingMode or None, optional
            As for ``EA``.

        Returns
        -------
        Self
            The new run, ready to ``run()``.

        Raises
        ------
        FileNotFoundError
            If ``source`` does not exist.
        ValueError
            If ``source`` is the file the new run would write to, holds no
            individuals, or has no evaluated individuals at ``generation``.
        """
        source_db = Path(source)
        target_db = db_file_path or config.db_file_path
        if not source_db.exists():
            msg = f"Restart database not found: {source_db}"
            raise FileNotFoundError(msg)
        if source_db.resolve() == target_db.resolve():
            msg = (
                "restart source and db_file_path are the same file "
                f"({source_db}); pass db_file_path= to write the new "
                "run elsewhere"
            )
            raise ValueError(msg)

        source_engine = create_engine(f"sqlite:///{source_db}")
        try:
            with Session(source_engine) as session:
                if generation is None:
                    # MAX over no rows is NULL, which the column type hides
                    latest = cast(
                        "int | None",
                        session.exec(
                            select(func.max(Individual.time_of_death))
                        ).one(),
                    )
                    if latest is None:
                        msg = "Source database contains no individuals."
                        raise ValueError(msg)
                    generation = latest

                rows = check_rows(
                    session.exec(
                        select(Individual)
                        .where(Individual.time_of_birth <= generation)
                        .where(Individual.time_of_death >= generation)
                        # Survivors only: those retired in this generation
                        # keep time_of_death == generation but are not alive
                        .where(
                            or_(
                                Individual.time_of_death > generation,
                                col(Individual.alive),
                            )
                        )
                        .where(Individual.requires_eval == False)  # ruff: ignore[true-false-comparison]
                    ).all()
                )
        finally:
            # Release the pooled connection; the engine is not used again
            source_engine.dispose()

        if not rows:
            msg = (
                f"No evaluated individuals at generation {generation} "
                f"in {source_db}."
            )
            raise ValueError(msg)

        population = Population([
            Individual(
                alive=True,
                time_of_birth=ind.time_of_birth,
                time_of_death=-1,
                requires_eval=False,
                fitness_=ind.fitness_,
                requires_init=ind.requires_init,
                genotype_=ind.genotype_,
                tags_=dict(ind.tags_),
            )
            for ind in rows
        ])
        return EA(
            # The rows hold what the recorded run stored, genotypes of H
            cast("Population[H]", population),
            operations,
            num_steps=num_steps,
            first_generation_id=(
                first_generation_id
                if first_generation_id is not None
                else generation + 1
            ),
            direction=direction,
            quiet=quiet,
            db_file_path=target_db,
            db_handling=db_handling,
        )

    # -- Database --------------------------------------------------------------

    def _commit(self) -> None:
        """Persist the current population snapshot to the database.

        For each individual in ``self.population``:

        - Sets ``time_of_birth`` to ``current_generation`` if the individual
            has not yet been assigned a birth time (i.e.
            ``time_of_birth == -1``).
        - Updates ``time_of_death`` to ``current_generation``, reflecting the
            last generation in which the individual was present.

        The individuals keep their values in memory after the commit, so
        ``self.population`` stays readable once the session closes.
        """
        with Session(self.engine, expire_on_commit=False) as session:
            for ind in self.population:
                if ind.time_of_birth == -1:
                    ind.time_of_birth = self.current_generation
                ind.time_of_death = self.current_generation
                session.add(ind)
            session.commit()

    # -- Query helpers ---------------------------------------------------------

    def _fetch(
        self,
        *,
        sort: Literal["asc", "desc"] | None = None,
        only_alive: bool = True,
        requires_eval: bool | None = None,
    ) -> Population[G]:
        """Query individuals from the database and return them as a Population.

        Parameters
        ----------
        sort : {"asc", "desc"} or None, optional
            Sort order by ``fitness_``. ``"desc"`` returns highest fitness
            first; ``"asc"`` returns lowest fitness first. When ``None`` the
            database default ordering is used. Default is ``None``.
        only_alive : bool, optional
            When ``True``, only individuals where ``alive`` is set are
            returned. Default is ``True``.
        requires_eval : bool or None, optional
            Filter by evaluation status. ``True`` returns only unevaluated
            individuals; ``False`` returns only evaluated ones. When ``None``
            no filter is applied. Default is ``None``.

        Returns
        -------
        Population
            A new ``Population`` containing all matching individuals.
        """
        statement = select(Individual)

        if only_alive:
            statement = statement.where(Individual.alive)
        if requires_eval is not None:
            statement = statement.where(
                Individual.requires_eval == requires_eval,
            )

        if sort == "desc":
            statement = statement.order_by(col(Individual.fitness_).desc())
        elif sort == "asc":
            statement = statement.order_by(col(Individual.fitness_).asc())

        with Session(self.engine) as session:
            rows = Population(list(session.exec(statement).all()))
        # The run stored these rows, so their genotypes are of G
        return cast("Population[G]", rows)

    def fetch_population(
        self,
        *,
        only_alive: bool = True,
        requires_eval: bool | None = None,
    ) -> None:
        """Refresh ``self.population`` from the database.

        Parameters
        ----------
        only_alive : bool, optional
            When ``True``, only individuals where ``alive`` is set are
            fetched. Default is ``True``.
        requires_eval : bool or None, optional
            Filter by evaluation status. ``True`` returns only unevaluated
            individuals; ``False`` returns only evaluated ones. When ``None``
            no filter is applied. Default is ``None``.
        """
        self.population = self._fetch(
            only_alive=only_alive,
            requires_eval=requires_eval,
        )

    # -- Population stats ------------------------------------------------------

    @property
    def size(self) -> int:
        """Current number of alive individuals in the population.

        Triggers a database fetch on every access.

        Returns
        -------
        int
            Number of alive individuals.
        """
        self.fetch_population()
        return self.population.size

    def get_solution(
        self,
        mode: Literal["best", "median", "worst"] = "best",
        *,
        only_alive: bool = True,
    ) -> Individual[G]:
        """Return a single representative individual by fitness rank.

        The sort order follows ``self.direction``: descending for ``"max"``,
        ascending for ``"min"``.
        Only evaluated individuals (``requires_eval=False``) are considered.

        Parameters
        ----------
        mode : {"best", "median", "worst"}, optional
            Which individual to return from the sorted population.

            ``"best"``
                Highest fitness for maximisation; lowest for minimisation.
            ``"median"``
                The individual at the middle index of the sorted population.
            ``"worst"``
                Lowest fitness for maximisation; highest for minimisation.

            Default is ``"best"``.
        only_alive : bool, optional
            When ``True``, restricts the query to alive individuals.
            Default is ``True``.

        Returns
        -------
        Individual
            The selected individual.

        Raises
        ------
        ValueError
            If ``mode`` is not one of the three above.
        """
        if mode not in {"best", "median", "worst"}:
            msg = (
                f"Unknown mode {mode!r}; expected 'best', 'median' or 'worst'."
            )
            raise ValueError(msg)
        # pop[0] must be the *best* individual: highest fitness first when
        # maximising, lowest fitness first when minimising.
        sort: Literal["asc", "desc"] = (
            "desc" if self.direction == "max" else "asc"
        )
        pop = self._fetch(sort=sort, only_alive=only_alive, requires_eval=False)

        if mode == "best":
            return pop[0]
        if mode == "median":
            return pop[len(pop) // 2]
        return pop[-1]

    # -- Execution -------------------------------------------------------------

    def step(self) -> None:
        """Advance the EA by one generation.

        Increments ``current_generation``, refreshes ``self.population`` from
        the database, passes the population through each ``EAOperation`` in
        ``self.operations`` in order, then commits the result.
        """
        self.current_generation += 1
        self.fetch_population()
        for op in self.operations:
            self.population = op.run(self.population)
        self._commit()

    def run(self) -> None:
        """Run the EA for ``num_steps`` generations.

        Displays a Rich progress bar while iterating. Prints a completion
        rule to the console when finished.
        """
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=self.console,
        ) as progress:
            task = progress.add_task(
                "Running EA",
                total=self.num_steps,
            )
            for _ in range(self.num_steps):
                self.step()
                progress.advance(task)

        self.console.rule("[green]EA Finished")

    def close(self) -> None:
        """Release the database connection.

        The run can still be read afterwards; the next query opens a new
        connection, which ``close`` releases again.
        """
        self.engine.dispose()

    def __enter__(self) -> Self:
        """Return this run, to be closed when the ``with`` block ends.

        Returns
        -------
        Self
            This run.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the run when the ``with`` block ends."""
        self.close()
