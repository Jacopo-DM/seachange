# Code map

Entry point: `import seachange`. `examples/a1_one_max.py` is a complete run (the README example); `examples/a2_revde.py` prints one RevDE mutation. Generated paths are in the ignore list in CLAUDE.md.

## `src/seachange/`

| Module | Purpose | Public interface |
|---|---|---|
| `__init__.py` | package exports | every name below except `Operation`, `setup_database` and `RevDE`, which are imported from their modules |
| `ea.py` | the generational engine: runs the operations once per generation and commits to SQLite; restarts from a database | `EA` |
| `ea_operation.py` | wraps a `Population -> Population` function as a pipeline step | `Operation`, `EAOperation` |
| `ea_settings.py` | defaults for the engine, overridable from the environment | `EASettings`, `DBHandlingMode`, `Direction`, `config` |
| `ea_database.py` | creates the database file | `setup_database` |
| `individual.py` | one row of the database: genotype, fitness, tags, birth and death | `Individual`, `JSONType`, `JSONPrimitive`, `JSONIterable`; `check_rows` (used by `ea` and `archive`, not exported) |
| `population.py` | a list of individuals with selection helpers | `Population` |
| `archive.py` | read-only queries over a finished run's database | `Archive`, `FitnessStats`, `GenerationRange` |
| `codecs.py` | turn a genotype into bytes and back; pick a codec for a genotype or by its stored name | `GenotypeCodec`, `JsonCodec`, `NumpyCodec`, `register_codec`; `codec_for`, `codec_named`, `Array` (not exported) |
| `model.py` | the frozen base class for records | `Model` (internal) |
| `crossover.py` | default crossover functions | `Crossover` |
| `generators/` | random float and integer sequences and their mutations | `FloatsGenerator`, `IntegersGenerator`, `FloatMutator`, `IntegerMutator`, `Floats`, `Integers`, `SEED`, `seed` |
| `generators/_shared.py` | the two shared generators (numpy `rng`, Python `py_rng`), `seed`, settings and types | internal |
| `optimizers/revde.py` | Reversible Differential Evolution | `RevDE` |

## Import direction

`ea` → `ea_database`, `ea_operation`, `ea_settings`, `individual`, `population`. `ea_database` → `ea_settings`. `ea_operation` → `population`. `codecs` → `individual` (the JSON types). `archive` → `ea_settings`, `generators._shared`, `individual`, `model`, `population`. `population` → `ea_settings` (types only), `generators._shared`. `crossover` → `generators._shared`. `generators/*` → `generators._shared`. `optimizers` imports nothing from the package.

## `tests/`

`test_<module>.py` for `archive`, `codecs`, `crossover`, `ea`, `ea_operation`, `individual`, `population` and `revde`; `test_ea_restart.py` covers restarting from a database, `test_examples.py` runs each example in a fresh interpreter, `test_database_check.py` checks that edited database rows are refused on load, `test_round_trip.py` checks with Hypothesis that genotypes and tags come back from the database unchanged, `test_seed.py` checks that a run and every draw repeat after `seed()`, `test_closing.py` checks that `close()` and `with` release connections (without the `dispose_engines` fixture), and `test_generators.py` the whole `generators/` package. `ea_settings` and `ea_database` have no test file of their own; the engine tests cover them. `conftest.py` sets the Hypothesis profile (derandomized when `CI` is set) and holds the `dispose_engines` fixture that `test_archive.py`, `test_database_check.py`, `test_ea.py`, `test_ea_restart.py` and `test_seed.py` opt into; `ea_helpers.py` holds shared fixtures and operations, `misuse.py` lets tests pass badly typed input on purpose.

## `docs/`, `tools/`, `.github/`

`docs/` is the Sphinx site (`conf.py`, `index.md`, `reference.md`). `tools/compress_images.py` and `tools/run_notebooks.py` are the shared templates the pre-commit hooks run. `tools/bench_genotypes.py` is goal 8's benchmark: seconds of database work per generation and database size for 100 genotypes of 10,000 weights. `.github/workflows/ci.yml` runs format, lint, mypy and pytest; `docs.yml` builds the docs.
