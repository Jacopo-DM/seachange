# Plan

## Goals

Users: researchers who install seachange from PyPI, and later ARIEL itself, once ARIEL drops its own `ariel.ec` engine and imports seachange instead. The public interface may change before 0.1, but each change needs the user's approval.

Order (approved 2026-10-21): 1 to 5 first, because they are small and fix or pin behaviour that the API cleanup (6) would otherwise have to carry along. 1 and 6 both touch `ea.py`. 7 comes last, because it checks the result of all the others.

| # | Name | Goal | Kind | Success measure | Status | Added |
|---|---|---|---|---|---|---|
| 1 | restart-guard | A restart whose new database file would be its own source raises an error instead of deleting the source. | new behaviour | A test calls `EA(None, ops, restart=X)` where the default `db_file_path` is also `X`: it raises `ValueError` naming the path, and the file's bytes are unchanged afterwards. The existing restart tests, which use a separate `db_file_path`, pass unchanged. | approved 2026-10-21 | 2026-10-21 |
| 2 | floats-size-none | `FloatsGenerator.uniform`, `normal` and `lognormal` with `size=None` return one plain `float`, as numpy does. | new behaviour | Hypothesis tests show each of the three returns a `float` for `size=None` and a list of the requested length otherwise. The three `known bug` ignores are gone and `ty check` reports 0 diagnostics. | approved 2026-10-21 | 2026-10-21 |
| 3 | docs-build | Done 2026-10-21 by T1 (`sphinx.ext.todo` loaded); the `docs.yml` command exits 0. | improvement, behaviour unchanged | met | done 2026-10-21 | 2026-10-21 |
| 4 | examples-tested | Every file in `examples/` runs under pytest, so a change that breaks the README example fails the suite. | improvement, behaviour unchanged | A test runs each example in a temporary folder. `a1_one_max.py` prints `best fitness 20.0 of 20`. The `a0_hello_world.py` stub is either given a real body or deleted (decided at the task list). Coverage stays at 100%. | approved 2026-10-21 | 2026-10-21 |
| 5 | close-connections | The engine and tests close every SQLite connection they open. | improvement, behaviour unchanged | `pytest -W error::ResourceWarning` passes with all 187 tests (today 79 warnings). | approved 2026-10-21 | 2026-10-21 |
| 6 | api-cleanup | The public interface is reviewed before 0.1, and each change the user approves is made and recorded for ARIEL's later switch. | new behaviour | Claude writes the candidate list (each with the call before and after, and why). Every approved change has a test and a line in a migration note that maps the `ariel.ec` name to the seachange name. Rejected candidates go to DESIGN.md. | approved 2026-10-21 | 2026-10-21 |
| 7 | release-0.1 | seachange 0.1.0 is ready for the user to publish on PyPI. | new behaviour | `uv build` makes a wheel and an sdist. A fresh temporary environment installs the wheel and runs the README example, which prints `best fitness 20.0 of 20`. Goal 3 passes, the README has no placeholders, and a CHANGELOG lists the changes from `ariel.ec`. Blocked until the hosting question is answered. | approved 2026-10-21 | 2026-10-21 |

