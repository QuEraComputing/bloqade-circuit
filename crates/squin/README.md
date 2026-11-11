# Squin

This crate defines squin as a Kirin Rust language with linear wires and registers.

A `Wire` names one qubit at one point in the program.
Each statement consumes its input wires and returns their next values.
A `Register[N]` holds `N` qubits.
`borrow` lends one element to a wire and returns a `Slot` token, and `release` consumes the token to put the wire back.
`replace` is the statement that moves a qubit to a new register position.

```text
%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1];
%a1 = h %a0;
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

## Rust examples

Cargo discovers the Rust programs in `examples/`.
Run them from the repository root in this order:

1. `nix develop -c cargo run -p squin --example bell` parses, optimizes, and emits the Bell circuit.
2. `nix develop -c cargo run -p squin --example types` compares types, register lengths, and ownership requirements.
3. `nix develop -c cargo run -p squin --example passes` inspects a Kirin stage and applies gate cancellation.
4. `nix develop -c cargo run -p squin --example verify_invalid` prints the violation for consuming one wire twice.
5. `nix develop -c cargo run -p squin --example custom_backend` traces the backend calls and measurement record positions.

Each example checks its expected result with assertions.
The `verify_invalid` example succeeds when the verifier rejects its input.
The Stim backend writes measurement instructions and returns their record positions.

### Build operations in Rust

Run `nix develop -c cargo run -p squin --example build_bell` to construct, verify, and execute a Bell circuit.
The example uses Kirin's generated constructors, including `Alloc::new`, `H::new`, and `CX::new`.
The operation declarations supply the fixed result types.
`BitsPack::new` computes its result length from the number of operands.
The example verifies the constructed stage, prints its text, and checks the emitted Stim circuit.

### Type declarations and verification

`SquinType` implements Kirin's `TypeLattice`, which describes how types contain other types.
`Register[2]` fits `Register[?]`, where `?` permits any length.
`join` keeps the information that both types guarantee.
For example, joining `Register[2]` and `Register[3]` gives `Register[?]`.
`meet` describes the values that fit both types.
Meeting `Register[2]` and `Register[3]` gives `Bottom`, which describes an impossible value.
The `types` example checks these relations.

`#[kirin(builders, type = SquinType)]` selects the type representation and generates operation constructors.
A result field can declare its builder default with `#[kirin(type = SquinType::Wire)]`.
Gate constructors use this declaration for their wire results.
Measurement constructors also declare their `Bit` result.
Pack constructors compute `Bits[N]` or `Register[N]` from the operand count.
The `Squin` variants use `#[wraps(lift_project_from(...))]` to connect nested operation constructors to the combined language.
Kirin also generates conversions that extract those operation types from `Squin`.

Operands use `SSAValue`, Kirin's reference to a program value.
The verifier reads the type of each referenced value and checks the operation's requirements.
For example, `Rx` requires an `f64` angle and a `Wire` operand.
The verifier also checks result types that callers supply through builders or program text.
Register results that depend on operand types still require explicit types from the caller.
For example, borrowing from `Register[3]` must produce `Register[3; lent=1]`.
Squin currently checks these types without an inference pass that fills in missing operand-dependent types.

The verifier preserves ownership when it checks whether one type fits another.
It rejects passing a `Wire` as `Any`, because that would lose the requirement to consume the wire exactly once.
Separate ownership checks track qubit identity, borrow slots, and uses across control flow.

### Compose numeric types

`SquinType::Number(ArithType)` includes the numeric types from `kirin-arith`.
`Scalar::Number(ArithValue)` holds numeric constants.
`runtime::Value::Number(ArithValue)` holds numeric values during execution.
Squin defines Boolean and quantum values alongside these numeric values.

Kirin supplies signed and unsigned integers with widths of 8, 16, 32, 64, and 128 bits.
It also supplies `f32` and `f64`.
The Squin type lattice treats each numeric type as distinct.
Arithmetic operands and their result must have the same numeric type.
The pinned Kirin version provides no arithmetic type verifier, so Squin checks this requirement when it verifies a program.

```rust
use squin::{ArithType, ArithValue, Scalar, SquinType};
use squin::runtime::Value;

let ty = SquinType::Number(ArithType::U32);
let constant = Scalar::Number(ArithValue::U32(7));
let argument: Value<bool> = Value::from(7_u32);
```

