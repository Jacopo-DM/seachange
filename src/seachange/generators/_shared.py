"""Shared state of the generators and mutators: the RNG, settings, types."""

from collections.abc import Sequence

import numpy as np
from numpy.random import Generator
from pydantic_settings import BaseSettings

UNIFORM_MEDIAN = 0.5


# -- Module-level RNG (shared across generators, mutators, crossover) ----------
SEED: int = 42
rng: Generator = np.random.default_rng(SEED)

type Integers = Sequence[int]
type Floats = Sequence[float]


# -- Settings ------------------------------------------------------------------


class _GeneratorSettings(BaseSettings):
    """
    Internal configuration for generator and mutator defaults.

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

    integers_endpoint: bool = True
    choice_replace: bool = True
    choice_shuffle: bool = False


settings: _GeneratorSettings = _GeneratorSettings()
