"""Codecs: how a genotype is turned into bytes for the database and back.

Every individual of a run shares one kind of genotype, so a run stores all
of its genotypes with one codec. seachange ships two:

``JsonCodec``
    Lists and dicts of strings, numbers and booleans, as JSON text.
``NumpyCodec``
    numpy arrays, as numpy's own ``.npy`` format: dtype and shape in a short
    header, then the raw values. Lossless; any numpy reads it back.

A run picks its codec from its first genotype with ``codec_for``: it asks
each automatic codec whether it ``handles`` that genotype, newest
registered first, and falls back to ``JsonCodec``. ``register_codec`` adds
an automatic codec, for example one for PyTorch tensors.
"""

import io
import json
from typing import Protocol

import numpy as np
from numpy.lib import format as npy_format
from numpy.typing import NDArray
from pydantic import TypeAdapter, ValidationError

from seachange.individual import JSONIterable

_JSON_GENOTYPE: TypeAdapter[JSONIterable] = TypeAdapter(JSONIterable)

# Any numpy array; numpy.generic takes its item type only in the stubs
type Array = NDArray[np.generic[object]]


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
        If a codec of the same name is already known.
    """
    if any(known.name == codec.name for known in _automatic()):
        msg = f"a codec named {codec.name!r} is already registered"
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
