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
| 8 | genotype-storage | A genotype comes back from the database as the type it went in (a numpy array keeps its dtype, shape and values), and large numeric genotypes are stored as raw bytes instead of JSON text. Spec in DESIGN.md. | new behaviour | (a) round-trip tests through `EA`, `EA.restart` and `Archive` for numpy arrays (Hypothesis over dtypes and shapes), JSON values (as today) and a user codec; (b) `tools/bench_genotypes.py` (100 individuals, 10,000 float32 weights, 20 generations, every parent replaced by a mutated child) measures genotype storage at most 0.05 s per generation, from 0.52 s, and a database of at most 90 MB, from 435 MB; (c) a database written by today's code still opens in `Archive` and `EA.restart` | approved 2026-10-21; T26 done | 2026-10-21 |

After 0.1 (planned, not yet goals with measures): robot genotypes (ARIEL's tree, CPPN and NDE) moving here, a database backend other than SQLite, and ARIEL switching to seachange (work in the ARIEL repo). The switch pays off first: CHANGELOG.md is already written as its migration guide. Before it, ask the ARIEL session why 3 of ARIEL's 1451 tests did not pass on 2026-10-21 (it reported 1448 passing without the cause). Scope these with /zz-02-project-plan.

Non-goals until 0.1: robot genotypes, databases other than SQLite.

## Current state

Phase: goal 8 (genotype-storage) approved on 2026-10-21 with its spec and tasks T26 to T32; T26 is done. The 0.1.0 release waits for goal 8 (user: the storage format should be settled before anyone has a 0.1 database). Goals 1 to 7 are done. A Python-standard compliance pass followed on 2026-10-21 (commits c24df65 to f78f2bd): 20 of its 21 checks met the standard; the one left, whether the settings should be frozen, was decided on 2026-10-21 (they are; DESIGN.md Decisions), so all 21 now meet it. Branch `compliance` is merged into `master` but not deleted (deleting needs the user's say-so). Nothing is uncommitted.

Next step: T27, the codecs module. After goal 8, the release steps are the user's, in this order: create github.com/Jacopo-DM/seachange (for example `gh repo create Jacopo-DM/seachange --public --source . --remote origin`), approve the push of `master` (Claude may run it only on that approval), then publish 0.1.0 with `uv build` and `uv publish` (the user publishes; Claude never does). Decisions waiting on the user, none blocking the release: the JSON aliases Known problem.

## Baseline

2026-10-21, rechecked on branch `setup-audit`: ruff format and check pass (33 files), mypy passes (34 files), pytest 187 passed at 100% branch coverage in ~1 s with 79 warnings, pre-commit passes, ty 3 diagnostics, the Sphinx docs build fails (fixed since by T1). ty's 3 diagnostics are fixed since by T6.

Goal measurements, 2026-10-21, Linux (host `johnny-dm`), Python 3.13, uv 0.13.1:

- Goal 3: `uv run --no-sync sphinx-build -W --keep-going -b html docs docs/_build/html` fails, 1 error (`Unknown directive type "todo"`, `optimizers/revde.py` module docstring). Pass or fail, no noise. Fixed by T1.
- Goal 4: no test runs `examples/`. Run by hand, `a1_one_max.py` takes 0.49 to 0.51 s (3 runs) and prints `best fitness 20.0 of 20`. After T4 the test runs it; with `num_steps=1` it fails (`best fitness 12.0 of 20`, checked once, then restored).
- Goal 8, 2026-10-21, a scratch script (T26 makes it `tools/bench_genotypes.py`): 100 individuals of 10,000 float32 weights stored as lists, 20 generations, each replacing every parent by a mutated child. 0.570 s per generation, of which the mutation itself is about 0.05 s, so genotype storage is about 0.52 s; the database reaches 435 MB for 2,100 individuals (207 KB each, against 40 KB as raw float32). Projected to 1,000 generations: about 9 minutes of storage and 21 GB. Confirmed by `tools/bench_genotypes.py` (T26), which times each `step()` minus the mutation: 0.530, 0.530 and 0.531 s of storage per generation and 435 MB in its 3 runs, about 36 s in all.
- Goal 5: `uv run --no-sync pytest -q -p no:cacheprovider -W default` reports 73 warnings in 4 of 5 runs and 79 in 1 (median 73, range 73 to 79), all `ResourceWarning: unclosed database`. They come from three test files: `test_archive.py` (31 when run alone), `test_ea.py` (14) and `test_ea_restart.py` (11). The count varies with garbage-collection timing; the target is 0, so the noise does not matter. With `-W error::ResourceWarning` alone the suite still passed (83 warnings, checked after T2), so that flag does not measure this. After T3: 0 warnings in 3 runs, and the `pytest.ini` filter fails the suite when one leaking `create_engine` call is put back (checked once, then restored).

## Tasks

Approved 2026-10-21. One task per commit.


### Tier 1: goal 8, approved 2026-10-21

- T26 `tools/bench_genotypes.py`: the goal 8 benchmark (100 individuals of 10,000 float32 weights, 20 generations, mutate-all), printing seconds per generation for genotype storage and the database size. Run before T28 to confirm the 0.52 s and 435 MB baseline. Status: done 2026-10-21 (see Baseline).
- T27 `seachange/codecs.py`: the `GenotypeCodec` protocol (`name`, `handles(genotype) -> bool`, `encode(genotype) -> bytes`, `decode(bytes) -> genotype`), the list of automatic codecs with `register_codec`, and two codecs, `json` (today's values) and `numpy` (dtype and shape, then the raw bytes). Unit and Hypothesis tests. No change to `EA` yet. Status: proposed.
- T28 Storage: `genotype_` becomes a bytes column; a `RunInfo` table holds the codec name and a format version; `EA` picks the codec from the first genotype (or takes `codec=`), encodes each genotype once, at its first save, and decodes on fetch; an assigned numpy genotype is marked read-only. Status: proposed.
- T29 `EA.restart` and `Archive` read the codec name from the file and use the matching codec (built in, or passed by the caller for a custom one); a database without a `RunInfo` table, as written by today's code or ARIEL's, is read with the `json` codec. Status: proposed.
- T30 Typing: `Individual` generic over its genotype type (`Individual[NDArray[np.float32]]`), so mypy knows `ind.genotype` exactly; the crossover functions follow. If SQLModel's table classes cannot take it cleanly, stop and ask the user. Status: proposed.
- T31 Docs and CHANGELOG: a docs page on codecs with a PyTorch codec as an example (no torch dependency), README note, CHANGELOG entries, and the ARIEL migration step. Status: proposed.
- T32 Measure goal 8 with T26 and record it in DESIGN.md Results. Status: proposed.

### Tier 3: listed, not planned

- Typing a `Sequence[int]` size (a numpy shape, which gives nested lists) correctly. No caller in this repo uses it, and goal 2 does not need it.
- Porting fixes back to ARIEL's copy: done in the ARIEL repo on 2026-10-21 for goal 1 (T5), goal 2 (T6) and the restart engine disposal (T2), ARIEL commits 6d8797d, 462f7af and a29589b on its `main` (not pushed). The goal 6 interface changes are not ported; ARIEL takes them when it switches to seachange.
- Smaller genotype storage, measured 2026-10-21 and left out of goal 8 (numbers in DESIGN.md Rejected approaches): storing a child as its difference from its parent (14% of the raw size when mutation touches 10% of the weights, 73% when it touches all of them), and an opt-in float16 codec (half the size, lossy).
- Measuring `-W default` warnings in user runs, outside the tests. Goal 5's measure covers the tests only. Users close a run with `close()` or `with` (T16).

## Open questions

None. Goal 8's three questions were answered on 2026-10-21 (DESIGN.md Specs, goal 8).

## Known problems

- The JSON type aliases promise more than a JSON column keeps: `JSONIterable` allows a tuple, which comes back as a list, and `dict[Hashable, ...]` allows non-string keys, which come back as strings (`{1: "a"}` returns as `{"1": "a"}`). Checked 2026-10-21. Fixing it means narrowing the aliases to lists and string keys (a typing change) or validating on save; not changed without the user's approval. Option found later: convert in the `genotype` and `tags` setters, so `ind.genotype = (1, 2)` reads back `[1, 2]` at once and the value never changes on its way through the database, with the aliases narrowed too. A storage format that keeps tuples was rejected: the column would stop being plain JSON and `Archive`'s queries get harder. Asked 2026-10-21; the user has not chosen yet.
