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
from rich.traceback import install
from sqlalchemy import Engine, create_engine, func
from sqlmodel import Session, col, select

from seachange.ea_database import setup_database
from seachange.ea_operation import Operation
from seachange.ea_settings import DBHandlingMode, Direction, config
from seachange.individual import Individual
from seachange.population import Population

install()


class EA:
    """
    Generational evolutionary algorithm engine.

    Each call to ``step()`` / ``run()`` executes the ordered list of
    ``EAOperation`` operations against the current population, then persists
    the result to a SQLite database via SQLModel.

    Parameters
    ----------
    population : Population or None, optional
        Initial population. Required unless ``restart`` is given.
    operations : list[EAOperation]
        Ordered pipeline of operations executed once per generation.
    restart : (Path | str, int) or Path | str or None, optional
        Resume from a previous run's database. Pass a path alone to
        restart from the latest recorded generation, or a
        ``(path, generation)`` tuple to restart from a specific
        generation. Overrides ``population`` and auto-sets
        ``first_generation_id`` when not specified. Default is ``None``.
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

    Restart from latest generation in an existing database:

    >>> ea = EA(None, ops, restart="__data__/run_1/database.db")
    >>> ea.run()

    Restart from a specific generation:

    >>> ea = EA(None, ops, restart=("__data__/run_1/database.db", 50))
    """

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        population: Population | None = None,
        operations: Sequence[Operation] | None = None,
        *,
        restart: "tuple[Path | str, int] | Path | str | None" = None,
        num_steps: int | None = None,
        first_generation_id: int | None = None,
        direction: Direction | None = None,
        quiet: bool | None = None,
        db_file_path: Path | None = None,
        db_handling: DBHandlingMode | None = None,
    ) -> None:
        """Create an EA from an optional population and list of operations.

        Raises
        ------
        FileNotFoundError
            If the restart database does not exist.
        ValueError
            If the operations are missing, both or neither of population and
            restart are given, or the restart database has no usable
            individuals, or the restart database is the file this run
            would write to.
        """
        if operations is None:
            msg = "'operations' is required."
            raise ValueError(msg)

        target_db = db_file_path or config.db_file_path
        if restart is not None:
            source_db, restart_gen = (
                (Path(restart), None)
                if isinstance(restart, (Path, str))
                else (Path(restart[0]), int(restart[1]))
            )
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
                    if restart_gen is None:
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
                        restart_gen = latest

                    rows = list(
                        session.exec(
                            select(Individual)
                            .where(Individual.time_of_birth <= restart_gen)
                            .where(Individual.time_of_death >= restart_gen)
                            .where(Individual.requires_eval == False)  # ruff: ignore[true-false-comparison]
                        ).all()
                    )
            finally:
                # Release the pooled connection; the engine is not used again
                source_engine.dispose()

            if not rows:
                msg = (
                    f"No evaluated individuals at generation {restart_gen} "
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
            if first_generation_id is None:
                first_generation_id = restart_gen + 1

        elif population is None:
            msg = "Provide either 'population' or 'restart'."
            raise ValueError(msg)

        self.operations: Sequence[Operation] = operations
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
            db_file_path=target_db,
            db_handling=db_handling or config.db_handling,
            console=self.console,
        )
        self.population: Population = population
        self._commit()
        self.console.rule("[blue]EA Initialized")

    # -- Database --------------------------------------------------------------

    def _commit(self) -> None:
        """Persist the current population snapshot to the database.

        For each individual in ``self.population``:

        - Sets ``time_of_birth`` to ``current_generation`` if the individual
            has not yet been assigned a birth time (i.e.
            ``time_of_birth == -1``).
        - Updates ``time_of_death`` to ``current_generation``, reflecting the
            last generation in which the individual was present.
        """
        with Session(self.engine) as session:
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
    ) -> Population:
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
            return Population(list(session.exec(statement).all()))

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
    ) -> Individual:
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
            self.population = op(self.population)
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
