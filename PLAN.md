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
| 6 | api-cleanup | Done 2026-10-21: audit T7 (ab86dd5) found 12 candidates; all approved and made as T12 to T23 (8a2f40c to b7e5902). Each change and its ARIEL migration step is a row in DESIGN.md Results, for the CHANGELOG (T9). | new behaviour | met: every approved change has tests and a migration line; rejected options are in DESIGN.md | done 2026-10-21 | 2026-10-21 |
| 7 | release-0.1 | Done 2026-10-21: licence (T8), CHANGELOG (T9), build-and-install check (T10), repository URL (T11), plus T24 and T25 (a1bb034 to c6fac55). | new behaviour | met: `uv build` makes both archives; a throwaway environment installs the wheel and the one-max example prints `best fitness 20.0 of 20`; docs build with `-W`; no placeholders in the README; CHANGELOG lists every change | done 2026-10-21 | 2026-10-21 |

After 0.1 (planned, not yet goals with measures): robot genotypes (ARIEL's tree, CPPN and NDE) moving here, a database backend other than SQLite, and ARIEL switching to seachange (work in the ARIEL repo).

Non-goals until 0.1: robot genotypes, databases other than SQLite.

## Current state

Phase: all seven goals done; 0.1.0 is ready to publish. Next steps are the user's: create github.com/Jacopo-DM/seachange, push, then publish 0.1.0 to PyPI.

## Baseline

2026-10-21, rechecked on branch `setup-audit`: ruff format and check pass (33 files), mypy passes (34 files), pytest 187 passed at 100% branch coverage in ~1 s with 79 warnings, pre-commit passes, ty 3 diagnostics, the Sphinx docs build fails (fixed since by T1). ty's 3 diagnostics are fixed since by T6.

Goal measurements, 2026-10-21, Linux (host `johnny-dm`), Python 3.13, uv 0.13.1:

- Goal 3: `uv run --no-sync sphinx-build -W --keep-going -b html docs docs/_build/html` fails, 1 error (`Unknown directive type "todo"`, `optimizers/revde.py` module docstring). Pass or fail, no noise. Fixed by T1.
- Goal 4: no test runs `examples/`. Run by hand, `a1_one_max.py` takes 0.49 to 0.51 s (3 runs) and prints `best fitness 20.0 of 20`. After T4 the test runs it; with `num_steps=1` it fails (`best fitness 12.0 of 20`, checked once, then restored).
- Goal 5: `uv run --no-sync pytest -q -p no:cacheprovider -W default` reports 73 warnings in 4 of 5 runs and 79 in 1 (median 73, range 73 to 79), all `ResourceWarning: unclosed database`. They come from three test files: `test_archive.py` (31 when run alone), `test_ea.py` (14) and `test_ea_restart.py` (11). The count varies with garbage-collection timing; the target is 0, so the noise does not matter. With `-W error::ResourceWarning` alone the suite still passed (83 warnings, checked after T2), so that flag does not measure this. After T3: 0 warnings in 3 runs, and the `pytest.ini` filter fails the suite when one leaking `create_engine` call is put back (checked once, then restored).

## Tasks

Approved 2026-10-21. One task per commit.


### Tier 3: listed, not planned

- Typing a `Sequence[int]` size (a numpy shape, which gives nested lists) correctly. No caller in this repo uses it, and goal 2 does not need it.
- Porting fixes back to ARIEL's copy: done in the ARIEL repo on 2026-10-21 for goal 1 (T5), goal 2 (T6) and the restart engine disposal (T2), ARIEL commits 6d8797d, 462f7af and a29589b on its `main` (not pushed). The goal 6 interface changes are not ported; ARIEL takes them when it switches to seachange.
- Measuring `-W default` warnings in user runs, outside the tests. Goal 5's measure covers the tests only. Users close a run with `close()` or `with` (T16).

## Open questions

- Should `seachange.config` stay changeable at run time? Today `config.direction = "min"` changes every `EA` created afterwards; ARIEL's Ackley notebook uses this style (`config.is_maximisation = False`), and an ARIEL example comment shows it surprising someone. The Python standard wants settings read-only (`frozen=True`), which would make that line raise; the run would pass `direction="min"` to `EA` instead. Asked three times on 2026-10-21 without a clear answer; left as is, which changes nothing.

## Known problems

- Right after `EA(...)`, `ea.population` holds rows the database session has already expired, so reading a field such as `ea.population[0].genotype` raises `DetachedInstanceError`. `step()` refetches before it uses them, so runs work; a caller has to call `ea.fetch_population()` first. Found 2026-10-21 while writing the round-trip test; existing behaviour, not changed.
- The JSON type aliases promise more than a JSON column keeps: `JSONIterable` allows a tuple, which comes back as a list, and `dict[Hashable, ...]` allows non-string keys, which come back as strings (`{1: "a"}` returns as `{"1": "a"}`). Checked 2026-10-21. Fixing it means narrowing the aliases to lists and string keys (a typing change) or validating on save; not changed without the user's approval.
