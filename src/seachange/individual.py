"""Individual: one row of the EA database, and the table of its genotypes."""

import sqlite3
from collections.abc import Sequence, Sized
from contextlib import closing
from pathlib import Path
from typing import Literal, Self, cast

import numpy as np
from pydantic import PrivateAttr, ValidationError
from sqlalchemy import (
    JSON,
    Column,
    Connection,
    bindparam,
    delete,
    event,
    func,
    inspect,
    update,
)
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import InstanceState, make_transient_to_detached
from sqlmodel import Field, SQLModel, col, select

from seachange.codecs import (
    Genotype,
    GenotypeColumn,
    JSONType,
    decode_error,
    read_stored,
)
from seachange.model import Model

type GenotypeLayout = Literal["table", "row"]

# SQLite's default limit on the parameters of one statement is 32,766
_CHUNK = 10_000


class GenotypeSource(Model):
    """Where a genotype that has not been read yet is stored.

    ``Archive`` gives each individual it returns one, so the genotype is
    read from the file only when it is first asked for, even after the
    archive is closed.

    Parameters
    ----------
    path : Path
        The database file, as an absolute path.
    row_id : int
        ``Individual.id`` of the row in that file.
    layout : {"table", "row"}
        ``"table"`` for a ``genotype`` table, as seachange writes it;
        ``"row"`` for a ``genotype_`` column in the individual table, as
        earlier seachange and ARIEL wrote it.
    """

    path: Path
    row_id: int
    layout: GenotypeLayout

    def read(self) -> object | None:
        """Return the stored genotype, or ``None`` if there is none.

        Returns
        -------
        object or None
            As ``read_stored`` returns it.
        """
        sql = (
            "SELECT data FROM genotype WHERE individual_id = ?"
            if self.layout == "table"
            else "SELECT genotype_ FROM individual WHERE id = ?"
        )
        uri = f"{self.path.as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            row = connection.execute(sql, (self.row_id,)).fetchone()
        return read_stored(None if row is None else row[0])


