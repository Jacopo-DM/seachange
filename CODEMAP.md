# Code map

Entry point: `import seachange`. `examples/a1_one_max.py` is a complete run (the README example); `examples/a2_revde.py` prints one RevDE mutation; `examples/a3_numpy_genotypes.py` evolves float32 array genotypes with typed operations and reads the best back through `Archive[Weights]` (included in `docs/genotypes.md`). Generated paths are in the ignore list in CLAUDE.md.

## `src/seachange/`

| Module | Lines | Purpose | Public interface |
|---|---|---|---|
| `__init__.py` | 60 | package exports | every name below except `Operation`, `setup_database` and `RevDE`, which are imported from their modules |
| `ea.py` | 498 | the generational engine: runs the operations once per generation and commits to SQLite; restarts from a database | `EA[G]` |
| `ea_operation.py` | 259 | wraps a `Population -> Population` function as a pipeline step; `EA` calls each step's `run` | `Operation[G]`, `EAOperation[**P, G]` |
| `ea_settings.py` | 81 | defaults for the engine, overridable from the environment | `EASettings`, `DBHandlingMode`, `Direction`, `config` |
| `ea_database.py` | 59 | creates the database file | `setup_database` |
| `individual.py` | 255 | one row of the database: genotype, fitness, tags, birth and death | `Individual[G]`; `check_rows` (used by `ea` and `archive`, not exported) |
| `population.py` | 403 | a list of individuals with selection helpers | `Population[G]` |
| `archive.py` | 590 | read-only queries over a finished run's database | `Archive[G]`, `FitnessStats`, `GenerationRange` |
| `codecs.py` | 460 | genotype types; turn a genotype into bytes and back; pick a codec for a genotype or by its stored name; the database column type that stores genotypes | `Genotype`, `JSONType`, `JSONPrimitive`, `JSONIterable`, `GenotypeCodec`, `JsonCodec`, `NumpyCodec`, `register_codec`; `codec_for`, `codec_named`, `Array`, `GenotypeColumn`, `UndecodableGenotype`, `decode_error` (not exported) |
| `_rng.py` | 35 | the two random generators every draw uses (numpy `rng`, Python `py_rng`) and `seed`, which restarts both | internal; `seed` and `SEED` are exported through `generators` and `seachange` |
| `model.py` | 9 | the frozen base class for records | `Model` (internal) |
| `crossover.py` | 395 | default crossover functions; arrays in give arrays out | `Crossover` |
| `generators/` | 899 | random float and integer sequences and their mutations | `FloatsGenerator`, `IntegersGenerator`, `FloatMutator`, `IntegerMutator`, `Floats`, `Integers`, `SEED`, `seed` |
| `generators/_shared.py` | 106 | settings and types of the generators, and the steps several mutators share (`swap_genes`, `cut_points`) | internal |
| `optimizers/revde.py` | 66 | Reversible Differential Evolution | `RevDE` |

Lines as of 2026-10-22 (`wc -l`); `generators/` counts `__init__.py`, `sampling.py` and both mutators. `src/seachange/`, `generators/` and `optimizers/` each have a `README.md`: what the package does, what it assumes, and what it must never import (they ship in the wheel).

`G` is the genotype type, for type checkers only; it defaults to `Genotype`, and `Individual[X]` is `Individual` at run time.

## Boundaries

