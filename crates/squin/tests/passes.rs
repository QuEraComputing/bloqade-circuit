//! Check the rewrite passes on small kernels.

mod common;

use kirin::prelude::*;
use squin::passes::cancel_gates;
use squin::{Squin, verify};

/// Run `cancel_gates` on the kernel and return the rewrite count and the new text.
///
/// The verifier must accept the kernel before and after the pass.
fn cancel(parameters: &str, body: &str) -> (usize, String) {
    let mut pipeline = common::kernel(parameters, body);
    let stage = pipeline.stage_by_name("kernel").expect("the stage exists");
    assert_eq!(verify(pipeline.stage(stage).unwrap()), Ok(()));
    let rewrites = cancel_gates(&mut pipeline, stage).expect("the pass succeeds");
    let rewritten: &StageInfo<Squin> = pipeline.stage(stage).expect("the stage is in its slot");
    assert_eq!(verify(rewritten), Ok(()));
    (rewrites, pipeline.sprint())
}

/// Wrap `gates` in a kernel that owns the wires `%a0` and `%b0`.
///
/// `gates` must leave the wires `%a` and `%b`.
fn on_two_wires(gates: &str) -> String {
    format!(
        "%a0 = alloc -> Wire;
         %b0 = alloc -> Wire;
         {gates}
         free %a;
         free %b;
         %n = constant 0 -> Int;
         ret %n;"
    )
}

#[test]
fn two_hadamards_in_a_row_cancel() {
    let body = on_two_wires(
        "%a1 = h %a0 -> Wire;
         %a = h %a1 -> Wire;
         %b = x %b0 -> Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 1);
    assert!(!text.contains(" h "), "{text}");
    assert!(text.contains("free %a0;"), "{text}");
    assert!(text.contains("x %b0"), "{text}");
}

#[test]
fn four_hadamards_in_a_row_cancel() {
    let body = on_two_wires(
        "%a1 = h %a0 -> Wire;
         %a2 = h %a1 -> Wire;
         %a3 = h %a2 -> Wire;
         %a = h %a3 -> Wire;
         %b = x %b0 -> Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 2);
    assert!(!text.contains(" h "), "{text}");
}

#[test]
fn a_pair_that_appears_after_a_rewrite_cancels() {
    let body = on_two_wires(
        "%a1 = x %a0 -> Wire;
         %a2 = h %a1 -> Wire;
         %a3 = h %a2 -> Wire;
         %a = x %a3 -> Wire;
         %b = z %b0 -> Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 2);
    assert!(!text.contains(" x "), "{text}");
    assert!(text.contains("z %b0"), "{text}");
}

#[test]
fn two_controlled_gates_on_the_same_qubits_cancel() {
    let body = on_two_wires(
        "%a1, %b1 = cx %a0, %b0 -> Wire, Wire;
         %a, %b = cx %a1, %b1 -> Wire, Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 1);
    assert!(!text.contains(" cx "), "{text}");
}

#[test]
fn two_controlled_gates_with_exchanged_qubits_stay() {
    let body = on_two_wires(
        "%a1, %b1 = cx %a0, %b0 -> Wire, Wire;
         %b, %a = cx %b1, %a1 -> Wire, Wire;",
    );
    assert_eq!(cancel("", &body).0, 0);
}

#[test]
fn gates_that_do_not_multiply_to_the_identity_stay() {
    let body = on_two_wires(
        "%a1 = s %a0 -> Wire;
         %a = s %a1 -> Wire;
         %b1 = h %b0 -> Wire;
         %b = x %b1 -> Wire;",
    );
    assert_eq!(cancel("", &body).0, 0);
}

#[test]
fn a_gate_before_an_if_stays_when_one_arm_repeats_it() {
    let body = on_two_wires(
        "%a1 = h %a0 -> Wire;
         %a = if %c then block ^then() {
           %again = h %a1 -> Wire;
           yield %again;
         } else block ^else() {
           yield %a1;
         } -> Wire;
         %b = x %b0 -> Wire;",
    );
    assert_eq!(cancel("%c: Bool", &body).0, 0);
}
