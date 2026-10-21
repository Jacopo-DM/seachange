# Design

## Specs

None yet.

## Decisions

- 2026-10-21: copy, not move. seachange starts as a copy of ARIEL's `ariel.ec` engine; ARIEL keeps its own and does not depend on seachange. Chosen by the user: nothing in ARIEL breaks. The cost is that the two copies drift.
- 2026-10-21: scope is the engine (`EA`, `EAOperation`, `Individual`, `Population`, `Archive`, `Crossover`, settings, database) plus `generators/` and `optimizers/`, everything in `ariel.ec` that imports no robot code. ARIEL's genotypes (tree, CPPN, NDE) build robot bodies and stay there.
- 2026-10-21: the name comes from Ariel's song in The Tempest ("doth suffer a sea-change / Into something rich and strange"), close to what mutation does to a genotype, and it contains "ea". Free on PyPI on that date.
- Storage: every individual is a row in SQLite through sqlmodel and sqlalchemy, so a run can restart from any recorded generation. Settings come from pydantic-settings. Reason as in ARIEL, not recorded there.

## Rejected approaches

- Making ARIEL depend on seachange (one copy of the engine). Rejected by the user for now in favour of leaving ARIEL untouched.

## Results

None yet.

## Gotchas

- The dependency versions are newer than ARIEL's lock (numpy 2.5.4, sqlalchemy 2.1.6, sqlmodel 0.0.48 against 2.3.3, 2.0.43, 0.0.27). numpy 2.5's stubs are what exposed the `size=None` bug in PLAN.md Known problems.
