# Design

## Specs

Approved by the user on 2026-10-21. Goal numbers refer to PLAN.md. Goal 6 (api-cleanup) gets its spec once goals 1 to 5 are done.

### Goal 1: restart-guard

- `EA.restart` (in `EA.__init__` until T23) resolves the restart source and the target database (`db_file_path`, or `config.db_file_path` when it is `None`). If both name the same file, it raises `ValueError` naming the path and suggesting `db_file_path=`, before any database is opened.
- The check runs in both `db_handling` modes. In `"halt"` mode, this one case now raises `ValueError` where ARIEL raises `FileExistsError`.
- Acceptance: `ValueError` in both modes; the source file's bytes are unchanged afterwards; a relative and an absolute path to the same file are caught.
- Must not regress: restarts with a separate `db_file_path` (`tests/test_ea_restart.py`).

### Goal 2: floats-size-none

- `FloatsGenerator.uniform`, `normal` and `lognormal` return a plain `float` when `size=None`, as numpy does.
- Typing overloads on those three, `IntegersGenerator.integers` and both `choice` methods: `size=None` gives `float` or `int`, an `int` size gives a sequence. A `Sequence[int]` size (a numpy shape) keeps its current annotation.
- Acceptance: Hypothesis tests of the return type and length; the three `known bug` ignores removed; `ty check` reports 0 diagnostics.
- Must not regress: `tests/test_generators.py`.

### Goal 3: docs-build

- `docs/conf.py` loads `sphinx.ext.todo`, so the `Todo` section of a numpy docstring renders.
- Acceptance: `sphinx-build -W --keep-going -b html docs docs/_build/html` exits 0.

### Goal 4: examples-tested

- `tests/test_examples.py` runs each example in a fresh interpreter (`subprocess`, `sys.executable`) with a temporary folder as the working directory. Not `runpy`: inside the suite the shared generator's state depends on earlier tests, so an in-process run could vary. (When T4 was written, `config.output_folder` was also fixed at import and an in-process run would have written to the repo's `__data__/`; T14 removed that.)
- `examples/a0_hello_world.py`, the empty `uv-cr-lib` template, is deleted (user, 2026-10-21).
- Acceptance: `a1_one_max.py` prints `best fitness 20.0 of 20` (deterministic: the generators use the fixed `SEED`). Coverage stays at 100%.

### Goal 5: close-connections

- `EA.restart` (in `EA.__init__` until T23) disposes the engine it opens on the restart source. The `dispose_engines` fixture in `tests/conftest.py` records every engine the package creates during a test and disposes them afterwards; test modules that build an `EA` or `Archive` opt in with `pytestmark`.
- Acceptance: `pytest.ini` turns `ResourceWarning` and `pytest.PytestUnraisableExceptionWarning` into errors, and every test passes. (Corrected from `-W error::ResourceWarning` alone, which could not fail; see Gotchas.)
- A public way for users to close a run (`close()` or a context manager) is a goal 6 candidate, not part of this goal.

### Goal 7: release-0.1

- Licence GPL-3.0-or-later, as ARIEL (copyright 2025 Jacopo Michele di Matteo and Ioannis Grigoriadis); `LICENSE` copied from ARIEL and `license = "GPL-3.0-or-later"` in `pyproject.toml`.
- `CHANGELOG.md` lists every change from `ariel.ec`, including goal 6's renames, as the migration note for ARIEL.
- Acceptance: `uv build` makes a wheel and an sdist; an isolated temporary environment installs the wheel and runs the README example, which reaches fitness 20 (the README version prints the genotype; `examples/a1_one_max.py` prints `best fitness 20.0 of 20`); goal 3 passes; the README and `[project.urls]` carry the repository URL.

## Decisions

