# Squin

This crate defines squin as a Kirin Rust language with linear wires and registers.

A `Wire` names one qubit at one point in the program.
Each statement consumes its input wires and returns their next values.
A `Register[N]` holds `N` qubits.
`borrow` lends one element to a wire and returns a `Slot` token, and `release` consumes the token to put the wire back.
`replace` is the statement that moves a qubit to a new register position.

```text
%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
%a1 = h %a0 -> Wire;
%r2 = release %r1, %s, %a1 -> Register[2];
```

## Use

The `squin` tool reads a program in the Kirin text format.

```sh
nix develop -c cargo run -p squin -- check crates/squin/examples/bell.kirin
nix develop -c cargo run -p squin -- opt crates/squin/examples/bell.kirin
nix develop -c cargo run -p squin -- stim crates/squin/examples/bell.kirin
```

`Kernel` gives the same steps to Rust code.

```rust
let mut kernel = squin::Kernel::parse(text)?;
kernel.optimize()?;
let circuit = kernel.to_stim("main")?;
```

## Modules

| Module | Responsibility | Start here |
| --- | --- | --- |
| `kernel` | `Kernel` connects parsing, verification, optimization, and execution. | `src/kernel.rs` |
| `dialect` | `Squin` combines quantum statements, types, and adapters for Kirin statements. | `src/dialect/mod.rs` |
| `compiler` | The verifier checks programs, and rewrite passes transform them. | `src/compiler/mod.rs` |
| `runtime` | `Machine` evaluates programs and sends quantum operations to a `Backend`. | `src/runtime/mod.rs` |

The source directories follow these responsibilities:

```text
src/
  kernel.rs
  dialect/
    mod.rs
    traits.rs
    semantics/
    types/
    gate/
    state/
    bits.rs
    adapters/
  compiler/
    verify/
    rewrite/
    passes.rs
  runtime/
    machine.rs
    stim.rs
```

Each layer imports only the layers above it in this list: `dialect`, then `compiler`, then `runtime`, then `kernel`.
A statement checks its types through the `TypeCheck` trait and runs through the `Evaluator` trait.
`dialect::traits` defines both traits, and the verifier and the `Machine` implement them.
So the dialect never imports the compiler or the runtime.
`dialect::semantics` defines the run-time `Value`, `Failure`, `Backend` and `Operation`, and `runtime` re-exports them.

`dialect::types` defines `SquinType`, the type lattice, and `Scalar`, the constant value type.
A type lattice describes which types contain other types.
Each quantum statement is one struct with its rule implementations beside its definition.
The gate macros generate the repeated fields and rules of a gate family.
`dialect::adapters` implements the Squin rules for Kirin constants, arithmetic, comparisons, functions, branches, and loops.

`compiler::verify` returns a `Verified` value for a program that passes its checks.
`compiler::rewrite` defines rewrite rules and the driver that applies them.
`compiler::passes` runs rewrites over one pipeline stage.
`cancel_gates` removes adjacent inverse gates, and `merge_rotations` combines adjacent rotations about the same axis.
`simplify` repeats these rules until they stop changing the program.
`fold_phases` combines phase gates that act on the same parity, a sum of qubit values modulo two.

`runtime::Machine` requires a `Verified` program.
It computes classical values and register indices.
`Machine::call` checks the argument types, the register shapes, and that no two arguments own the same qubit.
The verifier proves these facts for every value inside the program, so the machine checks them once, at the function entry.
The backend carries out quantum operations.
`runtime::stim` writes those operations as a Stim circuit.

`Kernel::run` selects the most specific function specialization that accepts the argument types.
A specialization supplies a function body for a parameter type signature.
If no specialization matches, or equally specific candidates remain, execution returns an error.

The evaluator is squin code. The Kirin concrete interpreter at the pinned commit has no place for the state of a backend, so an `Interpretable` rule cannot reach it.

## Reading order

1. Read `src/kernel.rs` to follow a program through parsing, verification, optimization, and execution.
2. Read `src/dialect/mod.rs` to see the statements that the `Squin` enum accepts.
3. Read `src/dialect/gate/mod.rs` with `src/dialect/traits.rs` to follow a gate and its rules.
4. Read `src/compiler/rewrite/cancel.rs` to see how a rewrite reconnects wires after removing gates.
5. Read `src/runtime/machine.rs` with `src/runtime/stim.rs` to follow execution through circuit emission.

## Statement traits

A statement states its own rules in four traits, next to its definition.

`dialect::traits` defines `Threads`, `Typed`, `Structure` and `Execute`.

- `Threads` tells which result continues which linear operand.
- `Typed` checks the types of the operands and the results.
- `Structure` tells the verifier how the statement nests blocks, lends a register element, or computes an index.
- `Execute` carries out the statement on a `Machine`.

The `delegate!` macro forwards the four traits from an enum to the statement of each variant. A new statement needs its struct, its four impls and one variant.

## Verifier rules

`verify` reports each `Violation` with its `Rule`.

`Scope` requires every operand to have a visible definition before its use.
`Structure` requires function bodies to end with `ret` and nested blocks to end with `yield`.
The verifier checks these rules before it follows value definitions.

- `Type`: each operand and result has the type that its statement needs. A statement on a whole register needs `lent=0`, and a loop body yields each register with the `lent` count that it received.
- `SingleUse`: each wire, register and slot has exactly one use.
- `Capture`: both arms of an `if` consume the same outer linear values, and a loop body receives its linear values as block arguments.
- `SlotScope`: a `release` in the block of the `borrow` consumes the slot.
- `Origin`: a `release` fills its slot with the qubit that the `borrow` took out, into the same register. A loop body yields each linear argument at its position.
- `Distinct`: two open borrows of one register use indices that differ in every execution. The verifier proves this for two constants and for two constant offsets from one value, such as `%k` and `add %k, %one`.

It accepts any static length on the result of `alloc_register`, `split` and `join`.

The type checks reject register types whose open borrow count exceeds their known length.
Borrow checks reject a count that exceeds `u32::MAX`.
The index analysis caches each expression that it visits.
The scalar parser rejects float literals that exceed the finite range of `f64`.

## Build

The workspace pins Kirin to commit `a8e48ec1c394bc9a6e04464c7459b5f75864bfe3` on its `rust` branch.
Kirin requires Rust 1.98 or later.
The Nix development shell supplies a compatible compiler, Cargo, rustfmt, and Clippy.

Run these commands from the repository root:

```sh
nix develop -c cargo test --workspace
nix develop -c cargo clippy --workspace --all-targets -- -D warnings
nix develop -c cargo fmt --all --check
```
