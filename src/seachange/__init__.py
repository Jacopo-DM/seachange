"""seachange: a generational evolutionary algorithm engine."""

from seachange.archive import Archive
from seachange.crossover import Crossover
from seachange.ea import EA
from seachange.ea_operation import EAOperation
from seachange.ea_settings import DBHandlingMode, EASettings, config
from seachange.generators import (
    SEED,
    FloatMutator,
    Floats,
    FloatsGenerator,
    IntegerMutator,
    Integers,
    IntegersGenerator,
)
from seachange.individual import (
    Individual,
    JSONIterable,
    JSONPrimitive,
    JSONType,
)
from seachange.population import Population

__all__: list[str] = [
    # EA engine
    "EA",
    # Shared
    "SEED",
    # Archive
    "Archive",
    # Crossover
    "Crossover",
    "DBHandlingMode",
    "EAOperation",
    "EASettings",
    "FloatMutator",
    "Floats",
    # Float generators / mutators
    "FloatsGenerator",
    # Data layer
    "Individual",
    "IntegerMutator",
    "Integers",
    # Integer generators / mutators
    "IntegersGenerator",
    "JSONIterable",
    "JSONPrimitive",
    "JSONType",
    # Population
    "Population",
    "config",
]
