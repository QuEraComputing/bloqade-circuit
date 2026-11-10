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

- `types` holds the type lattice `SquinType`.
- `state`, `gate` and `bits` hold the statements.
- `language` composes them with functions, integer constants, `if` and `for` into `Squin`.
- `threads` tells which result of a statement continues which linear operand.
- `verify` checks the rules below.
- `rewrite` holds the `Rule` trait, the driver `apply` and the rules.
- `passes` runs rules over one stage of a pipeline. `cancel_gates` removes two gates in a row that multiply to the identity.
- `run` holds the evaluator `Machine` and the `Backend` trait. The machine computes classical values and register indices, and the backend carries out the quantum operations.
- `stim` holds the backend that writes a Stim circuit.
- `kernel` holds `Kernel`, which parses, verifies, optimizes and emits a program.

The evaluator is squin code. The Kirin concrete interpreter at the pinned commit has no place for the state of a backend, so an `Interpretable` rule cannot reach it.

## Verifier rules

`verify` reports each `Violation` with its `Rule`.

- `Type`: each operand and result has the type that its statement needs. A statement on a whole register needs `lent=0`, and a loop body yields each register with the `lent` count that it received.
- `SingleUse`: each wire, register and slot has exactly one use.
- `Capture`: both arms of an `if` consume the same outer linear values, and a loop body receives its linear values as block arguments.
- `SlotScope`: a `release` in the block of the `borrow` consumes the slot.
- `Origin`: a `release` fills its slot with the qubit that the `borrow` took out, into the same register. A loop body yields each linear argument at its position.

The verifier does not yet check that two open borrows of one register use distinct indices.
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
