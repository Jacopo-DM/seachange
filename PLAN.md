# Plan

## Goals

No goals yet: run /zz-02-project-plan.

## Current state

Phase: extracted. The engine, generators and optimizers are copied from ARIEL with their tests, all checks pass. Next step: decide the goals for the library (run /zz-02-project-plan).

## Baseline

2026-10-21, branch `extract-ea-engine`: ruff format and check pass, mypy passes (33 files), pytest 187 passed at 100% branch coverage in ~2 s, ty 3 diagnostics (see Known problems).

## Tasks

None yet.

## Open questions

- The README is still the template (`LINK.com`, `...`). It needs prose before any push; the user writes or approves it.
- No remote exists. Where to host it (GitHub under `Jacopo-DM`?) is the user's call.

## Known problems

- `FloatsGenerator.uniform`, `normal` and `lognormal` crash with `AttributeError: 'float' object has no attribute 'tolist'` when `size=None` (`src/seachange/generators/sampling.py`). numpy returns a plain float there. ARIEL has the same bug. The lines carry `# type: ignore[union-attr]  # known bug`, and ty reports them (3 diagnostics).
- pytest shows 81 ResourceWarnings for unclosed SQLite connections; ARIEL's suite shows 3. Likely from sqlalchemy 2.1.6 and sqlmodel 0.0.48 here against 2.0.43 and 0.0.27 in ARIEL; not confirmed.
- Importing `seachange.optimizers.revde` creates `__data__/` in the working directory (module-level `mkdir`), copied as is.
- `uv-cr-lib`'s template `tools/run_notebooks.py` fails mypy until `nbclient`, `nbformat` and `ipykernel` are installed; they are in the dev group here.
