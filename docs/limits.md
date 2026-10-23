# How far SQLite storage goes

seachange keeps a run in one SQLite file. This page gives the measured limits of that choice: how large one genotype can be, and what happens when many processes write to one file at once. Both were measured on 2026-10-23 on a Linux laptop (16 cores, Samsung NVMe disk, ext4) with Python 3.13 and SQLite 3.53.1, with nothing else running. The numbers depend on the disk; read them as orders of magnitude.

## How seachange writes

A run has one writer: the `EA` that owns the database. It stores the starting population once, then commits once per generation, at the end of each `step()`. Everything a generation changed goes to the file in that one commit. The database uses SQLite's defaults: a rollback journal, a full disk sync on every commit, and a 5 second wait for a lock before a write gives up with `database is locked`.

This shapes how to run things in parallel:

- **Evaluating in parallel** works with one writer. An evaluation operation can hand its individuals to worker processes and set each fitness from what they return; the `EA` then stores the population as usual. The workers never touch the database.
- **Several runs at once** each need their own file: give each `EA` its own `db_file_path`.
- **Network filesystems** (NFS and similar) are a poor place for a running database: SQLite's own documentation warns that their file locking is unreliable. Write the run to a local disk and copy the file afterwards.

## How large a genotype can be

SQLite refuses any single value over 1,000,000,000 bytes. A float32 genotype is therefore limited to just under 250 million weights; the stored value also holds the codec name and a 128-byte `.npy` header. Below that limit, speed does not fall with size. Each case wrote its genotypes in one commit and read them back, and every array came back equal:

| Genotype | Count | Write through seachange | Read through seachange | Write, plain `sqlite3` | Read, plain `sqlite3` |
|---|---|---|---|---|---|
| 1 million weights (4 MB) | 50 | 363 MB/s | 619 MB/s | 313 MB/s | 1,129 MB/s |
| 10 million weights (40 MB) | 10 | 174 MB/s | 343 MB/s | 223 MB/s | 524 MB/s |
| 100 million weights (400 MB) | 3 | 190 MB/s | 341 MB/s | 283 MB/s | 529 MB/s |
| 240 million weights (960 MB) | 1 | 195 MB/s | 341 MB/s | 231 MB/s | 536 MB/s |
| 260 million weights (1.04 GB) | 1 | fails | | fails | |

The 1.04 GB genotype fails when it is saved, with `sqlite3.DataError: string or blob too big` (wrapped in SQLAlchemy's `DataError` through seachange). SQLite reads and writes a value whole, so a genotype also needs several times its size in memory: the 960 MB case used 4.8 GB at its peak.

## Many writers on one file

seachange does not write from several processes, but a parallel design that does will meet these limits. In this test, each process wrote rows to one shared file as fast as it could, one commit per row, with the 5 second lock wait seachange uses. A failed write is one that waited longer than that.

| Rows of 40 KB | 8 processes | 128 processes | 512 processes |
|---|---|---|---|
| SQLite defaults (rollback journal, full sync) | 117 writes/s, 0.7% failed | 115 writes/s, 9.7% failed | 110 writes/s, 32% failed |
| WAL journal, full sync | 222 writes/s, 0.07% failed | 205 writes/s, 3.4% failed | 210 writes/s, 18% failed |
| WAL journal, `synchronous=NORMAL` | 7,678 writes/s, none failed | 1,967 writes/s, 0.01% failed | 2,137 writes/s, none failed |

With rows of 4 MB in WAL mode with full sync, the file took 250 to 295 MB/s at every process count, and the share of failed writes rose from none at 8 processes to 36% at 512.

Three things follow from the numbers:

- **Commits are the limit, not data.** With a full sync, every commit waits for the disk, which held this one to about 200 commits a second however many processes wrote. `synchronous=NORMAL` in WAL mode skips that wait on each commit and raised the rate about 35 times. The price is that a power cut can lose the last commits; the file itself stays intact.
- **Failures come from unfair waiting.** SQLite does not queue writers: a waiting writer sleeps and tries again, so an unlucky one can be passed over for longer than the lock wait while others get in. That is why a few writes failed even with 8 processes.
- **Larger commits did not help under contention.** Writing 10 rows per commit, in WAL mode with `synchronous=NORMAL`, reached 10,180 rows a second with 8 processes, but with 128 and 512 each commit held the lock longer and 5 to 6% of writes failed.

For scale: an evaluation that takes one second, such as a robot simulation, would need more than 2,000 workers each writing its own result before the WAL and `synchronous=NORMAL` rate is reached.
