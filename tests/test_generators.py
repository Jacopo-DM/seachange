"""Test: generators and mutators in the ec module."""

from collections.abc import Callable

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from seachange import seed
from seachange.generators import (
    FloatMutator,
    FloatsGenerator,
    IntegerMutator,
    IntegersGenerator,
)
from seachange.generators._shared import settings  # ruff: ignore[import-private-name]  # tests the internal generator settings
from tests.misuse import assign

NUM_INTS = 5
INT_HIGH = 10
NUM_SAMPLES = 20
NUM_POINTS = 5

# ---------------------------------------------------------------------------
# IntegersGenerator
# ---------------------------------------------------------------------------


def test_integers_generator_returns_list() -> None:
    """IntegersGenerator.integers returns a list."""
    result = IntegersGenerator.integers(0, 10, size=NUM_INTS)
    assert isinstance(result, list)
    assert len(result) == NUM_INTS


def test_integers_generator_in_range() -> None:
    """All generated integers fall within [low, high]."""
    result = IntegersGenerator.integers(0, INT_HIGH, size=100)
    assert all(0 <= v <= INT_HIGH for v in result)


def test_integers_generator_choice_from_set() -> None:
    """Choice samples from the supplied set."""
    value_set = [10, 20, 30]
    result = IntegersGenerator.choice(value_set, size=50)
    assert all(v in value_set for v in result)


def test_integers_generator_permutation_length() -> None:
    """permutation(n) returns a list of length n containing 0..n-1."""
    n = 8
    result = IntegersGenerator.permutation(n)
    assert sorted(result) == list(range(n))


# ---------------------------------------------------------------------------
# FloatsGenerator
# ---------------------------------------------------------------------------


def test_floats_generator_uniform_range() -> None:
    """FloatsGenerator.uniform samples from [low, high)."""
    result = FloatsGenerator.uniform(0.0, 1.0, size=100)
    assert isinstance(result, list)
    assert all(0.0 <= v < 1.0 for v in result)


def test_floats_generator_normal_size() -> None:
    """FloatsGenerator.normal returns the requested number of samples."""
    result = FloatsGenerator.normal(mean=0.0, std=1.0, size=NUM_SAMPLES)
    assert len(result) == NUM_SAMPLES


def test_floats_generator_lognormal_positive() -> None:
    """Log-normal samples are all positive."""
    result = FloatsGenerator.lognormal(mean=0.0, sigma=1.0, size=50)
    assert all(v > 0 for v in result)


def test_floats_generator_linspace() -> None:
    """FloatsGenerator.linspace returns evenly spaced values."""
    result = FloatsGenerator.linspace(0.0, 1.0, NUM_POINTS)
    assert len(result) == NUM_POINTS
    assert result[0] == pytest.approx(0.0)
    assert result[-1] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# IntegerMutator
# ---------------------------------------------------------------------------


def test_integer_mutator_random_reset_same_length() -> None:
    """random_reset returns a list of the same length."""
    individual = [1, 2, 3, 4, 5]
    result = IntegerMutator.random_reset(individual, 0, 10, 0.5)
    assert len(result) == len(individual)


def test_integer_mutator_random_reset_prob_zero_unchanged() -> None:
    """random_reset with probability 0 never mutates."""
    individual = [5, 5, 5, 5, 5]
    result = IntegerMutator.random_reset(individual, 0, 10, 0.0)
    assert result == individual


def test_integer_mutator_creep_same_length() -> None:
    """integer_creep returns a list of the same length."""
    individual = [1, 2, 3]
    result = IntegerMutator.integer_creep(
        individual, span=2, mutation_probability=1.0
    )
    assert len(result) == len(individual)


def test_integer_mutator_swap_same_elements() -> None:
    """Swap preserves the multiset of genes."""
    individual = [1, 2, 3, 4, 5]
    result = IntegerMutator.swap(individual, mutation_probability=1.0)
    assert sorted(result) == sorted(individual)


def test_integer_mutator_inversion_same_elements() -> None:
    """Inversion preserves the multiset of genes."""
    individual = [1, 2, 3, 4, 5]
    result = IntegerMutator.inversion(individual, mutation_probability=1.0)
    assert sorted(result) == sorted(individual)


def test_integer_mutator_scramble_same_elements() -> None:
    """Scramble preserves the multiset of genes."""
    individual = [10, 20, 30, 40, 50]
    result = IntegerMutator.scramble(individual, mutation_probability=1.0)
    assert sorted(result) == sorted(individual)


