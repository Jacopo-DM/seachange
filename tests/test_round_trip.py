"""Test: genotypes and tags come back from the database unchanged."""

from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import given
from hypothesis import strategies as st

from seachange import EA, Archive, Individual, Population
from seachange.individual import JSONIterable, JSONType
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
            # Rows are expired after the constructor's commit (PLAN.md)
            ea.fetch_population()
            restarted = ea.population[0]
    assert stored.genotype == genotype
    assert stored.tags == tags
    assert restarted.genotype == genotype
    assert restarted.tags == tags
