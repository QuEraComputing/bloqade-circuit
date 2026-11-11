//! Check the rewrite passes on small kernels.

mod common;

use kirin::prelude::*;
use squin::rewrite::passes::cancel_gates;
use squin::runtime::{Backend, Failure, Operation, Qubit};
use squin::{Kernel, Squin, verify};

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
        "%a1 = h %a0;
         %a = h %a1;
         %b = x %b0;",
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
        "%a1 = h %a0;
         %a2 = h %a1;
         %a3 = h %a2;
         %a = h %a3;
         %b = x %b0;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 2);
    assert!(!text.contains(" h "), "{text}");
}

#[test]
fn a_pair_that_appears_after_a_rewrite_cancels() {
    let body = on_two_wires(
        "%a1 = x %a0;
         %a2 = h %a1;
         %a3 = h %a2;
         %a = x %a3;
         %b = z %b0;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 2);
    assert!(!text.contains(" x "), "{text}");
    assert!(text.contains("z %b0"), "{text}");
}

#[test]
fn a_gate_and_its_inverse_cancel() {
    let body = on_two_wires(
        "%a1 = s %a0;
         %a = s_dag %a1;
         %b1 = sqrt_x_dag %b0;
         %b = sqrt_x %b1;",
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
        "%a1, %b1 = cx %a0, %b0;
         %a, %b = cx %a1, %b1;",
    );
    let (rewrites, text) = cancel("", &body);
    assert_eq!(rewrites, 1);
    assert!(!text.contains(" cx "), "{text}");
}

#[test]
fn two_controlled_gates_with_exchanged_qubits_stay() {
    let body = on_two_wires(
        "%a1, %b1 = cx %a0, %b0;
         %b, %a = cx %b1, %a1;",
    );
    assert_eq!(cancel("", &body).0, 0);
}

#[test]
fn gates_that_do_not_multiply_to_the_identity_stay() {
    let body = on_two_wires(
        "%a1 = s %a0;
         %a = s %a1;
         %b1 = h %b0;
         %b = x %b1;",
    );
    assert_eq!(cancel("", &body).0, 0);
}

#[test]
fn a_gate_before_an_if_stays_when_one_arm_repeats_it() {
    let body = on_two_wires(
        "%a1 = h %a0;
         %a = if %c then block ^then() {
           %again = h %a1;
           yield %again;
         } else block ^else() {
           yield %a1;
         } -> Wire;
         %b = x %b0;",
    );
    assert_eq!(cancel("%c: Bool", &body).0, 0);
}

/// Record the gates of a kernel in the order of their application.
#[derive(Default)]
struct Recorder {
    gates: Vec<(Operation, Vec<Qubit>)>,
    qubits: u32,
}

impl Backend for Recorder {
    type Bit = bool;

    fn alloc(&mut self) -> Result<Qubit, Failure> {
        self.qubits += 1;
        Ok(Qubit(self.qubits - 1))
    }

    fn free(&mut self, _qubit: Qubit) -> Result<(), Failure> {
        Ok(())
    }

    fn gate(&mut self, operation: Operation, qubits: &[Qubit]) -> Result<(), Failure> {
        self.gates.push((operation, qubits.to_vec()));
        Ok(())
    }

    fn measure(&mut self, qubits: &[Qubit]) -> Result<Vec<bool>, Failure> {
        Ok(vec![false; qubits.len()])
    }

    fn reset(&mut self, _qubit: Qubit) -> Result<(), Failure> {
        Ok(())
    }
}

/// Return the gates that the function `@main` of `text` applies.
fn gates(kernel: &Kernel) -> Vec<(Operation, Vec<Qubit>)> {
    let mut recorder = Recorder::default();
    kernel.run("main", Vec::new(), &mut recorder).unwrap();
    recorder.gates
}

const ROTATIONS: &str = "stage @kernel fn @main() -> Int;
specialize @kernel fn @main() -> Int cfg {
  ^entry() {
    %x = constant 0.25 -> Float;
    %y = constant 0.5 -> Float;
    %a0 = alloc;
    %a1 = rz(%x) %a0;
    %a2 = rz(%y) %a1;
    %a3 = rz(%x) %a2;
    %a4 = rx(%x) %a3;
    free %a4;
    %n = constant 0 -> Int;
    ret %n;
  }
}
";

#[test]
fn rotations_in_a_row_about_one_axis_merge_into_one_rotation() {
    let mut kernel = Kernel::parse(ROTATIONS).unwrap();
    let qubit = vec![Qubit(0)];
    let before = gates(&kernel);
    assert_eq!(before.len(), 4);
    assert_eq!(kernel.optimize().unwrap(), 2);
    let after = [
        (Operation::Rz(1.0), qubit.clone()),
        (Operation::Rx(0.25), qubit),
    ];
    assert_eq!(gates(&kernel), after);
    let text = kernel.text();
    assert_eq!(text.matches("= rz").count(), 1, "{text}");
    assert_eq!(text.matches(" add ").count(), 2, "{text}");
}
