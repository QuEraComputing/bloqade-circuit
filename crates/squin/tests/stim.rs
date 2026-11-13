//! Check the Stim circuits that the emitter writes.

use kirin::prelude::*;
use squin::Squin;
use squin::emit::stim::{self, StimError};
use squin::rewrite::passes;

/// Return the text of a kernel whose function `@main` holds `body`.
fn program(body: &str) -> String {
    format!(
        "stage @kernel fn @main() -> Int;\n\
         specialize @kernel fn @main() -> Int cfg {{\n  ^entry() {{\n{body}\n  }}\n}}\n"
    )
}

fn parse(text: &str) -> Pipeline<StageInfo<Squin>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(text).expect("the kernel parses");
    pipeline
}

fn emit(text: &str) -> Result<String, StimError> {
    stim::emit(&parse(text), "kernel", "main")
}

fn stim(body: &str) -> Result<String, StimError> {
    emit(&program(body))
}

const BELL: &str = include_str!("../examples/bell.kirin");

#[test]
fn a_bell_kernel_emits_its_gates_on_the_register_qubits() {
    assert_eq!(emit(BELL).unwrap(), "X 0\nX 0\nH 0\nCX 0 1\nM 0 1\n");
}

#[test]
fn the_optimized_bell_kernel_emits_no_cancelled_gates() {
    let mut pipeline = parse(BELL);
    let stage = pipeline.stage_by_name("kernel").unwrap();
    assert_eq!(passes::optimize(&mut pipeline, stage).unwrap(), 1);
    let circuit = stim::emit(&pipeline, "kernel", "main").unwrap();
    assert_eq!(circuit, "H 0\nCX 0 1\nM 0 1\n");
}

#[test]
fn a_loop_needs_unrolling_before_emission() {
    let circuit = stim(
        "%n = constant 3 -> Int;
         %zero = constant 0 -> Int;
         %one = constant 1 -> Int;
         %r0 = alloc_register %n -> Register[3];
         %r3 = for %zero in %zero..%n step %one iter_args(%r0) do block ^body(%k: Int, %r: Register[3]) {
           %r1, %s, %a0 = borrow %r, %k -> Register[3; lent=1];
           %a1 = circuit %a0 digraph ^g0(%a0: Wire) {
             %a1 = h %a0;
             yield %a1;
           } -> Wire;
           %r2 = release %r1, %s, %a1 -> Register[3];
           yield %r2;
         } -> Register[3];
         free_register %r3;
         ret %n;",
    );
    assert!(
        matches!(circuit, Err(StimError::Unsupported(_))),
        "{circuit:?}"
    );
}

#[test]
fn an_allocation_after_a_free_takes_the_freed_qubit_and_resets_it() {
    let circuit = stim(
        "%a0 = alloc;
         %a2, %bit = circuit %a0 digraph ^g1(%a0: Wire) {
           %a1 = h %a0;
           %a2, %bit = measure %a1;
           yield %a2, %bit;
         } -> Wire, MeasurementResult;
         free %a2;
         %b0 = alloc;
         %b1 = circuit %b0 digraph ^g2(%b0: Wire) {
           %b1 = x %b0;
           yield %b1;
         } -> Wire;
         free %b1;
         %n = constant 0 -> Int;
         ret %n;",
    );
    assert_eq!(circuit.unwrap(), "H 0\nM 0\nR 0\nX 0\n");
}

#[test]
fn a_replace_moves_a_fresh_qubit_into_a_register() {
    let circuit = stim(
        "%n = constant 2 -> Int;
         %one = constant 1 -> Int;
         %r0 = alloc_register %n -> Register[2];
         %fresh = alloc;
         %r1, %old = replace %r0, %one, %fresh -> Register[2];
         %old1 = circuit %old digraph ^g3(%old: Wire) {
           %old1 = x %old;
           yield %old1;
         } -> Wire;
         free %old1;
         %r2, %bits = measure_register %r1 -> Register[2], MeasurementResults[2];
         free_register %r2;
         ret %n;",
    );
    assert_eq!(circuit.unwrap(), "X 1\nM 0 2\n");
}

