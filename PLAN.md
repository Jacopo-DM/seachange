# Plan

## Goals

Users: researchers who install seachange from PyPI, and later ARIEL itself, once ARIEL drops its own `ariel.ec` engine and imports seachange instead. The public interface may change before 0.1, but each change needs the user's approval.

Order (approved 2026-10-21): 1 to 5 first, because they are small and fix or pin behaviour that the API cleanup (6) would otherwise have to carry along. 1 and 6 both touch `ea.py`. 7 comes last, because it checks the result of all the others.

| # | Name | Goal | Kind | Success measure | Status | Added |
|---|---|---|---|---|---|---|
| 1 | restart-guard | Done 2026-10-21 by T5 (9d4c290): `EA` raises `ValueError` when the restart source and the target database are the same file, in both `db_handling` modes, before opening either. | new behaviour | met: 3 new tests in `tests/test_ea_restart.py`; the 10 existing restart tests pass unchanged | done 2026-10-21 | 2026-10-21 |
| 2 | floats-size-none | Done 2026-10-21 by T6 (3f20e83): the float generators return a plain `float` for `size=None`, and typing overloads on all six generators say so. | new behaviour | met: 5 new tests in `tests/test_generators.py` (3 with Hypothesis); `known bug` ignores removed; `ty check` 0 diagnostics | done 2026-10-21 | 2026-10-21 |
| 3 | docs-build | Done 2026-10-21 by T1 (49f8351) (`sphinx.ext.todo` loaded); the `docs.yml` command exits 0. | improvement, behaviour unchanged | met | done 2026-10-21 | 2026-10-21 |
| 4 | examples-tested | Done 2026-10-21 by T4 (e424d6b): `tests/test_examples.py` runs `examples/a1_one_max.py` and checks `best fitness 20.0 of 20`; the empty `a0_hello_world.py` was deleted. | improvement, behaviour unchanged | met | done 2026-10-21 | 2026-10-21 |
| 5 | close-connections | The engine and tests close every SQLite connection they open. | improvement, behaviour unchanged | Corrected and re-approved 2026-10-21: `pytest` with `-W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning` passes every test (now set in `pytest.ini`). The approved measure, `-W error::ResourceWarning` alone, passed even before the fix: a leak found during garbage collection reaches pytest as `PytestUnraisableExceptionWarning`. | done 2026-10-21 by T2 and T3 (dd77424, d621b85) | 2026-10-21 |
| 6 | api-cleanup | The public interface is reviewed before 0.1, and each change the user approves is made and recorded for ARIEL's later switch. | new behaviour | Claude writes the candidate list (each with the call before and after, and why). Every approved change has a test and a line in a migration note that maps the `ariel.ec` name to the seachange name. Rejected candidates go to DESIGN.md. | approved 2026-10-21 | 2026-10-21 |
| 7 | release-0.1 | seachange 0.1.0 is ready for the user to publish on PyPI. | new behaviour | `uv build` makes a wheel and an sdist. A fresh temporary environment installs the wheel and runs the README example, which prints `best fitness 20.0 of 20`. Goal 3 passes, the README has no placeholders, and a CHANGELOG lists the changes from `ariel.ec`. Blocked until the hosting question is answered. | approved 2026-10-21 | 2026-10-21 |

