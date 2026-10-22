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
| Format | `uv run --no-sync ruff format .` | 64 files unchanged, <1 s; covers the notebooks in `tests/functional/` and Python code blocks in Markdown (`docs/*.md`), as the Stop hook's `ruff format --check` does |
| Lint | `uv run --no-sync ruff check --no-fix .` | passes, <1 s; without `--no-fix` it rewrites files (`fix = true` in the template) |
| Types (mypy) | `uv run --no-sync mypy .` | passes, 47 files, <1 s; does not read notebooks |
| Types (ty, advisory) | `uv run --locked ty check` | 0 diagnostics; also checks the notebooks, so a type error in a notebook cell shows here |
| Tests | `uv run --no-sync pytest -q` | 270 passed, 100% branch coverage, ~8 s; no warnings; `pytest.ini` turns a leaked SQLite connection into a failure |
| Functional notebooks | `uv run --locked python tools/run_notebooks.py` | 6 PASS, ~13 s (2026-10-22); runs each `tests/functional/*.ipynb` in a fresh kernel in a temp folder, writes nothing back. `--save <notebook>` refreshes a notebook's committed outputs after a change; run it on every notebook the change affects. The pre-push hook runs all of them |
| Docs | `uv run --no-sync sphinx-build -W --keep-going -b html docs docs/_build/html` | passes, ~2 s; same command as `docs.yml` |
| Docs, shortcut | `uv-docs build` | passes, ~2 s; the shell function in `~/Functions/functions/my-funcs` that runs the build above with `--locked --group docs` |
| Docs, live preview | `uv-docs` | opens the docs in a browser and rebuilds when `docs/` or `src/` change (`sphinx-autobuild`); stop it with Ctrl+C. Not run by Claude: it opens a browser |
| Build | `uv build --offline` | passes, <1 s; writes the wheel and sdist to `dist/` (wheel: the package, `py.typed`, `LICENSE`) |
| Clean install | `uv run --isolated --no-project --python 3.13 --with dist/seachange-0.1.0-py3-none-any.whl python -I examples/a1_one_max.py` | after Build; prints `best fitness 20.0 of 20`, ~1 s; imports seachange from a throwaway environment, not `src/`. Needs network to pypi.org: with `--offline` uv cannot resolve the dependencies |
| Benchmark (goal 8) | `uv run --no-sync python tools/bench_genotypes.py` | ~38 s; prints storage seconds per generation and database MB for 3 runs of list and of numpy genotypes, and each median (2026-10-21 after T28: lists 0.506 s, 435 MB; numpy 0.015 s, 86 MB). Run nothing else meanwhile |
| Secret scan | `gitleaks git --no-banner --redact .` | no leaks in 76 commits (2026-10-21); `gitleaks dir --no-banner --redact .` scans the working files. gitleaks is a global tool, installed on the Lenovo in `~/.local/bin` |
| Vulnerable dependencies | `osv-scanner scan --lockfile uv.lock` | no issues in 113 packages (2026-10-21); sends the package list to osv.dev. Global tool, installed on the Lenovo |
| Pre-commit | `uv run --no-sync pre-commit run --all-files` | passes, <1 s; image and notebook hooks skip (no files) |

## Code rules

- Package `seachange` in `src/seachange/`. Users import from `seachange` (its `__init__.py` exports). Subpackages `generators` and `optimizers` import nothing above them except `generators._shared`, which `crossover.py`, `population.py` and `archive.py` also read (its two random generators).
- No compatibility shims. No abstraction before two real call sites. Clear names over clever one-liners. No options nobody asked for.
- Behaviour matches ARIEL's copy until the user approves a change. A lint or type fix that would change behaviour gets a line-level suppression with `known bug` and an entry in PLAN.md Known problems.
- Approved differences from the templates (user, 2026-10-21): `pytest.ini` adds `filterwarnings` turning `ResourceWarning` and `pytest.PytestUnraisableExceptionWarning` into errors, so a leaked SQLite connection fails the suite (goal 5); `docs/conf.py` adds `sphinx.ext.todo`, so RevDE's numpy `Todo` docstring section builds under `-W` (goal 3).

## Git and approvals

- The default branch is `main` (renamed from `master`, which `uv-cr-lib` made, on 2026-10-21, because `ci.yml` and `docs.yml` run on pushes to `main`). Work goes on feature branches from `main`. No remote yet.

## Data and secrets

- `EASettings.output_folder` makes a run write `__data__/` under the current working directory (git-ignored). Run examples and ad hoc scripts from a scratch folder, never the repo root: the default `db_handling="delete"` replaces an existing `__data__/database.db`, which may be one of the user's runs. No keys or environment variables are needed; `EASettings` and the generator settings read overrides from environment variables prefixed `SEACHANGE_` (for example `SEACHANGE_NUM_STEPS`).

## Ignore list

| Path | Kind | What makes it |
|---|---|---|
| `__data__/` | generated | EA runs and the examples |
| `.venv/` | generated | `uv sync` |
| `.coverage` | generated | `pytest` |
| `docs/_build/` | generated | sphinx |
| `dist/` | generated | `uv build` |