After 0.1 (planned, not yet goals with measures): robot genotypes (ARIEL's tree, CPPN and NDE) moving here, a database backend other than SQLite, and ARIEL switching to seachange (work in the ARIEL repo).

Non-goals until 0.1: robot genotypes, databases other than SQLite.

## Current state

Phase: planning. The engine, generators and optimizers are copied from ARIEL with their tests. All seven goals are approved, and the specs for goals 1 to 5 and 7 are in DESIGN.md. Next step: the user approves the task list.

## Baseline

2026-10-21, rechecked on branch `setup-audit`: ruff format and check pass (33 files), mypy passes (34 files), pytest 187 passed at 100% branch coverage in ~1 s with 79 warnings, pre-commit passes, ty 3 diagnostics, the Sphinx docs build fails (fixed since by T1). ty: see Known problems.

Goal measurements, 2026-10-21, Linux (host `johnny-dm`), Python 3.13, uv 0.13.1:

- Goal 3: `uv run --no-sync sphinx-build -W --keep-going -b html docs docs/_build/html` fails, 1 error (`Unknown directive type "todo"`, `optimizers/revde.py` module docstring). Pass or fail, no noise. Fixed by T1.
- Goal 4: no test runs `examples/`. Run by hand, `a1_one_max.py` takes 0.49 to 0.51 s (3 runs) and prints `best fitness 20.0 of 20`.
- Goal 5: `uv run --no-sync pytest -q -p no:cacheprovider -W default` reports 73 warnings in 4 of 5 runs and 79 in 1 (median 73, range 73 to 79), all `ResourceWarning: unclosed database`. They come from three test files: `test_archive.py` (31 when run alone), `test_ea.py` (14) and `test_ea_restart.py` (11). The count varies with garbage-collection timing; the target is 0, so the noise does not matter.

## Tasks

Draft 2026-10-21, awaiting the user's approval. One task per commit. Every area these tasks touch is covered by existing tests (100% branch coverage), except `examples/`, which T4 covers.

### Tier 1: goals 1 to 5 (approved order: these first)

- **T2 Dispose the restart source engine** (goal 5). Files: `src/seachange/ea.py`. Call `source_engine.dispose()` once the restart rows are read, including on the error paths. Serves: part of the 11 warnings from `test_ea_restart.py`. Risk low: the engine is local and never used again. Cost: about 3 lines. Verify: `test_ea_restart.py` passes unchanged, with fewer warnings.
- **T3 Dispose engines in the tests** (goal 5). Files: `tests/test_archive.py`, `tests/test_ea.py`, `tests/test_ea_restart.py`, maybe `tests/ea_helpers.py`. Fixtures that return an `Archive` or `EA` become `yield` fixtures that dispose the engine; inline objects are disposed at the end of the test. Then make the suite fail on any new leak: add a `filterwarnings` line to `pytest.ini` that turns this warning into an error. The exact filter depends on how pytest reports a warning raised during garbage collection (possibly `PytestUnraisableExceptionWarning`), and I will check that before writing it. This tightens the pytest config and loosens nothing. Serves: `pytest -W error::ResourceWarning` passes (baseline: median 73 warnings). Risk low: it changes tests only, not product code. Cost: about 30 changed lines, 1 config line. Verify: the full suite under the filter, 3 runs.
- **T4 Test the examples** (goal 4). Files: new `tests/test_examples.py`. Run `examples/a1_one_max.py` with `runpy` in `tmp_path` and assert `best fitness 20.0 of 20`. Also delete `examples/a0_hello_world.py`. It is the empty `uv-cr-lib` template: `main()` returns nothing, and running it only creates `__data__/`. Deleting it is my recommendation and needs your approval with this list; the alternative is to write a real hello-world. Risk low. Cost: about 25 lines and one file deleted. Verify: the new test passes, and it fails when the example's fitness assertion is changed by hand (checked once, then reverted).
- **T5 Guard restarts onto their own source** (goal 1). Files: `src/seachange/ea.py`, `tests/test_ea_restart.py`. Write the tests first (both `db_handling` modes, bytes unchanged, relative against absolute path) and watch them fail. Then add the `Path.resolve()` comparison and the `ValueError`, and update the `Raises` section of the docstring. Remove the Known problems entry and the README sentence that works around it. The README's restart example already passes `db_file_path` and stays. Risk low: one new check before any file is opened. Cost: about 8 lines plus 3 tests. Verify: the new tests, plus the existing 10 restart tests unchanged.
- **T6 Return a number for `size=None`, with overloads** (goal 2). Files: `src/seachange/generators/sampling.py`, `tests/test_generators.py`. Hypothesis tests first: return type and length for `size=None` and for `int` sizes, on all six methods. Then add the `@overload`s and the runtime fix in the three float methods, and remove the three `known bug` ignores and their Known problems entry. Risk medium: the overloads have to satisfy mypy, pyright and ty at once, and `Floats` and `Integers` are used across `generators/` and `crossover.py`. Cost: about 60 lines, mostly overload stubs; no new dependency. Verify: the new tests, existing generator and crossover tests unchanged, mypy clean, `ty check` 0 diagnostics.

### Tier 2: goals 6 and 7 (after Tier 1)

- **T7 Audit the public interface** (goal 6). Files: none changed. Write a candidate list into this file: each candidate shows the call before and after and gives the reason. The engine-closing candidate from goal 5 is on it. You approve the candidates one by one; each approved change becomes its own task, approved separately. Risk none. Verify: every name exported from `seachange/__init__.py` is either on the list or judged fine.
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

- `FloatsGenerator.uniform`, `normal` and `lognormal` crash with `AttributeError: 'float' object has no attribute 'tolist'` when `size=None` (`src/seachange/generators/sampling.py`). numpy returns a plain float there. ARIEL has the same bug. The lines carry `# type: ignore[union-attr]  # known bug`, and ty reports them (3 diagnostics).
- pytest shows 79 ResourceWarnings (81 when first measured) for unclosed SQLite connections; ARIEL's suite shows 3. Likely from sqlalchemy 2.1.6 and sqlmodel 0.0.48 here against 2.0.43 and 0.0.27 in ARIEL; not confirmed.
- `EA(None, ops, restart="__data__/database.db")` without `db_file_path` deletes the source run: the new run opens the default path, which is the same file, and `db_handling="delete"` removes it after the restart rows are read. Checked 2026-10-21 (102 KB before, 32 KB after, only the restart generation left). ARIEL has the same code. The README tells users to pass a separate `db_file_path`; no fix without the user's approval.
- Importing `seachange.optimizers.revde` creates `__data__/` in the working directory (module-level `mkdir`), copied as is.
- No test runs `examples/a1_one_max.py` (the README example) or `examples/a0_hello_world.py` (the `uv-cr-lib` template, still a stub), so a change that breaks the README example would pass CI.
- `uv-cr-lib`'s template `tools/run_notebooks.py` fails mypy until `nbclient`, `nbformat` and `ipykernel` are installed; they are in the dev group here.