#[test]
fn a_gate_outside_of_the_clifford_group_is_an_error() {
    let error = stim(
        "%a0 = alloc;
         %a1 = circuit %a0 digraph ^g4(%a0: Wire) {
           %a1 = t %a0;
           yield %a1;
         } -> Wire;
         free %a1;
         %n = constant 0 -> Int;
         ret %n;",
    )
    .unwrap_err();
    assert!(matches!(error, StimError::Unsupported(_)), "{error}");
}

#[test]
fn an_index_outside_of_the_register_is_an_error() {
    let error = stim(
        "%n = constant 2 -> Int;
         %r0 = alloc_register %n -> Register[2];
         %r1, %s, %a = borrow %r0, %n -> Register[2; lent=1];
         %r2 = release %r1, %s, %a -> Register[2];
         free_register %r2;
         ret %n;",
    )
    .unwrap_err();
    assert!(matches!(error, StimError::UnknownQubit(_)), "{error}");
}

#[test]
fn a_program_that_breaks_a_rule_is_not_emitted() {
    let text = program(
        "%a0 = alloc;
         %n = constant 0 -> Int;
         ret %n;",
    );
    let error = emit(&text).expect_err("the wire has no use");
    assert!(matches!(error, StimError::Invalid(_)), "{error}");
}

#[test]
fn a_computed_index_selects_the_register_element() {
    let circuit = stim(
        "%n = constant 3 -> Int;
         %one = constant 1 -> Int;
         %last = sub %n, %one -> Int;
         %r0 = alloc_register %n -> Register[3];
         %r1, %s, %a0 = borrow %r0, %last -> Register[3; lent=1];
         %a1 = circuit %a0 digraph ^g5(%a0: Wire) {
           %a1 = x %a0;
           yield %a1;
         } -> Wire;
         %r2 = release %r1, %s, %a1 -> Register[3];
         free_register %r2;
         ret %n;",
    );
    assert_eq!(circuit.unwrap(), "X 2\n");
}

#[test]
fn a_comparison_selects_the_arm_of_an_if() {
    let circuit = stim(
        "%n = constant 3 -> Int;
         %one = constant 1 -> Int;
         %small = lt %n, %one -> Bool;
         %a0 = alloc;
         %a1 = conditional %small (%a0) then block ^then(%t: Wire) {
           %flipped = circuit %t digraph ^g6(%t: Wire) {
             %flipped = x %t;
             yield %flipped;
           } -> Wire;
           yield %flipped;
         } else block ^else(%e: Wire) {
           %turned = circuit %e digraph ^g7(%e: Wire) {
             %turned = h %e;
             yield %turned;
           } -> Wire;
           yield %turned;
         } -> Wire;
         free %a1;
         ret %n;",
    );
    assert_eq!(circuit.unwrap(), "H 0\n");
}

#[test]
fn a_division_by_zero_is_an_error() {
    let error = stim(
        "%n = constant 3 -> Int;
         %zero = constant 0 -> Int;
         %bad = div %n, %zero -> Int;
         ret %bad;",
    )
    .unwrap_err();
    assert!(error.to_string().contains("by zero"), "{error}");
}

#[test]
fn each_clifford_gate_has_its_stim_name() {
    let circuit = stim(
        "%a0 = alloc;
         %b0 = alloc;
         %a5, %b1 = circuit %a0, %b0 digraph ^g8(%a0: Wire, %b0: Wire) {
           %a1 = s %a0;
           %a2 = s_dag %a1;
           %a3 = sqrt_x %a2;
           %a4 = sqrt_y_dag %a3;
           %a5, %b1 = cz %a4, %b0;
           yield %a5, %b1;
         } -> Wire, Wire;
         free %a5;
         free %b1;
         %n = constant 0 -> Int;
         ret %n;",
    );
    assert_eq!(
        circuit.unwrap(),
        "S 0\nS_DAG 0\nSQRT_X 0\nSQRT_Y_DAG 0\nCZ 0 1\n"
    );
}
