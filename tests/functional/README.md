# Functional notebooks

Each notebook here shows one feature area of seachange working end to end: a tutorial to read top to bottom, a picture or table to judge by eye, and a smoke test that fails when a cell raises. They do not replace the unit tests and do not count toward coverage.

Run them from the repo root:

```bash
uv run --locked python tools/run_notebooks.py
```

Each notebook runs in a fresh kernel inside a temporary folder and prints one line: its name, `PASS`, `FAIL` or `SKIP`, and the seconds it took. Name files to run only those; `--save` writes the new outputs back, which is how the committed outputs are refreshed (`uv run --locked python tools/run_notebooks.py --save tests/functional/engine.ipynb`).

The pre-commit hook runs the notebooks in a commit, and the pre-push hook runs all of them, so a library change that breaks a notebook nobody edited stops the push. `git commit --no-verify` and `git push --no-verify` skip that check. A notebook that needs something the machine lacks (declared as `"requires"` in its metadata) shows `SKIP`, which is not a pass. None of the notebooks below needs a display, a GPU or a network.

## Coverage

One row per public module of `seachange`. Adding a module means adding a row; `tests/test_functional_notebooks.py` fails when one is missing.

| Module | What it does | Notebook |
|---|---|---|
| `ea` | runs the generations and saves each one | [engine.ipynb](engine.ipynb) |
| `ea_operation` | wraps a step function for the engine | [engine.ipynb](engine.ipynb) |
| `ea_settings` | run settings, read from `SEACHANGE_` variables | [engine.ipynb](engine.ipynb) |
| `ea_database` | creates the run's database file | [engine.ipynb](engine.ipynb) |
| `population` | a list of individuals with sorting and filters | [engine.ipynb](engine.ipynb) |
| `individual` | one individual: genotype, fitness, alive | [engine.ipynb](engine.ipynb) |
| `model` | the base class of the records | [engine.ipynb](engine.ipynb) |
| `archive` | queries a finished run | [archive.ipynb](archive.ipynb) |
| `codecs` | how genotypes are stored | [genotypes.ipynb](genotypes.ipynb) |
| `generators` | random genotypes and mutations | [generators.ipynb](generators.ipynb) |
| `crossover` | combining two parents into two children | none yet |
| `optimizers` | RevDE | none yet |
