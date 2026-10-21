"""Test: genotypes and tags come back from the database unchanged."""

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp

from seachange import (
    EA,
    Archive,
    Individual,
    JSONIterable,
    JSONType,
    Population,
)
from seachange.codecs import Array
from tests.ea_helpers import noop

# What JSONType allows and a JSON column keeps: lists, string dict keys,
# no None (JSONType has none), no NaN or inf
JSON_VALUES = st.recursive(
    st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda inner: (
        st.lists(inner, max_size=4)
        | st.dictionaries(st.text(max_size=5), inner, max_size=4)
    ),
    max_leaves=10,
)
GENOTYPES = st.lists(JSON_VALUES, max_size=5) | st.dictionaries(
    st.text(max_size=5), JSON_VALUES, max_size=4
)
TAGS = st.dictionaries(st.text(max_size=5), JSON_VALUES, max_size=4)


@given(genotype=GENOTYPES, tags=TAGS)
def test_genotype_and_tags_survive_a_run(
    genotype: JSONIterable, tags: dict[JSONType, JSONType]
) -> None:
    """What a run stores, Archive and EA.restart read back equal."""
    with TemporaryDirectory() as folder:
        db = Path(folder) / "run.db"
        individual = Individual()
        individual.genotype = genotype
        individual.tags = tags
        individual.fitness = 1.0
        with EA(Population([individual]), [noop], db_file_path=db, quiet=True):
            pass
        with Archive(db) as archive:
            stored = archive.random_individual()
        with EA.restart(
            db, [noop], db_file_path=Path(folder) / "again.db", quiet=True
        ) as ea:
            restarted = ea.population[0]
    assert stored.genotype == genotype
    assert stored.tags == tags
    assert restarted.genotype == genotype
    assert restarted.tags == tags


# Non-empty numeric arrays of every numeric dtype, up to 3 dimensions
ARRAY_GENOTYPES = hnp.arrays(
    dtype=hnp.floating_dtypes()
    | hnp.integer_dtypes()
    | hnp.complex_number_dtypes(),
    shape=hnp.array_shapes(min_dims=1, max_dims=3, min_side=1, max_side=4),
)


@given(genotype=ARRAY_GENOTYPES)
def test_numpy_genotypes_survive_a_run(genotype: Array) -> None:
    """A numpy genotype comes back as an array of the same dtype and shape."""
    with TemporaryDirectory() as folder:
        db = Path(folder) / "run.db"
        individual = Individual()
        individual.genotype = genotype
        individual.fitness = 1.0
        with EA(Population([individual]), [noop], db_file_path=db, quiet=True):
            pass
        with Archive(db) as archive:
            stored = archive.random_individual().genotype
        with EA.restart(
            db, [noop], db_file_path=Path(folder) / "again.db", quiet=True
        ) as ea:
            ea.fetch_population()
            restarted = ea.population[0].genotype
    for back in (stored, restarted):
        assert isinstance(back, np.ndarray)
        assert back.dtype == genotype.dtype
        assert back.shape == genotype.shape
        assert back.tobytes() == genotype.tobytes()
        assert not back.flags.writeable