seachange is pure Python with one boundary: the SQLite database, through SQLModel and SQLAlchemy. The contract is the `individual` table that `Individual` defines (`id`, `alive`, `time_of_birth`, `time_of_death`, `requires_eval`, `fitness_`, `requires_init`, `genotype_`, `tags_`). `genotype_` holds bytes: a codec's name, a zero byte, and that codec's output (for `numpy`, a complete `.npy` file); text in that column is read as JSON from databases written before codecs (and by ARIEL's `ariel.ec`). `tags_` is a JSON column. `EA` writes the file, `Archive` and `EA.restart` only read it, and `check_rows` refuses rows that do not validate. No FFI, IPC or generated bindings.

## Import direction

`ea` → `codecs`, `ea_database`, `ea_operation`, `ea_settings`, `individual`, `population`. `ea_database` → `ea_settings`. `ea_operation` → `codecs`, `population`. `individual` → `codecs`. `codecs` → `model`. `archive` → `_rng`, `codecs`, `ea_settings`, `individual`, `model`, `population`. `population` → `_rng`, `codecs`, `ea_settings`, `individual` (types only). `crossover` → `_rng`, `codecs` (the JSON types). `generators/*` → `_rng`, `generators._shared`. `optimizers` imports nothing from the package.

## `tests/`

`test_<module>.py` for `archive`, `codecs`, `crossover`, `ea`, `ea_operation`, `individual`, `population` and `revde`; `test_ea_restart.py` covers restarting from a database, `test_examples.py` runs each example in a fresh interpreter, `test_database_check.py` checks that edited database rows are refused on load, `test_genotype_types.py` that the genotype type parameter reaches every class (its `assert_type` lines are checked by mypy) and that crossover keeps arrays, `test_reading_files.py` that a database from before codecs (as ARIEL writes it) opens and restarts, and that a file stored with a user codec needs that codec registered to read, `test_round_trip.py` checks with Hypothesis that genotypes and tags come back from the database unchanged, `test_seed.py` checks that a run and every draw repeat after `seed()`, `test_closing.py` checks that `close()` and `with` release connections (without the `dispose_engines` fixture), and `test_generators.py` the whole `generators/` package. `ea_settings` and `ea_database` have no test file of their own; the engine tests cover them. `conftest.py` sets the Hypothesis profile (derandomized when `CI` is set) and holds the `dispose_engines` fixture that `test_archive.py`, `test_database_check.py`, `test_ea.py`, `test_ea_restart.py`, `test_genotype_types.py`, `test_reading_files.py` and `test_seed.py` opt into; `ea_helpers.py` holds shared fixtures and operations, `misuse.py` lets tests pass badly typed input on purpose. `test_functional_notebooks.py` checks that every public module of `seachange` has a row in `tests/functional/README.md` and that every notebook a row names exists.

## `tests/functional/`

Functional notebooks, one per feature area, committed with their outputs and run by `tools/run_notebooks.py` (not by pytest). `README.md` says how to run them and holds the coverage table (one row per public module). `engine.ipynb`: individual, population, operations and a one-max run with a fitness plot, and the settings (covers `ea`, `ea_operation`, `ea_settings`, `ea_database`, `population`, `individual`, `model`). `archive.ipynb`: `Archive` queries over a recorded run and `EA.restart` from generation 10. `genotypes.ipynb`: round trips of JSON and numpy genotypes, the raw column bytes, stored size of JSON against numpy, read-only arrays, a frozenset codec (`codecs`). `generators.ipynb`: `seed`, the samplers' histograms, every float and integer mutator. `crossover.ipynb`: `one_point`, `n_point`, `uniform` and `order_crossover`. `revde.ipynb`: RevDE's matrix, its inverse, and RevDE inside an `EA` on 2-D points (`optimizers`). Each notebook builds its own data and writes only to `__data__/` in the runner's temp folder.

## `docs/`, `tools/`, `.github/`, `.vscode/`

`docs/` is the Sphinx site (`conf.py`, `index.md`, `genotypes.md` on how genotypes are stored and typed, `reference.md`). `tools/compress_images.py` and `tools/run_notebooks.py` are the shared templates the pre-commit hooks run; `run_notebooks.py` runs the functional notebooks (staged ones at commit, all at push), and its own test lives in the template repo (`~/Functions/_rsync/python-tests/`), not here. `tools/measure_structure.py` prints goal 10's structure numbers (files over 400 lines, wide imports, imports past an entry point, jscpd clones). `tools/bench_genotypes.py` is goal 8's benchmark: seconds of database work per generation and database size for 100 genotypes of 10,000 weights. `.github/workflows/ci.yml` runs format, lint, mypy and pytest; `docs.yml` builds the docs. `.vscode/` holds the editor settings and tasks (format, lint, mypy, ty, pytest, docs preview and build) copied from the template `~/Functions/_rsync/vscode/` by `pull-vscode`; identical to it.
