"""Codecs: how a genotype is turned into bytes for the database and back.

Every individual of a run shares one kind of genotype, so a run stores all
of its genotypes with one codec. seachange ships two:

``JsonCodec``
    Lists and dicts of strings, numbers and booleans, as JSON text.
``NumpyCodec``
    numpy arrays, as numpy's own ``.npy`` format: dtype and shape in a short
    header, then the raw values. Lossless; any numpy reads it back.

Each genotype picks its codec with ``codec_for``: it asks each automatic
codec whether it ``handles`` that genotype, newest registered first, and
falls back to ``JsonCodec``. ``register_codec`` adds an automatic codec, for
example one for PyTorch tensors.

``GenotypeColumn`` is the database column type that uses them: it stores
the codec's name, a zero byte, then the codec's bytes, and on reading picks
the codec by that name.
"""

import io
import json
from collections.abc import Hashable, Sequence
from typing import Protocol, override

import numpy as np
from numpy.lib import format as npy_format
from numpy.typing import NDArray
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Dialect, LargeBinary
from sqlalchemy.types import TypeDecorator

from seachange.model import Model

type JSONPrimitive = str | int | float | bool
type JSONType = JSONPrimitive | Sequence[JSONType] | dict[Hashable, JSONType]
type JSONIterable = Sequence[JSONType] | dict[Hashable, JSONType]

_JSON_GENOTYPE: TypeAdapter[JSONIterable] = TypeAdapter(JSONIterable)

# Any numpy array; numpy.generic takes its item type only in the stubs
type Array = NDArray[np.generic[object]]
type Genotype = JSONIterable | Array

# Separates the codec name from the codec's bytes in a stored genotype
_NAME_END = b"\0"


class GenotypeCodec(Protocol):
    """Turns one kind of genotype into bytes and back.

    A codec is stateless: ``decode(encode(genotype))`` gives back a genotype
    equal to the original, of the same type.
    """

    @property
    def name(self) -> str:
        """Name stored in the database, so a reader can find the codec."""

    def handles(self, genotype: object) -> bool:
        """Return whether this codec can store ``genotype``.

        Parameters
        ----------
        genotype : object
            A genotype, as assigned to ``Individual.genotype``.

        Returns
        -------
        bool
            ``True`` when ``encode`` accepts it.
        """

    def encode(self, genotype: object) -> bytes:
        """Return ``genotype`` as bytes.

        Parameters
        ----------
        genotype : object
            A genotype this codec ``handles``.

        Returns
        -------
        bytes
            The stored form.

        Raises
        ------
        TypeError
            If the codec does not handle ``genotype``.
        """

    def decode(self, data: bytes) -> object:
        """Return the genotype that ``encode`` turned into ``data``.

        Parameters
        ----------
        data : bytes
            Bytes read from the database.

        Returns
        -------
        object
            The genotype.

        Raises
        ------
        ValueError
            If ``data`` is not something this codec wrote.
        """


# Behaviour, not a record: a codec holds no data
class JsonCodec:
    """Stores lists and dicts of strings, numbers and booleans as JSON text.

    A tuple is stored as a list and a non-string dict key as a string, as
    JSON has no tuples and only string keys; they come back changed.
    """

    name = "json"

    @staticmethod
    def handles(genotype: object) -> bool:
        """Return whether ``genotype`` is a list, tuple or dict.

        Parameters
        ----------
        genotype : object
            A genotype.

        Returns
        -------
        bool
            ``True`` for a list, tuple or dict.
        """
        return isinstance(genotype, list | tuple | dict)

    def encode(self, genotype: object) -> bytes:
        """Return ``genotype`` as UTF-8 JSON text.

        Parameters
        ----------
        genotype : object
            A list, tuple or dict of JSON values.

        Returns
        -------
        bytes
            The JSON text.

        Raises
        ------
        TypeError
            If ``genotype`` is not a list, tuple or dict, or holds a value
            JSON cannot store.
        """
        if not self.handles(genotype):
            msg = f"JsonCodec stores lists and dicts, not {type(genotype)}"
            raise TypeError(msg)
        return json.dumps(genotype).encode()

    @staticmethod
    def decode(data: bytes) -> JSONIterable:
        """Return the list or dict stored as JSON text in ``data``.

        Parameters
        ----------
        data : bytes
            UTF-8 JSON text of a list or dict.

        Returns
        -------
        JSONIterable
            The genotype.

        Raises
        ------
        ValueError
            If ``data`` is not JSON text of a list or dict.
        """
        try:
            return _JSON_GENOTYPE.validate_json(data)
        except ValidationError as error:
            msg = f"not a JSON genotype: {error}"
            raise ValueError(msg) from error


# Behaviour, not a record: a codec holds no data
class NumpyCodec:
    """Stores numpy arrays in numpy's ``.npy`` format, without loss.

    The stored bytes are a complete ``.npy`` file: dtype and shape, then the
    raw values. Arrays of Python objects are refused, since storing them
    would need pickle. Decoded arrays are read-only, as a genotype is set
    once and never changed in place.
    """

    name = "numpy"

    @staticmethod
    def handles(genotype: object) -> bool:
        """Return whether ``genotype`` is a numpy array without objects.

        Parameters
        ----------
        genotype : object
            A genotype.

        Returns
        -------
        bool
            ``True`` for an array whose dtype holds no Python objects.
        """
        return isinstance(genotype, np.ndarray) and not genotype.dtype.hasobject

    def encode(self, genotype: object) -> bytes:
        """Return ``genotype`` as the bytes of a ``.npy`` file.

        Parameters
        ----------
        genotype : object
            A numpy array without Python objects.

        Returns
        -------
        bytes
            The ``.npy`` file.

        Raises
        ------
        TypeError
            If ``genotype`` is not such an array.
        """
        if not isinstance(genotype, np.ndarray) or not self.handles(genotype):
            msg = (
                "NumpyCodec stores numpy arrays without Python objects, "
                f"not {type(genotype)}"
            )
            raise TypeError(msg)
        buffer = io.BytesIO()
        npy_format.write_array(buffer, genotype, allow_pickle=False)
        return buffer.getvalue()

    @staticmethod
    def decode(data: bytes) -> Array:
        """Return the array stored in the ``.npy`` bytes ``data``.

        Parameters
        ----------
        data : bytes
            A ``.npy`` file.

        Returns
        -------
        Array
            The array, read-only.

        Raises
        ------
        ValueError
            If ``data`` is not a ``.npy`` file without Python objects.
        """
        try:
            array: Array = npy_format.read_array(
                io.BytesIO(data), allow_pickle=False
            )
        except ValueError as error:
            msg = f"not a numpy genotype: {error}"
            raise ValueError(msg) from error
        array.flags.writeable = False
        return array


