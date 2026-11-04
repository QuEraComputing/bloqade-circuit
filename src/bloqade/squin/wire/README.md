# Squin wire conversion

`SquinToWire` converts qubit references into explicit sequences of wire values.
A reference names a logical qubit or a list of logical qubits.
A wire names one version of a logical qubit during execution.
Each operation consumes its input wire and produces the next version.

```python
from bloqade.squin.passes.squin_to_wire import SquinToWire
from bloqade.squin.passes.wire_to_squin import WireToSquin

wired = SquinToWire().emit(source)
reconstructed = WireToSquin().emit(wired)
```

## Compilation stages

| Stage | Kirin mechanism | Result |
| --- | --- | --- |
| Check source | `ValidationSuite`, `Walk` | Check source structure and types, then collect static callees. |
| Emit | `EmitABC`, `EmitFrame`, `interp.MethodTable`, `ssacfg.Concrete` | Build a fresh wire method from the source method. |
| Clean up | `Fixpoint`, `Walk`, `DeadCodeElimination` | Delete unused classical expressions, including source slice objects. |
| Infer types | `TypeInfer` | Resolve types of emitted classical operations and specialized library operations. |
| Check output | `ConversionTarget`, wire validation passes | Require complete wire conversion and valid ownership. |

`SquinToWire.emit()` reads the source method and constructs a separate output method.
It converts user callees first and supplies their validated wire methods to the caller's emitter.
Each callee must pass the same conversion target and validation.

`reachable` in `squin/rewrite/wire/driver.py` lists the user callees before their callers and rejects recursion.
Before emission, a `ValidationSuite` runs `StructureValidation` for source structure and types.
The emitter rejects each source form that it cannot convert where it meets the form.
It requires static calls, and regions only of functions, loops and branches, each with one block.
Emission visits each source statement once per method conversion.
Kirin's region interpreter controls statement order and fills the frame after each operation.
Standard library wrappers execute through nested emission frames with shared output and wire state.
Each library call interprets its wrapper body once.
The frame's `site` names the user call, and every operation of the wrapper takes that call's source location.
Validation, type inference and cleanup perform their own traversals.
Wire validation interprets each callee once for each list of abstract arguments.
The full pipeline has no established linear-time bound.

Unsupported source forms stop conversion at their first failed condition.
The converter preserves the source and propagates the error without retrying through inlining.

## Emission state

`WireFrame` extends Kirin's `EmitFrame` with an output block and allocation state.
Its inherited entries map source SSA values to their emitted meanings.
An SSA value names one compiler value with one definition.

| State | Meaning |
| --- | --- |
| `entries` | Map each source value to an emitted classical value, quantum location or container of values. |
| `latest` | Map each allocation root to its latest wire or register value. |
| `local_roots` | Record allocations that this region must free unless the function returns them. |
| `output` | Hold the emitted block and its arguments. |
| `site` | Name the user call that runs a library wrapper. It is None in user code. |

A `Location` is one of six forms, and each form has a `root`.
The root is the emitted allocation result, a call result or a function parameter.

| Form | Meaning | Example |
| --- | --- | --- |
| `Qubit(root)` | A standalone qubit. | `q` |
| `Element(root, index)` | One qubit of a register. | `qs[i]` |
| `Register(root, length)` | A whole flat register. | `qs` |
| `View(root, span)` | A slice of the qubits of a register. | `qs[1:3]`, `grid[1]` of 2 dimensions |
| `Grid(root, length, row_shape)` | A whole nested register. | `grid` |
| `Rows(root, span, row_shape)` | A row whose items are rows. | `cube[1]` of 3 dimensions |

`select` and `select_slice` in `values.py` derive the location of an item or a slice.
A nested register has one flat root register that holds its rows in order.
The frame keeps locations stable while `latest` changes after each quantum operation.
An alias copies its operand's frame entry.
An index selects from that entry using the index expression of the source integer operand.
A source list holds its element locations in a tuple.

