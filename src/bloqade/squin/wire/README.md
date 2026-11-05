# Squin wires

A wire names a qubit at one point in execution.
Each operation consumes its input wires and produces their next values.
The conversion passes preserve the source kernel and validate the result.
The `state`, `gate`, and `noise` modules define separate dialects.
`group.kernel` combines them with the source dialects.

## Conversion

```python
from bloqade import squin
from bloqade.jeff import JeffToWire, WireToJeff
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin


@squin.kernel
def source():
    qs = squin.qalloc(2)
    squin.x(qs[1])
    return squin.broadcast.measure(qs)


wired = SquinToWire().emit(source)
restored = WireToSquin().emit(wired)
jeff = WireToJeff().emit(wired)
round_trip = WireToSquin().emit(JeffToWire().emit(jeff))
```

## Requirements

- Source functions return classical values and pass qubits through parameters.
- Runtime indices must satisfy `0 <= index < length`. Validation requires proof that simultaneous borrows use distinct elements.
- Conversion supports indexed loops, branches, broadcasts and static calls. It rejects recursion, closures and direct iteration over qubit registers.
- Jeff rejects noise operations and some classical operations. Runtime measurement arrays cannot return from Jeff to squin.

## Optional passes

[`UnpackRegisters`](../passes/wire_unpack.py) expands constant-size registers where their uses permit it.
[`merge_native_rotations`](../passes/wire_rotations.py) merges runs of native rotations in a copy of a source kernel.
Both require an explicit call.

## Tests

```sh
uv run --locked pytest -q test/squin/wire test/jeff test/analysis
```
