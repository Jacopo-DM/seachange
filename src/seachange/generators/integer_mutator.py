"""Mutations of integer sequences."""

from typing import TYPE_CHECKING, cast

import numpy as np

from seachange.generators._shared import (
    Integers,
    cut_points,
    rng,
    swap_genes,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

# -- Integer mutator -----------------------------------------------------------


class IntegerMutator:
    """Static mutation operators for integer-encoded individuals."""

    @staticmethod
    def random_reset(
        individual: Integers,
        low: int,
        high: int,
        mutation_probability: float,
    ) -> Integers:
        """Replace with random ingeger individual.

        Replace each gene with a random integer drawn uniformly
        from ``[low, high]``.

        Each gene is independently mutated with probability
        ``mutation_probability``.

        Parameters
        ----------
        individual : Integers
            The integer-encoded genotype to mutate.
        low : int
            Lower bound of the replacement range (inclusive).
        high : int
            Upper bound of the replacement range (inclusive).
        mutation_probability : float
            Per-gene probability of mutation. Must be in ``[0.0, 1.0]``.

        Returns
        -------
        Integers
            A new genotype with randomly reset genes.
        """
        arr: NDArray[np.int_] = np.asarray(individual, dtype=np.int_)
        shape = arr.shape
        replacement = rng.integers(
            low=low,
            high=high,
            size=shape,
            endpoint=True,
        )
        mask: NDArray[np.bool_] = rng.random(shape) < mutation_probability
        return cast(
            "Integers",
            np.where(mask, replacement, arr).astype(int).tolist(),
        )

    @staticmethod
    def integer_creep(
        individual: Integers,
        span: int,
        mutation_probability: float,
    ) -> Integers:
        """
        Apply creep mutation by adding a small random step to each gene.

        Each gene is independently perturbed by a random integer step drawn
        from ``[1, span]`` in a random direction, with the mutation gated by
        ``mutation_probability``.

        Parameters
        ----------
        individual : Integers
            The integer-encoded genotype to mutate.
        span : int
            Maximum absolute step size for each mutation (inclusive).
        mutation_probability : float
            Per-gene probability of mutation. Must be in ``[0.0, 1.0]``.

        Returns
        -------
        Integers
            A new genotype with creep-mutated genes.
        """
        arr: NDArray[np.int_] = np.array(individual, dtype=np.int_)
        shape = arr.shape
        step = rng.integers(low=1, high=span, size=shape, endpoint=True)
        sign: NDArray[np.int_] = rng.choice(np.array([-1, 1]), size=shape)
        gate: NDArray[np.int_] = rng.choice(
            np.array([1, 0]),
            size=shape,
            p=[mutation_probability, 1.0 - mutation_probability],
        )
        return cast("Integers", (arr + step * sign * gate).astype(int).tolist())

    @staticmethod
    def swap(
        individual: Integers,
        mutation_probability: float,
    ) -> Integers:
        """
        Randomly swap pairs of genes within the individual.

        Each gene is independently considered for a swap with a randomly
        chosen other gene, with probability ``mutation_probability``.

        Parameters
        ----------
        individual : Integers
            The integer-encoded genotype to mutate.
        mutation_probability : float
            Per-gene probability of initiating a swap. Must be in
            ``[0.0, 1.0]``.

        Returns
        -------
        Integers
            A new genotype with swapped genes.
        """
        return swap_genes(individual, mutation_probability)

    @staticmethod
    def inversion(
        individual: Integers,
        mutation_probability: float,
    ) -> Integers:
        """
        Reverse a randomly selected sub-sequence of the genotype.

        With probability ``mutation_probability``, two cut points are chosen
        uniformly at random and the segment between them is reversed in place.

        Parameters
        ----------
        individual : Integers
            The integer-encoded genotype to mutate.
        mutation_probability : float
            Probability that inversion occurs. Must be in ``[0.0, 1.0]``.

        Returns
        -------
        Integers
            A new genotype with the selected segment reversed, or an
            unchanged copy if mutation did not occur.
        """
        if rng.random() >= mutation_probability:
            return list(individual)
        arr: list[int] = list(individual)
        lo, hi = cut_points(len(arr))
        arr[lo:hi] = arr[lo:hi][::-1]
        return arr

    @staticmethod
    def scramble(
        individual: Integers,
        mutation_probability: float,
    ) -> Integers:
        """
        Randomly shuffle a sub-sequence of the genotype.

        With probability ``mutation_probability``, two cut points are chosen
        uniformly at random and the segment between them is shuffled in place.

        Parameters
        ----------
        individual : Integers
            The integer-encoded genotype to mutate.
        mutation_probability : float
            Probability that scramble occurs. Must be in ``[0.0, 1.0]``.

        Returns
        -------
        Integers
            A new genotype with the selected segment scrambled, or an
            unchanged copy if mutation did not occur.
        """
        if rng.random() >= mutation_probability:
            return list(individual)
        arr: list[int] = list(individual)
        lo, hi = cut_points(len(arr))
        segment: list[int] = arr[lo:hi]
        rng.shuffle(
            np.array(segment)
        )  # shuffle produces NDArray; re-assign below
        shuffled: list[int] = cast(
            "list[int]",
            rng.permutation(segment).tolist(),
        )
        arr[lo:hi] = shuffled
        return arr