Emission uses these frame entries for all source reference resolution.
Each reference operation reads the meanings of its operands from that frame.
`IndexAnalysis` in `bloqade.analysis.indices` is a Kirin forward analysis of integer arithmetic.
`Indices` runs it once on each function, on the first lookup of a value of that function.
It represents expressions such as `i + 1`.
The emitter analyzes source integers, so the symbols of an index are source values.
A loop symbol carries the constant range of its source loop.
`emit_index` maps each symbol to its emitted value through the frame entries.
An integer without that form, such as `i * i`, becomes one opaque symbol.
Two uses of one opaque symbol name the same element.

A wire register index lies between 0 and the register length minus 1, as in Jeff.
The converter counts a negative constant index from the end and checks constant bounds.
A runtime index must be a valid wire index, which is a precondition of the source program.
The converter emits a runtime index unchanged and checks neither its sign nor its upper bound.
So `qs[k]` with a runtime `k` of -1 is invalid input, although Python would read it as the last element.
Two operands of one operation must name different qubits, which is also a precondition.
The pipeline rejects only operands that provably name the same qubit, such as `cx(qs[0], qs[0])`.
So `cx(qs[j], qs[k])` converts, and a runtime `j` equal to `k` is invalid input.
Jeff has no assertion statement, so the converter cannot emit a runtime check that Jeff keeps.
Runtime register lengths come from wire `Length` operations.
Nested register parameters use one flat register with their rows in source order.

The operation tables live in `squin.emit.wire`:

| File | Responsibility |
| --- | --- |
| `base.py` | Define the emitter, the frame and the operations on latest wires, and copy classical operations. |
| `functions.py` | Emit function boundaries, library wrappers and calls. |
| `references.py` | Resolve qubit references in allocations, aliases, lists, tuples, additions, lengths and indexing. |
| `control.py` | Convert loop and branch regions through Kirin's region interpreter. |
| `gates.py` | Emit scalar operations on qubits and register operations on whole registers or slices. |
| `values.py` | Define the location forms and select elements, slices and rows. |

## Gates and allocation lifetimes

Each quantum operation consumes its input wire and produces the next version of that qubit.
`Threads` declares which output continues each input.
`Swap` exchanges quantum states while each output continues its corresponding input qubit.
Measurement produces a classical result and continues the measured qubit.

The wire dialect has 4 scalar operations: `Gate`, `Noise`, `Measure` and `Reset`.
Each one acts on one group of qubits.
A `Gate` or a `Noise` statement holds its kind as an attribute, such as `GateKind.CX`.
A `Gate` or a `Noise` statement acts on one or more groups of wires at the same time, and the groups share no qubit.
For example, `Gate(kind=cx, wires=(c0, t0, c1, t1))` applies CX to `(c0, t0)` and to `(c1, t1)` in one parallel step.
The emitter gives a broadcast over separate qubits, such as `rx(a, [q0, q2])`, one such statement, so the round trip keeps the broadcast.
If the groups of a broadcast can share a qubit, the emitter emits one statement per group in source order.
`kinds.py` gives each kind its arity, which is its number of wires and parameters.
The `HasArity` trait checks the arity when Kirin verifies the IR.
`TRUNCATES` in `kinds.py` names the kinds whose register form stops at the shortest register.
The `Threads` trait is the one record of which result continues which wire.
The wire dialect imports nothing from squin.

Each scalar operation has a register form: `RegisterGate`, `RegisterNoise`, `RegisterMeasure` and `RegisterReset`.
A register form takes one register for each qubit list and applies the scalar form at each position.
Its classical results stay lists, so `RegisterMeasure` returns one list of measurement results.

`sources.py` maps each squin statement on qubits to its kind and names its qubit-list fields, classical fields and results.
Only the conversions read this table.
When the module loads, it checks each entry against Kirin's statement schema.
`WireToSquin` reads the table backwards to rebuild the source operation.
It gives a scalar operation singleton qubit lists, and a register form the same registers.

A scalar gate handler gets each operand location from the frame.
For a standalone qubit, it consumes the latest wire and records the output wire.
For a register element, it emits `Borrow`, the gate and `Release`.
`Borrow` produces the selected wire and a register with that element temporarily unavailable.
`Release` restores the updated wire to that register element.

```text
r0 = AllocRegister(2)
r1, q0 = Borrow(r0, 0)
q1 = Gate(kind=x, wires=(q0,))
r2 = Release(r1, 0, q1)
FreeRegister(r2)
```

