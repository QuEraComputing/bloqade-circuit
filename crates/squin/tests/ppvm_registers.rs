//! Check how the ppvm emitter lends register elements at fixed and at run-time indices.

mod common;

use kirin::prelude::*;
use squin::Squin;
use squin::emit::ppvm::{self, PpvmError};

/// Flip `r[k]` for each `k` in `0..2` of a 3-qubit register, then measure the register.
///
/// The loop index is known only at run time, so the lent wire needs the register table.
const FLIP_TWO: &str = "
    %n = constant 3 -> Int;
    %two = constant 2 -> Int;
    %zero = constant 0 -> Int;
    %one = constant 1 -> Int;
    %r0 = alloc_register %n -> Register[3];
    %r3 = for %zero in %zero..%two step %one iter_args(%r0) do block ^body(%k: Int, %r: Register[3]) {
      %r1, %s, %a0 = borrow %r, %k -> Register[3; lent=1];
      %a1 = circuit %a0 digraph ^g(%w: Wire) {
        %w1 = x %w;
        yield %w1;
      } -> Wire;
      %r2 = release %r1, %s, %a1 -> Register[3];
      yield %r2;
    } -> Register[3];
    %r4, %bits = measure_register %r3 -> Register[3], MeasurementResults[3];
    free_register %r4;
    ret %zero;";

/// Emit the kernel `body` and return its instructions without comments.
/// Flip `r[k]` three times in an inner loop for each `k` in `0..2`, then measure the register.
///
/// The inner loop carries a wire whose qubit is known only at run time.
const NESTED: &str = "
    %n = constant 3 -> Int;
    %two = constant 2 -> Int;
    %zero = constant 0 -> Int;
    %one = constant 1 -> Int;
    %r0 = alloc_register %n -> Register[3];
    %r3 = for %zero in %zero..%two step %one iter_args(%r0) do block ^outer(%k: Int, %r: Register[3]) {
      %r1, %s, %a0 = borrow %r, %k -> Register[3; lent=1];
      %a2 = for %zero in %zero..%n step %one iter_args(%a0) do block ^inner(%j: Int, %w: Wire) {
        %w2 = circuit %w digraph ^g(%v: Wire) {
          %v1 = x %v;
          yield %v1;
        } -> Wire;
        yield %w2;
      } -> Wire;
      %r2 = release %r1, %s, %a2 -> Register[3];
      yield %r2;
    } -> Register[3];
    %r4, %bits = measure_register %r3 -> Register[3], MeasurementResults[3];
    free_register %r4;
    ret %zero;";

/// Flip `r[k]` once if `k` is 0 and twice in total otherwise, for each `k` in `0..3`.
///
/// A `conditional` arm flips the lent wire when `k` is 0, and a gate after
/// the `conditional` flips its wire result. So `r[0]` ends in 0, and the other
/// elements end in 1.
const BRANCHED: &str = "
    %n = constant 3 -> Int;
    %zero = constant 0 -> Int;
    %one = constant 1 -> Int;
    %r0 = alloc_register %n -> Register[3];
    %r3 = for %zero in %zero..%n step %one iter_args(%r0) do block ^body(%k: Int, %r: Register[3]) {
      %r1, %s, %a0 = borrow %r, %k -> Register[3; lent=1];
      %first = eq %k, %zero -> Bool;
      %a1 = conditional %first (%a0) then block ^yes(%t: Wire) {
        %t2 = circuit %t digraph ^f(%v: Wire) {
          %v1 = x %v;
          yield %v1;
        } -> Wire;
        yield %t2;
      } else block ^no(%e: Wire) {
        yield %e;
      } -> Wire;
      %a2 = circuit %a1 digraph ^g(%v: Wire) {
        %v1 = x %v;
        yield %v1;
      } -> Wire;
      %r2 = release %r1, %s, %a2 -> Register[3];
      yield %r2;
    } -> Register[3];
    %r4, %bits = measure_register %r3 -> Register[3], MeasurementResults[3];
    free_register %r4;
    ret %zero;";

fn emit(body: &str) -> Result<String, PpvmError> {
    ppvm::emit(&common::kernel("", body), "kernel", "main").map(|text| common::instructions(&text))
}

#[test]
fn a_borrow_at_a_loop_index_reads_the_register_table() {
    let text = emit(FLIP_TWO).unwrap();
    let table = "cpu::cpu.const u64, 0\n    cpu::cpu.const u64, 1\n    cpu::cpu.const u64, 2\n    cpu::cpu.heap_alloc 3\n    cpu::cpu.store heap_ref,";
    assert!(text.contains(table), "{text}");
    assert!(
        text.contains("cpu::cpu.get_item\n    cpu::cpu.store u64,"),
        "{text}"
    );
    // The gate loads its qubit index from the slot that `get_item` filled.
    let lines: Vec<&str> = text.lines().map(str::trim).collect();
    let gate = lines
        .iter()
        .position(|line| *line == "circuit::circuit.x")
        .unwrap();
    assert!(lines[gate - 1].starts_with("cpu::cpu.load u64,"), "{text}");
}

