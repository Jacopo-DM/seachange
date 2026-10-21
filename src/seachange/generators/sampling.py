"""Generators of integer and float sequences."""

from collections.abc import Sequence
from typing import cast, overload

import numpy as np

from seachange.generators._shared import (
    Floats,
    Integers,
    rng,
    settings,
)

# -- Integer generator ---------------------------------------------------------


class IntegersGenerator:
    """Namespace of static methods for generating integer sequences."""

    @overload
    @staticmethod
    def integers(
        low: int,
        high: int,
        size: None,
        *,
        endpoint: bool | None = None,
    ) -> int: ...

    @overload
    @staticmethod
    def integers(
        low: int,
        high: int,
        size: int | Sequence[int] = 1,
        *,
        endpoint: bool | None = None,
    ) -> Integers: ...

    @staticmethod
    def integers(
        low: int,
        high: int,
        size: int | Sequence[int] | None = 1,
        *,
        endpoint: bool | None = None,
    ) -> int | Integers:
        """
        Draw random integers from a uniform discrete distribution.

        Parameters
        ----------
        low : int
            Lowest integer to be drawn (inclusive).
        high : int
            Upper boundary. Inclusive when ``endpoint`` is ``True``,
            exclusive otherwise.
        size : int or Sequence[int] or None, optional
            Output shape. Default is ``1``.
        endpoint : bool or None, optional
            Whether ``high`` is included in the range. Falls back to
            ``settings.integers_endpoint`` when ``None``.

        Returns
        -------
        int or Integers
            One integer when ``size`` is ``None``, otherwise a list of
            sampled integers with length ``size``.
        """
        ep: bool = (
            endpoint if endpoint is not None else settings.integers_endpoint
        )
        return cast(
            "int | Integers",
            rng
            .integers(
                low=low,
                high=high,
                size=size,
                endpoint=ep,
            )
            .astype(int)
            .tolist(),
        )

    @overload
    @staticmethod
    def choice(
        value_set: int | Integers,
        size: None,
        probabilities: Sequence[float] | None = None,
        axis: int = 0,
        *,
        replace: bool | None = None,
        shuffle: bool | None = None,
    ) -> int: ...

    @overload
    @staticmethod
    def choice(
        value_set: int | Integers,
        size: int | Sequence[int] = 1,
        probabilities: Sequence[float] | None = None,
        axis: int = 0,
        *,
        replace: bool | None = None,
        shuffle: bool | None = None,
    ) -> Integers: ...

    @staticmethod
    def choice(  # ruff: ignore[too-many-arguments]  # signature kept as copied from ARIEL
        value_set: int | Integers,
        size: int | Sequence[int] | None = 1,
        probabilities: Sequence[float] | None = None,
        axis: int = 0,
        *,
        replace: bool | None = None,
        shuffle: bool | None = None,
    ) -> int | Integers:
        """
        Draw a random sample from a given integer set or range.

        Parameters
        ----------
        value_set : int or Integers
            If an ``int``, samples are drawn from ``range(value_set)``.
            Otherwise, samples are drawn from the provided sequence.
        size : int or Sequence[int] or None, optional
            Output shape. Default is ``1``.
        probabilities : Sequence[float] or None, optional
            Probabilities associated with each element of ``value_set``.
            Must sum to 1. When ``None``, a uniform distribution is used.
        axis : int, optional
            Axis along which to draw samples when ``value_set`` is
            multi-dimensional. Default is ``0``.
        replace : bool or None, optional
            Whether to sample with replacement. Falls back to
            ``settings.choice_replace`` when ``None``.
        shuffle : bool or None, optional
            Whether to shuffle the output. Falls back to
            ``settings.choice_shuffle`` when ``None``.

        Returns
        -------
        int or Integers
            One integer when ``size`` is ``None``, otherwise a list of
            sampled integers.
        """
        r: bool = replace if replace is not None else settings.choice_replace
        s: bool = shuffle if shuffle is not None else settings.choice_shuffle
        return cast(
            "int | Integers",
            np
            .array(
                rng.choice(
                    a=value_set,
                    size=size,
                    replace=r,
                    p=probabilities,
                    axis=axis,
                    shuffle=s,
                ),
            )
            .astype(int)
            .tolist(),
        )

    @staticmethod
    def permutation(n: int) -> list[int]:
        """
        Return a random permutation of integers ``0`` to ``n - 1``.

        Parameters
        ----------
        n : int
            Upper bound (exclusive) of the integer range to permute.

        Returns
        -------
        list[int]
            A randomly ordered list of integers from ``0`` to ``n - 1``.
        """
        return cast("list[int]", rng.permutation(n).tolist())


# -- Float generator -----------------------------------------------------------


