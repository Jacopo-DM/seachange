# seachange.generators

Random genotypes and mutations of them: `IntegersGenerator` and `FloatsGenerator` draw sequences; `IntegerMutator` and `FloatMutator` make a child from a parent. `_shared.py` holds their settings (`SEACHANGE_` environment variables), the `Integers` and `Floats` types, and the steps several mutators share.

Assumes: genotypes are flat sequences of numbers; every draw uses `seachange._rng.rng`, so `seed()` repeats them; a mutator returns a new sequence and never changes its input.

Must never depend on: any seachange module other than `seachange._rng`. The engine, populations and the database know nothing of these functions, and these functions know nothing of them. Code outside this package imports from `seachange.generators`, never from its modules.

The public interface is in `CODEMAP.md` at the repo root.
