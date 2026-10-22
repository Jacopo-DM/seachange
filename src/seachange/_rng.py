"""The two random generators behind every random draw seachange makes.

``rng`` (numpy) serves the generators, mutators and crossover operators;
``py_rng`` (a private ``random.Random``) serves the draws ``Population``
and ``Archive`` make from sequences. ``seed`` restarts both.
"""

import random

import numpy as np
from numpy.random import Generator

SEED: int = 42
rng: Generator = np.random.default_rng(SEED)
# For draws from Python sequences; private so the global random is untouched
py_rng: random.Random = random.Random(SEED)  # ruff: ignore[suspicious-non-cryptographic-random-usage]  # simulation, not security


def seed(value: int) -> None:
    """Restart every random draw seachange makes from ``value``.

    Two generators, both seeded with ``SEED`` when seachange is imported,
    make all of seachange's random choices: a numpy generator for the
    generators, mutators and crossover operators, and a private
    ``random.Random`` for the draws ``Population`` and ``Archive`` make
    from sequences. This resets both in place, so after ``seed(n)`` a run
    repeats exactly. Python's global ``random`` is not touched.

    Parameters
    ----------
    value : int
        The new seed.
    """
    rng.bit_generator.state = np.random.default_rng(value).bit_generator.state
    py_rng.seed(value)