_BUILT_IN: tuple[GenotypeCodec, ...] = (NumpyCodec(), JsonCodec())
_registered: list[GenotypeCodec] = []


def register_codec(codec: GenotypeCodec) -> None:
    """Add ``codec`` to the codecs a run can pick automatically.

    A run asks the codecs registered last first, then ``NumpyCodec``, then
    ``JsonCodec``.

    Parameters
    ----------
    codec : GenotypeCodec
        The codec to add.

    Raises
    ------
    ValueError
        If a codec of the same name is already known, or the name is
        empty or holds a zero byte.
    """
    if any(known.name == codec.name for known in _automatic()):
        msg = f"a codec named {codec.name!r} is already registered"
        raise ValueError(msg)
    if not codec.name or _NAME_END.decode() in codec.name:
        msg = f"a codec name must be text without a zero byte: {codec.name!r}"
        raise ValueError(msg)
    _registered.append(codec)


def _automatic() -> list[GenotypeCodec]:
    # Newest registered first, then the built-in ones, JSON last
    return [*reversed(_registered), *_BUILT_IN]


def codec_for(genotype: object) -> GenotypeCodec:
    """Return the first automatic codec that handles ``genotype``.

    Parameters
    ----------
    genotype : object
        The first genotype of a run.

    Returns
    -------
    GenotypeCodec
        The codec, ``JsonCodec`` when no other one handles it.
    """
    for codec in _automatic():
        if codec.handles(genotype):
            return codec
    return JsonCodec()


def codec_named(name: str) -> GenotypeCodec:
    """Return the known codec called ``name``.

    Parameters
    ----------
    name : str
        A codec name, as stored in a database.

    Returns
    -------
    GenotypeCodec
        The codec.

    Raises
    ------
    ValueError
        If no built-in or registered codec has that name.
    """
    for codec in _automatic():
        if codec.name == name:
            return codec
    known = ", ".join(repr(codec.name) for codec in _automatic())
    msg = f"no codec named {name!r}; known: {known}"
    raise ValueError(msg)


def _decode_stored(value: object) -> object:
    # Bytes as GenotypeColumn writes them, or JSON text from before codecs
    if isinstance(value, str):
        return JsonCodec.decode(value.encode())
    if not isinstance(value, bytes):
        msg = f"a stored genotype is bytes, not {type(value)}"
        raise TypeError(msg)
    name, separator, data = value.partition(_NAME_END)
    if not separator:
        msg = "a stored genotype starts with its codec name"
        raise ValueError(msg)
    return codec_named(name.decode(errors="replace")).decode(data)


class UndecodableGenotype(Model):
    """What a stored genotype reads as when no codec can decode it.

    ``check_rows`` turns it into an error naming the database row, which
    the column type cannot know.

    Parameters
    ----------
    error : str
        Why decoding failed.
    """

    error: str


def decode_error(stored: object) -> str | None:
    """Return why a stored genotype could not be decoded, if it could not.

    Parameters
    ----------
    stored : object
        ``Individual.genotype_`` as loaded.

    Returns
    -------
    str or None
        The decoding error, or ``None`` when ``stored`` is a genotype.
    """
    return stored.error if isinstance(stored, UndecodableGenotype) else None


# Behaviour, not a record: a column type holds no data
class GenotypeColumn(TypeDecorator[object]):
    """Database column that stores a genotype through its codec.

    Writing picks the codec with ``codec_for`` and stores its name, a zero
    byte and its bytes. Reading picks the codec by the stored name. Text
    (as written before codecs, by seachange or ARIEL) is read as JSON.
    """

    impl = LargeBinary
    cache_ok = True

    @override
    def process_bind_param(
        self, value: object | None, dialect: Dialect
    ) -> bytes | None:
        """Return ``value`` encoded for the database.

        Parameters
        ----------
        value : object or None
            A genotype, or ``None`` before one is assigned.
        dialect : Dialect
            The database dialect (unused).

        Returns
        -------
        bytes or None
            The codec name, a zero byte and the codec's bytes.
        """
        if value is None:
            return None
        codec = codec_for(value)
        return codec.name.encode() + _NAME_END + codec.encode(value)

    @override
    def process_result_value(
        self, value: object | None, dialect: Dialect
    ) -> object | None:
        """Return the genotype stored as ``value``.

        Parameters
        ----------
        value : object or None
            The stored bytes, or text written before codecs.
        dialect : Dialect
            The database dialect (unused).

        Returns
        -------
        object or None
            The genotype, or an ``UndecodableGenotype`` saying why there is
            none.
        """
        if value is None:
            return None
        try:
            return _decode_stored(value)
        except (TypeError, ValueError) as error:
            return UndecodableGenotype(error=str(error))