Allocation handlers record their roots in the current frame.
At region exit, `free_local_allocations` frees each local allocation that the region still holds.

A broadcast over whole registers or step-1 slices emits one register operation, for any length.
A slice operand becomes a `TakeSlice` before the operation and a `PutSlice` after it.
A broadcast over a list of separate qubits, such as `[a, qs[2]]`, emits one scalar operation on all operand groups.
Operations with shortest-list semantics stop at the shortest register.
For every other operation, equal operand lengths are a precondition of the source program.
The converter rejects operands whose known lengths differ.

## Loops and branches

The loop handler reads every available outer allocation from `latest`.
It creates output parameters for classical loop state and those allocations.
It builds the output loop after its body, and `scf.For` reads its result types from the final yield.
The body's frame starts with those parameters as its latest wire values.
Kirin interprets the source body once.
The handler then emits a yield with the final classical values and latest wires.
The loop results replace the enclosing frame's latest values.
For zero iterations, the loop returns its initial values.

```text
r_after = For(indices, initial=r0):
    r_iter = iteration_argument
    r_hole, q0 = Borrow(r_iter, i)
    q1 = Gate(kind=x, wires=(q0,))
    r_next = Release(r_hole, i, q1)
    Yield(r_next)
```

Each branch starts with a separate copy of the incoming `latest` map.
The handler interprets both source regions once.
Both output regions yield the incoming allocations in the same order.
The conditional's results become the enclosing frame's latest values.
Every register must contain all its borrowed elements at these boundaries.

Source reference variables must retain their allocation identity across a loop.
Both branches must return the same location for a quantum reference result.
If a reference changes its allocation or element across a boundary, conversion fails.
A program can express changing element selections with a classical integer index.
Each structured region must contain one block with its expected terminator.

## Calls and returns

Every quantum parameter borrows its input allocation.
The function returns the latest value of each borrowed parameter in declaration order.
Ordinary results precede this borrowed-parameter suffix.
A function cannot return qubits, so every ordinary result is classical.
A function can allocate qubits and free them before it returns.
A caller allocates the qubits that a callee needs and passes them in.
A register parameter keeps the number of qubits that its source type gives, such as `Register[3]`.
Kirin type inference gives every other register its static length when it can, as the Jeff section describes.

For a source call `answer = f(q, n)`, the wire convention is:

```text
answer, q1 = call f_wire(q0, n)
```

`Layout` reads this convention from the source signature.
It gives the borrowed parameter positions, the ordinary result count and the tuple packing of the source return.
The caller reads the type of each wire result from the callee's inferred signature.

The caller consumes its latest inputs and restores them from the borrowed-parameter suffix.
Calls on register elements use `Borrow` and `Release` around the call.
The helper below borrows `q`, and its loop carries the wire of `q`:

```python
@squin.kernel
def kick(q: Qubit, k: int) -> int:
    for _ in range(k):
        squin.x(q)
    return k + 1


@squin.kernel
def main():
    qs = squin.qalloc(2)
    return kick(qs[1], 3)
```

```text
func kick(q: Wire, k: int) -> tuple[int, Wire]:
    q_end = For(range(0, k), initial=q):
        q_iter = iteration_argument
        q_next = X(q_iter)
        Yield(q_next)
    Return(tuple(k + 1, q_end))

func main() -> int:
    r0 = AllocRegister(2)
    r1, q0 = Borrow(r0, 1)
    result = call kick(q0, 3)
    total = result[0]
    q1 = result[1]
    r2 = Release(r1, 1, q1)
    FreeRegister(r2)
    Return(total)
```

Quantum call operands must name separate scalar qubits or whole registers.
Calls with register slices or quantum containers fail.
A register argument must provably have the shape that its parameter type declares.
A qubit parameter takes one qubit, and a register parameter takes a whole register.
The emitter reports unsupported argument layouts, argument shapes and returned qubits as `WireConversionError`.
An operation that uses one qubit or register twice fails with a plain `WireConversionError`.
Callee validation failures propagate directly to the caller.
Each conversion error retains its operation, source location and failed condition.

