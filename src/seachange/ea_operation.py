"""Operation protocol and the EAOperation step wrapper."""

import inspect
from typing import ParamSpec, Protocol, cast, get_origin, overload

from seachange.codecs import Genotype
from seachange.population import Population

P = ParamSpec("P")


# -- Step wrapper --------------------------------------------------------------


class Operation[G = Genotype](Protocol):
    """What the EA needs from an element of its pipeline.

    Every ``EAOperation``, whatever its bound arguments, fits this shape.
    ``G`` is the genotype type of the populations it takes and returns.
    The EA calls ``run``, a plain method: matching ``EAOperation``'s
    overloaded ``__call__`` against a generic protocol makes mypy read the
    population as a bound argument when operations are listed inline in
    ``EA(...)``.
    """

    name: str

    def run(  # pragma: no cover  # typing stub only
        self, population: Population[G], /
    ) -> Population[G]:
        """Run on a population and return the next one."""
        ...


class _PipelineFunction[G, **Q](Protocol):
    """A named function that takes a Population first and returns one."""

    @property
    def __name__(self) -> str: ...  # pragma: no cover  # ruff: ignore[bad-dunder-method-name]  # mirrors the __name__ of functions and methods

    def __call__(  # pragma: no cover  # typing stub only
        self, population: Population[G], /, *args: Q.args, **kwargs: Q.kwargs
    ) -> Population[G]: ...


class _Factory[G, **Q](Protocol):
    """EAOperation's constructor, with the bound arguments left unchecked."""

    def __call__(  # pragma: no cover  # typing stub only
        self, func: _PipelineFunction[G, Q], /, *args: object, **kwargs: object
    ) -> "EAOperation[Q, G]": ...


def _is_population(annotation: object) -> bool:
    # Population, or Population[X] (whose origin is Population)
    return annotation is Population or get_origin(annotation) is Population


class EAOperation[**P, G = Genotype]:
    """EAOperation class.

    Decorating a function with ``@EAOperation`` validates its signature and
    turns it into a factory. Calling the decorated name with configuration
    arguments returns a new bound ``EAOperation`` instance ready to be placed
    in the ``ops`` list. The EA engine then calls each instance with a
    ``Population`` to execute it.

    Parameters
    ----------
    func : _PipelineFunction[G, P]
        The pipeline function to wrap. Its first argument must be annotated
        as ``Population`` and its return type must be ``Population``;
        ``Population[NDArray[np.float32]]`` counts, and sets ``G``.
    *args : P.args
        Positional configuration arguments bound at construction time.
    **kwargs : P.kwargs
        Keyword configuration arguments bound at construction time.

    Raises
    ------
    TypeError
        If the decorated function has no parameters.
    TypeError
        If the first parameter of the decorated function is not annotated
        as ``Population``.
    TypeError
        If the return annotation of the decorated function is not
        ``Population``.

    Examples
    --------
    >>> @EAOperation
    ... def mutate(
    ...     population: Population, probability: float = 0.2, span: int = 1
    ... ) -> Population:
    ...     ...
    ...     return population

    >>> ops: list[EAOperation] = [
    ...     mutate(probability=0.5, span=2),
    ...     parent_selection(tournament_size=5),
    ... ]
    """

    def __init__(
        self,
        func: _PipelineFunction[G, P],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> None:
        """Wrap `func` with its bound positional and keyword arguments.

        Raises
        ------
        TypeError
            If an operation does not take and return a Population.
        """
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        if not args and not kwargs:
            if not params:
                msg = (
                    f"@EAOperation function '{func.__name__}' must have "
                    f"a Population as its first argument."
                )
                raise TypeError(
                    msg,
                )
            if not _is_population(params[0].annotation):
                annotation_name = getattr(
                    params[0].annotation,
                    "__name__",
                    params[0].annotation,
                )
                msg = (
                    f"@EAOperation function '{func.__name__}' first argument "
                    f"must be annotated as Population, got "
                    f"'{annotation_name}'."
                )
                raise TypeError(
                    msg,
                )
            if not _is_population(sig.return_annotation):
                return_name = getattr(
                    sig.return_annotation,
                    "__name__",
                    sig.return_annotation,
                )
                msg = (
                    f"@EAOperation function '{func.__name__}' must return "
                    f"Population, got "
                    f"'{return_name}'."
                )
                raise TypeError(
                    msg,
                )

        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.name = func.__name__

    @overload
    def __call__(  # type: ignore[overload-overlap]  # pragma: no cover  # a Population first runs the operation, as __call__ checks first
        self, population: Population[G], /
    ) -> Population[G]: ...

    @overload
    def __call__(  # pragma: no cover  # typing stub only
        self, *args: P.args, **kwargs: P.kwargs
    ) -> "EAOperation[P, G]": ...

    def __call__(
        self, *args: object, **kwargs: object
    ) -> "Population[G] | EAOperation[P, G]":
        """
        Either bind configuration arguments or execute against a population.

        When the first positional argument is a ``Population`` the operator
        executes immediately and returns the result. Otherwise a new bound
        ``EAOperation`` instance is returned with the supplied arguments
        forwarded on every subsequent execution.

        Parameters
        ----------
        *args
            If the first element is a ``Population``, it is passed as the
            population argument to the wrapped function. Otherwise treated
            as configuration arguments to bind.
        **kwargs
            Configuration keyword arguments to bind.

        Returns
        -------
        Population
            When called with a ``Population`` as the first argument.
        EAOperation
            When called with configuration arguments, returning a new
            bound instance.
        """
        if args and isinstance(args[0], Population):
            return self.run(args[0])

        # The arguments to bind are whatever P accepts, which only the call
        # site of the factory can check, so it is called untyped here
        factory = cast("_Factory[G, P]", EAOperation)
        return factory(self.func, *args, **kwargs)

    def run(self, population: Population[G], /) -> Population[G]:
        """Run the wrapped function on ``population`` with the bound arguments.

        ``operation(population)`` does the same.

        Parameters
        ----------
        population : Population[G]
            The population to pass as the first argument.

        Returns
        -------
        Population[G]
            What the wrapped function returned.

        Raises
        ------
        TypeError
            If the wrapped function does not return a ``Population``.
        """
        # Checked at run time: a wrapped function may break its annotation
        result = cast(
            "object", self.func(population, *self.args, **self.kwargs)
        )
        if not isinstance(result, Population):
            msg = (
                f"'{self.func.__name__}' expected a Population as return "
                f"value, got '{type(result).__name__}'."
            )
            raise TypeError(
                msg,
            )
        # The wrapped function is typed to return Population[G]
        return cast("Population[G]", result)

    def __repr__(self) -> str:
        """Return the function name with its bound keyword arguments.

        Returns
        -------
        str
            The function name and its bound keyword arguments.
        """
        # P.kwargs is a dict at run time; mypy cannot read a stored one
        bound = cast("dict[str, object]", self.kwargs)
        kwargs = ", ".join(f"{k}={v!r}" for k, v in bound.items())
        return f"{self.func.__name__}({kwargs})"


# -- EA ------------------------------------------------------------------------
