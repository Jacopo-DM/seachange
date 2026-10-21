# Design

## Specs

Approved by the user on 2026-10-21. Goal numbers refer to PLAN.md. Goal 6 (api-cleanup) gets its spec once goals 1 to 5 are done.

### Goal 1: restart-guard

- `EA.__init__` resolves the restart source and the target database (`db_file_path`, or `config.db_file_path` when it is `None`). If both name the same file, it raises `ValueError` naming the path and suggesting `db_file_path=`, before any database is opened.
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

- `tests/test_examples.py` runs each example in a fresh interpreter (`subprocess`, `sys.executable`) with a temporary folder as the working directory. Not `runpy`: inside the suite the shared generator's state depends on earlier tests, and `config.output_folder` is fixed to the working directory when `seachange` is imported, so an in-process run could vary and would write to the repo's `__data__/`.
- `examples/a0_hello_world.py`, the empty `uv-cr-lib` template, is deleted (user, 2026-10-21).
- Acceptance: `a1_one_max.py` prints `best fitness 20.0 of 20` (deterministic: the generators use the fixed `SEED`). Coverage stays at 100%.

### Goal 5: close-connections

- `EA.__init__` disposes the engine it opens on a restart source. The `dispose_engines` fixture in `tests/conftest.py` records every engine the package creates during a test and disposes them afterwards; test modules that build an `EA` or `Archive` opt in with `pytestmark`.
- Acceptance: `pytest.ini` turns `ResourceWarning` and `pytest.PytestUnraisableExceptionWarning` into errors, and every test passes. (Corrected from `-W error::ResourceWarning` alone, which could not fail; see Gotchas.)
- A public way for users to close a run (`close()` or a context manager) is a goal 6 candidate, not part of this goal.

### Goal 7: release-0.1

- Licence GPL-3.0-or-later, as ARIEL (copyright 2025 Jacopo Michele di Matteo and Ioannis Grigoriadis); `LICENSE` copied from ARIEL and `license = "GPL-3.0-or-later"` in `pyproject.toml`.
- `CHANGELOG.md` lists every change from `ariel.ec`, including goal 6's renames, as the migration note for ARIEL.
- Acceptance: `uv build` makes a wheel and an sdist; an isolated temporary environment installs the wheel and runs the README example, which prints `best fitness 20.0 of 20`; goal 3 passes; the README and `[project.urls]` carry the repository URL.

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
- 2026-10-21: the docs build fixes the `Todo` directive by loading `sphinx.ext.todo`, not by deleting the empty template sections (user).

## Rejected approaches

- Making ARIEL depend on seachange at the time of the copy (one copy of the engine). Rejected by the user then, in favour of leaving ARIEL untouched; on 2026-10-21 the user planned it for after 0.1 (see Decisions).
- Restart onto its own source file: writing the new run under a derived name such as `database_restart.db`. Rejected: the user may not notice where the data went. Checking inside `setup_database` was also rejected, because it does not know about restarts.
- `size=None`: returning a one-item list (rejected by the user; it breaks numpy's convention), or annotating the return as a plain union (every caller would have to narrow, even with the default `size=1`).
- Docs build: deleting the empty `Notes` and `Todo` sections from `revde.py`'s docstring. The user chose to enable `sphinx.ext.todo` instead.
- Licence: relicensing under MIT or similar. It needs written consent from every copyright holder of ARIEL's code.

## Results

| Date | Task | Goal | Change | Measured effect |
|---|---|---|---|---|
| 2026-10-21 | T1 | 3 | `docs/conf.py` loads `sphinx.ext.todo` | docs build with `-W`: 1 error before, 0 after (exit 0) |
| 2026-10-21 | T2 | 5 | `EA.__init__` disposes the restart source engine, also on its error paths | `test_ea_restart.py` alone, `-W default`: 11 warnings before, 10 after; full suite 79 before, 77 after |
| 2026-10-21 | T3 | 5 | `dispose_engines` fixture in `tests/conftest.py`, opted into by three test modules; one test disposes its own engine; `pytest.ini` fails on leaks | full suite: 77 warnings before, 0 after (3 runs); with the leak put back the suite fails |
| 2026-10-21 | T4 | 4 | `tests/test_examples.py` runs the one-max example; `a0_hello_world.py` deleted | 187 tests before, 188 after, suite ~0.8 s to ~1.3 s; the test fails when the example runs 1 generation |

## Gotchas

- The dependency versions are newer than ARIEL's lock (numpy 2.5.4, sqlalchemy 2.1.6, sqlmodel 0.0.48 against 2.3.3, 2.0.43, 0.0.27). numpy 2.5's stubs are what exposed the `size=None` bug in PLAN.md Known problems.
- A SQLite connection that the garbage collector closes raises its `ResourceWarning` inside `__del__`, where pytest catches it as an unraisable exception and reports `PytestUnraisableExceptionWarning`. So `-W error::ResourceWarning` alone never fails a test for a leak; `pytest.ini` turns both into errors. The failure is reported on whichever test is running when the collector runs, often the test after the leaking one.
- ruff bans `autouse=True` fixtures (`pytest-fixture-autouse`). Shared setup is opted into per module with `pytestmark = pytest.mark.usefixtures(...)`.
