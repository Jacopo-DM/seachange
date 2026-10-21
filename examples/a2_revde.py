"""RevDE: turn three random parents into three children.

``RevDE`` is a reversible differential-evolution mutation: a fixed 3x3
matrix, built from the scaling factor, mixes three parent vectors into
three children. This draws three random parents and prints both sets.
"""

import numpy as np

from seachange.optimizers.revde import RevDE

SEED = 42
GENOME_LENGTH = 4


def main() -> None:
    """Mutate three random parents and print parents and children."""
    rng = np.random.default_rng(SEED)
    parents = [rng.random(GENOME_LENGTH) for _ in range(3)]
    children = RevDE(scaling_factor=-0.5).mutate(*parents)
    for i, parent in enumerate(parents):
        print(f"parent {i}: {parent}")  # ruff: ignore[print]  # an example shows its result
    for i, child in enumerate(children):
        print(f"child {i}: {child}")  # ruff: ignore[print]  # an example shows its result


if __name__ == "__main__":  # pragma: no cover
    main()
