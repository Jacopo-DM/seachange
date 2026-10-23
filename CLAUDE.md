# seachange

A generational evolutionary algorithm engine whose population lives in a SQLite database. Copied on 2026-10-21 from ARIEL's `ariel.ec` (`~/projects/ariel`); ARIEL keeps its own copy and does not depend on this one.

Read PLAN.md first, then DESIGN.md, CODEMAP.md, the README, and the `README.md` of the package you will change (`src/seachange/`, `generators/`, `optimizers/`). If a file and the code disagree, trust the code, fix the file, and say what was wrong. If a file and the user's instructions disagree, stop and ask.

## Where facts live

| File | Holds |
|---|---|
| CLAUDE.md | rules and commands for every session in this repo |
| PLAN.md | state of the work; goes stale as it progresses |
| CODEMAP.md | structure of the code, regenerable from it; never plans, decisions or measurements |
| DESIGN.md | reasoning and reference that stays true after a task is done |

Test: the code could regenerate it → CODEMAP.md. Stale once the work is done → PLAN.md. A rule for every session here → CLAUDE.md. Otherwise → DESIGN.md.

## Commands

From the repo root. Python 3.13 (`.python-version`), uv 0.13.1. Checked 2026-10-23.

| Purpose | Command | Checked |
|---|---|---|
| Install everything | `uv sync --all-groups` | passes; `--locked --dry-run` reports no changes |
| Format | `uv run --no-sync ruff format .` | 70 files unchanged (2026-10-23), <1 s; covers the notebooks in `tests/functional/` and Python code blocks in Markdown (`docs/*.md`), as the Stop hook's `ruff format --check` does |
| Lint | `uv run --no-sync ruff check --no-fix .` | passes, <1 s; without `--no-fix` it rewrites files (`fix = true` in the template) |
| Types (mypy) | `uv run --no-sync mypy .` | passes, 49 files (2026-10-23), <1 s; does not read notebooks |
| Types (ty, advisory) | `uv run --locked ty check` | 0 diagnostics; also checks the notebooks, so a type error in a notebook cell shows here |
| Tests | `uv run --no-sync pytest -q` | 270 passed, 100% branch coverage, 8 to 15 s; no warnings; `pytest.ini` turns a leaked SQLite connection into a failure |
| Functional notebooks | `uv run --locked python tools/run_notebooks.py` | 6 PASS, 13 to 35 s (2026-10-22 and 2026-10-23); runs each `tests/functional/*.ipynb` in a fresh kernel in a temp folder, writes nothing back. `--save <notebook>` refreshes a notebook's committed outputs after a change; run it on every notebook the change affects. The pre-push hook runs all of them |
| Docs | `uv run --no-sync sphinx-build -W --keep-going -b html docs docs/_build/html` | passes, ~2 s; same command as `docs.yml` |
| Docs, shortcut | `uv-docs build` | passes, ~2 s; the shell function in `~/Functions/functions/my-funcs` that runs the build above with `--locked --group docs` |
| Docs, live preview | `uv-docs` | opens the docs in a browser and rebuilds when `docs/` or `src/` change (`sphinx-autobuild`); stop it with Ctrl+C. Not run by Claude: it opens a browser |
| Build | `uv build --offline` | passes, <1 s; writes the wheel and sdist to `dist/` (wheel: the package, `py.typed`, `LICENSE`) |
| Clean install | `(cd "$(mktemp -d)" && uv run --isolated --no-project --python 3.13 --with "$OLDPWD/dist/seachange-0.1.0-py3-none-any.whl" python -I "$OLDPWD/examples/a1_one_max.py")` | after Build; prints `best fitness 20.0 of 20`, ~1 s; imports seachange from a throwaway environment, not `src/`, and writes its `__data__/` in a new temp folder, never the repo root. Needs network to pypi.org: with `--offline` uv cannot resolve the dependencies |
| Benchmark (goal 8) | `uv run --no-sync python tools/bench_genotypes.py` | ~38 s; prints storage seconds per generation and database MB for 3 runs of list and of numpy genotypes, and each median (2026-10-21 after T28: lists 0.506 s, 435 MB; numpy 0.015 s, 86 MB). Run nothing else meanwhile |
| Structure numbers (goal 10) | `uv run --no-sync python tools/measure_structure.py` | ~2 s; prints file and line counts, files over 400 lines, modules importing more than 5 seachange modules, imports past another package's entry point, and jscpd's clones over `src` (0 clones after goal 10, 2026-10-22; 2 and 0.58% before). jscpd is a global tool (`~/.local/bin`, 5.4.0); without it the clone line says so |
| Secret scan | `gitleaks git --no-banner --redact .` | no leaks in 107 commits (2026-10-23); `gitleaks dir --no-banner --redact .` scans the working files. gitleaks is a global tool, installed on the Lenovo in `~/.local/bin` |
| Vulnerable dependencies | `osv-scanner scan --lockfile uv.lock` | no issues in 119 packages (2026-10-23); sends the package list to osv.dev. Global tool, installed on the Lenovo |
| Pre-commit | `uv run --no-sync pre-commit run --all-files` | passes, ~12 s; with `--all-files` the commit-stage notebook hook runs all six notebooks; the image hook skips (no images) |

## Code rules

- Package `seachange` in `src/seachange/`. Users import from `seachange` (its `__init__.py` exports). Subpackages `generators` and `optimizers` import nothing above them except `seachange._rng`, the two random generators every random draw uses (also read by `crossover.py`, `population.py` and `archive.py`). Other modules import a subpackage only through its `__init__.py`; `generators._shared` is for the generators alone.
- No compatibility shims. No abstraction before two real call sites. Clear names over clever one-liners. No options nobody asked for.
- Behaviour matches ARIEL's copy until the user approves a change. A lint or type fix that would change behaviour gets a line-level suppression with `known bug` and an entry in PLAN.md Known problems.
- Approved differences from the templates (user, 2026-10-21): `pytest.ini` adds `filterwarnings` turning `ResourceWarning` and `pytest.PytestUnraisableExceptionWarning` into errors, so a leaked SQLite connection fails the suite (goal 5). `docs/conf.py` is identical to the template again since 2026-10-22 (goal 10, R3).

## Git and approvals

- The default branch is `main` (renamed from `master`, which `uv-cr-lib` made, on 2026-10-21, because `ci.yml` and `docs.yml` run on pushes to `main`). Remote `origin` is `git@github.com:Jacopo-DM/seachange.git` (public, created by the user 2026-10-22).

## Data and secrets

- `EASettings.output_folder` makes a run write `__data__/` under the current working directory (git-ignored). Run examples and ad hoc scripts from a scratch folder, never the repo root: the default `db_handling="delete"` replaces an existing `__data__/database.db`, which may be one of the user's runs. No keys or environment variables are needed; `EASettings` and the generator settings read overrides from environment variables prefixed `SEACHANGE_` (for example `SEACHANGE_NUM_STEPS`).

## Ignore list

| Path | Kind | What makes it |
|---|---|---|
| `__data__/` | generated | EA runs and the examples |
| `.venv/` | generated | `uv sync` |
| `.coverage` | generated | `pytest` |
| `docs/_build/` | generated | sphinx |
| `docs/api/` | generated | sphinx autosummary, from `docs/reference.md` |
| `dist/` | generated | `uv build` |

## Things that bite

- The Clean install command used to run the example from the repo root, so each check replaced `__data__/database.db` there (it did on 2026-10-23). Commands that run an example or an `EA` start in a temp folder, as the Clean install row now does.
