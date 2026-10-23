"""Shared state of the generators and mutators: settings and types.

Also the two steps that several mutators share: swapping genes and
picking cut points.
"""

from collections.abc import Sequence
from typing import cast

import numpy as np
from pydantic_settings import BaseSettings, SettingsConfigDict

from seachange._rng import rng

UNIFORM_MEDIAN = 0.5


type Integers = Sequence[int]
type Floats = Sequence[float]


# -- Steps shared by the mutators ----------------------------------------------


def swap_genes[T](
    individual: Sequence[T], mutation_probability: float
) -> list[T]:
    """Swap each gene, with some probability, with a randomly chosen gene.

    Parameters
    ----------
    individual : Sequence[T]
        The genotype to mutate.
    mutation_probability : float
        Per-gene probability of initiating a swap.

    Returns
    -------
    list[T]
        A new genotype with swapped genes.
    """
    arr: list[T] = list(individual)
    n: int = len(arr)
    for idx in range(n):
        if rng.random() < mutation_probability:
            jdx: int = int(rng.integers(0, n))
            arr[idx], arr[jdx] = arr[jdx], arr[idx]
    return arr


def cut_points(n: int) -> "slice[int, int, None]":
    """Pick two different cut points of a sequence of length ``n``.

    Parameters
    ----------
    n : int
        The length of the sequence.

    Returns
    -------
    slice
        ``slice(lo, hi)`` with ``lo < hi``, both in ``[0, n]``; ``seq[cut]``
        is the segment between them.
    """
    lo, hi = sorted(
        cast(
            "list[int]",
            rng.choice(np.arange(n + 1), size=2, replace=False).tolist(),
        ),
    )
    return slice(lo, hi)


# -- Settings ------------------------------------------------------------------


class _GeneratorSettings(BaseSettings):
    """
    Internal configuration for generator and mutator defaults.

    Each field can be overridden by an environment variable named
    ``SEACHANGE_`` plus the field name, for example
    ``SEACHANGE_CHOICE_SHUFFLE=true``. Read-only: pass a value to the
    generator call instead of assigning to ``settings``.

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

    model_config = SettingsConfigDict(env_prefix="SEACHANGE_", frozen=True)

    integers_endpoint: bool = True
    choice_replace: bool = True
    choice_shuffle: bool = False


settings: _GeneratorSettings = _GeneratorSettings()
