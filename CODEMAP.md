# Code map

Entry point: `import seachange`. `optimizers/revde.py` also runs as a script (`main()` prints a RevDE mutation). Generated paths are in the ignore list in CLAUDE.md.

## `src/seachange/`

| Module | Purpose | Public interface |
|---|---|---|
| `__init__.py` | package exports | every name below except `Operation`, `setup_database`, `FitnessMode` and `RevDE`, which are imported from their modules |
| `ea.py` | the generational engine: runs the operations once per generation and commits to SQLite; restarts from a database | `EA` |
| `ea_operation.py` | wraps a `Population -> Population` function as a pipeline step | `Operation`, `EAOperation` |
| `ea_settings.py` | defaults for the engine, overridable from the environment | `EASettings`, `DBHandlingMode`, `config` |
| `ea_database.py` | creates the database file | `setup_database` |
| `individual.py` | one row of the database: genotype, fitness, tags, birth and death | `Individual`, `JSONType`, `JSONPrimitive`, `JSONIterable` |
| `population.py` | a list of individuals with selection helpers | `Population` |
| `archive.py` | read-only queries over a finished run's database | `Archive`, `FitnessMode` |
| `crossover.py` | default crossover functions | `Crossover` |
| `generators/` | random float and integer sequences and their mutations | `FloatsGenerator`, `IntegersGenerator`, `FloatMutator`, `IntegerMutator`, `Floats`, `Integers`, `SEED` |
| `generators/_shared.py` | the shared RNG, settings and types | internal |
| `optimizers/revde.py` | Reversible Differential Evolution | `RevDE` |

## Import direction

`ea` → `ea_database`, `ea_operation`, `ea_settings`, `individual`, `population`. `ea_database` → `ea_settings`. `ea_operation` → `population`. `archive` → `individual`, `population`. `crossover` → `generators._shared`. `generators/*` → `generators._shared`. `optimizers` imports nothing from the package.

## `tests/`

One `test_<module>.py` per module above; `ea_helpers.py` holds shared fixtures and operations, `misuse.py` lets tests pass badly typed input on purpose.
