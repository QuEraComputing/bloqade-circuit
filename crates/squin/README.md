# Squin

This crate defines squin as a Kirin Rust language with linear wires and registers.

A `Wire` names one qubit at one point in the program.
Each statement consumes its input wires and returns their next values.
A `Register[N]` holds `N` qubits.
`borrow` lends one element to a wire and returns a `Slot` token, and `release` consumes the token to put the wire back.
`replace` is the statement that moves a qubit to a new register position.

```text
%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1];
%a1 = circuit %a0 digraph ^flip(%q: Wire) {
  %q1 = h %q;
  yield %q1;
} -> Wire;
%r2 = release %r1, %s, %a1 -> Register[2];
```

Control flow and quantum dataflow live at two levels.
A function body, the arms of `if` and `conditional`, and the bodies of `for` and `repeat` are blocks, and they hold the control flow.
A `circuit` statement holds a dataflow graph, Kirin's `DiGraph`, and the graph reads only its own ports.
Wires enter as edge ports, and classical values such as angles enter as captures. The `circuit` lists the wires first and the captured values after them:

```text
%a1 = circuit %a0, %theta digraph ^turn(%q: Wire) capture(%t: Float) {
  %q1 = rz(%t) %q;
  yield %q1;
} -> Wire;
```

A `conditional` hands its wires to the arm that runs as block arguments.
A `repeat` runs its body until the body yields a true stop flag, as a repeat-until-success loop does. The body receives its wires as block arguments and yields the flag before them.
Each linear value crosses into a nested block or a region only as an operand.
Gates, `measure` and `reset` sit only in `circuit` graphs. Control flow, registers and `circuit` itself sit only in blocks. `alloc`, `free`, constants, arithmetic, comparisons, bitwise statements and measurement result statements sit in both.

```text
%d1, %m = circuit %d0 digraph ^prepare(%q: Wire) {
  %q1 = h %q;
  %q2, %result = measure %q1;
  yield %q2, %result;
} -> Wire, MeasurementResult;
%flip = is_one %m;
%d2 = conditional %flip (%d1) then block ^flip(%t: Wire) {
  %t1 = circuit %t digraph ^x(%w: Wire) {
    %w1 = x %w;
    yield %w1;
  } -> Wire;
  yield %t1;
} else block ^keep(%e: Wire) {
  yield %e;
} -> Wire;
%d3 = repeat (%d2) do block ^attempt(%q: Wire) {
  %a0 = alloc;
  %q1, %a1, %ok = circuit %q, %a0 digraph ^try(%p: Wire, %a: Wire) {
    %a2 = h %a;
    %p1, %a3 = cx %p, %a2;
    %a4, %result = measure %a3;
    yield %p1, %a4, %result;
  } -> Wire, Wire, MeasurementResult;
  free %a1;
  %done = is_one %ok;
  yield %done, %q1;
} -> Wire;
```

A measurement of a neutral atom ends in one of three ways: the qubit is zero, the qubit is one, or the atom is lost.
`measure` returns a `MeasurementResult`, and `measure_register` returns `MeasurementResults[N]`, as the Python squin does.
`is_zero`, `is_one` and `is_lost` read a result as a `Bool`.
A `conditional` and a `repeat` take a `Bool` only, so each program states what a lost atom means.
Kirin's `kirin-bitwise` dialect gives `and`, `or`, `xor` and `not` on `Bool` and `Int`, and `shl` and `shr` on `Int`, so a program can combine the reads, as in `%kept = not %lost -> Bool;`.

## Use

The crate is a library. Rust code parses a program into a Kirin pipeline and calls the squin passes:

```rust
let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
pipeline.parse(text)?;
let stage = pipeline.stage_by_name("kernel").unwrap();
squin::verify(pipeline.stage(stage).unwrap())?;
squin::rewrite::passes::optimize(&mut pipeline, stage)?;
let circuit = squin::emit::stim::emit(&pipeline, "kernel", "main")?;
```

## Rust examples

- `address` runs the address analysis on a straight-line program and on a loop, and prints the qubit that each value holds.
- `bell` parses, verifies, optimizes and emits the Bell circuit.
- `build_bell` builds the same circuit, with its gates in a `circuit` region, through the generated statement constructors and `Circuit::build`.
- `passes` runs one rewrite pass and walks the blocks of a stage.
- `phase_folding` merges two `t` gates into one `s` gate across a `cx`.
- `types` shows the type lattice and the constant types.
- `verify_invalid` reads the report of the verifier for a wire with two uses.

