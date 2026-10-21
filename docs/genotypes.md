# Genotypes and how they are stored

A genotype is what an individual inherits and mutates: the bits of a one-max string, the weights of a neural network. seachange stores every genotype in the run's SQLite database and gives it back as the same kind of value it was given.

Out of the box a genotype can be:

- a list or dict of strings, numbers and booleans, stored as JSON text;
- a numpy array of any dtype except Python objects, stored as raw bytes, with its dtype and shape.

Anything else needs a codec of its own; the last section, Your own genotype type, shows one.

## A run with numpy genotypes

This example evolves 100 float32 weights toward a target vector. It is `examples/a3_numpy_genotypes.py`, and the test suite runs it.

```{literalinclude} ../examples/a3_numpy_genotypes.py
:language: python
```

It prints how far the best weights are from the target before and after, and the type of the genotype read back from the file:

```text
error 1.274 -> 0.804
stored genotype: float32 (100,)
```

## A genotype is set once

Mutation makes a new genotype for the child; it never changes the parent's. seachange holds you to that for numpy arrays: assigning an array to `individual.genotype` makes it read-only. Write the child as a new array:

```python
child.genotype = parent.genotype + noise
```

Changing an array in place raises `ValueError: assignment destination is read-only`. That catches a child that shares its parent's array, where `child.genotype += noise` would otherwise change the parent's weights too. Making the array read-only also affects your own variable that points to it; copy it first (`weights.copy()`) if you still need to change it.

## Telling the type checker what a genotype is

`Individual`, `Population`, `EA` and `Archive` take the genotype type as a parameter. Annotate each operation once and mypy (and ty) know the type everywhere in the run:

```python
type Weights = NDArray[np.float32]


def mutate(population: Population[Weights]) -> Population[Weights]:
    for parent in population:
        child = Individual[Weights]()
        child.genotype = parent.genotype + noise  # a float32 array
        ...
```

`EA(first, [EAOperation(mutate), ...])` then is an `EA[Weights]`, and so is `EA.restart(path, [EAOperation(mutate), ...])`. An `Archive` cannot see your operations, so name the type there: `Archive[Weights](path)`. Without a parameter, a genotype is `seachange.Genotype`: a JSON list or dict, or a numpy array.

List the operations inside the `EA(...)` call, as above. Built separately, `ops = [EAOperation(a), EAOperation(b, 0.5)]` fails mypy when the operations bind different arguments; annotate it as `ops: list[Operation[Weights]]` if you need the list on its own (`from seachange.ea_operation import Operation`).

## How a genotype is stored

When seachange writes an individual, it asks each codec in turn whether it handles the genotype: your registered codecs first, newest first, then `NumpyCodec`, then `JsonCodec`. The first that does turns it into bytes. The database stores the codec's name, a zero byte, and those bytes. One cycle for an array of two float32 weights:

1. `individual.genotype = np.array([1.5, 2.5], dtype=np.float32)` keeps the array in memory.
2. Saving the individual stores `numpy`, a zero byte, and a 136-byte `.npy` file: 128 bytes of header with the dtype and shape, then 8 bytes of weights.
3. Reading the row back splits off `numpy`, hands the rest to `NumpyCodec`, and returns a read-only float32 array of shape `(2,)`.

Because the bytes after the name are a complete `.npy` file, any numpy can read a stored genotype without seachange: `np.load(io.BytesIO(blob[6:]))`.

Raw bytes are much faster than JSON for large arrays. With 100 individuals of 10,000 float32 weights, replacing every parent each generation (`tools/bench_genotypes.py`, median of 3 runs of 20 generations):

| Genotype | Storage time per generation | Database size |
|---|---|---|
| list of floats (JSON) | 0.506 s | 435 MB |
| float32 array | 0.015 s | 86 MB |

Databases written before codecs, by earlier seachange or by ARIEL's `ariel.ec`, hold JSON text; they open in `Archive` and `EA.restart` unchanged. A stored genotype no codec can read is reported with its row: `Database row 2 is not a valid Individual: its genotype cannot be decoded: ...`.

## Your own genotype type

A codec is a class with a `name`, and `handles`, `encode` and `decode` methods (the `seachange.GenotypeCodec` protocol). Register it once with `register_codec`, in every program that writes or reads the run's files: a program that reads the file without it gets `no codec named 'torch'`.

For example, PyTorch tensors stored through `NumpyCodec`, so the bytes stay a readable `.npy` file. seachange does not depend on PyTorch and does not run this example:

```python
import torch

from seachange import NumpyCodec, register_codec


class TorchCodec:
    """Stores CPU tensors as .npy bytes; a tensor comes back as a tensor."""

    name = "torch"

    @staticmethod
    def handles(genotype: object) -> bool:
        return isinstance(genotype, torch.Tensor)

    def encode(self, genotype: object) -> bytes:
        if not isinstance(genotype, torch.Tensor):
            msg = f"TorchCodec stores tensors, not {type(genotype)}"
            raise TypeError(msg)
        return NumpyCodec().encode(genotype.detach().cpu().numpy())

    @staticmethod
    def decode(data: bytes) -> torch.Tensor:
        # NumpyCodec gives a read-only array; torch wants a writable one
        return torch.from_numpy(NumpyCodec.decode(data).copy())


register_codec(TorchCodec())
```

A tensor comes back on the CPU, without its gradient. numpy has no `bfloat16`, so convert such a tensor to `float32` first. seachange makes only numpy arrays read-only, not tensors, so treat a tensor genotype as set once yourself.

A codec name must be unique, non-empty, and free of zero bytes; registering a second codec with the same name raises `ValueError`.
