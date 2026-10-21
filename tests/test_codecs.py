"""Test: genotype codecs, and how a run picks one."""

import json

import numpy as np
import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from hypothesis.extra import numpy as hnp
from sqlalchemy.dialects import sqlite

from seachange import (
    GenotypeCodec,
    JsonCodec,
    JSONIterable,
    NumpyCodec,
    register_codec,
)
from seachange import codecs as codecs_module
from seachange.codecs import Array, GenotypeColumn, codec_for, codec_named
from tests.test_round_trip import GENOTYPES

# Every dtype numpy stores without pickle, in shapes up to 3 dimensions
ARRAYS = hnp.arrays(
    dtype=hnp.scalar_dtypes()
    | hnp.byte_string_dtypes()
    | hnp.unicode_string_dtypes(),
    shape=hnp.array_shapes(min_dims=0, max_dims=3, min_side=0, max_side=4),
)


@pytest.fixture
def no_registered_codecs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the test an empty list of registered codecs, restored after."""
    monkeypatch.setattr(codecs_module, "_registered", [])


# Behaviour, not a record: a test codec holds no data
class FrozensetCodec:
    """A user codec: frozensets of strings, stored as a sorted JSON list."""

    name = "frozenset"

    @staticmethod
    def handles(genotype: object) -> bool:
        """Return whether ``genotype`` is a frozenset.

        Parameters
        ----------
        genotype : object
            A genotype.

        Returns
        -------
        bool
            ``True`` for a frozenset.
        """
        return isinstance(genotype, frozenset)

    def encode(self, genotype: object) -> bytes:
        """Return the sorted members as JSON text.

        Parameters
        ----------
        genotype : object
            A frozenset of strings.

        Returns
        -------
        bytes
            The JSON text.

        Raises
        ------
        TypeError
            If ``genotype`` is not a frozenset.
        """
        if not isinstance(genotype, frozenset) or not self.handles(genotype):
            raise TypeError
        return json.dumps(sorted(str(member) for member in genotype)).encode()

    @staticmethod
    def decode(data: bytes) -> frozenset[str]:
        """Return the frozenset stored in ``data``.

        Parameters
        ----------
        data : bytes
            JSON text of a list of strings.

        Returns
        -------
        frozenset of str
            The genotype.
        """
        members: list[str] = json.loads(data)
        return frozenset(members)


# -- JsonCodec -----------------------------------------------------------------


@given(genotype=GENOTYPES)
def test_json_codec_round_trips(genotype: JSONIterable) -> None:
    """Lists and dicts with string keys come back equal."""
    codec = JsonCodec()
    assert codec.decode(codec.encode(genotype)) == genotype


def test_json_codec_turns_tuples_and_number_keys_into_json() -> None:
    """JSON has no tuples and only string keys: they come back changed."""
    codec = JsonCodec()
    assert codec.decode(codec.encode((1, 2))) == [1, 2]
    assert codec.decode(codec.encode({1: "a"})) == {"1": "a"}


def test_json_codec_refuses_what_is_not_a_list_or_dict() -> None:
    """A number is not a JSON genotype."""
    with pytest.raises(TypeError, match="lists and dicts"):
        JsonCodec().encode(5)


@given(data=st.binary())
@example(data=b'[1, "a", {"k": true}]')
@example(data=b"5")
def test_json_codec_decodes_a_genotype_or_refuses(data: bytes) -> None:
    """Any bytes give a list or dict, or ValueError: nothing else."""
    outcome: object
    try:
        outcome = JsonCodec().decode(data)
    except ValueError as error:
        outcome = error
    if isinstance(outcome, ValueError):
        assert "not a JSON genotype" in str(outcome)
    else:
        assert isinstance(outcome, list | dict)


# -- NumpyCodec ----------------------------------------------------------------


@given(array=ARRAYS)
def test_numpy_codec_round_trips_exactly(array: Array) -> None:
    """dtype, shape and every bit come back, NaN and byte order included."""
    codec = NumpyCodec()
    back = codec.decode(codec.encode(array))
    assert back.dtype == array.dtype
    assert back.shape == array.shape
    assert back.tobytes() == array.tobytes()


def test_numpy_codec_returns_read_only_arrays() -> None:
    """A decoded genotype cannot be changed in place."""
    codec = NumpyCodec()
    back = codec.decode(codec.encode(np.zeros(3, dtype=np.float32)))
    with pytest.raises(ValueError, match="read-only"):
        back[0] = 1.0


def test_numpy_codec_refuses_object_arrays_and_non_arrays() -> None:
    """Storing Python objects would need pickle; a list is not an array."""
    codec = NumpyCodec()
    objects = np.array([object()])
    assert not codec.handles(objects)
    with pytest.raises(TypeError, match="without Python objects"):
        codec.encode(objects)
    with pytest.raises(TypeError, match="without Python objects"):
        codec.encode([1.0, 2.0])


@given(data=st.binary())
@example(data=NumpyCodec().encode(np.arange(3)))
def test_numpy_codec_decodes_an_array_or_refuses(data: bytes) -> None:
    """Any bytes give an array, or ValueError: nothing else."""
    outcome: object
    try:
        outcome = NumpyCodec().decode(data)
    except ValueError as error:
        outcome = error
    if isinstance(outcome, ValueError):
        assert "not a numpy genotype" in str(outcome)
    else:
        assert isinstance(outcome, np.ndarray)


# -- Picking a codec -----------------------------------------------------------


@pytest.mark.usefixtures("no_registered_codecs")
@pytest.mark.parametrize(
    ("genotype", "name"),
    [
        (np.zeros(3), "numpy"),
        ([1.0, 2.0], "json"),
        ({"a": 1}, "json"),
        (np.array([object()]), "json"),
        (5, "json"),
    ],
)
def test_codec_for_picks_by_the_genotype(genotype: object, name: str) -> None:
    """Arrays get NumpyCodec; everything else falls back to JsonCodec."""
    assert codec_for(genotype).name == name


@pytest.mark.usefixtures("no_registered_codecs")
def test_a_registered_codec_is_picked_and_found_by_name() -> None:
    """register_codec adds an automatic codec without touching EA."""
    codec: GenotypeCodec = FrozensetCodec()
    register_codec(codec)
    genotype = frozenset({"b", "a"})
    picked = codec_for(genotype)
    assert picked is codec
    assert codec_named("frozenset") is codec
    assert picked.decode(picked.encode(genotype)) == genotype
    with pytest.raises(TypeError):
        picked.encode(["a"])


@pytest.mark.usefixtures("no_registered_codecs")
def test_a_codec_name_can_be_registered_once() -> None:
    """Two codecs of one name would make a stored name ambiguous."""
    register_codec(FrozensetCodec())
    with pytest.raises(ValueError, match="already registered"):
        register_codec(FrozensetCodec())
    with pytest.raises(ValueError, match="already registered"):
        register_codec(JsonCodec())


@pytest.mark.usefixtures("no_registered_codecs")
def test_codec_named_finds_built_ins_and_names_the_known_ones() -> None:
    """A stored name finds its codec; an unknown one lists the known."""
    assert codec_named("numpy").name == "numpy"
    assert codec_named("json").name == "json"
    with pytest.raises(ValueError, match="known: 'numpy', 'json'"):
        codec_named("torch")


@pytest.mark.usefixtures("no_registered_codecs")
@pytest.mark.parametrize("name", ["", "a\0b"])
def test_a_codec_name_is_text_without_a_zero_byte(name: str) -> None:
    """The zero byte ends the name in a stored genotype."""
    codec = FrozensetCodec()
    codec.name = name
    with pytest.raises(ValueError, match="without a zero byte"):
        register_codec(codec)


# -- GenotypeColumn ------------------------------------------------------------


def test_the_column_stores_the_codec_name_first() -> None:
    """Stored bytes are the codec name, a zero byte, the codec's bytes."""
    column = GenotypeColumn()
    dialect = sqlite.dialect()
    stored = column.process_bind_param([1, 2], dialect)
    assert stored == b"json\0[1, 2]"
    assert column.process_result_value(stored, dialect) == [1, 2]


def test_the_column_keeps_a_missing_genotype_missing() -> None:
    """None is stored as NULL and read back as None."""
    column = GenotypeColumn()
    dialect = sqlite.dialect()
    assert column.process_bind_param(None, dialect) is None
    assert column.process_result_value(None, dialect) is None