# Mutable on purpose: SQLAlchemy saves a table row by changing it
class Individual[G = Genotype](SQLModel, table=True):
    """
    A single candidate solution in an evolutionary algorithm.

    Persisted as a SQLite row via SQLModel; its genotype is stored in the
    ``genotype`` table (``GenotypeRow``), so queries over the other fields
    do not read it. All mutable state, fitness, genotype, and tags, is
    accessed through properties that enforce consistency invariants (e.g.
    clearing ``requires_eval`` on fitness assignment).

    ``G`` is the type of the genotype, for type checkers only:
    ``Individual[NDArray[np.float32]]`` says ``ind.genotype`` is a float32
    array. Plain ``Individual`` means ``Genotype``, a JSON list or dict or
    a numpy array. At run time ``Individual[...]`` is ``Individual``.

    Parameters
    ----------
    id : int or None, optional
        Primary key assigned by the database on first commit. ``None``
        before the individual is persisted. Default is ``None``.
    alive : bool, optional
        Whether the individual is still active in the population.
        Indexed for fast survivor-selection queries. Default is ``True``.
    time_of_birth : int, optional
        Generation in which this individual was created. Set to ``-1``
        until assigned by the EA engine on first commit. Default is ``-1``.
    time_of_death : int, optional
        Last generation in which this individual was present. Updated on
        every commit by the EA engine. Default is ``-1``.
    requires_eval : bool, optional
        ``True`` when the individual's fitness has not yet been computed.
        Automatically set to ``False`` by the ``fitness`` setter. Indexed
        for fast unevaluated-individual queries. Default is ``True``.
    fitness_ : float or None, optional
        Raw stored fitness value. Access via the ``fitness`` property in
        user code; use ``fitness_`` only for direct database queries.
        Default is ``None``.
    requires_init : bool, optional
        ``True`` when the genotype has not yet been assigned. Automatically
        updated by the ``genotype`` setter. Indexed for fast queries.
        Default is ``True``.
    tags_ : dict[JSONType, JSONType], optional
        Raw stored tag dictionary. Access and update via the ``tags``
        property. Stored as a JSON column. Default is ``{}``.
    """

    id: int | None = Field(default=None, primary_key=True)

    # -- Lifetime --------------------------------------------------------------
    alive: bool = Field(default=True, index=True)
    time_of_birth: int = Field(default=-1, index=True)
    time_of_death: int = Field(default=-1, index=True)

    # -- Fitness ---------------------------------------------------------------
    requires_eval: bool = Field(default=True, index=True)
    fitness_: float | None = Field(default=None, index=True)

    # -- Genotype --------------------------------------------------------------
    requires_init: bool = Field(default=True, index=True)

    # -- Tags ------------------------------------------------------------------
    tags_: dict[JSONType, JSONType] = Field(default={}, sa_column=Column(JSON))

    # -- Genotype, kept in memory (not columns) --------------------------------
    # The value as assigned or read; None before either
    _genotype: object = PrivateAttr(default=None)
    # Set by assignment: the run's database does not hold this value yet
    _genotype_unsaved: bool = PrivateAttr(default=False)
    # Where to read the genotype from when it is first asked for
    _genotype_source: GenotypeSource | None = PrivateAttr(default=None)

    # -- Fitness property ------------------------------------------------------

    @property
    def fitness(self) -> float:
        """Evaluated fitness of the individual.

        Returns
        -------
        float
            The stored fitness value.

        Raises
        ------
        ValueError
            If accessed before the individual has been evaluated
            (i.e. ``fitness_`` is ``None``).
        """
        if self.fitness_ is None:
            msg = f"fitness accessed before evaluation: {self.id=}"
            raise ValueError(msg)
        return self.fitness_

    @fitness.setter
    def fitness(self, value: float) -> None:
        """Assign the fitness and mark the individual as evaluated.

        Sets ``requires_eval`` to ``False`` and stores ``value`` as a
        ``float`` in ``fitness_``.

        Parameters
        ----------
        value : int or float
            The fitness score to assign.
        """
        self.requires_eval = False
        self.fitness_ = float(value)

    # Typing only: Individual[X] stays Individual at run time. pydantic would
    # build a subclass per X, and SQLModel a second "individual" table.
    def __class_getitem__(cls, typevar_values: object) -> type[Self]:
        """Return the class itself for ``Individual[...]``.

        Parameters
        ----------
        typevar_values : object
            The genotype type, read by type checkers only.

        Returns
        -------
        type
            ``Individual``.
        """
        return cls

    # -- Genotype property -----------------------------------------------------

    @property
    def genotype_(self) -> object:
        """Raw genotype: as assigned, or as read from the database.

        Reads it from its ``GenotypeSource`` the first time, if it has one.
        ``None`` when there is no genotype, or the run did not keep it.

        Returns
        -------
        object
            The genotype, ``None``, or an ``UndecodableGenotype``.
        """
        if self._genotype_source is not None and self._genotype is None:
            self._genotype = self._genotype_source.read()
        return self._genotype

    @genotype_.setter
    def genotype_(self, value: object) -> None:
        """Assign the raw genotype; the run saves it at its next commit.

        Parameters
        ----------
        value : object
            The genotype, or ``None``.
        """
        self._genotype = value
        self._genotype_unsaved = True
        self._genotype_source = None

    @property
    def genotype(self) -> G:
        """Genotype of the individual.

        Returns
        -------
        G
            The genotype as assigned: by default a list or dict of JSON
            values, or a read-only numpy array.

        Raises
        ------
        ValueError
            If accessed before the genotype has been initialised
            (i.e. ``genotype_`` is ``None``), if the run did not keep it
            (``genotype_`` is ``None`` but ``requires_init`` is ``False``,
            see ``keep_genotypes``), or if the stored genotype could not be
            decoded.
        """
        stored = self.genotype_
        row = self.id
        if row is None and self._genotype_source is not None:
            row = self._genotype_source.row_id
        if stored is None and not self.requires_init:
            msg = (
                f"genotype of row {row} was not kept: its run dropped "
                "it when the individual died (keep_genotypes)"
            )
            raise ValueError(msg)
        if stored is None:
            msg = f"genotype accessed before initialization: {self.id=}"
            raise ValueError(msg)
        if (error := decode_error(stored)) is not None:
            msg = f"genotype of row {row} cannot be decoded: {error}"
            raise ValueError(msg)
        # genotype_ holds what the setter or a codec put there
        return cast("G", stored)

    @genotype.setter
    def genotype(self, value: G) -> None:
        """Assign the genotype and update the initialisation flag.

        Sets ``requires_init`` to ``False`` when ``value`` is non-empty,
        ``True`` when it is empty. A numpy array is made read-only, as a
        genotype is set once and never changed in place; this also affects
        the caller's array object.

        Parameters
        ----------
        value : G
            The genotype to assign: by default a list or dict of JSON
            values, or a numpy array; any type a registered codec handles.
        """
        if isinstance(value, np.ndarray):
            value.flags.writeable = False
            self.requires_init = value.size == 0
        else:
            self.requires_init = isinstance(value, Sized) and len(value) == 0
        self.genotype_ = value

    def read_genotype_from(self, source: GenotypeSource) -> None:
        """Read the genotype from ``source`` when it is first asked for.

        Parameters
        ----------
        source : GenotypeSource
            Where the genotype is stored.
        """
        self._genotype = None
        self._genotype_unsaved = False
        self._genotype_source = source

    def unsaved_genotype(self) -> object | None:
        """Return the genotype if a run's database does not hold it yet.

        That is a genotype assigned since the last save, or one read from
        another file (``read_genotype_from``), which is read now.

        Returns
        -------
        object or None
            The genotype to save, or ``None`` when there is nothing to save.
        """
        if self._genotype_unsaved or self._genotype_source is not None:
            return self.genotype_
        return None

    def genotype_saved(self) -> None:
        """Note that the run's database now holds the genotype."""
        self._genotype_unsaved = False
        self._genotype_source = None

    def drop_genotype(self) -> None:
        """Forget the genotype, as ``keep_genotypes`` drops it.

        ``requires_init`` stays as it is, so reading the genotype says it
        was not kept.
        """
        self._genotype = None
        self.genotype_saved()

    # -- Tags property ---------------------------------------------------------

    @property
    def tags(self) -> dict[JSONType, JSONType]:
        """Metadata tags attached to this individual.

        Returns
        -------
        dict[JSONType, JSONType]
            The current tag dictionary.
        """
        return self.tags_

    @tags.setter
    def tags(self, value: dict[JSONType, JSONType]) -> None:
        """Replace the tag dictionary with a copy of ``value``.

        To keep the existing tags, merge them in:
        ``ind.tags = {**ind.tags, "key": "value"}``. Changing the dict in
        place (``ind.tags["key"] = ...``) is not saved to the database,
        because the JSON column does not track changes inside it.

        Parameters
        ----------
        value : dict[JSONType, JSONType]
            The new tags.
        """
        self.tags_ = dict(value)


