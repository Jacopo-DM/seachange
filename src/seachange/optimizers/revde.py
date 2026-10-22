"""Reversible Differential Evolution (RevDE) optimizer.

References
----------
    [1] https://dl.acm.org/doi/abs/10.1145/3377929.3389972
"""

# Third-party libraries
import numpy as np
import numpy.typing as npt

# Type Aliases
ArrayGenotype = npt.NDArray[np.float64]


class RevDE:
    """Reversible differential evolution (RevDE) mutation operator."""

    def __init__(self, scaling_factor: float) -> None:
        # Passed parameters
        """Build the mutation matrix from `scaling_factor`."""
        f = scaling_factor
        f2 = f**2
        f3 = f**3

        # Prep work
        a = 1 - f2
        b = f + f2
        c = -f + f2 + f3
        d = 1 - (2 * f2) - f3

        # Linear transformation matrix
        self.r_matrix = np.array([
            [1, f, -f],
            [-f, a, b],
            [b, c, d],
        ])

    def mutate(
        self,
        parent_a: ArrayGenotype,
        parent_b: ArrayGenotype,
        parent_c: ArrayGenotype,
    ) -> list[ArrayGenotype]:
        # Ensure parents have the same shape
        """Return three mutants of three parents of equal shape.

        Returns
        -------
        list[ArrayGenotype]
            The three mutants.

        Raises
        ------
        ValueError
            If the parents differ in shape.
        """
        if not (parent_a.shape == parent_b.shape == parent_c.shape):
            msg = "Parents must have the same shape"
            raise ValueError(msg)

        # Perform mutation
        x_matrix = np.vstack((parent_a, parent_b, parent_c))
        out = self.r_matrix @ x_matrix
        y1, y2, y3 = out
        return [y1, y2, y3]