- 2026-10-21: copy, not move. seachange starts as a copy of ARIEL's `ariel.ec` engine; ARIEL keeps its own and does not depend on seachange. Chosen by the user: nothing in ARIEL breaks. The cost is that the two copies drift.
- 2026-10-21: scope is the engine (`EA`, `EAOperation`, `Individual`, `Population`, `Archive`, `Crossover`, settings, database) plus `generators/` and `optimizers/`, everything in `ariel.ec` that imports no robot code. ARIEL's genotypes (tree, CPPN, NDE) build robot bodies and stay there.
- 2026-10-21: the name comes from Ariel's song in The Tempest ("doth suffer a sea-change / Into something rich and strange"), close to what mutation does to a genotype, and it contains "ea". Free on PyPI on that date.
- Storage: every individual is a row in SQLite through sqlmodel and sqlalchemy, so a run can restart from any recorded generation. Settings come from pydantic-settings. Reason as in ARIEL, not recorded there.
- 2026-10-21: seachange is for researchers installing it from PyPI, and later for ARIEL, which will remove its own `ariel.ec` and import seachange. Chosen by the user. The public interface may change before 0.1; each change needs the user's approval and a line in the CHANGELOG mapping the `ariel.ec` name to the new one.
- 2026-10-21: until 0.1, seachange does not take ARIEL's robot genotypes or support databases other than SQLite. Both are planned for after 0.1 (user).
- 2026-10-21: the licence is GPL-3.0-or-later, as ARIEL, because the code is copied from ARIEL and relicensing needs every copyright holder's consent (user).
- 2026-10-21: restarting onto the source file raises `ValueError` in every `db_handling` mode (user). One rule with one message beats keeping halt's generic `FileExistsError` for this case.
- 2026-10-21: `size=None` returns a plain number, matching numpy, with typing overloads so a default `size=1` caller still gets a sequence type (user). The integer generators get the same overloads.
- 2026-10-21: the fitness direction has one name everywhere, `direction: Literal["max", "min"]` (user, goal 6 C10). A boolean `maximise=` was rejected: `sort(maximise=False)` reads as "do not maximise" rather than "ascending".
- 2026-10-21: a restart is `EA.restart(source, operations, *, generation=None, ...)`, and `EA(population, operations)` requires both (user, goal 6 C12). It makes a new run and a continued run two separate calls, which drops the `None` placeholder and the "either population or restart" error. The user accepted the migration cost because C10 and C2 already change ARIEL's calls.
- 2026-10-21: after `seed(n)`, a whole run repeats exactly: every random choice seachange makes follows it (user). Leaving `seed()` to the numpy generator only was rejected: a run whose selection uses `population.sample` would still differ from run to run.
- 2026-10-21: a restart continues from the individuals still alive at the end of the chosen generation, not everyone who lived through part of it (user). Keeping ARIEL's query was rejected: on one-max it restarted with 30 instead of the 20 the run had.
- 2026-10-21: the public repository is `https://github.com/Jacopo-DM/seachange` (user). The CI and docs workflows already target GitHub Actions; the repo can move to an org later.
- 2026-10-21: `LICENSE` carries two copyright lines: 2025 for the ARIEL code (Jacopo Michele di Matteo and Ioannis Grigoriadis) and 2026 for the seachange changes (Jacopo Michele di Matteo). Chosen by the user.
- 2026-10-21: the docs build fixes the `Todo` directive by loading `sphinx.ext.todo`, not by deleting the empty template sections (user).

## Rejected approaches

