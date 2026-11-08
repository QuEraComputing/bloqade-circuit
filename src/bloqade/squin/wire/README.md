# Squin wires

A wire names a qubit at one point in execution.
Each operation consumes its input wires and produces their next values.
The conversion passes preserve the source kernel and validate the result.
The `state`, `gate`, and `noise` modules define separate dialects.
`group.kernel` combines them with the source dialects.

Use `@squin.kernel(wirevalidation=True)` to validate a wire copy during decoration and keep the ordinary kernel.
The flag defaults to `False`.

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
- Allocation sizes must be nonnegative. The caller must satisfy this condition for runtime sizes.
- Runtime indices must satisfy `0 <= index < length`. Validation requires proof that simultaneous borrows use distinct elements.
- Conversion supports indexed loops, branches, broadcasts and static calls. It rejects recursion, closures and direct iteration over qubit registers.
- Jeff rejects noise operations and some classical operations. Runtime measurement arrays cannot return from Jeff to squin.

## Optional passes

[`UnpackRegisters`](../passes/wire_unpack.py) expands constant-size registers where their uses permit it.
[`merge_native_rotations`](../passes/wire_rotations.py) merges runs of native rotations in a copy of a source kernel.
Both require an explicit call.

## Direct Python lowering

Import `wire_kernel` from `bloqade.squin.wire.lowering` and apply it as a decorator.
It uses Kirin's Python lowering interface and returns a validated wire method.
It supports Squin gates, native gates, noise, measurement, reset, aliases, slices, branches, loops and static helper calls.
Loops can iterate over registers directly.
Each operation updates the current wire value of its qubits.
Branches, loops and helper calls carry those values through their inputs and results.
Helpers retain their Python source and use explicit parameters for qubits.
Functions use one final return and return classical values.
The frontend rejects recursion, closures, changing quantum locations across branches, and growing quantum lists in loops.
It requires proof that simultaneous borrows use distinct qubits.
Use `WireToSquin().emit(method)` to run the result with the existing simulator.
See [the Bell-pair example](../../../../examples/wire/07_direct_lowering.py).

## Tests

```sh
uv run --locked pytest -q test/squin/wire test/jeff test/analysis
```
