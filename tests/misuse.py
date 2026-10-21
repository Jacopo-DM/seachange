"""Break the typed rules on purpose, for tests of the run-time checks.

A test that checks that wrong input is refused has to pass that input
past the type checkers. These helpers do it in one visible place instead
of an ignore comment on every such line.
"""

from typing import Protocol, cast


class AnyCall(Protocol):
    """A callable that accepts any arguments."""

    def __call__(  # pragma: no cover  # typing stub only
        self, *args: object, **kwargs: object
    ) -> object: ...


def untyped(func: object) -> AnyCall:
    """Return ``func`` unchanged, typed so a test may call it wrongly.

    Parameters
    ----------
    func : object
        The function or class to call with arguments its types forbid.

    Returns
    -------
    AnyCall
        The same object.
    """
    return cast("AnyCall", func)


def assign(target: object, name: str, *, value: object) -> None:
    """Set ``target.<name> = value``, past a type checker that forbids it.

    Parameters
    ----------
    target : object
        The object whose attribute is set.
    name : str
        The attribute name.
    value : object
        The value to assign.
    """
    setattr(target, name, value)
