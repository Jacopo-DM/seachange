# seachange

A generational evolutionary algorithm engine whose population lives in a SQLite database. Copied on 2026-10-21 from ARIEL's `ariel.ec` (`~/projects/ariel`); ARIEL keeps its own copy and does not depend on this one.

Read PLAN.md first, then DESIGN.md, CODEMAP.md and the README. If a file and the code disagree, trust the code, fix the file, and say what was wrong. If a file and the user's instructions disagree, stop and ask.

## Where facts live

| File | Holds |
|---|---|
| CLAUDE.md | rules and commands for every session in this repo |
| PLAN.md | state of the work; goes stale as it progresses |
| CODEMAP.md | structure of the code, regenerable from it; never plans, decisions or measurements |
| DESIGN.md | reasoning and reference that stays true after a task is done |

Test: the code could regenerate it → CODEMAP.md. Stale once the work is done → PLAN.md. A rule for every session here → CLAUDE.md. Otherwise → DESIGN.md.

## Commands

From the repo root. Python 3.13 (`.python-version`), uv 0.13.1. Checked 2026-10-21.

| Purpose | Command | Checked |
|---|---|---|
| Install everything | `uv sync --all-groups` | passes; `--locked --dry-run` reports no changes |
| Format | `uv run --no-sync ruff format src tests tools examples` | 35 files unchanged, <1 s |
| Lint | `uv run --no-sync ruff check --no-fix .` | passes, <1 s; without `--no-fix` it rewrites files (`fix = true` in the template) |
| Types (mypy) | `uv run --no-sync mypy .` | passes, 36 files, <1 s |
| Types (ty, advisory) | `uv run --locked ty check` | 0 diagnostics |
| Tests | `uv run --no-sync pytest -q` | 214 passed, 100% branch coverage, ~2.5 s; no warnings; `pytest.ini` turns a leaked SQLite connection into a failure |
| Docs | `uv run --no-sync sphinx-build -W --keep-going -b html docs docs/_build/html` | passes, ~2 s; same command as `docs.yml` |
| Pre-commit | `uv run --no-sync pre-commit run --all-files` | passes, <1 s; image and notebook hooks skip (no files) |

## Code rules

- Package `seachange` in `src/seachange/`. Users import from `seachange` (its `__init__.py` exports). Subpackages `generators` and `optimizers` import nothing above them except `generators._shared`, which `crossover.py` also reads.
- No compatibility shims. No abstraction before two real call sites. Clear names over clever one-liners. No options nobody asked for.
- Behaviour matches ARIEL's copy until the user approves a change. A lint or type fix that would change behaviour gets a line-level suppression with `known bug` and an entry in PLAN.md Known problems.

## Git and approvals

- `uv-cr-lib` made the first six commits on `master`; work goes on feature branches from there. No remote yet.

## Data and secrets

- `EASettings.output_folder` makes a run write `__data__/` under the current working directory (git-ignored). No keys or environment variables are needed; `EASettings` and the generator settings read overrides from environment variables prefixed `SEACHANGE_` (for example `SEACHANGE_NUM_STEPS`).

## Ignore list

| Path | Kind | What makes it |
|---|---|---|
| `__data__/` | generated | EA runs and the examples |
| `.venv/` | generated | `uv sync` |
| `.coverage` | generated | `pytest` |
| `docs/_build/` | generated | sphinx |
