"""seachange: a generational evolutionary algorithm engine."""

from seachange.archive import Archive, FitnessStats, GenerationRange
from seachange.codecs import (
    GenotypeCodec,
    JsonCodec,
    NumpyCodec,
    register_codec,
)
from seachange.crossover import Crossover
from seachange.ea import EA
from seachange.ea_operation import EAOperation
from seachange.ea_settings import DBHandlingMode, Direction, EASettings, config
from seachange.generators import (
    SEED,
    FloatMutator,
    Floats,
    FloatsGenerator,
    IntegerMutator,
    Integers,
    IntegersGenerator,
    seed,
)
from seachange.individual import (
    Individual,
    JSONIterable,
    JSONPrimitive,
    JSONType,
)
from seachange.population import Population

__all__: list[str] = [
    "EA",
    "SEED",
    "Archive",
    "Crossover",
    "DBHandlingMode",
    "Direction",
    "EAOperation",
    "EASettings",
    "FitnessStats",
    "FloatMutator",
    "Floats",
    "FloatsGenerator",
    "GenerationRange",
    "GenotypeCodec",
    "Individual",
    "IntegerMutator",
    "Integers",
    "IntegersGenerator",
    "JSONIterable",
    "JSONPrimitive",
    "JSONType",
    "JsonCodec",
    "NumpyCodec",
    "Population",
    "config",
    "register_codec",
    "seed",
]