class FloatsGenerator:
    """Namespace of static methods for generating float sequences."""

    @overload
    @staticmethod
    def uniform(low: float, high: float, size: None) -> float: ...

    @overload
    @staticmethod
    def uniform(
        low: float,
        high: float,
        size: int | Sequence[int] = 1,
    ) -> Floats: ...

    @staticmethod
    def uniform(
        low: float,
        high: float,
        size: int | Sequence[int] | None = 1,
    ) -> float | Floats:
        """
        Draw samples from a continuous uniform distribution.

        Parameters
        ----------
        low : float
            Lower boundary of the distribution (inclusive).
        high : float
            Upper boundary of the distribution (exclusive).
        size : int or Sequence[int] or None, optional
            Output shape. Default is ``1``.

        Returns
        -------
        float or Floats
            One float when ``size`` is ``None``, otherwise a list of
            uniformly sampled floats.
        """
        return cast(
            "float | Floats",
            np.asarray(rng.uniform(low=low, high=high, size=size)).tolist(),
        )

    @overload
    @staticmethod
    def normal(mean: float, std: float, size: None) -> float: ...

    @overload
    @staticmethod
    def normal(mean: float = 0.0, std: float = 1.0, *, size: None) -> float: ...

    @overload
    @staticmethod
    def normal(
        mean: float = 0.0,
        std: float = 1.0,
        size: int | Sequence[int] = 1,
    ) -> Floats: ...

    @staticmethod
    def normal(
        mean: float = 0.0,
        std: float = 1.0,
        size: int | Sequence[int] | None = 1,
    ) -> float | Floats:
        """
        Draw samples from a Gaussian (normal) distribution.

        Parameters
        ----------
        mean : float, optional
            Mean of the distribution. Default is ``0.0``.
        std : float, optional
            Standard deviation of the distribution. Default is ``1.0``.
        size : int or Sequence[int] or None, optional
            Output shape. Default is ``1``.

        Returns
        -------
        float or Floats
            One float when ``size`` is ``None``, otherwise a list of
            normally distributed floats.
        """
        return cast(
            "float | Floats",
            np.asarray(rng.normal(loc=mean, scale=std, size=size)).tolist(),
        )

    @overload
    @staticmethod
    def lognormal(mean: float, sigma: float, size: None) -> float: ...

    @overload
    @staticmethod
    def lognormal(
        mean: float = 0.0, sigma: float = 1.0, *, size: None
    ) -> float: ...

    @overload
    @staticmethod
    def lognormal(
        mean: float = 0.0,
        sigma: float = 1.0,
        size: int | Sequence[int] = 1,
    ) -> Floats: ...

    @staticmethod
    def lognormal(
        mean: float = 0.0,
        sigma: float = 1.0,
        size: int | Sequence[int] | None = 1,
    ) -> float | Floats:
        """
        Draw samples from a log-normal distribution.

        Parameters
        ----------
        mean : float, optional
            Mean of the underlying normal distribution. Default is ``0.0``.
        sigma : float, optional
            Standard deviation of the underlying normal distribution.
            Default is ``1.0``.
        size : int or Sequence[int] or None, optional
            Output shape. Default is ``1``.

        Returns
        -------
        float or Floats
            One float when ``size`` is ``None``, otherwise a list of
            log-normally distributed floats.
        """
        return cast(
            "float | Floats",
            np.asarray(
                rng.lognormal(mean=mean, sigma=sigma, size=size)
            ).tolist(),
        )

    @overload
    @staticmethod
    def choice(
        value_set: Floats,
        size: None,
        probabilities: Sequence[float] | None = None,
        *,
        replace: bool = True,
    ) -> float: ...

    @overload
    @staticmethod
    def choice(
        value_set: Floats,
        size: int | Sequence[int] = 1,
        probabilities: Sequence[float] | None = None,
        *,
        replace: bool = True,
    ) -> Floats: ...

    @staticmethod
    def choice(
        value_set: Floats,
        size: int | Sequence[int] | None = 1,
        probabilities: Sequence[float] | None = None,
        *,
        replace: bool = True,
    ) -> float | Floats:
        """
        Draw a random sample from a given float sequence.

        Parameters
        ----------
        value_set : Floats
            The pool of float values to sample from.
        size : int or Sequence[int] or None, optional
            Output shape. Default is ``1``.
        probabilities : Sequence[float] or None, optional
            Probabilities associated with each element of ``value_set``.
            Must sum to 1. When ``None``, a uniform distribution is used.
        replace : bool, optional
            Whether to sample with replacement. Default is ``True``.

        Returns
        -------
        float or Floats
            One float when ``size`` is ``None``, otherwise a list of
            sampled floats.
        """
        return cast(
            "float | Floats",
            np
            .array(
                rng.choice(
                    a=np.array(value_set),
                    size=size,
                    replace=replace,
                    p=probabilities,
                ),
            )
            .astype(float)
            .tolist(),
        )

    @staticmethod
    def linspace(
        start: float,
        stop: float,
        num: int,
    ) -> Floats:
        """
        Return evenly spaced floats over a specified interval.

        Parameters
        ----------
        start : float
            The starting value of the sequence (inclusive).
        stop : float
            The end value of the sequence (inclusive).
        num : int
            Number of evenly spaced samples to generate.

        Returns
        -------
        Floats
            A list of ``num`` evenly spaced floats from ``start`` to ``stop``.
        """
        return cast("Floats", np.linspace(start, stop, num).tolist())