The primitive Rust type determines which numeric variant `Scalar::from` and `Value::from` construct.
Use `7_i64` when an argument needs `i64`.
Rust assigns `i32` to an integer literal without a suffix or another type constraint.
The `types` example shows how these representations connect.

In program text, an integer literal has type `i64`, and a float literal has type `f64`.
Kirin's number parser reads no other width, so only `i64` and `f64` constants survive a round trip through the text.
The parser accepts `Int` as an alias for `i64` and `Float` as an alias for `f64`.
The printer uses `i64` and `f64` for those types.
Quantum gate angles use `f64`.
Register sizes, indices, and loop bounds use `i64`.
Integer operations return an error if they divide by zero or exceed the range of their type.
Unsigned negation succeeds for zero and returns an error for positive values.
Floating-point operations use the selected Rust width and its IEEE 754 behavior.

### Control flow, specialization, and phase folding

Each example has a Rust driver and a `.kirin` source file with the same name.
Read the source to follow the values, then run the driver to see the emitted circuit.

1. `nix develop -c cargo run -p squin --example ghz_chain` prepares a register whose length comes from an argument.
2. `nix develop -c cargo run -p squin --example conditional_layers` carries a register through nested loops and conditional gates.
3. `nix develop -c cargo run -p squin --example register_dispatch` selects a function body from a register's runtime length.
4. `nix develop -c cargo run -p squin --example phase_folding` combines two T gates across a controlled-X gate.

`ghz_chain` runs with lengths 1, 2, and 5.
Its caller must supply a positive length.
The loop borrows elements `k` and `k + 1` together, then returns both before the next iteration.
The verifier proves that those indices differ.

`conditional_layers` runs both branches with 0, 1, and 2 outer iterations.
The inner loop visits each element of a three-qubit register.
Both branches consume the borrowed wire and yield its successor.
The caller supplies the branch condition as a Boolean argument.

`register_dispatch` allocates registers in Rust and transfers them into the kernel.
The two-qubit specialization prepares a Bell pair.
The generic specialization applies a Hadamard gate to each qubit.
The driver checks the selected behavior for lengths 1, 2, and 3.

`phase_folding` prints the program before and after the pass.
Controlled-X preserves its control parity, so the two T gates on that wire combine into one S gate.
The driver checks the gate counts, verifies the rewritten program, and emits the resulting Stim circuit.
These examples check emitted instructions and measurement record positions.

## Modules

| Module | Responsibility | Start here |
| --- | --- | --- |
| `ir` | What a program is: the types, the statements of each dialect, and the `Squin` enum. | `src/ir/mod.rs` |
| `verify` | The verifier: the type rule of each statement, and one file per ownership rule. | `src/verify/mod.rs` |
| `rewrite` | Rewrite rules and the passes that run them. | `src/rewrite/mod.rs` |
| `runtime` | What each statement does when it runs, the `Machine`, and the backends. | `src/runtime/mod.rs` |
| `kernel` | `Kernel` connects parsing, verification, optimization, and execution. | `src/kernel.rs` |

```text
src/
  ir/
    types/         SquinType, Length, Scalar, QuantumTypes and their text form
    traits.rs      Threads, which follows a qubit through a statement
    query.rs       function definitions and block traversal
    dialects/      qubit.rs, register.rs, gate.rs, bits.rs, from_kirin.rs
    ops.rs         the squin names of the statements, such as `ops::H` for `gate::H<SquinType>`
    language.rs    the Squin enum
  verify/
    type_check.rs  TypeCheck, the interface that type rules use
    typing_context.rs  Typing, the verifier's implementation of TypeCheck
    typing/        Typed and the type rules: one file per dialect
    structure/     Structure and the ownership facts: one file per dialect
    scope.rs  linearity.rs  origin.rs  distinct.rs
  rewrite/
    rules/         CancelInverse, MergeRotations and the driver
    passes/        cancel_gates, merge_rotations, simplify, fold_phases
      fold/        parity, group, scan, rewrite, and the pass driver
  runtime/
    execute/       Execute, and the execution of each statement: one file per dialect
    evaluator.rs  machine.rs  value.rs  failure.rs  backend.rs  stim.rs
    dispatch.rs    function specialization selection
  kernel.rs
```

