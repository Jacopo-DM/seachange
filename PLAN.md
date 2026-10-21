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
| 5 | close-connections | The engine and tests close every SQLite connection they open. | improvement, behaviour unchanged | Corrected 2026-10-21, needs re-approval: `pytest` with `-W error::ResourceWarning -W error::pytest.PytestUnraisableExceptionWarning` passes every test (now set in `pytest.ini`). The approved measure, `-W error::ResourceWarning` alone, passed even before the fix: a leak found during garbage collection reaches pytest as `PytestUnraisableExceptionWarning`. | done 2026-10-21 by T2 and T3 (dd77424, d621b85), measure awaiting re-approval | 2026-10-21 |
| 6 | api-cleanup | The public interface is reviewed before 0.1, and each change the user approves is made and recorded for ARIEL's later switch. | new behaviour | Claude writes the candidate list (each with the call before and after, and why). Every approved change has a test and a line in a migration note that maps the `ariel.ec` name to the seachange name. Rejected candidates go to DESIGN.md. | approved 2026-10-21 | 2026-10-21 |
| 7 | release-0.1 | seachange 0.1.0 is ready for the user to publish on PyPI. | new behaviour | `uv build` makes a wheel and an sdist. A fresh temporary environment installs the wheel and runs the README example, which prints `best fitness 20.0 of 20`. Goal 3 passes, the README has no placeholders, and a CHANGELOG lists the changes from `ariel.ec`. Blocked until the hosting question is answered. | approved 2026-10-21 | 2026-10-21 |

After 0.1 (planned, not yet goals with measures): robot genotypes (ARIEL's tree, CPPN and NDE) moving here, a database backend other than SQLite, and ARIEL switching to seachange (work in the ARIEL repo).

Non-goals until 0.1: robot genotypes, databases other than SQLite.

## Current state

Phase: Tier 1 done (goals 1 to 5, tasks T1 to T6, on branch `tier1-fixes`). Goal 5's corrected measure awaits re-approval. Next step: T7, the interface audit for goal 6.

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

- Importing `seachange.optimizers.revde` creates `__data__/` in the working directory (module-level `mkdir`), copied as is.
- `uv-cr-lib`'s template `tools/run_notebooks.py` fails mypy until `nbclient`, `nbformat` and `ipykernel` are installed; they are in the dev group here.