```sh
nix develop -c cargo run -p squin --example bell
```

## Modules

| Module | Responsibility | Start here |
| --- | --- | --- |
| `ir` | What a program is: the types, the statements of each dialect, and the `Squin` enum. | `src/ir/mod.rs` |
| `verify` | The verifier: the type rule of each statement, and one file per ownership rule. | `src/verify/mod.rs` |
| `rewrite` | Rewrite rules as Kirin `#[rewrite_rule]` patterns, and the passes that run them with Kirin's `RewriteDriver`. | `src/rewrite/mod.rs` |
| `analysis` | The forward rule of each statement on Kirin's sparse forward engine, and the address analysis. | `src/analysis/mod.rs` |
| `emit` | The emitters, such as Stim. | `src/emit/mod.rs` |

```text
src/
  ir/
    types/         SquinType, Length, Scalar and their text form
    traits.rs      Threads, which follows a qubit through a statement
    dialects/      qubit.rs, register.rs, gate/, measurement.rs, circuit.rs, conditional.rs, repeat.rs, from_kirin.rs
    language.rs    the Squin enum
    query.rs       questions about the functions, blocks and names of a stage
  verify/
    typing/        Typed and the type rules: one file per dialect
    structure/     Structure: how a statement nests blocks, lends an element, computes an index
    scope.rs  linearity.rs  origin.rs  distinct.rs
  rewrite/
    rules/         the cancel and merge rules as Kirin #[rewrite_rule] patterns
    passes/        cancel_gates, merge_rotations, simplify, fold_phases, optimize
  analysis/
    semantics/     the ForwardEval rule of each squin statement, one file per dialect
    address/       the Address domain and the address analysis
  emit/
    stim/          the Stim emitter, its errors, its gate names and its walk
    ppvm/          the ppvm emitter: the walk, the control flow, the classical values and their slots
    qubits.rs      the qubit index pool that both emitters share
```

`ir` holds definitions only, and it imports no other module.
The module that asks a question owns the trait and the answers.
`verify` owns `Typed` and `Structure`, and `analysis` owns the `ForwardEval` rules of the squin statements.
`ir::traits` keeps `Threads`, because the verifier, the rewrites and the analyses all read it.
`verify`, `rewrite` and `analysis` import only `ir`. `emit` imports `analysis` and `verify`.

Another language can wrap the squin dialects next to its own statements, as `tests/composition.rs` shows.
Its type must be `SquinType`, because every statement of one Kirin language shares one type.

## Analysis

`analysis` runs squin programs on Kirin's sparse forward engine.
Each squin statement has a `ForwardEval` rule that is generic over the value domain through `QuantumValue`.
Kirin's own dialects supply the rules for constants, arithmetic, comparisons, bitwise statements, `if`, `for` and functions.
A `circuit` region pushes Kirin's `AbstractDiGraphFrame`, and a `conditional` pushes a `ConditionalFrame` that enters each arm with the inputs as its arguments.
A `repeat` pushes a `RepeatFrame`, which reruns the body until its entry facts stop changing or a stop flag is true.

`analysis::address` finds the qubit that each wire carries.
`address::analyze(&pipeline, "kernel", "main")` returns an `Addresses` value, and `addresses.of(value)` returns the fact of one SSA value.
A qubit is named by the statement that allocates it and its position there, so a rerun of the statement gives the same name.
A `borrow` and its `release` leave the register fact unchanged, because the verifier proves that the qubit returns to its element.
A wire after a `borrow` at a loop index has the fact `Top`, because the analysis joins every iteration.

## Emission

`emit::stim::emit` verifies the stage, runs the address analysis, and walks the function in program order. It walks the graph of each `circuit` in dependency order.
It writes one Stim instruction for each gate, measurement and reset.
Each wire must carry a known qubit, so register sizes and indices must be constants.
An `if` or a `conditional` needs a condition that the analysis knows.
A `for` is an error until an unroll pass exists.
A `repeat` is an error, because Stim cannot end a loop on a measurement.
Stim holds Clifford gates only, so `t`, the rotations and `u3` are errors.
A qubit after a `free` gives its Stim index to the next allocation, which resets it first.

