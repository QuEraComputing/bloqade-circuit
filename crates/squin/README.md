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

- `types` holds the type lattice `SquinType` and the constant value `Scalar`.
- `state`, `gate` and `bits` hold the statements. Each statement is one struct, and each gate is one statement. A macro writes the gates of one family, such as the controlled gates.
- `language` composes them with functions, constants, `kirin-arith`, `kirin-cmp`, `if` and `for` into `Squin`.
- `verify` checks the rules below and returns a `Verified` value for a program that passes.
- `rewrite` holds the `Rule` trait, the driver `apply` and the rules.
- `passes` runs rules over one stage of a pipeline. `cancel_gates` removes two gates in a row that multiply to the identity. `merge_rotations` replaces a run of rotations about one axis by one rotation. `simplify` runs both.
- `run` holds the evaluator `Machine` and the `Backend` trait. The machine requires a `Verified` program. It computes classical values and register indices, and the backend carries out the quantum operations.
- `stim` holds the backend that writes a Stim circuit.
- `kernel` holds `Kernel`, which parses, verifies, optimizes and emits a program.

The evaluator is squin code. The Kirin concrete interpreter at the pinned commit has no place for the state of a backend, so an `Interpretable` rule cannot reach it.

## Statement traits

A statement states its own rules in four traits, next to its definition.

- `Threads` tells which result continues which linear operand.
- `Typed` checks the types of the operands and the results.
- `Structure` tells the verifier how the statement nests blocks, lends a register element, or computes an index.
- `Execute` carries out the statement on a `Machine`.

The `delegate!` macro forwards the four traits from an enum to the statement of each variant. A new statement needs its struct, its four impls and one variant.

## Verifier rules

`verify` reports each `Violation` with its `Rule`.

- `Type`: each operand and result has the type that its statement needs. A statement on a whole register needs `lent=0`, and a loop body yields each register with the `lent` count that it received.
- `SingleUse`: each wire, register and slot has exactly one use.
- `Capture`: both arms of an `if` consume the same outer linear values, and a loop body receives its linear values as block arguments.
- `SlotScope`: a `release` in the block of the `borrow` consumes the slot.
- `Origin`: a `release` fills its slot with the qubit that the `borrow` took out, into the same register. A loop body yields each linear argument at its position.
- `Distinct`: two open borrows of one register use indices that differ in every execution. The verifier proves this for two constants and for two constant offsets from one value, such as `%k` and `add %k, %one`.

It accepts any static length on the result of `alloc_register`, `split` and `join`.

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
