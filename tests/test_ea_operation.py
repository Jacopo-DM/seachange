"""Test: EASettings and EAOperation."""

from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from seachange import EAOperation, EASettings
from seachange.population import Population
from tests.ea_helpers import (
    CUSTOM_NUM_STEPS,
    DEFAULT_NUM_STEPS,
    SIZE_AFTER_DOUBLING,
    SIZE_BEFORE_DOUBLING,
    double_pop,
    make_ind,
    make_pop,
    noop,
)
from tests.misuse import untyped


@EAOperation
def returns_a_list(population: Population) -> Population:
    # Lies about its return value to reach the runtime check.
    return cast("Population", [len(population)])


def test_easettings_defaults() -> None:
    """EASettings initializes with expected defaults."""
    s = EASettings()
    assert s.num_steps == DEFAULT_NUM_STEPS
    assert s.db_file_name == "database.db"
    assert s.db_handling == "delete"
    assert s.direction == "max"
    assert s.first_generation_id == 0
    assert s.quiet is False


def test_easettings_db_file_path() -> None:
    """db_file_path computed field combines output_folder and db_file_name."""
    s = EASettings(output_folder=Path("/tmp/ea"), db_file_name="run.db")  # ruff: ignore[hardcoded-temp-file]
    assert s.db_file_path == Path("/tmp/ea/run.db")  # ruff: ignore[hardcoded-temp-file]


def test_easettings_override() -> None:
    """EASettings fields can be overridden at construction."""
    s = EASettings(num_steps=CUSTOM_NUM_STEPS, quiet=True)
    assert s.num_steps == CUSTOM_NUM_STEPS
    assert s.quiet is True


def test_easettings_has_no_target_population_size() -> None:
    """The unused setting is gone, so setting it is an error."""
    with pytest.raises(ValidationError, match="target_population_size"):
        EASettings.model_validate({"target_population_size": 5})


def test_easettings_ignores_unprefixed_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare NUM_STEPS from another tool does not change the engine."""
    monkeypatch.setenv("NUM_STEPS", str(CUSTOM_NUM_STEPS))
    monkeypatch.setenv("QUIET", "true")
    s = EASettings()
    assert s.num_steps == DEFAULT_NUM_STEPS
    assert s.quiet is False


def test_easettings_reads_prefixed_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEACHANGE_ variables override the defaults."""
    monkeypatch.setenv("SEACHANGE_NUM_STEPS", str(CUSTOM_NUM_STEPS))
    assert EASettings().num_steps == CUSTOM_NUM_STEPS


def test_eaoperation_valid_decoration() -> None:
    """@EAOperation on a valid function returns an EAOperation."""
    assert isinstance(noop, EAOperation)


def test_eaoperation_no_params_raises() -> None:
    """@EAOperation on a zero-parameter function raises TypeError."""

    def bad() -> Population:  # no params
        return Population([])

    assert len(bad()) == 0
    with pytest.raises(TypeError, match="first argument"):
        untyped(EAOperation)(bad)


def test_eaoperation_wrong_first_param_type_raises() -> None:
    """First parameter not annotated as Population raises TypeError."""

    def bad(x: int) -> Population:
        return Population([make_ind(x)])

    assert len(bad(1)) == 1
    with pytest.raises(TypeError, match="Population"):
        untyped(EAOperation)(bad)


def test_eaoperation_wrong_return_type_raises() -> None:
    """Return annotation not Population raises TypeError."""

    def bad(population: Population) -> list[int]:
        return [len(population)]

    assert bad(make_pop()) == [4]
    with pytest.raises(TypeError, match="Population"):
        untyped(EAOperation)(bad)


def test_eaoperation_call_with_population_executes() -> None:
    """Calling an EAOperation with a Population returns a Population."""
    pop = make_pop()
    result = noop(pop)
    assert isinstance(result, Population)
    assert len(result) == len(pop)


def test_eaoperation_call_result_is_population() -> None:
    """double_pop operation doubles the population size."""
    pop = make_pop(SIZE_BEFORE_DOUBLING)
    result = double_pop(pop)
    assert isinstance(result, Population)
    assert len(result) == SIZE_AFTER_DOUBLING


def test_eaoperation_call_with_kwargs_returns_bound_op() -> None:
    """Calling with kwargs returns a new bound EAOperation (not executing)."""

    @EAOperation
    def with_param(population: Population, factor: float = 1.0) -> Population:  # ruff: ignore[unused-function-argument]
        return population

    bound = with_param(factor=2.0)
    assert isinstance(bound, EAOperation)
    result = bound(make_pop())
    assert isinstance(result, Population)
    # mypy 1.18 crashes on `bound.kwargs` (ParamSpec attribute), so read it
    # through the instance dict.
    assert vars(bound)["kwargs"] == {"factor": 2.0}


def test_eaoperation_bound_executes_with_population() -> None:
    """A bound EAOperation executes correctly when called with a Population."""
    results = []

    @EAOperation
    def capture(population: Population, tag: str = "x") -> Population:
        results.append(tag)
        return population

    op = capture(tag="hello")
    assert isinstance(op, EAOperation)
    pop = make_pop()
    op(pop)
    assert results == ["hello"]


def test_eaoperation_repr() -> None:
    """__repr__ includes the function name."""
    assert "noop" in repr(noop)


def test_eaoperation_repr_with_kwargs() -> None:
    """__repr__ includes bound kwargs."""

    @EAOperation
    def op(population: Population, k: int = 1) -> Population:  # ruff: ignore[unused-function-argument]
        return population

    bound = op(k=42)
    assert isinstance(bound, EAOperation)
    assert "42" in repr(bound)
    assert isinstance(bound(make_pop()), Population)


def test_operation_returning_a_list_is_rejected() -> None:
    """An operation must hand back a Population."""
    with pytest.raises(TypeError, match="expected a Population as return"):
        returns_a_list(make_pop())