After 0.1 (planned, not yet goals with measures): robot genotypes (ARIEL's tree, CPPN and NDE) moving here, a database backend other than SQLite, and ARIEL switching to seachange (work in the ARIEL repo).

Non-goals until 0.1: robot genotypes, databases other than SQLite.

## Current state

Phase: Tier 1 done (goals 1 to 5, tasks T1 to T6, on branch `tier1-fixes`). Next step: T7, the interface audit for goal 6.

## Baseline

2026-10-21, rechecked on branch `setup-audit`: ruff format and check pass (33 files), mypy passes (34 files), pytest 187 passed at 100% branch coverage in ~1 s with 79 warnings, pre-commit passes, ty 3 diagnostics, the Sphinx docs build fails (fixed since by T1). ty's 3 diagnostics are fixed since by T6.

Goal measurements, 2026-10-21, Linux (host `johnny-dm`), Python 3.13, uv 0.13.1:

- Goal 3: `uv run --no-sync sphinx-build -W --keep-going -b html docs docs/_build/html` fails, 1 error (`Unknown directive type "todo"`, `optimizers/revde.py` module docstring). Pass or fail, no noise. Fixed by T1.
- Goal 4: no test runs `examples/`. Run by hand, `a1_one_max.py` takes 0.49 to 0.51 s (3 runs) and prints `best fitness 20.0 of 20`. After T4 the test runs it; with `num_steps=1` it fails (`best fitness 12.0 of 20`, checked once, then restored).
- Goal 5: `uv run --no-sync pytest -q -p no:cacheprovider -W default` reports 73 warnings in 4 of 5 runs and 79 in 1 (median 73, range 73 to 79), all `ResourceWarning: unclosed database`. They come from three test files: `test_archive.py` (31 when run alone), `test_ea.py` (14) and `test_ea_restart.py` (11). The count varies with garbage-collection timing; the target is 0, so the noise does not matter. With `-W error::ResourceWarning` alone the suite still passed (83 warnings, checked after T2), so that flag does not measure this. After T3: 0 warnings in 3 runs, and the `pytest.ini` filter fails the suite when one leaking `create_engine` call is put back (checked once, then restored).

## Tasks

Draft 2026-10-21, awaiting the user's approval. One task per commit. Every area these tasks touch is covered by existing tests (100% branch coverage), except `examples/`, which T4 covers.

### Tier 1: goals 1 to 5 (approved order: these first)


### Tier 2: goals 6 and 7 (after Tier 1)

- **T7 Audit the public interface** (goal 6). Done 2026-10-21; the candidates are below, each awaiting the user's yes or no. Each approved candidate becomes its own task.

#### Goal 6 candidates (from T7)

Correctness hazards:

- **C1 Prefix the environment variables.** Before: `NUM_STEPS=7` or `QUIET=true` in the shell changes every run (checked: `config.num_steps` was 7). After: only `SEACHANGE_NUM_STEPS` and the like are read, and the generator settings get the same prefix. Why: an unrelated variable such as `QUIET` or `NUM_STEPS` from another tool silently changes results. Files: `ea_settings.py`, `generators/_shared.py`.
- **C2 Make `Archive` take the fitness direction explicitly.** Before: `archive.best_individual()` defaults to `fitness_mode="min"`, while `EA` and `Population` default to maximising; on the one-max run it returned fitness 7.0, not 20.0 (checked). After: `best_individual`, `hall_of_fame` and `tournament_population` require `fitness_mode=`. Why: the default gives the wrong answer for the engine's own default. The alternative is a default of `"max"`, which fixes one-max but leaves minimisation users with the same silent trap.
- **C3 Drop the ignored `fitness_mode` from `fitness_percentile_population`.** Before: the parameter is accepted and ignored (a `ruff: ignore[unused-method-argument]` marks it). After: the parameter is gone. Why: a caller who passes `"max"` believes it changes the result.
- **C4 Raise on an unknown `get_solution` mode.** Before: `ea.get_solution("bset")` returns `None` despite the `Individual` return type (a test pins this). After: `ValueError`. Why: a typo fails later, far from its cause.

Missing capabilities:

- **C5 Close a run.** Before: `ea.engine.dispose()`, which is undocumented. After: `ea.close()` and `with EA(...) as ea:`, and the same for `Archive`. Why: a long script that opens many runs leaks one SQLite connection per run (goal 5 found this in the tests).
- **C6 Reseed the generators.** Before: everything draws from one generator seeded with 42 at import; `SEED` is exported, but changing it does nothing, and there is no supported way to run with another seed. After: `seachange.seed(123)` reseeds the shared generator in place. Why: researchers repeat runs over several seeds.
- **C7 Remove RevDE's import side effects.** Before: `import seachange.optimizers.revde` creates `__data__/` in the working directory, installs rich's traceback handler for the whole program, and keeps its own generator seeded with 42. After: no module-level setup. `The `main()` demo, the only code that uses that generator, moves to `examples/`; `RevDE.mutate` is deterministic and does not change. Why: importing a library should not change the user's program or folders. This clears a Known problem.
- **C8 Decide the output folder when the run starts.** Before: `output_folder` defaults to `Path.cwd() / "__data__"` as computed at import, so a script that changes directory afterwards still writes to the old folder. After: the default is computed when `EA` is created. Why: it surprises in notebooks and test runners; goal 4's test had to work around it.

Cleanups:

- **C9 Remove `target_population_size`.** Before: `EASettings` has it and `EA` stores it, but nothing reads it. After: it is gone. Why: users set it and expect the engine to hold the population at that size.
- **C10 One word for the fitness direction.** Before: `EA(is_maximisation=True)`, `population.sort(sort="max")`, `archive.best_individual(fitness_mode="max")`. After: one name everywhere, for example `direction="max"`. Why: three names for one idea. Cost: a rename across every caller in ARIEL. My lean is no: the churn buys only consistency.
- **C11 Make `tags =` replace instead of merge.** Before: `ind.tags = {"a": 1}` keeps the existing keys (documented). After: assignment replaces; to merge, write `ind.tags = {**ind.tags, "a": 1}`. (`ind.tags.update(...)` in place would not be saved: the JSON column does not track changes inside the dict.) Why: assignment that merges surprises. My lean is no: ARIEL code may rely on the merge, and the docstring says so.
- **C12 Make `operations` required.** Before: `EA(population=None, operations=None)`, where `operations=None` raises `ValueError`. After: `operations` has no default. Why: the type would show it is required. Cost (corrected 2026-10-21): drop the defaults of both `population` and `operations`. Positional calls, including both README calls, keep working; calls that leave out `population`, such as the tests' `EA(restart=..., operations=...)`, must add `population=None`. The user chose a third option on 2026-10-21: `EA.restart()` (T23).

Approved by the user on 2026-10-21: C1 to C11, and C12 as `EA.restart()`.

Judged fine: `EAOperation`, `Individual` (fields and the `fitness` and `genotype` properties), `Population` (apart from C10), `Crossover`, `FloatMutator`, `IntegerMutator`, `FloatsGenerator`, `IntegersGenerator`, `Floats`, `Integers`, `JSONType`, `JSONPrimitive`, `JSONIterable`, `DBHandlingMode`, `EASettings` (apart from C1, C8 and C9), `config`, `Archive.random_individual`, `random_population`, `by_generation`, `fitness_stats`, `size` and `generation_range`.
#### Goal 6 tasks (approved by the user on 2026-10-21)

Each task: tests first (watch them fail), then the change, a CHANGELOG note recorded in DESIGN.md Results for T9, and the README updated where it shows the old call. All areas have tests at 100% branch coverage. Ordered so tasks that touch the same file follow each other, and so the rename (T18) happens before `direction` becomes required (T19).

- **T15 C4: unknown `get_solution` mode raises.** Files: `ea.py`, `tests/test_ea_restart.py` (the test that pins `None` changes to expect `ValueError`). Risk low. Cost: 3 lines.
- **T16 C5: `close()` and `with`.** Files: `ea.py`, `archive.py`, tests. `close()` disposes the engine; `__enter__` returns the object and `__exit__` calls `close()`. Tests: after `with`, the pool holds no connection and the `pytest.ini` filter stays green. Risk low. Cost: about 25 lines, 1 new idea for users.
- **T17 C3: drop the ignored parameter.** Files: `archive.py`, tests. Risk low. Cost: 2 lines removed and one suppression gone.
- **T18 C10: one direction word.** Files: `ea.py`, `ea_settings.py`, `population.py`, `archive.py`, `examples/a1_one_max.py`, README, tests (44 call sites). The user chose `direction: Literal["max", "min"]`, exported as `Direction`, replacing `is_maximisation`, `sort=` (on `Population`) and `fitness_mode=` (with its `FitnessMode` alias). Risk medium: wide but mechanical; mypy finds every missed caller. Cost: no new lines, many changed.
- **T19 C2: `Archive` requires the direction.** Files: `archive.py`, `tests/test_archive.py`. The three methods lose the default. Test: omitting it is a `TypeError`; one-max's `best_individual(direction="max")` gives 20.0. Risk low. Cost: 3 defaults removed, tests updated.
- **T20 C6: `seed()`.** Files: `generators/_shared.py`, `generators/__init__.py`, `__init__.py`, tests. `seed(n)` resets the shared generator's state in place, so modules that imported `rng` see it. Test: the same seed gives the same draws; different seeds give different ones. Risk low. Cost: about 15 lines.
- **T21 C7: RevDE without import side effects.** Files: `optimizers/revde.py`, new `examples/a2_revde.py` (the demo), `tests/test_revde.py`. `tests/test_examples.py` runs the new example. Test: importing `revde` in an empty folder creates nothing. Risk low. Cost: about 20 lines moved. Clears a Known problem.
- **T22 C11: `tags =` replaces.** Files: `individual.py`, `tests/test_individual.py`, plus any merge in `src/` or `examples/` rewritten as `{**ind.tags, ...}`. Risk medium: callers in ARIEL that rely on the merge lose tags silently; the CHANGELOG line must say so plainly. Cost: 1 line changed, docstring rewritten.
- **T23 C12: `EA.restart()`.** Files: `ea.py`, `tests/test_ea_restart.py`, `tests/test_ea.py`, README. `EA(population, operations, *, ...)` with both arguments required and no `None`; a new class method `EA.restart(source, operations, *, generation=None, ...)` with the same keywords as `EA` takes over the restart branch, including T5's same-file guard. The `(path, generation)` tuple and the "provide either population or restart" error go. Tests: every existing restart test rewritten to the new call, with the same assertions; `EA(None, ops)` is a mypy error. Risk medium: it moves about 40 lines of the constructor. Cost: one new public method, one removed argument. Last of goal 6, so T5 and T14 are settled first.

- **T8 Add the licence** (goal 7). Files: new `LICENSE` (copied from ARIEL), `pyproject.toml` (`license = "GPL-3.0-or-later"`, plus `license-files`). Risk low. Cost: 2 lines and one file. Verify: `uv build` puts the licence in the wheel's metadata.
- **T9 Write `CHANGELOG.md`** (goal 7). After goal 6. It lists every change from `ariel.ec` (goals 1, 2 and 6), each with the old call and the new one. Risk low. Verify: every behaviour change recorded in DESIGN.md has a line.
- **T10 Build-and-install check** (goal 7). Files: `CLAUDE.md` (the commands). Run `uv build`, then `uv run --isolated --with dist/<wheel> python <README example>` in a temporary folder, and record the commands with their output. Risk low. Verify: it prints `best fitness 20.0 of 20`.
- **T11 Repository URL** (goal 7). Blocked on hosting. Files: `README.md` (install step), `pyproject.toml` (`[project.urls]`).

### Tier 3: listed, not planned

- Typing a `Sequence[int]` size (a numpy shape, which gives nested lists) correctly. No caller in this repo uses it, and goal 2 does not need it.
- Porting the goal 1 and goal 2 fixes back to ARIEL's copy. That is work in the ARIEL repo, and it ends anyway when ARIEL switches to seachange.
- Measuring `-W default` warnings in user runs, outside the tests. Goal 5's measure covers the tests only. Users can close a run once goal 6 adds a way to do it.

## Open questions

- The README was approved and merged on 2026-10-21. Its install step has a `<repository URL>` placeholder until a remote exists.
- No remote exists. On 2026-10-21 the user deferred where to host it. Goal 7 (release-0.1) waits on the answer.

## Known problems

- Importing `seachange.optimizers.revde` creates `__data__/` in the working directory (module-level `mkdir`), copied as is.
- `uv-cr-lib`'s template `tools/run_notebooks.py` fails mypy until `nbclient`, `nbformat` and `ipykernel` are installed; they are in the dev group here.