# ---------------------------------------------------------------------------
# FloatMutator
# ---------------------------------------------------------------------------


def test_float_mutator_gaussian_same_length() -> None:
    """Gaussian mutation returns a list of the same length."""
    individual = [0.1, 0.2, 0.3]
    result = FloatMutator.gaussian(
        individual, std=0.01, mutation_probability=0.5
    )
    assert len(result) == len(individual)


def test_float_mutator_gaussian_respects_bounds() -> None:
    """Gaussian mutation with bounds clips results."""
    individual = [0.5] * 20
    result = FloatMutator.gaussian(
        individual,
        std=100.0,
        mutation_probability=1.0,
        lower_bound=0.0,
        upper_bound=1.0,
    )
    assert all(0.0 <= v <= 1.0 for v in result)


def test_float_mutator_uniform_reset_same_length() -> None:
    """uniform_reset returns a list of the same length."""
    individual = [1.0, 2.0, 3.0]
    result = FloatMutator.uniform_reset(individual, 0.0, 5.0, 0.5)
    assert len(result) == len(individual)


def test_float_mutator_uniform_reset_prob_zero_unchanged() -> None:
    """uniform_reset with probability 0 never changes any gene."""
    individual = [0.5, 0.5, 0.5]
    result = FloatMutator.uniform_reset(individual, 0.0, 1.0, 0.0)
    assert result == pytest.approx(individual)


def test_float_mutator_boundary_only_extremes() -> None:
    """Boundary mutation replaces genes with either low or high."""
    individual = [0.5] * 20
    result = FloatMutator.boundary(
        individual, low=0.0, high=1.0, mutation_probability=1.0
    )
    assert all(
        v == pytest.approx(0.0) or v == pytest.approx(1.0) for v in result
    )


def test_float_mutator_polynomial_within_bounds() -> None:
    """Polynomial mutation keeps all genes within [low, high]."""
    individual = [0.5] * 10
    result = FloatMutator.polynomial(
        individual, low=0.0, high=1.0, mutation_probability=1.0
    )
    assert all(0.0 <= v <= 1.0 for v in result)


def test_float_mutator_swap_same_elements() -> None:
    """Float swap preserves the multiset of genes."""
    individual = [1.0, 2.0, 3.0, 4.0]
    result = FloatMutator.swap(individual, mutation_probability=1.0)
    assert sorted(result) == pytest.approx(sorted(individual))


def test_float_mutator_inversion_same_elements() -> None:
    """Float inversion preserves the multiset of genes."""
    individual = [1.0, 2.0, 3.0, 4.0, 5.0]
    result = FloatMutator.inversion(individual, mutation_probability=1.0)
    assert sorted(result) == pytest.approx(sorted(individual))


# ---------------------------------------------------------------------------
# Choice, and mutation that does not happen
# ---------------------------------------------------------------------------

POOL = [0.5, 1.5, 2.5]
GENES = [1.0, 2.0, 3.0, 4.0]
INT_GENES = [1, 2, 3, 4]
NEVER = 0.0
CHOICES = 6


def test_floats_choice_draws_from_the_pool() -> None:
    """FloatsGenerator.choice returns the requested number of pool values."""
    result = FloatsGenerator.choice(POOL, size=CHOICES)
    assert len(result) == CHOICES
    assert set(result) <= set(POOL)


def test_floats_choice_follows_the_probabilities() -> None:
    """A probability of 1 on one value always draws that value."""
    result = FloatsGenerator.choice(
        POOL, size=CHOICES, probabilities=[0.0, 1.0, 0.0]
    )
    assert set(result) == {POOL[1]}


@pytest.mark.parametrize(
    "mutate",
    [
        IntegerMutator.inversion,
        IntegerMutator.scramble,
    ],
)
def test_integer_mutators_do_nothing_at_probability_zero(
    mutate: Callable[[list[int], float], list[int]],
) -> None:
    """With probability 0 the genotype comes back unchanged."""
    assert mutate(INT_GENES, NEVER) == INT_GENES


def test_float_inversion_does_nothing_at_probability_zero() -> None:
    """With probability 0 the float genotype comes back unchanged."""
    assert FloatMutator.inversion(GENES, NEVER) == GENES


