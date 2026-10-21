"""TODO(jmdm): description of script.

Notes
-----
    *

References
----------
    [1]

Todo
----
    [ ]

"""

# Standard library
from pathlib import Path

# Third-party libraries
import numpy as np
from rich.console import Console
from rich.traceback import install

# Local libraries
# --- Globals --- #
# --- Warnings --- #
# --- Typing --- #

# --- RANDOM GENERATOR SETUP --- #
SEED = 42
RNG = np.random.default_rng(SEED)

# --- TERMINAL OUTPUT SETUP --- #
install(show_locals=False)
console = Console()

print = console.print  # ruff: ignore[builtin-variable-shadowing]

# --- DATA SETUP --- #
SCRIPT = Path(__file__)
CWD = Path.cwd()
DATA = CWD / "__data__"
DATA.mkdir(exist_ok=True)


def main() -> None:
    """Entry point."""
    return


if __name__ == "__main__":  # pragma: no cover
    main()
