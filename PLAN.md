# Plan

## Goals

No goals yet: run /zz-02-project-plan.

## Current state

Phase: extracted. The engine, generators and optimizers are copied from ARIEL with their tests, all checks pass. Next step: decide the goals for the library (run /zz-02-project-plan).

## Baseline

2026-10-21, rechecked on branch `setup-audit`: ruff format and check pass (33 files), mypy passes (34 files), pytest 187 passed at 100% branch coverage in ~1 s with 79 warnings, pre-commit passes, ty 3 diagnostics, the Sphinx docs build fails (see Known problems for both).

## Tasks

None yet.

## Open questions

- The README was approved and merged on 2026-10-21. Its install step has a `<repository URL>` placeholder until a remote exists.
- No remote exists. Where to host it (GitHub under `Jacopo-DM`?) is the user's call.

## Known problems

- `FloatsGenerator.uniform`, `normal` and `lognormal` crash with `AttributeError: 'float' object has no attribute 'tolist'` when `size=None` (`src/seachange/generators/sampling.py`). numpy returns a plain float there. ARIEL has the same bug. The lines carry `# type: ignore[union-attr]  # known bug`, and ty reports them (3 diagnostics).
- pytest shows 79 ResourceWarnings (81 when first measured) for unclosed SQLite connections; ARIEL's suite shows 3. Likely from sqlalchemy 2.1.6 and sqlmodel 0.0.48 here against 2.0.43 and 0.0.27 in ARIEL; not confirmed.
- `EA(None, ops, restart="__data__/database.db")` without `db_file_path` deletes the source run: the new run opens the default path, which is the same file, and `db_handling="delete"` removes it after the restart rows are read. Checked 2026-10-21 (102 KB before, 32 KB after, only the restart generation left). ARIEL has the same code. The README tells users to pass a separate `db_file_path`; no fix without the user's approval.
- Importing `seachange.optimizers.revde` creates `__data__/` in the working directory (module-level `mkdir`), copied as is.
- The docs build fails: `uv run --no-sync sphinx-build -W -b html docs docs/_build/html` (the command in `.github/workflows/docs.yml`) stops on `Unknown directive type "todo"` from the `Todo` section of the `optimizers/revde.py` module docstring. Found 2026-10-21. Either the docstring changes or `sphinx.ext.todo` goes into `docs/conf.py`; not decided.
- No test runs `examples/a1_one_max.py` (the README example) or `examples/a0_hello_world.py` (the `uv-cr-lib` template, still a stub), so a change that breaks the README example would pass CI.
- `uv-cr-lib`'s template `tools/run_notebooks.py` fails mypy until `nbclient`, `nbformat` and `ipykernel` are installed; they are in the dev group here.