`emit::ppvm::emit` writes the same function as `.sst` source text for [ppvm](https://github.com/QuEraComputing/ppvm), QuEra's circuit simulator.
ppvm runs programs on vihaco, a stack machine with a `cpu` component and a `circuit` component.
A gate pushes its qubit indices, then its angles, and runs one `circuit::circuit` instruction.
`measure` stores its outcome in a local slot as a `u32`: 0 for zero, 1 for one and 2 for a lost atom.
`is_zero`, `is_one` and `is_lost` compare that outcome with a constant.
A `conditional`, an `if`, a `repeat` and a `for` become CPU labels and branches, so a program can branch on a measurement and loop until success.
ppvm has no `cy`, so the writer emits `s_adj`, `cnot` and `s` on the target.
An allocation in a loop resets its qubit, because the index holds the state of the previous run.
With the cargo feature `ppvm`, `emit::ppvm::bytecode` turns the text into `.ssb` bytecode through ppvm's own encoder, `ppvm_vihaco::bytecode::compile_to_bytes`.
The emitter runs nothing. The feature-gated tests run the bytecode on ppvm to check each branch and loop.

## Statement traits

- `ir::traits::Threads` tells which result continues which linear operand.
- `verify::Structure` tells the ownership rules where the statement sits, how it nests blocks or a graph, how it lends a register element, and how it computes an index.
- `verify::Typed` checks the types of the operands and the results.
- `Interpretable<I, ForwardEval>` from Kirin gives the forward rule of the statement.

`verify` has a `delegate!` macro that forwards its traits from an enum to the statement of each variant, and `analysis` has `forward!` for the forward rules.

## Reading order

1. Read `src/ir/language.rs` to see the dialects that the `Squin` enum combines.
2. Read `src/ir/dialects/qubit.rs`, then `src/verify/typing/qubit.rs` and `src/analysis/semantics/qubit.rs`, to follow one dialect through the layers.
3. Read `src/rewrite/rules/cancel.rs` to see how a Kirin rewrite pattern reconnects wires. Kirin's `RewriteDriver` then erases the gates that nothing reads.
4. Read `src/analysis/address/mod.rs` and `src/emit/stim/writer.rs` to follow a program from facts to a Stim circuit.

## Verifier rules

`verify` reports each `Violation` with its `Rule`.

`Scope` requires every operand to have a visible definition before its use, and every `circuit` graph to have no cycle.
`Terminator` requires function bodies to end with `ret` and nested blocks to end with `yield`.
The verifier checks these rules before it follows value definitions.

- `Type`: each operand and result has the type that its statement needs. A statement on a whole register needs `lent=0`, and a loop body yields each register with the `lent` count that it received.
- `SingleUse`: each wire, register and slot has exactly one use.
- `Capture`: a nested block reads no linear value of an outer block, and a `circuit` graph reads no outer value at all. A graph receives its wires as edge ports and its classical values as captures, and a capture is never linear. An arm receives its wires as inputs of a `conditional`, and a `for` or `repeat` body receives them as carried values.
- `SlotScope`: a `release` in the block of the `borrow` consumes the slot.
- `Origin`: a `release` fills its slot with the qubit that the `borrow` took out, into the same register. A loop body yields each linear argument at its position. A `circuit` result continues the input whose port the graph yields at that position.
- `Placement`: a gate, a `measure` and a `reset` sit in the graph of a `circuit`, and control flow, registers and `circuit` sit in blocks.
- `Distinct`: two open borrows of one register use indices that differ in every execution. The verifier proves this for two constants and for two constant offsets from one value, such as `%k` and `add %k, %one`.

It accepts any static length on the result of `alloc_register`, `split` and `join`.

The type checks reject register types whose open borrow count exceeds their known length.
Borrow checks reject a count that exceeds `u32::MAX`.
The index analysis caches each expression that it visits.
Float literals must have finite values.

## Build

The workspace pins Kirin to commit `93629607358289f168d4c10405ce32a11c07d04a` on the `fix/digraph-yield-with-scf` branch of the fork `nathanieltornow/kirin`.
That commit is Kirin's `rust` branch at `2958d85ddcd8c98a5e11c7c5e0e621e1730211e2` plus one parser fix, so a digraph body can end with `yield` in a language that also has `scf.yield`.
Kirin requires Rust 1.98 or later.
The Nix development shell supplies a compatible compiler, Cargo, rustfmt, and Clippy.

Run these commands from the repository root:

```sh
nix develop -c cargo test --workspace
nix develop -c cargo test -p squin --features ppvm
nix develop -c cargo clippy --workspace --all-targets -- -D warnings
nix develop -c cargo clippy -p squin --all-targets --features ppvm -- -D warnings
nix develop -c cargo fmt --all --check
```