#[test]
fn two_loops_over_one_register_share_one_table() {
    let second_loop = "%r5 = for %zero in %zero..%two step %one iter_args(%r3) do block ^again(%j: Int, %q: Register[3]) {
      %q1, %t, %b0 = borrow %q, %j -> Register[3; lent=1];
      %b1 = circuit %b0 digraph ^h(%v: Wire) {
        %v1 = x %v;
        yield %v1;
      } -> Wire;
      %q2 = release %q1, %t, %b1 -> Register[3];
      yield %q2;
    } -> Register[3];
    %r4, %bits = measure_register %r5";
    let body = FLIP_TWO.replace("%r4, %bits = measure_register %r3", second_loop);
    let text = emit(&body).unwrap();
    assert_eq!(text.matches("cpu::cpu.heap_alloc").count(), 1, "{text}");
    assert_eq!(text.matches("cpu::cpu.get_item").count(), 2, "{text}");
}

#[test]
fn a_borrow_at_a_known_index_needs_no_table() {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline
        .parse(include_str!("../examples/address.kirin"))
        .unwrap();
    let text = common::instructions(&ppvm::emit(&pipeline, "kernel", "main").unwrap());
    assert!(!text.contains("heap_alloc"), "{text}");
    // `replace` puts the fresh qubit 3 at element 1, so the register measures qubits 0, 3 and 2.
    let order = "cpu::cpu.const u64, 0\n    circuit::circuit.measure\n    cpu::cpu.store u32, 3\n    cpu::cpu.const u64, 3\n    circuit::circuit.measure";
    assert!(text.contains(order), "{text}");
}

#[test]
fn a_replace_at_a_loop_index_is_an_error() {
    let body = "%n = constant 2 -> Int;
                %zero = constant 0 -> Int;
                %one = constant 1 -> Int;
                %r0 = alloc_register %n -> Register[2];
                %r3 = for %zero in %zero..%n step %one iter_args(%r0) do block ^body(%k: Int, %r: Register[2]) {
                  %w0 = alloc;
                  %r1, %old = replace %r, %k, %w0 -> Register[2];
                  free %old;
                  yield %r1;
                } -> Register[2];
                free_register %r3;
                ret %zero;";
    let error = emit(body).unwrap_err();
    assert!(matches!(error, PpvmError::Unsupported(_)), "{error}");
    assert!(
        error.to_string().contains("`replace` at an index"),
        "{error}"
    );
}

#[test]
fn an_inner_loop_carries_the_qubit_index_of_a_run_time_wire() {
    let text = emit(NESTED).unwrap();
    // The `borrow` stores the index, the inner loop copies it into its
    // argument at entry, and each run copies the yielded index back.
    assert_eq!(text.matches("cpu::cpu.store u64,").count(), 3, "{text}");
    let lines: Vec<&str> = text.lines().map(str::trim).collect();
    let gate = lines
        .iter()
        .position(|line| *line == "circuit::circuit.x")
        .unwrap();
    assert!(lines[gate - 1].starts_with("cpu::cpu.load u64,"), "{text}");
}

#[test]
fn a_conditional_stores_the_qubit_index_of_its_wire_result() {
    let text = emit(BRANCHED).unwrap();
    // Each arm stores the index of its yield in the slot of the result.
    assert_eq!(text.matches("cpu::cpu.store u64,").count(), 3, "{text}");
}

#[cfg(feature = "ppvm")]
mod bytecode {
    use ppvm_vihaco::measurements::MeasurementOutcome::{One, Zero};

    use super::common;

    #[test]
    fn an_inner_loop_flips_the_lent_element_three_times() {
        let outcomes = common::ppvm::run(&common::kernel("", super::NESTED));
        assert_eq!(outcomes, [One, One, Zero]);
    }

    #[test]
    fn a_conditional_passes_the_lent_element_to_the_next_gate() {
        let outcomes = common::ppvm::run(&common::kernel("", super::BRANCHED));
        assert_eq!(outcomes, [Zero, One, One]);
    }

    #[test]
    fn a_loop_flips_the_elements_that_its_index_names() {
        let outcomes = common::ppvm::run(&common::kernel("", super::FLIP_TWO));
        assert_eq!(outcomes, [One, One, Zero]);
    }
}
