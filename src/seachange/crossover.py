"""Default crossover functions.

``one_point``, ``n_point`` and ``uniform`` take two lists or two numpy
arrays. Arrays keep their dtype and shape, and the children are arrays;
lists are worked on as ``float64`` and the children are nested lists.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, cast, overload

import numpy as np

from seachange.generators._shared import rng

from .codecs import Array, Genotype, JSONIterable

if TYPE_CHECKING:
    from numpy.typing import NDArray


def _validate_same_shape(
    arr_i: Array,
    arr_j: Array,
) -> None:
    """
    Assert that two arrays share the same shape.

    Parameters
    ----------
    arr_i : Array
        First parent array.
    arr_j : Array
        Second parent array.

    Raises
    ------
    ValueError
        If ``arr_i.shape != arr_j.shape``.
    """
    if arr_i.shape != arr_j.shape:
        msg = (
            f"Parents must share the same shape: "
            f"{arr_i.shape!r} vs {arr_j.shape!r}"
        )
        raise ValueError(
            msg,
        )


def _load(
    parent_i: Genotype,
    parent_j: Genotype,
) -> tuple[tuple[int, ...], Array, Array]:
    """
    Convert two parent genotypes into flat NumPy arrays ready for crossover.

    Two numpy arrays keep their dtype; anything else is cast to
    ``float64``. Both are validated to share the same shape and returned as
    independent flat copies alongside the original shape so results can be
    reshaped before being returned to the caller.

    Parameters
    ----------
    parent_i : Genotype
        First parent genotype.
    parent_j : Genotype
        Second parent genotype.

    Returns
    -------
    shape : tuple[int, ...]
        The original shape of the parent arrays (used for repacking).
    flat_i : Array
        Flattened copy of ``parent_i``.
    flat_j : Array
        Flattened copy of ``parent_j``.
    """
    if isinstance(parent_i, np.ndarray) and isinstance(parent_j, np.ndarray):
        arr_i: Array = parent_i
        arr_j: Array = parent_j
    else:
        arr_i = np.array(parent_i, dtype=float)
        arr_j = np.array(parent_j, dtype=float)
    _validate_same_shape(arr_i, arr_j)
    return arr_i.shape, arr_i.flatten(), arr_j.flatten()


def _pack(flat: Array, shape: tuple[int, ...], like: Genotype) -> Genotype:
    """Reshape to original shape.

    Reshape a flat array back to the original genotype shape: an array when
    the parent ``like`` is one, otherwise a JSON-serialisable Python object.

    Parameters
    ----------
    flat : Array
        One-dimensional array to reshape.
    shape : tuple[int, ...]
        Target shape, as returned by ``_load``.
    like : Genotype
        A parent; its kind decides the kind of the child.

    Returns
    -------
    Genotype
        An array, or nested Python list(s), with the original shape.
    """
    if isinstance(like, np.ndarray):
        return flat.reshape(shape)
    return cast("JSONIterable", flat.reshape(shape).tolist())


class Crossover:
    """Namespace of static crossover operators for evolutionary algorithms."""

    # -- One-point -------------------------------------------------------------

    @overload
    @staticmethod
    def one_point[A: Array](  # pragma: no cover  # typing stub only
        parent_i: A,
        parent_j: A,
    ) -> tuple[A, A]: ...

    @overload
    @staticmethod
    def one_point(  # pragma: no cover  # typing stub only
        parent_i: JSONIterable,
        parent_j: JSONIterable,
    ) -> tuple[JSONIterable, JSONIterable]: ...

    @staticmethod
    def one_point(
        parent_i: Genotype,
        parent_j: Genotype,
    ) -> tuple[Genotype, Genotype]:
        """
        Produce two offspring via single-point crossover.

        A single cut point is chosen uniformly at random from
        ``[1, len(parent) - 1]``. The segment to the right of the cut is
        swapped between the two parents to form two children.

        Parameters
        ----------
        parent_i : JSONIterable or Array
            First parent genotype.
        parent_j : JSONIterable or Array
            Second parent genotype, of the same kind and shape.

        Returns
        -------
        child_i : JSONIterable or Array
            Offspring inheriting the left segment from ``parent_i`` and the
            right segment from ``parent_j``.
        child_j : JSONIterable or Array
            Offspring inheriting the left segment from ``parent_j`` and the
            right segment from ``parent_i``.
        """
        shape, flat_i, flat_j = _load(parent_i, parent_j)
        point: int = int(rng.integers(1, len(flat_i)))
        c1, c2 = flat_i.copy(), flat_j.copy()
        c1[point:] = flat_j[point:]
        c2[point:] = flat_i[point:]
        return _pack(c1, shape, parent_i), _pack(c2, shape, parent_j)

    # -- N-point ---------------------------------------------------------------

    @overload
    @staticmethod
    def n_point[A: Array](  # pragma: no cover  # typing stub only
        parent_i: A,
        parent_j: A,
        n: int,
    ) -> tuple[A, A]: ...

    @overload
    @staticmethod
    def n_point(  # pragma: no cover  # typing stub only
        parent_i: JSONIterable,
        parent_j: JSONIterable,
        n: int,
    ) -> tuple[JSONIterable, JSONIterable]: ...

    @staticmethod
    def n_point(
        parent_i: Genotype,
        parent_j: Genotype,
        n: int,
    ) -> tuple[Genotype, Genotype]:
        """
        Produce two offspring via n-point crossover.

        ``n`` cut points are chosen uniformly at random without replacement
        from ``[1, len(parent) - 1]``. Alternating segments between
        consecutive cut points are swapped between the two parents.

        Parameters
        ----------
        parent_i : JSONIterable or Array
            First parent genotype.
        parent_j : JSONIterable or Array
            Second parent genotype, of the same kind and shape.
        n : int
            Number of cut points. Must satisfy ``1 <= n < len(parent)``.

        Returns
        -------
        child_i : JSONIterable or Array
            First offspring produced by alternating segment exchange.
        child_j : JSONIterable or Array
            Second offspring produced by alternating segment exchange.

        Raises
        ------
        ValueError
            If ``n`` is not in ``[1, len(parent) - 1]``.
        ValueError
            If the parents do not share the same shape.
        """
        shape, flat_i, flat_j = _load(parent_i, parent_j)
        length: int = len(flat_i)

        if n < 1 or n >= length:
            msg = f"n must be in [1, len(parent)-1], got n={n}, length={length}"
            raise ValueError(
                msg,
            )

        raw: NDArray[np.intp] = rng.choice(
            np.arange(1, length, dtype=np.intp),
            size=n,
            replace=False,
        )
        cuts: list[int] = [0, *sorted(raw.tolist()), length]

        c1, c2 = flat_i.copy(), flat_j.copy()
        for seg in range(1, len(cuts) - 1):
            lo: int = cuts[seg]
            hi: int = cuts[seg + 1]
            if seg % 2 == 1:
                c1[lo:hi] = flat_j[lo:hi]
                c2[lo:hi] = flat_i[lo:hi]

        return _pack(c1, shape, parent_i), _pack(c2, shape, parent_j)

    # -- Uniform ---------------------------------------------------------------

    @overload
    @staticmethod
    def uniform[A: Array](  # pragma: no cover  # typing stub only
        parent_i: A,
        parent_j: A,
        swap_probability: float = ...,
    ) -> tuple[A, A]: ...

    @overload
    @staticmethod
    def uniform(  # pragma: no cover  # typing stub only
        parent_i: JSONIterable,
        parent_j: JSONIterable,
        swap_probability: float = ...,
    ) -> tuple[JSONIterable, JSONIterable]: ...

    @staticmethod
    def uniform(
        parent_i: Genotype,
        parent_j: Genotype,
        swap_probability: float = 0.5,
    ) -> tuple[Genotype, Genotype]:
        """
        Produce two offspring via uniform crossover.

        Each gene is independently swapped between parents with probability
        ``swap_probability``. At ``0.5`` each gene has an equal chance of
        coming from either parent.

        Parameters
        ----------
        parent_i : JSONIterable or Array
            First parent genotype.
        parent_j : JSONIterable or Array
            Second parent genotype, of the same kind and shape.
        swap_probability : float, optional
            Per-gene probability of exchanging alleles between parents.
            Must be in ``[0.0, 1.0]``. Default is ``0.5``.

        Returns
        -------
        child_i : JSONIterable or Array
            First offspring after uniform gene exchange.
        child_j : JSONIterable or Array
            Second offspring after uniform gene exchange.

        Raises
        ------
        ValueError
            If ``swap_probability`` is outside ``[0.0, 1.0]``.
        ValueError
            If the parents do not share the same shape.
        """
        if not 0.0 <= swap_probability <= 1.0:
            msg = f"swap_probability must be in [0, 1], got {swap_probability}"
            raise ValueError(msg)

        shape, flat_i, flat_j = _load(parent_i, parent_j)
        mask: NDArray[np.bool_] = rng.random(len(flat_i)) < swap_probability

        c1, c2 = flat_i.copy(), flat_j.copy()
        c1[mask] = flat_j[mask]
        c2[mask] = flat_i[mask]

        return _pack(c1, shape, parent_i), _pack(c2, shape, parent_j)

    # -- Order crossover (OX), for permutation representations ---------------

    @staticmethod
    def order_crossover(
        parent_i: Sequence[int],
        parent_j: Sequence[int],
    ) -> tuple[list[int], list[int]]:
        """
        Produce two offspring via order crossover (OX).

        OX is designed for permutation-encoded individuals. A contiguous
        segment is copied directly from one parent; the remaining positions
        are filled in the relative order they appear in the other parent,
        starting from the position immediately after the segment end and
        wrapping around. This preserves both the sub-sequence and the
        relative ordering of genes not in the segment.

        Parameters
        ----------
        parent_i : Sequence[int]
            First parent permutation.
        parent_j : Sequence[int]
            Second parent permutation.

        Returns
        -------
        child_i : list[int]
            Offspring with the ``[lo:hi]`` segment inherited from
            ``parent_i`` and remaining genes filled from ``parent_j``.
        child_j : list[int]
            Offspring with the ``[lo:hi]`` segment inherited from
            ``parent_j`` and remaining genes filled from ``parent_i``.

        Raises
        ------
        ValueError
            If ``parent_i`` and ``parent_j`` differ in length.
        """
        if len(parent_i) != len(parent_j):
            msg = (
                f"Parents must have equal length: "
                f"{len(parent_i)} vs {len(parent_j)}"
            )
            raise ValueError(
                msg,
            )

        n: int = len(parent_i)
        pi: list[int] = list(parent_i)
        pj: list[int] = list(parent_j)

        cuts: list[int] = sorted(
            cast(
                "list[int]",
                rng.choice(
                    np.arange(n + 1, dtype=np.intp),
                    size=2,
                    replace=False,
                ).tolist(),
            ),
        )
        lo: int = cuts[0]
        hi: int = cuts[1]

        def _ox(donor: list[int], other: list[int]) -> list[int]:
            segment: set[int] = set(donor[lo:hi])
            child: list[int | None] = [None] * n
            child[lo:hi] = donor[lo:hi]
            fill_positions: list[int] = [
                (hi + k) % n for k in range(n - (hi - lo))
            ]
            fill_values: list[int] = [
                gene
                for gene in (other[hi:] + other[:hi])
                if gene not in segment
            ]
            for pos, val in zip(fill_positions, fill_values, strict=False):
                child[pos] = val
            return cast("list[int]", child)

        return _ox(pi, pj), _ox(pj, pi)