@event.listens_for(Individual, "load")
def _start_private_state(target: Individual, _context: object) -> None:
    # SQLAlchemy builds loaded rows without __init__, and SQLModel leaves
    # pydantic's private storage empty; give it the declared defaults
    target.__pydantic_private__ = {
        name: attribute.get_default()
        for name, attribute in Individual.__private_attributes__.items()
    }


# Mutable on purpose: SQLAlchemy saves a table row by changing it
class GenotypeRow(SQLModel, table=True):
    """
    The stored genotype of one individual.

    Written by ``EA`` when it saves an individual with a new genotype, and
    deleted when ``keep_genotypes`` drops it. Kept apart from the
    individual's row so that queries over fitness and lifetimes read no
    genotype bytes, and a deleted genotype frees whole pages.

    Parameters
    ----------
    individual_id : int
        ``Individual.id`` of the individual.
    data : object
        The genotype, stored through its codec (``GenotypeColumn``).
    """

    __tablename__ = "genotype"

    individual_id: int = Field(primary_key=True)
    data: object = Field(sa_column=Column(GenotypeColumn(), nullable=False))


# Mutable on purpose: SQLAlchemy saves a table row by changing it
class KeptGenotype(SQLModel, table=True):
    """
    A genotype a run keeps after its individual dies.

    Written by ``EA`` for each generation when ``keep_genotypes`` names
    ranks: one row per rank, naming the individual ranked so in that
    generation. A dying individual keeps its genotype if any row names it.

    Parameters
    ----------
    id : int or None, optional
        Primary key assigned by the database. Default is ``None``.
    generation : int
        The generation in which the individual held the rank.
    rank : str
        ``"best"``, ``"median"`` or ``"worst"``.
    individual_id : int
        ``Individual.id`` of the individual.
    """

    __tablename__ = "kept_genotype"

    id: int | None = Field(default=None, primary_key=True)
    generation: int = Field(index=True)
    rank: str
    individual_id: int = Field(index=True)


