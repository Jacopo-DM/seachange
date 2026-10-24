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
from sqlalchemy import Connection, Engine, create_engine, func, insert
from sqlmodel import Session, col, or_, select

from seachange.codecs import Genotype
from seachange.ea_database import (
    file_identity,
    leave_write_ahead,
    setup_database,
)
from seachange.ea_operation import Operation
from seachange.ea_settings import (
    DBHandlingMode,
    Direction,
    KeepGenotypes,
    Rank,
    config,
)
from seachange.individual import (
    Individual,
    KeptGenotype,
    check_rows,
    drop_genotypes,
    genotype_layout,
    is_new,
    load_genotypes,
    mark_genotypes_saved,
    mark_saved,
    save_genotypes,
    save_individuals,
)
from seachange.population import Population

RANKS: frozenset[str] = frozenset({"best", "median", "worst"})


def _checked_keep(keep: Literal["all"] | Sequence[Rank]) -> KeepGenotypes:
    """Return ``keep_genotypes`` as the run stores it, after checking it.

    Parameters
    ----------
    keep : "all" or Sequence of Rank
        The value passed to ``EA`` or read from ``config``.

    Returns
    -------
    KeepGenotypes
        ``"all"``, or the ranks as a tuple.

    Raises
    ------
    ValueError
        If ``keep`` is another string, or names another rank.
    """
    if isinstance(keep, str):
        if keep == "all":
            return "all"
    elif set(keep) <= RANKS:
        return tuple(keep)
    msg = (
        "keep_genotypes must be 'all' or a sequence of 'best', 'median' "
        f"and 'worst', not {keep!r}"
    )
    raise ValueError(msg)


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
    keep_genotypes : "all" or Sequence of Rank, optional
        Which genotypes the run keeps once their individual dies (see
        ``EASettings.keep_genotypes``): ``["best"]`` keeps the living
        population's and each generation's best. Falls back to
        ``config.keep_genotypes`` when ``None``. Default is ``None``.

    Raises
    ------
    ValueError
        If ``keep_genotypes`` is neither ``"all"`` nor a sequence of
        ``"best"``, ``"median"`` and ``"worst"``.

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
        keep_genotypes: Literal["all"] | Sequence[Rank] | None = None,
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
        self.keep_genotypes: KeepGenotypes = _checked_keep(
            keep_genotypes
            if keep_genotypes is not None
            else config.keep_genotypes
        )
        self.console: Console = Console(
            quiet=quiet if quiet is not None else config.quiet,
        )
        path = db_file_path or config.db_file_path
        # A genotype not read yet from the file this run replaces would be
        # read from the new, empty one: read it now
        for ind in population:
            ind.read_genotype_if_in(path)
        self.engine: Engine = setup_database(
            db_file_path=path,
            db_handling=db_handling or config.db_handling,
            console=self.console,
        )
        with self.engine.connect() as connection:
            self._identity = file_identity(connection)
        for ind in population:
            if ind.from_another_file() or ind.stored_elsewhere(self._identity):
                # Drawn from an Archive, or saved by another run, to seed
                # this run: it starts alive, as restart's survivors do
                ind.alive = True
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
        keep_genotypes: Literal["all"] | Sequence[Rank] | None = None,
    ) -> "EA[H]":
        """Continue a recorded run in a new database.

        Reads the evaluated individuals that survived ``generation`` in
        ``source`` (born by then and not retired during or before it) and
        starts a new run with them. The new file also gets the rest of
        ``source``'s history up to ``generation``: every other individual
        born by then, retired, with its genotype if ``source`` kept it.
        Every individual keeps its id, so the new file answers questions
        about generations up to ``generation`` as ``source`` does. The
        other keywords are those of ``EA``.

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
            As for ``EA``, but defaults to ``generation``: the survivors are
            stored as that generation, so a run restarted from generation 10
            for 20 steps writes generations 11 to 30, numbered as in
            ``source``.
        direction : {"max", "min"} or None, optional
            As for ``EA``.
        quiet : bool or None, optional
            As for ``EA``.
        db_file_path : Path or None, optional
            As for ``EA``. Must not be ``source``.
        db_handling : DBHandlingMode or None, optional
            As for ``EA``.
        keep_genotypes : "all" or Sequence of Rank, optional
            As for ``EA``. It applies to the new run; the copied history
            keeps the genotypes ``source`` kept.

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
            individuals, has no evaluated individuals at ``generation``, or
            did not keep their genotypes (see ``keep_genotypes``; the
            survivors of its latest generation always have theirs).
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
                load_genotypes(session.connection(), rows)
        finally:
            # Release the pooled connection; the engine is not used again
            source_engine.dispose()

        if not rows:
            msg = (
                f"No evaluated individuals at generation {generation} "
                f"in {source_db}."
            )
            raise ValueError(msg)
        if any(ind.genotype_ is None and not ind.requires_init for ind in rows):
            msg = (
                f"{source_db} did not keep the genotypes of generation "
                f"{generation}'s survivors (keep_genotypes); restart from "
                "its latest generation instead."
            )
            raise ValueError(msg)

        survivors = []
        for ind in rows:
            survivor = Individual(
                id=ind.id,
                alive=True,
                time_of_birth=ind.time_of_birth,
                time_of_death=-1,
                requires_eval=False,
                fitness_=ind.fitness_,
                requires_init=ind.requires_init,
                tags_=dict(ind.tags_),
            )
            survivor.genotype_ = ind.genotype_
            survivors.append(survivor)
        population = Population(survivors)
        ea = EA(
            # The rows hold what the recorded run stored, genotypes of H
            cast("Population[H]", population),
            operations,
            num_steps=num_steps,
            first_generation_id=(
                first_generation_id
                if first_generation_id is not None
                else generation
            ),
            direction=direction,
            quiet=quiet,
            db_file_path=target_db,
            db_handling=db_handling,
            keep_genotypes=keep_genotypes,
        )
        ea._copy_history(source_db, generation)
        return ea

    def _copy_history(self, source: Path, generation: int) -> None:
        """Copy ``source``'s other individuals born by ``generation``.

        The survivors are already stored. Everyone else born by
        ``generation`` is copied as stored, genotype bytes included, with
        ``alive`` false and ``time_of_death`` capped at ``generation``,
        and so are the records of which genotypes ``source`` kept up to
        ``generation``.

        Parameters
        ----------
        source : Path
            Database of the recorded run. It is only read.
        generation : int
            The generation the run restarted from.
        """
        names = list(Individual.model_fields)
        changed = {"alive": "0", "time_of_death": "min(time_of_death, ?)"}
        columns = ", ".join(names)
        copied = ", ".join(changed.get(name, name) for name in names)
        with self.engine.connect() as connection:
            connection.exec_driver_sql(
                "ATTACH DATABASE ? AS source", (str(source),)
            )
            try:
                connection.exec_driver_sql(
                    f"INSERT INTO individual ({columns}) "  # ruff: ignore[hardcoded-sql-expression]  # only the model's column names are filled in
                    f"SELECT {copied} FROM source.individual "
                    "WHERE time_of_birth <= ? "
                    "AND id NOT IN (SELECT id FROM main.individual)",
                    (generation, generation),
                )
                self._copy_genotypes(connection, generation)
                has_kept = connection.exec_driver_sql(
                    "SELECT count(*) FROM source.sqlite_master "
                    "WHERE type = 'table' AND name = 'kept_genotype'"
                ).scalar_one()
                if has_kept:
                    connection.exec_driver_sql(
                        "INSERT INTO kept_genotype "
                        "(generation, rank, individual_id) "
                        "SELECT generation, rank, individual_id "
                        "FROM source.kept_genotype WHERE generation <= ?",
                        (generation,),
                    )
                connection.commit()
            finally:
                connection.exec_driver_sql("DETACH DATABASE source")

    @staticmethod
    def _copy_genotypes(connection: Connection, generation: int) -> None:
        """Copy the attached ``source``'s genotypes born by ``generation``.

        Those already stored (the survivors') are skipped. ``source`` may
        keep them in a ``genotype`` table or, as earlier seachange and
        ARIEL did, in the individual table's ``genotype_`` column; the
        bytes or JSON text are copied as they are.

        Parameters
        ----------
        connection : Connection
            The new run's connection, with the old file attached as
            ``source``.
        generation : int
            The generation the run restarted from.
        """
        if genotype_layout(connection, "source") == "table":
            sql = (
                "INSERT INTO genotype (individual_id, data) "
                "SELECT g.individual_id, g.data FROM source.genotype g "
                "JOIN source.individual i ON i.id = g.individual_id "
                "WHERE i.time_of_birth <= ? "
                "AND g.individual_id NOT IN "
                "(SELECT individual_id FROM main.genotype)"
            )
        else:
            sql = (
                "INSERT INTO genotype (individual_id, data) "
                "SELECT id, genotype_ FROM source.individual "
                "WHERE time_of_birth <= ? AND genotype_ IS NOT NULL "
                "AND id NOT IN (SELECT individual_id FROM main.genotype)"
            )
        connection.exec_driver_sql(sql, (generation,))

    # -- Database --------------------------------------------------------------

    def _commit(self) -> None:
        """Persist the current population snapshot to the database.

        For each individual in ``self.population``:

        - Sets ``time_of_birth`` to ``current_generation`` if the individual
            has not yet been assigned a birth time (i.e.
            ``time_of_birth == -1``).
        - Updates ``time_of_death`` to ``current_generation``, reflecting the
            last generation in which the individual was present.

        Unless ``keep_genotypes`` is ``"all"``, the same commit records this
        generation's ranked individuals and drops the genotype of each
        individual that died in it and was never ranked (see
        ``_keep_ranked``).

        The individuals keep their values in memory after the commit, so
        ``self.population`` stays readable once the session closes.
        """
        # A population may hold one individual twice
        present = list({id(ind): ind for ind in self.population}.values())
        moved = [ind for ind in present if ind.stored_elsewhere(self._identity)]
        # What a failed commit gives back, as the ORM's rollback did
        undo = [
            (ind, ind.id, ind.time_of_birth)
            for ind in present
            if is_new(ind) or ind.stored_elsewhere(self._identity)
        ]
        # By identity: == on individuals compares their genotypes too
        moving = {id(ind) for ind in moved}
        for ind in moved:
            ind.id = None
        for ind in present:
            if id(ind) in moving or (is_new(ind) and ind.from_another_file()):
                # Drawn from an Archive or saved by another run: born in
                # this run when it joins it
                ind.time_of_birth = -1
            if ind.time_of_birth == -1:
                ind.time_of_birth = self.current_generation
            ind.time_of_death = self.current_generation
        try:
            with self.engine.begin() as connection:
                # Gives new individuals their ids, for their genotype rows
                saved = save_individuals(connection, present, moved)
                dropped = (
                    []
                    if self.keep_genotypes == "all"
                    else self._keep_ranked(
                        connection, present, self.keep_genotypes
                    )
                )
                gone = {id(ind) for ind in dropped}
                save_genotypes(
                    connection,
                    [ind for ind in present if id(ind) not in gone],
                    moved,
                )
        except BaseException:
            for ind, old_id, old_birth in undo:
                ind.id = old_id
                ind.time_of_birth = old_birth
            raise
        mark_saved(saved, self._identity)
        mark_genotypes_saved(present, dropped)

    def _keep_ranked(
        self,
        connection: Connection,
        present: Sequence[Individual[G]],
        ranks: tuple[Rank, ...],
    ) -> list[Individual[G]]:
        """Record this generation's ``ranks``; drop the other dead genotypes.

        The evaluated individuals present in the generation (alive, or
        retired during it) are ranked as ``get_solution`` ranks them. A
        ``KeptGenotype`` row names each of ``ranks``. An individual that
        died in this generation loses its genotype unless a row, from this
        generation or an earlier one, names it.

        Parameters
        ----------
        connection : Connection
            The connection of the commit, after the rows are saved, so every
            individual has its id.
        present : Sequence[Individual]
            The generation's individuals, each once.
        ranks : tuple of {"best", "median", "worst"}
            The ranks to keep.

        Returns
        -------
        list[Individual]
            The individuals whose genotypes were deleted, to forget them
            once the commit succeeds.
        """
        ranked = sorted(
            (ind for ind in present if not ind.requires_eval),
            key=lambda ind: ind.fitness,
            reverse=self.direction == "max",
        )
        if ranked and ranks:
            position = {"best": 0, "median": len(ranked) // 2, "worst": -1}
            connection.execute(
                insert(KeptGenotype),
                [
                    {
                        "generation": self.current_generation,
                        "rank": rank,
                        "individual_id": ranked[position[rank]].id,
                    }
                    for rank in ranks
                ],
            )
        dying = [
            ind
            for ind in present
            if not ind.alive and ind.genotype_ is not None
        ]
        if not dying:
            return []
        kept = set(
            connection.scalars(
                select(KeptGenotype.individual_id).where(
                    col(KeptGenotype.individual_id).in_([
                        ind.id for ind in dying
                    ])
                )
            )
        )
        dropped = [ind for ind in dying if ind.id not in kept]
        drop_genotypes(connection, dropped)
        return dropped

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
            load_genotypes(session.connection(), rows.to_list())
        for row in rows:
            row.stored_in(self._identity)
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
        connection, which ``close`` releases again. The closed file leaves
        WAL mode, so it reads like any other, in a read-only folder too.
        """
        self.engine.dispose()
        leave_write_ahead(self.engine)

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
