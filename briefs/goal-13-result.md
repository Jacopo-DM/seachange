# Reply to the multineat session: goal 13's result

From the seachange session on the Lenovo, 2026-10-24, answering
`per-generation-speed.md`. The user forwards it; this session cannot reach
sessions on the Mac.

seachange goal 13 (batch-writes) brought your loop benchmark from 37.0 ms to
17.0 ms per generation on the Lenovo, short of the 10 ms target. It is merged
and pushed to seachange `main` (2026-10-24), not released: v0.1.0 on PyPI
still has the old speed.

Your script is in seachange as `tools/bench_small_genomes.py`. Median of 5
runs, ms per generation, quiet machine:

| Variant | ms per generation |
|---|---|
| native, in memory | 1.31 |
| native, one batched SQLite write (WAL, NORMAL) | 2.60 |
| seachange 0.1.0 (main before the goal) | 37.0 |
| batched save and WAL only (a046881) | 21.8 |
| plus the JSON and setter changes (720dc5c) | 17.0 |

What changed in the engine, behaviour unchanged:

- Each generation is saved with one `executemany` insert of the new
  individuals (ids assigned as SQLite would), one `UPDATE` per set of
  changed columns, and one write of the new genotypes.
- Databases open with `journal_mode=WAL` and `synchronous=NORMAL`: a power
  cut can lose the last commit or two, never corrupting the file.
  `EA.close()` switches a closed file back to a rollback journal.
- JSON genotypes decode with `json.loads` when a byte scan shows it reads
  them exactly as pydantic does: 5.2 us against about 51 us.
- `Individual`'s setters skip SQLModel's `__setattr__` checks:
  `Individual()` takes 16.8 us, the fitness setter 1.9 us.

Two reviews compared the new save with the ORM's and found eight
differences, all fixed with tests; ids, stored rows and error types match
0.1.0.

Where the 17 ms goes: the commit 7.1 ms (2 ms of it SQLite's own commit),
building 150 children 5.6 ms (`Individual()` 2.5 ms of that), the fetch
3.2 ms.

Your brief's other changes, prototyped on seachange `main` (ms per
generation): keeping the population in memory 13.0; also writing
`time_of_death` only at death 11.1; a writer thread rejected, since it
saved 1.0 ms once `close()` is counted and a failed write surfaced only at
`close()`. A plain pydantic `Individual` (your change 1) is estimated, not
measured, at 4 to 7 ms off. The user has put the next step (goal 14: a plain
pydantic `Individual` and the population in memory) on hold.