def test_swap_mutators_keep_genes_that_are_not_selected() -> None:
    """At probability 0 no gene is swapped."""
    assert IntegerMutator.swap(INT_GENES, NEVER) == INT_GENES
    assert FloatMutator.swap(GENES, NEVER) == GENES


# ---------------------------------------------------------------------------
# size=None returns one number; an int size returns a list
# ---------------------------------------------------------------------------


def test_float_generators_return_one_float_for_size_none() -> None:
    """With size=None every float generator returns a plain float."""
    uniform: float = FloatsGenerator.uniform(0.0, 1.0, size=None)
    normal: float = FloatsGenerator.normal(size=None)
    normal_positional: float = FloatsGenerator.normal(0.0, 1.0, None)
    lognormal: float = FloatsGenerator.lognormal(size=None)
    lognormal_positional: float = FloatsGenerator.lognormal(0.0, 1.0, None)
    choice: float = FloatsGenerator.choice([0.5, 1.5], size=None)
    for value in (
        uniform,
        normal,
        normal_positional,
        lognormal,
        lognormal_positional,
        choice,
    ):
        assert type(value) is float


def test_integer_generators_return_one_int_for_size_none() -> None:
    """With size=None every integer generator returns a plain int."""
    drawn: int = IntegersGenerator.integers(0, INT_HIGH, size=None)
    chosen: int = IntegersGenerator.choice([10, 20, 30], size=None)
    assert type(drawn) is int
    assert type(chosen) is int


@given(
    low=st.floats(min_value=-1e6, max_value=1e6),
    width=st.floats(min_value=1e-3, max_value=1e6),
)
def test_uniform_size_none_stays_in_range(low: float, width: float) -> None:
    """A single uniform draw lies within [low, low + width]."""
    value = FloatsGenerator.uniform(low, low + width, size=None)
    assert low <= value <= low + width


@given(size=st.integers(min_value=1, max_value=50))
def test_float_generators_return_a_list_of_the_requested_length(
    size: int,
) -> None:
    """An int size gives a list of that many floats."""
    for result in (
        FloatsGenerator.uniform(0.0, 1.0, size=size),
        FloatsGenerator.normal(size=size),
        FloatsGenerator.lognormal(size=size),
        FloatsGenerator.choice([0.5, 1.5], size=size),
    ):
        assert isinstance(result, list)
        assert len(result) == size
        assert all(type(v) is float for v in result)


@given(size=st.integers(min_value=1, max_value=50))
def test_integer_generators_return_a_list_of_the_requested_length(
    size: int,
) -> None:
    """An int size gives a list of that many ints."""
    for result in (
        IntegersGenerator.integers(0, INT_HIGH, size=size),
        IntegersGenerator.choice([10, 20, 30], size=size),
    ):
        assert isinstance(result, list)
        assert len(result) == size
        assert all(type(v) is int for v in result)


def test_generator_settings_read_only_prefixed_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CHOICE_SHUFFLE is ignored; SEACHANGE_CHOICE_SHUFFLE is read."""
    generator_settings = type(settings)
    monkeypatch.setenv("CHOICE_SHUFFLE", "true")
    assert generator_settings().choice_shuffle is False
    monkeypatch.setenv("SEACHANGE_CHOICE_SHUFFLE", "true")
    assert generator_settings().choice_shuffle is True


def test_generator_settings_are_read_only() -> None:
    """Assigning to the generator settings raises."""
    with pytest.raises(ValidationError, match="frozen"):
        assign(settings, "choice_shuffle", value=True)
    assert settings.choice_shuffle is False


def test_seed_repeats_the_draws() -> None:
    """The same seed gives the same draws, across generators and mutators."""
    seed(5)
    first = (
        FloatsGenerator.uniform(0.0, 1.0, size=4),
        IntegerMutator.random_reset(
            [0, 1, 2, 3], low=0, high=9, mutation_probability=1.0
        ),
    )
    seed(5)
    again = (
        FloatsGenerator.uniform(0.0, 1.0, size=4),
        IntegerMutator.random_reset(
            [0, 1, 2, 3], low=0, high=9, mutation_probability=1.0
        ),
    )
    assert first == again


def test_different_seeds_give_different_draws() -> None:
    """Two seeds give two different sequences."""
    seed(5)
    five = FloatsGenerator.uniform(0.0, 1.0, size=4)
    seed(6)
    six = FloatsGenerator.uniform(0.0, 1.0, size=4)
    assert five != six
