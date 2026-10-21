"""Shared state of the generators and mutators: the RNG, settings, types."""

from collections.abc import Sequence

import numpy as np
from numpy.random import Generator
from pydantic_settings import BaseSettings, SettingsConfigDict

UNIFORM_MEDIAN = 0.5


# -- Module-level RNG (shared across generators, mutators, crossover) ----------
SEED: int = 42
rng: Generator = np.random.default_rng(SEED)


def seed(value: int) -> None:
    """Restart the shared generator from ``value``.

    The generators, mutators and crossover operators all draw from one
    numpy generator, seeded with ``SEED`` when seachange is imported. This
    resets its state in place, so every module that holds it sees the new
    sequence. It does not cover the other sources of chance:
    ``Population.sample``, ``Population.shuffle``,
    ``Archive.tournament_population`` and
    ``Archive.fitness_percentile_population`` use Python's ``random``
    module (seed it with ``random.seed``), and
    ``Archive.random_individual`` and ``Archive.random_population`` use
    SQLite's ``random()``, which cannot be seeded.

    Parameters
    ----------
    value : int
        The new seed.
    """
    rng.bit_generator.state = np.random.default_rng(value).bit_generator.state


type Integers = Sequence[int]
type Floats = Sequence[float]


# -- Settings ------------------------------------------------------------------


class _GeneratorSettings(BaseSettings):
    """
    Internal configuration for generator and mutator defaults.

    Each field can be overridden by an environment variable named
    ``SEACHANGE_`` plus the field name, for example
    ``SEACHANGE_CHOICE_SHUFFLE=true``.

    Parameters
    ----------
    integers_endpoint : bool, optional
        Whether the ``high`` bound is inclusive when sampling integers.
        Default is ``True``.
    choice_replace : bool, optional
        Whether sampling with replacement is the default for
        ``IntegersGenerator.choice``. Default is ``True``.
    choice_shuffle : bool, optional
        Whether the output of ``IntegersGenerator.choice`` is shuffled
        by default. Default is ``False``.
    """

    model_config = SettingsConfigDict(env_prefix="SEACHANGE_")

    integers_endpoint: bool = True
    choice_replace: bool = True
    choice_shuffle: bool = False


settings: _GeneratorSettings = _GeneratorSettings()
