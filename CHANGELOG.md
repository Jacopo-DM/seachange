# Changelog

## 0.1.0 (unreleased)

The first release. seachange starts as a copy of ARIEL's `ariel.ec` engine, taken on 2026-10-21; this entry lists every difference from that copy, so ARIEL code can move over. ARIEL has since ported three of the fixes below into its own copy (the restart guard, the restart engine disposal and `size=None`).

### Moving from `ariel.ec`

Import from `seachange` instead of `ariel.ec`: `from seachange import EA, Population` where you wrote `from ariel.ec import EA, Population`. `RevDE` is in `seachange.optimizers.revde`. ARIEL's robot genotypes (tree, CPPN, NDE) are not part of seachange.

### Added

- `EA.close()` and `Archive.close()` release the database connection, and both work as context managers: `with EA(...) as ea:` and `with Archive(path) as archive:`.
- `seachange.seed(n)` restarts every random draw seachange makes, so after `seed(5)` a whole run comes out the same every time. Python's global `random` is not touched.
- `EA.restart(source, operations, *, generation=None, ...)` continues a recorded run in a new database (see Changed).
- Genotype codecs: `seachange.GenotypeCodec` (the protocol), `JsonCodec`, `NumpyCodec` and `register_codec`. `NumpyCodec` stores an array as a `.npy` file, dtype and shape included, and gives it back read-only.
- `seachange.Direction`, the type of the new `direction=` keyword: `Literal["max", "min"]`.
- `seachange.FitnessStats` and `seachange.GenerationRange`, the records `Archive` returns (see Changed).
- `examples/a2_revde.py`, the RevDE demo that used to be `revde.main()`.

### Changed

- **Restarts have their own method.** `EA(population, operations, ...)` now requires both arguments, and a restart is a separate call:
    - `EA(None, ops, restart=path, ...)` becomes `EA.restart(path, ops, ...)`.
    - `EA(None, ops, restart=(path, 50), ...)` becomes `EA.restart(path, ops, generation=50, ...)`.
    - A missing `population` or `operations` is now a `TypeError`, not a `ValueError`.
- **A restart starts from the survivors of the chosen generation.** It used to include the individuals retired during that generation as well; on one-max, a restart from generation 50 started with 30 individuals instead of the run's 20.
- **One keyword for the fitness direction**, `direction="max"` or `direction="min"`:
    - `EA(..., is_maximisation=True)` becomes `EA(..., direction="max")`, and `config.is_maximisation` becomes `config.direction`.
    - `population.sort(sort="min")` and `population.best(sort="min")` become `direction="min"`.
    - `Archive` methods' `fitness_mode="min"` becomes `direction="min"`; `seachange.archive.FitnessMode` becomes `seachange.Direction`.
- **`Archive.best_individual`, `hall_of_fame` and `tournament_population` require `direction=`, as a keyword.** They used to default to `"min"`, which returned the worst individual on a maximising run. Write `direction="min"` where a call relied on the default, and `best_individual(direction="max")` where you wrote `best_individual("max")`.
- **Settings are read-only.** `config.direction = "min"` (or any other assignment to `seachange.config`) raises `ValidationError`, and mypy reports it before the code runs. It used to change every `EA` created afterwards. Pass the value to the run instead: `config.is_maximisation = False` followed by `EA(pop, ops)` becomes `EA(pop, ops, direction="min")`. To change a default for a whole program, set its `SEACHANGE_` environment variable before Python starts.
- **Settings read only `SEACHANGE_`-prefixed environment variables.** A stray `NUM_STEPS=7` or `QUIET=true` from another tool no longer changes a run; set `SEACHANGE_NUM_STEPS`, `SEACHANGE_DIRECTION` and so on instead.
- **The default output folder is decided when the run starts.** `config.output_folder` defaults to the relative `__data__`, joined onto the working directory when `EA(...)` is created; a script that changes directory after importing now writes under its new folder.
- **`ind.tags = {...}` replaces the tags instead of merging them.** To keep the old tags, write `ind.tags = {**ind.tags, "key": value}`. A call that relied on the merge loses the old tags without an error.
- **`Population.sample`, `Population.shuffle` and every `Archive` draw use seachange's own generator** instead of Python's global `random` or SQLite's `random()`, so `seed()` covers them. They draw different values than before for the same global seed.
- **`Archive` returns records instead of a dict and a tuple.** `archive.fitness_stats()["mean"]` becomes `archive.fitness_stats().mean` (a frozen `FitnessStats` with `min`, `max`, `mean`, `std`, `median`), and `lo, hi = archive.generation_range` becomes `span.first` and `span.last` (a `GenerationRange`).
- **Rows read from a database file are checked.** `EA.restart` and every `Archive` query validate each row as it loads; a file edited by another tool (say, a text `fitness_`) raises `ValueError` naming the row, where it used to load and fail later.
- **Unknown `get_solution` modes raise.** `ea.get_solution("bset")` raises `ValueError` naming the valid modes; it used to return `None`.

### Removed

- `restart=` on `EA` (use `EA.restart`).
- `target_population_size` from `EASettings` and `EA`; nothing read it. Operators that read `config.target_population_size` must keep their own constant.
- The ignored `fitness_mode` parameter of `Archive.fitness_percentile_population`; results do not change.
- `revde.main()`, `revde.RNG`, `revde.console` and `revde.DATA`. `RevDE` itself is unchanged.
- Import side effects: `import seachange` no longer installs rich's traceback printer for the whole program, and importing `revde` no longer creates `__data__/`. Call `rich.traceback.install()` yourself if you want rich tracebacks.

### Fixed

- Reading an individual right after `EA(...)`, as in `ea.population[0].genotype`, raised `DetachedInstanceError` until `ea.fetch_population()` ran; the saved individuals now keep their values.
- `FloatsGenerator.uniform`, `normal` and `lognormal` with `size=None` crashed with `AttributeError`; they return one `float`, as numpy does. Typing overloads on every generator say that `size=None` gives one number and an `int` size gives a list.
- A restart whose new database was its own source deleted the run it restarted from. `EA.restart` now raises `ValueError` before opening either file.
- A restart left its source database's connection open; it is now closed once the rows are read.
