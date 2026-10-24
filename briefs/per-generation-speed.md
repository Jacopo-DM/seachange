# Brief for the seachange session: per-generation speed

From the multineat planning session on the Mac, at the user's request. This
is a finding and a proposed seachange goal. Nothing has been changed in
seachange; plan it with the user (/zz-02-project-plan or /zz-04-speed-up),
who approves before any code.

## Why

multineat (a Rust/Python rework of MultiNEAT) wants to run NEAT's generation
loop on seachange. NEAT on cheap tasks (XOR) runs thousands of short
generations, so seachange's per-generation overhead matters. The user's goal:
bring the in-memory vs seachange difference to almost nothing.

## Benchmark

All on the Mac, Python 3.13.16, seachange at 5d85ddc run through
`uv run --project <seachange> --no-sync`, each database in a fresh temp
folder; 100 generations x 5 runs, median ms per generation. Four other
sessions were busy, so spreads are wide.

One generation: 150 parents each make one child (copy a small genome of 5
nodes and 10 links, nudge the weights), children get a random fitness, the
worst 150 retire (`alive = False`). `reproduce` creates `Individual()`, sets
`.genotype` and `.fitness`, appends; `retire` sets `alive = False` on
`p.alive.sort()[150:]`. Each run checks that the table holds 150 x 101 rows
with 150 alive.

List genomes (dict of lists, JSON codec):

| Variant | ms/gen |
| --- | --- |
| native Python loop, in memory | 0.67 to 0.72 |
| seachange operations alone, no database (building SQLModel Individuals) | 6.8 |
| seachange today, `EA.step` | 33.5 (an earlier quieter run: 24.5) |
| + keep the population in memory, no `fetch_population()` per step | 28.2 |
| + one raw sqlite3 batched write per generation, WAL + `synchronous=NORMAL` | 20.8 |
| + write only what changed, set id and times without ORM tracking | 18.5 |
| + that write on a background writer thread | 13.5 |

Plain-Python `Individual` (same interface, not SQLModel), seachange's real
schema from `setup_database` (indexes included), writer thread:

| Variant | ms/gen |
| --- | --- |
| plain Individual, operations only | 0.74 |
| + batched writes on the thread | 3.3 |
| + `time_of_death` written only at death | 2.6 |
| + compact binary genome codec instead of JSON | 1.65 |
| same, without the thread | 2.8 |
| pydantic `BaseModel` Individual (mutable, no `validate_assignment`) | 2.1 |

Array genomes on both sides (numpy 15x5 float64, encoded with `tobytes`):

| Variant | ms/gen | 5 runs |
| --- | --- | --- |
| native | 0.27 | 0.26 to 0.36 |
| plain Individual, operations only | 0.33 | 0.33 to 0.39 |
| plain Individual, all changes, writer thread | 1.16 | 0.40 to 1.48 |
| pydantic Individual, same | 2.07 | 1.38 to 3.49 |

The best runs sit about 0.1 to 0.3 ms above native; the spread is the GIL
hand-off between the two threads plus machine load. Per-genome encoding:
`json.dumps` 6.9 us, `np.array` from lists plus `tobytes` 4.5 us, `tobytes`
on an existing array 0.06 us.

## Where today's time goes

cProfile of `EA.step`: SQLModel `__setattr__` and SQLAlchemy attribute
instrumentation on every field write; pydantic `validate_json` decoding every
alive genotype in `fetch_population()` each step; one INSERT or UPDATE per
row through the ORM session; every alive row's `time_of_death` rewritten each
generation in `_commit()`. The disk sync itself is under 1 ms per generation.

## The four changes

Prototyped by subclassing `EA` in a scratch script, not in seachange.

1. `Individual` stops being a SQLModel table row: a plain record with the
    same interface (`genotype`, `fitness`, `tags`, `alive`, `id`, birth and
    death), with the `individual` table written through SQLAlchemy Core or
    sqlite3 `executemany`. Building 150 ORM Individuals alone costs 6.8 ms
    against 0.33 ms plain. The user's standards want pydantic for records
    unless a profile shows a hot path; the numbers above (pydantic about 0.4
    to 1 ms per generation more than a plain class) are that profile, and the
    choice is the user's.
2. The EA keeps the living population in memory between steps (the database
    is a log during the run, read back only by `Archive` and restart),
    assigns ids itself (next id = max id + 1, one writer), and writes each
    generation in one batch: one `executemany` INSERT for new individuals and
    one `executemany` UPDATE for those that died, in WAL mode with
    `synchronous=NORMAL`, on a writer thread fed by a queue and joined on
    `close()`. Survivors' genotypes and tags were not re-encoded: today's
    `_commit()` does not save an in-place change to them either (the columns
    are not mutation-tracked), so stored data should not change; confirm
    with the tests.
3. `time_of_death` is set when an individual dies instead of rewritten on
    every living row each generation. This changes what the column holds for
    living individuals during a run, so `Archive`, `keep_genotypes` and
    `_keep_ranked`, and `EA.restart` need checking. An alternative is one
    run-level "current generation" value that stands in for alive rows.
4. Binary genomes: a codec that stores arrays as raw bytes (registered with
    `register_codec`) is nearly free. multineat's genomes will be arrays or
    Rust structs, so this part is mostly multineat's. Encoding must happen on
    the main thread unless genotypes are immutable, because an operation
    could change one in place after the commit.

## Open risks, not checked

- seachange's 291 tests, `Archive`, `EA.restart` (ids, copied history).
- `keep_genotypes` ranking needs ids, which change 2 now assigns before the
    write.
- `check_rows` validation on load.
- WAL's `-wal` and `-shm` side files; the network-filesystem warning in
    `docs/limits.md` still applies. A power cut can lose the last generation
    or two but does not corrupt the file.
- The order of `Population` after a step (in-memory list order against the
    database's rowid order).
- The timings are from the Mac under load: re-measure on the Lenovo, ideally
    with a small-genome case added to `tools/bench_genotypes.py`.
