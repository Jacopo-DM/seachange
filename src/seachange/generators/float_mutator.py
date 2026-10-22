"""Mutations of float sequences."""

from typing import TYPE_CHECKING, cast

import numpy as np

from seachange._rng import rng
from seachange.generators._shared import (
    UNIFORM_MEDIAN,
    Floats,
    cut_points,
    swap_genes,
)

if TYPE_CHECKING:
    from numpy.typing import NDArray

# -- Float mutator -------------------------------------------------------------


class FloatMutator:
    """Namespace of static mutation operators for real-valued individuals."""

    @staticmethod
    def gaussian(
        individual: Floats,
        std: float,
        mutation_probability: float,
        *,
        lower_bound: float | None = None,
        upper_bound: float | None = None,
    ) -> Floats:
        """
        Perturb each gene by adding Gaussian noise.

        Each gene is independently mutated with probability
        ``mutation_probability`` by adding zero-mean Gaussian noise with
        standard deviation ``std``. Optional bounds clip the result.

        Parameters
        ----------
        individual : Floats
            The real-valued genotype to mutate.
        std : float
            Standard deviation of the Gaussian noise.
        mutation_probability : float
            Per-gene probability of mutation. Must be in ``[0.0, 1.0]``.
        lower_bound : float or None, optional
            Minimum allowable gene value after mutation. No clipping applied
            when ``None``. Default is ``None``.
        upper_bound : float or None, optional
            Maximum allowable gene value after mutation. No clipping applied
            when ``None``. Default is ``None``.

        Returns
        -------
        Floats
            A new genotype with Gaussian-perturbed genes.
        """
        arr: NDArray[np.float64] = np.array(individual, dtype=np.float64)
        shape = arr.shape
        noise: NDArray[np.float64] = rng.normal(loc=0.0, scale=std, size=shape)
        mask: NDArray[np.bool_] = rng.random(shape) < mutation_probability
        result: NDArray[np.float64] = np.where(mask, arr + noise, arr)
        if lower_bound is not None:
            result = np.maximum(result, lower_bound)
        if upper_bound is not None:
            result = np.minimum(result, upper_bound)
        return cast("Floats", result.tolist())

    @staticmethod
    def uniform_reset(
        individual: Floats,
        low: float,
        high: float,
        mutation_probability: float,
    ) -> Floats:
        """
        Replace each gene with a value drawn uniformly from ``[low, high)``.

        Each gene is independently mutated with probability
        ``mutation_probability``.

        Parameters
        ----------
        individual : Floats
            The real-valued genotype to mutate.
        low : float
            Lower bound of the replacement range (inclusive).
        high : float
            Upper bound of the replacement range (exclusive).
        mutation_probability : float
            Per-gene probability of mutation. Must be in ``[0.0, 1.0]``.

        Returns
        -------
        Floats
            A new genotype with uniformly reset genes.
        """
        arr: NDArray[np.float64] = np.array(individual, dtype=np.float64)
        shape = arr.shape
        replacement: NDArray[np.float64] = rng.uniform(
            low=low, high=high, size=shape
        )
        mask: NDArray[np.bool_] = rng.random(shape) < mutation_probability
        return cast("Floats", np.where(mask, replacement, arr).tolist())

    @staticmethod
    def boundary(
        individual: Floats,
        low: float,
        high: float,
        mutation_probability: float,
    ) -> Floats:
        """
        Reset each gene to either the lower or upper boundary value.

        Each gene is independently mutated with probability
        ``mutation_probability`` by replacing it with either ``low`` or
        ``high``, chosen at random with equal probability.

        Parameters
        ----------
        individual : Floats
            The real-valued genotype to mutate.
        low : float
            Lower boundary value.
        high : float
            Upper boundary value.
        mutation_probability : float
            Per-gene probability of mutation. Must be in ``[0.0, 1.0]``.

        Returns
        -------
        Floats
            A new genotype with boundary-reset genes.
        """
        arr: NDArray[np.float64] = np.array(individual, dtype=np.float64)
        shape = arr.shape
        boundary_vals: NDArray[np.float64] = rng.choice(
            np.array([low, high]),
            size=shape,
        ).astype(np.float64)
        mask: NDArray[np.bool_] = rng.random(shape) < mutation_probability
        return cast("Floats", np.where(mask, boundary_vals, arr).tolist())

    @staticmethod
    def polynomial(
        individual: Floats,
        low: float,
        high: float,
        mutation_probability: float,
        distribution_index: float = 20.0,
    ) -> Floats:
        """
        Apply polynomial mutation as defined in Deb & Goyal (1996).

        Each gene is independently mutated with probability
        ``mutation_probability`` using a polynomial perturbation that
        respects the ``[low, high]`` bounds. A higher ``distribution_index``
        produces perturbations closer to the parent gene.

        Parameters
        ----------
        individual : Floats
            The real-valued genotype to mutate.
        low : float
            Lower bound of the valid gene range (inclusive).
        high : float
            Upper bound of the valid gene range (inclusive).
        mutation_probability : float
            Per-gene probability of mutation. Must be in ``[0.0, 1.0]``.
        distribution_index : float, optional
            Controls the spread of the mutation distribution. Larger values
            concentrate mutations near the original gene. Default is ``20.0``.

        Returns
        -------
        Floats
            A new genotype with polynomial-mutated genes, clipped to
            ``[low, high]``.
        """
        arr: NDArray[np.float64] = np.array(individual, dtype=np.float64)
        mask: NDArray[np.bool_] = rng.random(arr.shape) < mutation_probability
        u: NDArray[np.float64] = rng.random(arr.shape)
        eta: float = distribution_index

        delta_low: NDArray[np.float64] = (arr - low) / (high - low)
        delta_high: NDArray[np.float64] = (high - arr) / (high - low)

        delta_q = np.where(
            u <= UNIFORM_MEDIAN,
            (2.0 * u + (1.0 - 2.0 * u) * (1.0 - delta_low) ** (eta + 1.0))
            ** (1.0 / (eta + 1.0))
            - 1.0,
            1.0
            - (
                2.0 * (1.0 - u)
                + 2.0 * (u - 0.5) * (1.0 - delta_high) ** (eta + 1.0)
            )
            ** (1.0 / (eta + 1.0)),
        )
        result: NDArray[np.float64] = np.clip(
            np.where(mask, arr + delta_q * (high - low), arr),
            low,
            high,
        )
        return cast("Floats", result.tolist())

    @staticmethod
    def swap(
        individual: Floats,
        mutation_probability: float,
    ) -> Floats:
        """
        Randomly swap pairs of genes within the individual.

        Each gene is independently considered for a swap with a randomly
        chosen other gene, with probability ``mutation_probability``.

        Parameters
        ----------
        individual : Floats
            The real-valued genotype to mutate.
        mutation_probability : float
            Per-gene probability of initiating a swap. Must be in
            ``[0.0, 1.0]``.

        Returns
        -------
        Floats
            A new genotype with swapped genes.
        """
        return swap_genes(individual, mutation_probability)

    @staticmethod
    def inversion(
        individual: Floats,
        mutation_probability: float,
    ) -> Floats:
        """
        Reverse a randomly selected sub-sequence of the genotype.

        With probability ``mutation_probability``, two cut points are chosen
        uniformly at random and the segment between them is reversed in place.

        Parameters
        ----------
        individual : Floats
            The real-valued genotype to mutate.
        mutation_probability : float
            Probability that inversion occurs. Must be in ``[0.0, 1.0]``.

        Returns
        -------
        Floats
            A new genotype with the selected segment reversed, or an
            unchanged copy if mutation did not occur.
        """
        if rng.random() >= mutation_probability:
            return list(individual)
        arr: list[float] = list(individual)
        lo, hi = cut_points(len(arr))
        arr[lo:hi] = arr[lo:hi][::-1]
        return arr