- Making ARIEL depend on seachange at the time of the copy (one copy of the engine). Rejected by the user then, in favour of leaving ARIEL untouched; on 2026-10-21 the user planned it for after 0.1 (see Decisions).
- Restart onto its own source file: writing the new run under a derived name such as `database_restart.db`. Rejected: the user may not notice where the data went. Checking inside `setup_database` was also rejected, because it does not know about restarts.
- `size=None`: returning a one-item list (rejected by the user; it breaks numpy's convention), or annotating the return as a plain union (every caller would have to narrow, even with the default `size=1`).
- Docs build: deleting the empty `Notes` and `Todo` sections from `revde.py`'s docstring. The user chose to enable `sphinx.ext.todo` instead.
- `operations` required (C12): keeping the `None` default (the mistake already fails at once) or dropping both defaults (restarts would still read `EA(None, ops, restart=...)`). Both rejected in favour of `EA.restart()`.
- Licence: relicensing under MIT or similar. It needs written consent from every copyright holder of ARIEL's code.

## Results

| Date | Task | Goal | Change | Measured effect |
|---|---|---|---|---|
| 2026-10-21 | T1 | 3 | `docs/conf.py` loads `sphinx.ext.todo` | docs build with `-W`: 1 error before, 0 after (exit 0) |
| 2026-10-21 | T2 | 5 | `EA.__init__` disposes the restart source engine, also on its error paths | `test_ea_restart.py` alone, `-W default`: 11 warnings before, 10 after; full suite 79 before, 77 after |
| 2026-10-21 | T3 | 5 | `dispose_engines` fixture in `tests/conftest.py`, opted into by three test modules; one test disposes its own engine; `pytest.ini` fails on leaks | full suite: 77 warnings before, 0 after (3 runs); with the leak put back the suite fails |
| 2026-10-21 | T4 | 4 | `tests/test_examples.py` runs the one-max example; `a0_hello_world.py` deleted | 187 tests before, 188 after, suite ~0.8 s to ~1.3 s; the test fails when the example runs 1 generation |
| 2026-10-21 | T5 | 1 | `EA.__init__` compares the resolved restart source and target database and raises `ValueError` if they match | 3 new tests failed before (delete mode overwrote the source; halt raised `FileExistsError`) and pass after; 191 tests pass |
| 2026-10-21 | T6 | 2 | `@overload`s on `integers`, both `choice` methods, `uniform`, `normal` and `lognormal`; the float methods wrap numpy's result in `np.asarray` before `.tolist()` | before: 2 new tests failed at runtime and mypy found 10 errors in the new tests; after: 196 tests pass, mypy clean, `ty check` 3 diagnostics to 0; pyright not installed, so not run |
| 2026-10-21 | T12 | 6 | `EASettings` and the generator settings read only `SEACHANGE_`-prefixed environment variables. For ARIEL: rename `NUM_STEPS` to `SEACHANGE_NUM_STEPS` and likewise for every settings variable | 3 new tests failed before (a bare `NUM_STEPS` changed `num_steps`) and pass after; 199 tests pass |
| 2026-10-21 | T13 | 6 | `target_population_size` removed from `EASettings` and `EA`; nothing in seachange read it. For ARIEL: operators that read `config.target_population_size` must keep their own constant | new test failed before (the field existed) and passes after; 200 tests pass |
| 2026-10-21 | T14 | 6 | `EASettings.output_folder` defaults to the relative `Path("__data__")`, and `db_file_path` joins it onto `Path.cwd()` when read, so a run lands under the working directory at `EA(...)` time. For ARIEL: scripts that change directory after importing now write under the new folder; `config.output_folder` reads `__data__` (relative) instead of an absolute path | 2 new tests: the path test failed before (it pointed at the repo's `__data__/`) and both pass after; 202 tests pass. Moving the path into `EA`, as the task first planned, was not needed |
| 2026-10-21 | T15 | 6 | `EA.get_solution` raises `ValueError` for a mode other than `"best"`, `"median"` or `"worst"`; it returned `None` before. The `match` became plain `if`s, since a guard now runs first. For ARIEL: code that checked for `None` must catch `ValueError` | the rewritten test failed before and passes after; 202 tests pass, coverage 100% |
| 2026-10-21 | T16 | 6 | `EA` and `Archive` gain `close()` and work as context managers (`with EA(...) as ea:`). New for ARIEL, nothing to migrate | `tests/test_closing.py` (4 tests, outside the `dispose_engines` fixture) failed before (no such methods) and pass after; with `close()` emptied, all 4 fail on the leaked connection; 206 tests pass |
| 2026-10-21 | T17 | 6 | `Archive.fitness_percentile_population` loses its ignored `fitness_mode` parameter (and its suppression). For ARIEL: delete `fitness_mode=` from these calls; results do not change | new test failed before (the argument was accepted) and passes after; 207 tests pass |
| 2026-10-21 | T18 | 6 | One name for the fitness direction: `direction: Direction` (`Literal["max", "min"]`, exported). For ARIEL: `EA(is_maximisation=True/False)` becomes `direction="max"/"min"`; `config.is_maximisation` becomes `config.direction` (env `SEACHANGE_DIRECTION`); `population.sort(sort=...)` and `best(sort=...)` become `direction=`; `Archive` methods' `fitness_mode=` becomes `direction=`; `seachange.archive.FitnessMode` becomes `seachange.Direction` | rename only; mypy found no missed caller; 207 tests pass unchanged apart from the renamed keywords |
| 2026-10-21 | T19 | 6 | `Archive.best_individual`, `hall_of_fame` and `tournament_population` require a keyword-only `direction=`; the `"min"` default is gone. For ARIEL: add `direction="min"` where a call relied on the default, and write `best_individual(direction="max")` instead of `best_individual("max")` | 4 new tests failed before and pass after; 11 existing tests that relied on the default now pass `direction="min"` and check the same results; 211 tests pass |
| 2026-10-21 | T20 | 6 | `seachange.seed(n)` resets the shared numpy generator in place. New for ARIEL, nothing to migrate; runs that never call it draw the same numbers as before. It does not seed Python's `random` or SQLite's `random()` (open question in PLAN.md) | 2 new tests failed before (no `seed`) and pass after; 213 tests pass |
| 2026-10-21 | T21 | 6 | `optimizers/revde.py` keeps only `RevDE`: no `__data__/` folder, no rich traceback handler, no module generator, no `main()`. The demo is now `examples/a2_revde.py`. For ARIEL: `revde.main()`, `revde.RNG`, `revde.console` and `revde.DATA` are gone; `RevDE` results are unchanged | 2 new tests (import changes nothing; the demo prints three parents and three children) failed before and pass after; the 2 tests of `main()` were removed; 213 tests pass |
| 2026-10-21 | T22 | 6 | `ind.tags = {...}` replaces the tags (a copy of the dict) instead of merging. For ARIEL: every `ind.tags = {...}` that meant "add these keys" must become `ind.tags = {**ind.tags, ...}`, or the old tags are lost without an error | the rewritten test failed before (merge) and passes after; a new test pins the explicit merge; 214 tests pass |
| 2026-10-21 | T23 | 6 | `EA(population, operations, *, ...)` requires both; restarts go through `EA.restart(source, operations, *, generation=None, ...)`. For ARIEL: `EA(None, ops, restart=path, ...)` becomes `EA.restart(path, ops, ...)`, and `restart=(path, g)` becomes `EA.restart(path, ops, generation=g, ...)`; the "operations is required" and "either population or restart" `ValueError`s are gone (a missing argument is a `TypeError`) | 10 restart tests rewritten to the new call with the same assertions; 2 constructor tests became 1; all failed before and pass after; 213 tests pass; the README snippet run by hand restarts a one-max run and the same-file guard fires |
| 2026-10-21 | T21 follow-up | 6 | `ea.py` no longer calls rich's `install()` on import, so `import seachange` leaves `sys.excepthook` alone (user, 2026-10-21). For ARIEL: scripts that want rich tracebacks call `rich.traceback.install()` themselves | new test (fresh interpreter, compares `sys.excepthook` before and after `import seachange`) failed before and passes after; 214 tests pass |
| 2026-10-21 | T8 | 7 | `LICENSE` is ARIEL's GPL-3.0 text, unchanged, under a header naming seachange, the 2025 copyright holders and ARIEL as the source; `pyproject.toml` has `license = "GPL-3.0-or-later"` and `license-files` | `uv build --offline`: the wheel's METADATA has `License-Expression: GPL-3.0-or-later` and `License-File: LICENSE`, and both wheel and sdist contain the file; `uv lock --check` unchanged |
| 2026-10-21 | T11 | 7 | README install step and `[project.urls]` (`Repository`, `Issues`) point at `https://github.com/Jacopo-DM/seachange` | `uv build --offline` metadata lists both URLs; the repository itself does not exist yet |
| 2026-10-21 | T24 | 7 | `EA.restart` takes only the survivors of the chosen generation: recorded in it and either still present after it or never retired. Before, individuals retired during that generation came along. For ARIEL: a restart's starting population shrinks to the run's real size (one-max: 20, was 30) | 2 new test cases failed before (4 and 6 instead of 2 and 4) and pass after; the 10 existing restart tests pass unchanged; one-max restart checked by hand: 20; 216 tests pass |
| 2026-10-21 | T25 | 7 | `seed(n)` also reseeds a private `random.Random` (`py_rng`) that `Population.sample`, `shuffle` and every `Archive` draw now use; `Archive.random_individual` and `random_population` pick from ids read in id order instead of SQLite's `random()`. Python's global `random` is untouched. For ARIEL: these draws give different values than before, and code that seeded the global `random` to repeat them should call `seed()` | `tests/test_seed.py`: 4 tests failed before (a two-run comparison, Population and Archive draws, global random untouched) and pass after, 3 runs in a row; 220 tests pass |
| 2026-10-21 | T9 | 7 | `CHANGELOG.md`: one 0.1.0 entry listing every difference from `ariel.ec` (Added, Changed, Removed, Fixed), each behaviour change with the old call beside the new one | every Results row with a user-visible change has a line; the new calls it shows were run once in an empty folder and all worked |
| 2026-10-21 | T10 | 7 | CLAUDE.md records the Build and Clean install commands; `dist/` joins the ignore list | `uv build --offline` <1 s, wheel 46.8 KB, sdist 41.2 KB; a throwaway environment (15 packages, only sqlalchemy downloaded) installs the wheel; the README example, run from a folder outside the repo, reaches fitness 20.0, and `examples/a1_one_max.py` prints `best fitness 20.0 of 20` |

## Gotchas

- The dependency versions are newer than ARIEL's lock (numpy 2.5.4, sqlalchemy 2.1.6, sqlmodel 0.0.48 against 2.3.3, 2.0.43, 0.0.27). numpy 2.5's stubs are what exposed the `size=None` crash (fixed by T6).
- A SQLite connection that the garbage collector closes raises its `ResourceWarning` inside `__del__`, where pytest catches it as an unraisable exception and reports `PytestUnraisableExceptionWarning`. So `-W error::ResourceWarning` alone never fails a test for a leak; `pytest.ini` turns both into errors. The failure is reported on whichever test is running when the collector runs, often the test after the leaking one.
- ruff bans `autouse=True` fixtures (`pytest-fixture-autouse`). Shared setup is opted into per module with `pytestmark = pytest.mark.usefixtures(...)`.
- Changing an individual's `tags` (or `genotype`) dict in place, as in `ind.tags["k"] = 1`, is not saved: the JSON columns do not track changes inside the value, so only assignment reaches the database. Checked 2026-10-21 with a two-generation run: the in-place tag was gone in the archive, the assigned one was there.
- `uv-cr-lib`'s template `tools/run_notebooks.py` fails mypy unless `nbclient`, `nbformat` and `ipykernel` are installed. They are in the dev group here, so `uv sync --all-groups` covers it.
- `uv run --isolated --offline --with dist/<wheel>` fails to resolve seachange's dependencies even though their wheels are in uv's cache; it needs network to pypi.org for the index listings (checked 2026-10-21). `uv pip` would avoid the resolver, but the user's python-guard hook blocks it.
- `uv_build`'s sdist contains a `pyproject.toml.orig` next to `pyproject.toml`; the repo has no such file.
