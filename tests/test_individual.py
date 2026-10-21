"""Test: Individual class behaviour."""

import numpy as np
import pytest

from seachange.codecs import UndecodableGenotype
from seachange.individual import Individual


def test_individual_default_state() -> None:
    """A freshly created Individual has the expected default flags."""
    ind = Individual()
    assert ind.alive is True
    assert ind.requires_eval is True
    assert ind.requires_init is True
    assert ind.fitness_ is None
    assert ind.genotype_ is None


def test_fitness_setter_clears_requires_eval() -> None:
    """Assigning fitness sets requires_eval to False."""
    ind = Individual()
    ind.fitness = 1.5
    assert ind.requires_eval is False
    assert ind.fitness_ == pytest.approx(1.5)


def test_fitness_getter_returns_float() -> None:
    """Fitness property returns a float after assignment."""
    ind = Individual()
    ind.fitness = 42
    assert isinstance(ind.fitness, float)
    assert ind.fitness == pytest.approx(42.0)


def test_fitness_before_eval_raises() -> None:
    """Accessing fitness before evaluation raises ValueError."""
    ind = Individual()
    with pytest.raises(ValueError, match="fitness accessed before evaluation"):
        _ = ind.fitness


def test_genotype_setter_clears_requires_init() -> None:
    """Assigning a non-empty genotype sets requires_init to False."""
    ind = Individual()
    ind.genotype = [1, 2, 3]
    assert ind.requires_init is False
    assert ind.genotype == [1, 2, 3]


def test_genotype_setter_empty_keeps_requires_init() -> None:
    """Assigning an empty genotype keeps requires_init as True."""
    ind = Individual()
    ind.genotype = []
    assert ind.requires_init is True


def test_genotype_before_init_raises() -> None:
    """Accessing genotype before initialization raises ValueError."""
    ind = Individual()
    with pytest.raises(
        ValueError, match="genotype accessed before initialization"
    ):
        _ = ind.genotype


def test_tags_default_is_empty_dict() -> None:
    """Default tags_ is an empty dict."""
    ind = Individual()
    assert ind.tags == {}


def test_tags_setter_replaces() -> None:
    """Assigning tags replaces the whole dict, like any other assignment."""
    ind = Individual()
    ind.tags = {"a": 1}
    ind.tags = {"b": 2}
    assert ind.tags == {"b": 2}


def test_tags_merge_is_written_out() -> None:
    """To keep the old keys, merge them into the new dict explicitly."""
    ind = Individual()
    ind.tags = {"a": 1}
    ind.tags = {**ind.tags, "b": 2}
    assert ind.tags == {"a": 1, "b": 2}


def test_tags_setter_overwrites_existing_key() -> None:
    """Setting a tag with an existing key overwrites it."""
    ind = Individual()
    ind.tags = {"key": "old"}
    ind.tags = {"key": "new"}
    assert ind.tags["key"] == "new"


def test_fitness_stored_as_float() -> None:
    """fitness_ is always stored as float, even when assigned an int."""
    ind = Individual()
    ind.fitness = 10
    assert isinstance(ind.fitness_, float)


def test_a_numpy_genotype_is_made_read_only() -> None:
    """A genotype is set once: an in-place edit raises at once."""
    parent = Individual()
    parent.genotype = np.zeros(3, dtype=np.float32)
    child = Individual()
    child.genotype = parent.genotype
    assert parent.requires_init is False
    array = child.genotype
    assert isinstance(array, np.ndarray)
    with pytest.raises(ValueError, match="read-only"):
        array[0] = 1.0


def test_an_empty_numpy_genotype_keeps_requires_init() -> None:
    """An array with no elements is an empty genotype."""
    ind = Individual()
    ind.genotype = np.zeros((2, 0))
    assert ind.requires_init is True


def test_an_undecodable_genotype_raises_on_reading() -> None:
    """A stored genotype no codec can read fails where it is read."""
    ind = Individual(genotype_=UndecodableGenotype(error="bad bytes"))
    with pytest.raises(ValueError, match="cannot be decoded: bad bytes"):
        _ = ind.genotype