def genotype_layout(
    connection: Connection, schema: str = "main"
) -> GenotypeLayout:
    """Return where the database open on ``connection`` stores genotypes.

    Parameters
    ----------
    connection : Connection
        An open connection to the database.
    schema : str, optional
        The schema to look in, such as an attached database's name.
        Default is ``"main"``.

    Returns
    -------
    {"table", "row"}
        ``"table"`` if it has a ``genotype`` table, else ``"row"``.
    """
    found = connection.exec_driver_sql(
        f"SELECT count(*) FROM {schema}.sqlite_master "  # ruff: ignore[hardcoded-sql-expression]  # schema is "main" or an attached name seachange chose
        "WHERE type = 'table' AND name = 'genotype'"
    )
    return "table" if found.scalar_one() else "row"


def load_genotypes[G](
    connection: Connection, rows: Sequence[Individual[G]]
) -> None:
    """Read the genotypes of ``rows`` from the database open on ``connection``.

    Each row's genotype is set as read, so saving the row again does not
    rewrite it. A row with no stored genotype reads as ``None``.

    Parameters
    ----------
    connection : Connection
        An open connection to the database the rows came from.
    rows : Sequence[Individual]
        Rows as loaded, with their ids.

    Raises
    ------
    ValueError
        If a stored genotype cannot be decoded; the message names its row.
    """
    sql = (
        "SELECT individual_id, data FROM genotype WHERE individual_id IN ({})"
        if genotype_layout(connection) == "table"
        else "SELECT id, genotype_ FROM individual WHERE id IN ({})"
    )
    ids = [row.id for row in rows]
    stored: dict[int, object] = {}
    for start in range(0, len(ids), _CHUNK):
        chunk = ids[start : start + _CHUNK]
        found = connection.exec_driver_sql(
            sql.format(", ".join("?" * len(chunk))), tuple(chunk)
        )
        stored.update(dict(found.all()))
    for row in rows:
        value = read_stored(stored.get(cast("int", row.id)))
        if (error := decode_error(value)) is not None:
            msg = (
                f"Database row {row.id} is not a valid Individual: "
                f"its genotype cannot be decoded: {error}"
            )
            raise ValueError(msg)
        row.genotype_ = value
        row.genotype_saved()


def _state(ind: object) -> InstanceState[object]:
    # SQLAlchemy's tracking state of a mapped object; inspect() is untyped
    return cast("InstanceState[object]", inspect(ind))