`ir` defines and queries programs.
It depends only on its own modules and external crates.
The module that asks a question owns the trait and the answers.
`verify::typing` owns `Typed`, so the type rule of `borrow` is in `verify/typing/register.rs`.
`verify::structure` owns `Structure`, because only the ownership rules read it.
`verify::TypeCheck` and `runtime::Evaluator` each have a file outside the directories that implement statement behavior.
The private `Typing` context implements `TypeCheck`, and `Machine` implements `Evaluator`.
`ir::traits` keeps `Threads`, because the verifier, the rewrites and the runtime all read it.
`runtime::execute` owns `Execute`, so the execution of `borrow` is in `runtime/execute/register.rs`.
`verify` and `rewrite` import only `ir`. `runtime` imports `ir` and the `Verified` proof of `verify`.

A new statement needs its struct in `ir/dialects`, a type rule in `verify/typing`, and an execution in `runtime/execute`.
The crate does not compile until all three exist, because each layer forwards from the `Squin` enum to every statement.
`for_each_gate!` in `ir/dialects/gate.rs` lists every gate once, and the type rules and the execution of the gates come from that list.

`ir::types` defines `SquinType`, the type lattice, and `Scalar`, the constant value type.

The qubit, register, gate and bits dialects are generic over their type lattice, as Kirin's `Arith<T>` is.
`QuantumTypes` names the types that they fix for their results, such as `Ty::wire()` for the output of a gate.
Another language implements `QuantumTypes` for its own lattice and wraps the dialects, as `tests/composition.rs` shows.
`#[wraps(lift_project_from(...))]` lets the builders of each statement build the wrapping language directly.
The squin language uses `SquinType`, and `ir::ops` names its statements, so code on squin programs writes `ops::H`.
A type lattice describes which types contain other types.
`ir::dialects::from_kirin` and its two sibling files give the Kirin constants, arithmetic, comparisons, functions, branches, and loops their squin rules.

`verify` returns a `Verified` value for a program that passes its checks.
`rewrite::rules::RewriteRule` defines the interface for local rewrites.
The rewrite driver and the verifier use `ir::query` to list function definitions.
`rewrite::passes` runs rewrites over one pipeline stage.
`cancel_gates` removes adjacent inverse gates, and `merge_rotations` combines adjacent rotations about the same axis.
`simplify` repeats these rules until they stop changing the program.
`fold_phases` combines phase gates that act on the same parity, a sum of qubit values modulo two.
Its `parity` module computes these sums, and `group` describes the phase gates that share a sum.
Its `scan` module collects the groups, and `rewrite` replaces their gates.

`runtime::Machine` requires a `Verified` program.
It computes classical values and register indices.
`Machine::call` checks the argument types, the register shapes, and that no two arguments own the same qubit.
The verifier proves these facts for every value inside the program, so the machine checks them once, at the function entry.
The backend carries out quantum operations.
`runtime::stim` writes those operations as a Stim circuit.

`Kernel::run` delegates specialization selection to `runtime::dispatch`.
A specialization supplies a function body for a parameter type signature.
For multiple specializations, dispatch selects the unique most specific candidate that accepts the argument types.
If no candidate matches, or several candidates remain, dispatch returns an error.
For a single specialization, `Machine::call` checks its arguments before execution.

The evaluator is squin code. The Kirin concrete interpreter at the pinned commit has no place for the state of a backend, so an `Interpretable` rule cannot reach it.

## Reading order

1. Read `src/kernel.rs` to follow a program through parsing, verification, optimization, and execution.
2. Read `src/ir/language.rs` to see the dialects that the `Squin` enum combines.
3. Read `src/ir/dialects/qubit.rs`, then `src/verify/typing/qubit.rs` and `src/runtime/execute/qubit.rs`, to follow one dialect through the layers.
4. Read `src/rewrite/rules/cancel.rs` to see how a rewrite reconnects wires after removing gates.
5. Read `src/runtime/machine.rs` with `src/runtime/stim.rs` to follow execution through circuit emission.

## Statement traits

- `ir::traits::Threads` tells which result continues which linear operand.
- `verify::Structure` tells the ownership rules how the statement nests blocks, lends a register element, or computes an index.
- `verify::Typed` checks the types of the operands and the results.
- `runtime::Execute` carries out the statement on an `Evaluator`.

Each layer has a `delegate!` macro that forwards its trait from an enum to the statement of each variant.

## Verifier rules

`verify` reports each `Violation` with its `Rule`.

`Scope` requires every operand to have a visible definition before its use.
`Terminator` requires function bodies to end with `ret` and nested blocks to end with `yield`.
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
The scalar parser rejects numeric literals that exceed the range of their type.
Float literals must have finite values.

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