The conversion driver rejects recursive calls.
A failed conversion leaves the source method and its callees unchanged.
Repeated public conversions clear the cache of converted methods.

## Validation contracts

| Check | Required property |
| --- | --- |
| `StructureValidation` | Kirin verifies method structure and types. |
| `LinearityValidation` | Each wire, register and quantum tuple field has one use on each execution path. |
| `BorrowValidation` | Releases match borrowed indices and registers restore every element before crossing a boundary. |
| `PositionValidation` | Releases, loop yields, branches and call return suffixes continue the correct qubits in order. |

Linearity and borrow validation use Kirin forward analyses with operation method tables.
The use of a value must sit in the region that defines it.
A branch may use an outer wire, once on each path, because `scf.IfElse` carries no block arguments.
A loop body must take every wire as a block argument, because the body runs more than once.
A register must hold no borrowed element when a statement frees, yields, returns or passes it.
`Take` and `TakeSlice` move elements out, and `DiscardRegister` accepts moved elements but no borrowed ones.
Borrow validation tracks outstanding register indices in its `Slots` lattice.
It rejects a borrow or a move only if it provably meets an outstanding slot.
Its `Moved` entries name elements that `Take` or `TakeSlice` moved out of a register.

Position validation uses Kirin's `Forward` analysis with operation method tables.
Its `Origin` lattice stores exact allocation identities and tuple fields in Kirin frames.
An unknown origin records insufficient information to prove continuity.
The analysis follows operation continuations and checks loop yields, branch results and borrowed return suffixes.
It checks each callee and gives every call's fresh outputs distinct identities.
Only functions imported from Jeff return fresh qubits, because source functions cannot return qubits.
`CachedCalls` reuses the result of a call with the same callee and abstract arguments.
Each analysis records its errors at callee nodes, so a reused result loses no error.

Quantum tuple fields require constant indices within their bounds.
Tuple construction, extraction, calls and region boundaries must preserve quantum field types.
Function parameters and region state carry separate wire or register values.
Function results can use a flat tuple of ordinary outputs followed by borrowed parameters.

## Statements of other dialects

A dialect outside squin, such as Gemini, can add its own statements to wire programs.
It owns 3 pieces, and bloqade-circuit needs no change for a new dialect:

1. A wire dialect with the linear form of each statement. A statement that continues wires carries a `Threads` trait, so the validators and passes follow its qubits.
2. A method table on the reference dialect under the key `emit.squin_wire`. It calls `EmitWire.qubits_of` to find the qubits of an operand, `EmitWire.operate` to emit a statement on their wires, and `EmitWire.new_qubit` to record a new wire as an allocation.
3. A `ReferenceForm` trait on each wire statement. `WireToSquin` calls its `rebuild` method to insert the reference statement.

The caller passes the wire dialect as `wire_dialects` to `SquinToWire` and `WireToSquin`.
If the dialect is missing from `wire_dialects`, `SquinToWire` names the option in its error.
If a wire statement threads wires but has no `ReferenceForm`, the linearity check names the trait.
`test/squin/wire/test_extension.py` shows a complete small dialect.
The squin, noise and native gate dialects use the same method tables under `emit.squin_wire`.

## Verification and limits

```sh
uv run --locked pytest -q test/squin/wire test/analysis test/jeff
```

The tests compare source execution with execution after conversion and reconstruction.
A separate dense-matrix interpreter executes wire operations directly in the tests.
Its unitary and noisy results must match independently constructed Cirq circuits.
Measurement tests enumerate outcomes and check their exact probabilities, including conditional gates.
Malformed-program tests exchange qubits and break ownership contracts to check validator rejection.

Complete conversion can reject a valid source program when it cannot resolve its reference expressions.
Public quantum parameters require distinct input qubits.
Recursion and arbitrary control-flow graphs exceed the current conversion contract.
Closures, list maps and direct iteration over qubit registers also exceed that contract.
Indexed loops, broadcasts and calls with whole-register or scalar-qubit arguments can convert directly.
The conversion tests have no expected-failure markers.
The pipeline emits wire operations and removes unused classical expressions.
It omits common-subexpression elimination, gate cancellation, angle merging and qubit reuse.
