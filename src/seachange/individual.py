"""Individual: one row of the EA database."""

from collections.abc import Sequence, Sized
from typing import Self, cast

import numpy as np
from pydantic import ValidationError
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from seachange.codecs import (
    Genotype,
    GenotypeColumn,
    JSONType,
    decode_error,
)


# Mutable on purpose: SQLAlchemy saves a table row by changing it
class Individual[G = Genotype](SQLModel, table=True):
    """
    A single candidate solution in an evolutionary algorithm.

    Persisted as a SQLite row via SQLModel. All mutable state, fitness,
    genotype, and tags, is accessed through properties that enforce
    consistency invariants (e.g. clearing ``requires_eval`` on fitness
    assignment).

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
    genotype_ : object, optional
        Raw stored genotype. Access via the ``genotype`` property in user
        code. Stored through the codec that handles it (see
        ``seachange.codecs``), so a numpy array comes back as one.
        Default is ``None``.
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
    genotype_: object = Field(default=None, sa_column=Column(GenotypeColumn()))

    # -- Tags ------------------------------------------------------------------
    tags_: dict[JSONType, JSONType] = Field(default={}, sa_column=Column(JSON))

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
        if self.genotype_ is None and not self.requires_init:
            msg = (
                f"genotype of row {self.id} was not kept: its run dropped "
                "it when the individual died (keep_genotypes)"
            )
            raise ValueError(msg)
        if self.genotype_ is None:
            msg = f"genotype accessed before initialization: {self.id=}"
            raise ValueError(msg)
        if (error := decode_error(self.genotype_)) is not None:
            msg = f"genotype of row {self.id} cannot be decoded: {error}"
            raise ValueError(msg)
        # genotype_ holds what the setter or a codec put there
        return cast("G", self.genotype_)

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


def check_rows(rows: Sequence[Individual]) -> list[Individual]:
    """Validate rows read from a database file before they are used.

    A SQLModel table model does not validate what it loads, so a file
    edited by another tool could hand over, say, a text ``fitness_``.

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
        if (error := decode_error(row.genotype_)) is not None:
            msg = (
                f"Database row {row.id} is not a valid Individual: "
                f"its genotype cannot be decoded: {error}"
            )
            raise ValueError(msg)
        try:
            Individual.model_validate(row, from_attributes=True)
        except ValidationError as error:
            msg = f"Database row {row.id} is not a valid Individual: {error}"
            raise ValueError(msg) from error
    return list(rows)