def save_individuals[G](
    connection: Connection, individuals: Sequence[Individual[G]]
) -> None:
    """Write ``individuals``' rows in a few batched statements.

    An individual not yet stored in this file (no id, or one read
    elsewhere and never stored here) is inserted, keeping a given id. The
    others get the ids SQLite would give them, one after the largest so
    far, in order; seachange assigns them itself so that one
    ``executemany`` can insert them all (a multi-row ``RETURNING`` has no
    guaranteed order in SQLite). The run's engine is the file's only
    writer, so nothing takes an id in between. A stored
    individual gets an ``UPDATE`` of the columns SQLAlchemy saw assigned
    since it was read; a dict changed in place is not one of them, as with
    the ORM. Genotypes are written separately (``save_genotypes``).

    Parameters
    ----------
    connection : Connection
        The connection of a commit.
    individuals : Sequence[Individual]
        The individuals to save, each once.

    Raises
    ------
    ValueError
        If a stored individual's row is not in this file, as when an
        individual from another run's database is saved here.
    """
    table = SQLModel.metadata.tables["individual"]
    names = list(Individual.model_fields)
    new = [
        ind for ind in individuals if ind.id is None or _state(ind).key is None
    ]
    # By identity: == on individuals compares their genotypes too
    inserting = {id(ind) for ind in new}
    stored = [ind for ind in individuals if id(ind) not in inserting]
    if new:
        largest = connection.scalar(select(func.max(table.c.id))) or 0
        for ind in new:
            if ind.id is None:
                largest += 1
                ind.id = largest
            else:
                largest = max(largest, ind.id)
        connection.execute(
            insert(table),
            [{name: getattr(ind, name) for name in names} for ind in new],
        )
        for ind in new:
            # Now stored: a later save updates it, as the ORM would
            make_transient_to_detached(ind)
    by_columns: dict[tuple[str, ...], list[Individual[G]]] = {}
    for ind in stored:
        changed = tuple(
            name for name in names if name not in _state(ind).unmodified
        )
        if changed:
            by_columns.setdefault(changed, []).append(ind)
    for changed, group in by_columns.items():
        statement = (
            update(table)
            .where(table.c.id == bindparam("row_id"))
            .values({name: bindparam(f"new_{name}") for name in changed})
        )
        result = connection.execute(
            statement,
            [
                {"row_id": ind.id}
                | {f"new_{name}": getattr(ind, name) for name in changed}
                for ind in group
            ],
        )
        if result.rowcount != len(group):
            msg = (
                f"{len(group) - result.rowcount} of the individuals saved "
                "are not in this run's database; an individual read from "
                "another file is saved as new only through Archive, which "
                "clears its id"
            )
            raise ValueError(msg)


def save_genotypes[G](
    connection: Connection, individuals: Sequence[Individual[G]]
) -> None:
    """Write the genotypes the database open on ``connection`` lacks.

    Parameters
    ----------
    connection : Connection
        The connection of a commit, after ``save_individuals``, so every
        individual has its id.
    individuals : Sequence[Individual]
        The individuals to look at; those with nothing to save are skipped.
    """
    values = [
        {"individual_id": ind.id, "data": value}
        for ind in individuals
        if (value := ind.unsaved_genotype()) is not None
    ]
    if values:
        statement = insert(GenotypeRow)
        connection.execute(
            statement.on_conflict_do_update(
                index_elements=["individual_id"],
                set_={"data": statement.excluded.data},
            ),
            values,
        )
    for ind in individuals:
        ind.genotype_saved()


def drop_genotypes[G](
    connection: Connection, individuals: Sequence[Individual[G]]
) -> None:
    """Delete the stored genotypes of ``individuals`` and forget them.

    Parameters
    ----------
    connection : Connection
        The connection of a commit.
    individuals : Sequence[Individual]
        The individuals whose genotypes ``keep_genotypes`` drops.
    """
    ids = [ind.id for ind in individuals]
    for start in range(0, len(ids), _CHUNK):
        connection.execute(
            delete(GenotypeRow).where(
                col(GenotypeRow.individual_id).in_(ids[start : start + _CHUNK])
            )
        )
    for ind in individuals:
        ind.drop_genotype()


def check_rows(rows: Sequence[Individual]) -> list[Individual]:
    """Validate rows read from a database file before they are used.

    A SQLModel table model does not validate what it loads, so a file
    edited by another tool could hand over, say, a text ``fitness_``.
    Genotypes are checked where they are read (``load_genotypes``, or
    ``Individual.genotype``).

    Parameters
    ----------
    rows : Sequence[Individual]
        Rows as loaded from the database.

    Returns
    -------
    list[Individual]
        The same rows.

    Raises
    ------
    ValueError
        If a row does not validate; the message names its ``id``.
    """
    for row in rows:
        try:
            Individual.model_validate(row, from_attributes=True)
        except ValidationError as error:
            msg = f"Database row {row.id} is not a valid Individual: {error}"
            raise ValueError(msg) from error
    return list(rows)
