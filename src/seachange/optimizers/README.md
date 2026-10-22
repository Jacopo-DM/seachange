# seachange.optimizers

Pre-built optimizers. Today one: `RevDE` in `revde.py`, the reversible differential-evolution mutation, which turns three float64 parent vectors of the same shape into three children with one fixed 3x3 matrix.

Assumes: genotypes are numpy float64 arrays. `RevDE` draws no random numbers; the caller picks the three parents.

Must never depend on: any other seachange module. An optimizer is plain numpy, so it can be used with or without the engine.

The public interface is in `CODEMAP.md` at the repo root.
