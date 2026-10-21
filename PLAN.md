# Plan

## Goals

Users: researchers who install seachange from PyPI, and later ARIEL itself, once ARIEL drops its own `ariel.ec` engine and imports seachange instead. The public interface may change before 0.1, but each change needs the user's approval.

Order: 1 to 5 first, because they are small and fix or pin behaviour that the API cleanup (6) would otherwise have to carry along. 1 and 6 both touch `ea.py`. 7 comes last, because it checks the result of all the others.

| # | Name | Goal | Kind | Success measure | Status | Added |
|---|---|---|---|---|---|---|
| 1 | restart-guard | A restart whose new database file would be its own source raises an error instead of deleting the source. | new behaviour | A test calls `EA(None, ops, restart=X)` where the default `db_file_path` is also `X`: it raises `ValueError` naming the path, and the file's bytes are unchanged afterwards. The existing restart tests, which use a separate `db_file_path`, pass unchanged. | draft | 2026-10-21 |
| 2 | floats-size-none | `FloatsGenerator.uniform`, `normal` and `lognormal` with `size=None` return one plain `float`, as numpy does. | new behaviour | Hypothesis tests show each of the three returns a `float` for `size=None` and a list of the requested length otherwise. The three `known bug` ignores are gone and `ty check` reports 0 diagnostics. | draft | 2026-10-21 |
| 3 | docs-build | The Sphinx docs build with warnings treated as errors. | improvement, behaviour unchanged | The command in `docs.yml` (`sphinx-build -W --keep-going -b html docs docs/_build/html`) exits 0. | draft | 2026-10-21 |
| 4 | examples-tested | Every file in `examples/` runs under pytest, so a change that breaks the README example fails the suite. | improvement, behaviour unchanged | A test runs each example in a temporary folder. `a1_one_max.py` prints `best fitness 20.0 of 20`. The `a0_hello_world.py` stub is either given a real body or deleted (decided at the task list). Coverage stays at 100%. | draft | 2026-10-21 |
| 5 | close-connections | The engine and tests close every SQLite connection they open. | improvement, behaviour unchanged | `pytest -W error::ResourceWarning` passes with all 187 tests (today 79 warnings). | draft | 2026-10-21 |
| 6 | api-cleanup | The public interface is reviewed before 0.1, and each change the user approves is made and recorded for ARIEL's later switch. | new behaviour | Claude writes the candidate list (each with the call before and after, and why). Every approved change has a test and a line in a migration note that maps the `ariel.ec` name to the seachange name. Rejected candidates go to DESIGN.md. | draft | 2026-10-21 |
| 7 | release-0.1 | seachange 0.1.0 is ready for the user to publish on PyPI. | new behaviour | `uv build` makes a wheel and an sdist. A fresh temporary environment installs the wheel and runs the README example, which prints `best fitness 20.0 of 20`. Goal 3 passes, the README has no placeholders, and a CHANGELOG lists the changes from `ariel.ec`. Blocked until the hosting question is answered. | draft | 2026-10-21 |

After 0.1 (planned, not yet goals with measures): robot genotypes (ARIEL's tree, CPPN and NDE) moving here, a database backend other than SQLite, and ARIEL switching to seachange (work in the ARIEL repo).

Non-goals until 0.1: robot genotypes, databases other than SQLite.

## Current state

Phase: planning. The engine, generators and optimizers are copied from ARIEL with their tests. Seven goals are drafted. Next step: the user approves or changes the goals.

## Baseline

2026-10-21, rechecked on branch `setup-audit`: ruff format and check pass (33 files), mypy passes (34 files), pytest 187 passed at 100% branch coverage in ~1 s with 79 warnings, pre-commit passes, ty 3 diagnostics, the Sphinx docs build fails (see Known problems for both).

## Tasks

None yet.

## Open questions

- The README was approved and merged on 2026-10-21. Its install step has a `<repository URL>` placeholder until a remote exists.
- No remote exists. On 2026-10-21 the user deferred where to host it. Goal 7 (release-0.1) waits on the answer.
- Goal order: is 1 to 5, then 6, then 7 right? Goals 1 and 6 both change `ea.py`.

## Known problems

- `FloatsGenerator.uniform`, `normal` and `lognormal` crash with `AttributeError: 'float' object has no attribute 'tolist'` when `size=None` (`src/seachange/generators/sampling.py`). numpy returns a plain float there. ARIEL has the same bug. The lines carry `# type: ignore[union-attr]  # known bug`, and ty reports them (3 diagnostics).
- pytest shows 79 ResourceWarnings (81 when first measured) for unclosed SQLite connections; ARIEL's suite shows 3. Likely from sqlalchemy 2.1.6 and sqlmodel 0.0.48 here against 2.0.43 and 0.0.27 in ARIEL; not confirmed.
- `EA(None, ops, restart="__data__/database.db")` without `db_file_path` deletes the source run: the new run opens the default path, which is the same file, and `db_handling="delete"` removes it after the restart rows are read. Checked 2026-10-21 (102 KB before, 32 KB after, only the restart generation left). ARIEL has the same code. The README tells users to pass a separate `db_file_path`; no fix without the user's approval.
- Importing `seachange.optimizers.revde` creates `__data__/` in the working directory (module-level `mkdir`), copied as is.
- The docs build fails: `uv run --no-sync sphinx-build -W -b html docs docs/_build/html` (the command in `.github/workflows/docs.yml`) stops on `Unknown directive type "todo"` from the `Todo` section of the `optimizers/revde.py` module docstring. Found 2026-10-21. Either the docstring changes or `sphinx.ext.todo` goes into `docs/conf.py`; not decided.
- No test runs `examples/a1_one_max.py` (the README example) or `examples/a0_hello_world.py` (the `uv-cr-lib` template, still a stub), so a change that breaks the README example would pass CI.
- `uv-cr-lib`'s template `tools/run_notebooks.py` fails mypy until `nbclient`, `nbformat` and `ipykernel` are installed; they are in the dev group here.
