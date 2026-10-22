# seachange

The evolution engine. `EA` runs a list of operations once per generation over a `Population` of `Individual`s and saves every individual in a SQLite database; `Archive` and `EA.restart` read that database back. `codecs.py` decides how a genotype is stored.

Assumes: one process owns a run's database file while `EA` writes it; genotypes are set once (a child gets a new genotype, numpy arrays are made read-only); every random draw comes from `_rng.py`, so `seed()` repeats a run.

Must never depend on: robot code (ARIEL's bodies, simulators), a database other than SQLite, or a subpackage's private modules (`generators/_shared.py`). Other code imports from `seachange` itself; inside the package, a subpackage is imported only through its `__init__.py`.

The public interface of each module is in `CODEMAP.md` at the repo root.
