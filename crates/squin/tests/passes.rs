//! Check the rewrite passes on small kernels.

mod common;

use common::Applied;
use kirin::prelude::*;
use squin::rewrite::passes;
use squin::rewrite::passes::cancel_gates;
use squin::{Squin, verify};

/// Run `cancel_gates` on the kernel and return the rewrite count and the new text.
///
/// The verifier must accept the kernel before and after the pass.
fn cancel(parameters: &str, body: &str) -> (usize, String) {
    let mut pipeline = common::kernel(parameters, body);
    let stage = pipeline.stage_by_name("kernel").expect("the stage exists");
    assert!(verify(pipeline.stage(stage).unwrap()).is_ok());
    let rewrites = cancel_gates(&mut pipeline, stage).expect("the pass succeeds");
    let rewritten: &StageInfo<Squin> = pipeline.stage(stage).expect("the stage is in its slot");
    assert!(verify(rewritten).is_ok());
    (rewrites, pipeline.sprint())
}

/// Wrap `gates` in a kernel that owns the wires `%a0` and `%b0`.
///
/// `gates` must leave the wires `%a` and `%b`.
fn on_two_wires(gates: &str) -> String {
    format!(
        "%a0 = alloc;
         %b0 = alloc;
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
        "%a, %b = circuit %a0, %b0 digraph ^g0(%a0: Wire, %b0: Wire) {
          %a1 = h %a0;
          %a = h %a1;
          %b = x %b0;
          yield %a, %b;
        } -> Wire, Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 1);
    assert!(!text.contains(" h "), "{text}");
    assert!(text.contains("yield %a0, %b;"), "{text}");
    assert!(text.contains("x %b0"), "{text}");
}

#[test]
fn four_hadamards_in_a_row_cancel() {
    let body = on_two_wires(
        "%a, %b = circuit %a0, %b0 digraph ^g1(%a0: Wire, %b0: Wire) {
          %a1 = h %a0;
          %a2 = h %a1;
          %a3 = h %a2;
          %a = h %a3;
          %b = x %b0;
          yield %a, %b;
        } -> Wire, Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 2);
    assert!(!text.contains(" h "), "{text}");
}

#[test]
fn a_pair_that_appears_after_a_rewrite_cancels() {
    let body = on_two_wires(
        "%a, %b = circuit %a0, %b0 digraph ^g2(%a0: Wire, %b0: Wire) {
          %a1 = x %a0;
          %a2 = h %a1;
          %a3 = h %a2;
          %a = x %a3;
          %b = z %b0;
          yield %a, %b;
        } -> Wire, Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 2);
    assert!(!text.contains(" x "), "{text}");
    assert!(text.contains("z %b0"), "{text}");
}

#[test]
fn a_gate_and_its_inverse_cancel() {
    let body = on_two_wires(
        "%a, %b = circuit %a0, %b0 digraph ^g3(%a0: Wire, %b0: Wire) {
          %a1 = s %a0;
          %a = s_dag %a1;
          %b1 = sqrt_x_dag %b0;
          %b = sqrt_x %b1;
          yield %a, %b;
        } -> Wire, Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 2);
    assert!(
        !text.contains("s_dag") && !text.contains("sqrt_x"),
        "{text}"
    );
}

#[test]
fn two_controlled_gates_on_the_same_qubits_cancel() {
    let body = on_two_wires(
        "%a, %b = circuit %a0, %b0 digraph ^g4(%a0: Wire, %b0: Wire) {
          %a1, %b1 = cx %a0, %b0;
          %a, %b = cx %a1, %b1;
          yield %a, %b;
        } -> Wire, Wire;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 1);
    assert!(!text.contains(" cx "), "{text}");
}

#[test]
fn two_controlled_gates_with_exchanged_qubits_stay() {
    let body = on_two_wires(
        "%b, %a = circuit %a0, %b0 digraph ^g5(%a0: Wire, %b0: Wire) {
          %a1, %b1 = cx %a0, %b0;
          %b, %a = cx %b1, %a1;
          yield %b, %a;
        } -> Wire, Wire;",
    );
    assert_eq!(cancel("", &body).0, 0);
}

#[test]
fn gates_that_do_not_multiply_to_the_identity_stay() {
    let body = on_two_wires(
        "%a, %b = circuit %a0, %b0 digraph ^g6(%a0: Wire, %b0: Wire) {
          %a1 = s %a0;
          %a = s %a1;
          %b1 = h %b0;
          %b = x %b1;
          yield %a, %b;
        } -> Wire, Wire;",
    );
    assert_eq!(cancel("", &body).0, 0);
}

#[test]
fn a_gate_before_an_if_stays_when_one_arm_repeats_it() {
    let body = on_two_wires(
        "%a1 = circuit %a0 digraph ^g7(%a0: Wire) {
          %a1 = h %a0;
          yield %a1;
        } -> Wire;
         %a = conditional %c (%a1) then block ^then(%t: Wire) {
           %again = circuit %t digraph ^g8(%t: Wire) {
             %again = h %t;
             yield %again;
           } -> Wire;
           yield %again;
         } else block ^else(%e: Wire) {
           yield %e;
         } -> Wire;
         %b = circuit %b0 digraph ^g9(%b0: Wire) {
           %b = x %b0;
           yield %b;
         } -> Wire;",
    );
    assert_eq!(cancel("%c: Bool", &body).0, 0);
}

const ROTATIONS: &str = "stage @kernel fn @main() -> Int;
specialize @kernel fn @main() -> Int cfg {
  ^entry() {
    %x = constant 0.25 -> Float;
    %y = constant 0.5 -> Float;
    %a0 = alloc;
    %a4 = circuit %a0, %x, %y digraph ^g10(%a0: Wire) capture(%x: Float, %y: Float) {
      %a1 = rz(%x) %a0;
      %a2 = rz(%y) %a1;
      %a3 = rz(%x) %a2;
      %a4 = rx(%x) %a3;
      yield %a4;
    } -> Wire;
    free %a4;
    %n = constant 0 -> Int;
    ret %n;
  }
}
";

#[test]
fn rotations_in_a_row_about_one_axis_merge_into_one_rotation() {
    let mut pipeline = common::check(ROTATIONS).expect("the kernel is valid");
    assert_eq!(common::applied(&pipeline).len(), 4);
    let stage = pipeline.stage_by_name("kernel").unwrap();
    assert_eq!(passes::optimize(&mut pipeline, stage).unwrap(), 2);
    let rotation = |gate: &str, angle| Applied {
        gate: gate.to_string(),
        qubits: vec![0],
        angles: vec![angle],
    };
    assert_eq!(
        common::applied(&pipeline),
        [rotation("Rz", 1.0), rotation("Rx", 0.25)]
    );
    let text = pipeline.sprint();
    assert_eq!(text.matches("= rz").count(), 1, "{text}");
    assert_eq!(text.matches(" add ").count(), 2, "{text}");
}
