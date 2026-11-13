//! Check the phase-folding pass against a state-vector simulator.

use std::f64::consts::PI;

mod common;

use common::Applied;
use kirin::prelude::*;
use squin::rewrite::passes::fold_phases;
use squin::{Squin, verify};

/// Hold one complex number as its real part and its imaginary part.
#[derive(Clone, Copy, Debug)]
struct Complex(f64, f64);

impl Complex {
    fn times(self, other: Complex) -> Complex {
        Complex(
            self.0 * other.0 - self.1 * other.1,
            self.0 * other.1 + self.1 * other.0,
        )
    }

    fn plus(self, other: Complex) -> Complex {
        Complex(self.0 + other.0, self.1 + other.1)
    }

    /// Return the number of length 1 at the angle `angle` in radians.
    fn phase(angle: f64) -> Complex {
        Complex(angle.cos(), angle.sin())
    }

    fn size(self) -> f64 {
        self.0.hypot(self.1)
    }
}

const ZERO: Complex = Complex(0.0, 0.0);
const ONE: Complex = Complex(1.0, 0.0);

/// Simulate the state vector of the qubits of a kernel.
///
/// MeasurementResult `k` of an index of `state` is the value of qubit `k`.
struct Simulator {
    state: Vec<Complex>,
}

impl Simulator {
    fn new(qubits: u32) -> Self {
        let mut state = vec![ZERO; 1 << qubits];
        state[0] = ONE;
        Self { state }
    }

    /// Apply the 2 by 2 matrix `m` to `target` on each index where `control` is 1.
    fn apply(&mut self, m: [[Complex; 2]; 2], target: u32, control: Option<u32>) {
        let bit = 1 << target;
        for index in 0..self.state.len() {
            let controlled = control.is_none_or(|control| index & (1 << control) != 0);
            if index & bit != 0 || !controlled {
                continue;
            }
            let (zero, one) = (self.state[index], self.state[index | bit]);
            self.state[index] = m[0][0].times(zero).plus(m[0][1].times(one));
            self.state[index | bit] = m[1][0].times(zero).plus(m[1][1].times(one));
        }
    }

    fn gate(&mut self, applied: &Applied) {
        let h = std::f64::consts::FRAC_1_SQRT_2;
        let x = [[ZERO, ONE], [ONE, ZERO]];
        let m = match applied.gate.as_str() {
            "X" | "CX" => x,
            "Z" | "CZ" => phase(0.5),
            "H" => [
                [Complex(h, 0.0), Complex(h, 0.0)],
                [Complex(h, 0.0), Complex(-h, 0.0)],
            ],
            "S" => phase(0.25),
            "SDag" => phase(-0.25),
            "T" => phase(0.125),
            "TDag" => phase(-0.125),
            "Rz" => {
                let half = PI * applied.angles[0];
                [[Complex::phase(-half), ZERO], [ZERO, Complex::phase(half)]]
            }
            other => panic!("the test simulator has no gate {other}"),
        };
        match applied.qubits[..] {
            [target] => self.apply(m, target, None),
            [control, target] => self.apply(m, target, Some(control)),
            _ => unreachable!("the test gates act on one or two qubits"),
        }
    }
}

/// Return the diagonal matrix with the phase `turns` on the one state.
fn phase(turns: f64) -> [[Complex; 2]; 2] {
    [[ONE, ZERO], [ZERO, Complex::phase(2.0 * PI * turns)]]
}

/// Check that the two states are equal up to one global phase.
fn same_up_to_phase(left: &[Complex], right: &[Complex]) -> bool {
    let Some(pivot) = (0..left.len()).max_by(|a, b| left[*a].size().total_cmp(&left[*b].size()))
    else {
        return true;
    };
    let (a, b) = (left[pivot], right[pivot]);
    let norm = a.0 * a.0 + a.1 * a.1;
    // `ratio` is b divided by a, so right is about ratio times left.
    let ratio = Complex(
        (b.0 * a.0 + b.1 * a.1) / norm,
        (b.1 * a.0 - b.0 * a.1) / norm,
    );
    left.iter().zip(right).all(|(l, r)| {
        let expected = ratio.times(*l);
        (expected.0 - r.0).abs() < 1e-9 && (expected.1 - r.1).abs() < 1e-9
    })
}

fn state(pipeline: &Pipeline<StageInfo<Squin>>) -> Vec<Complex> {
    let gates = common::applied(pipeline);
    let qubits = gates
        .iter()
        .flat_map(|gate| gate.qubits.iter())
        .max()
        .map_or(0, |q| q + 1);
    let mut simulator = Simulator::new(qubits);
    for gate in &gates {
        simulator.gate(gate);
    }
    simulator.state
}

/// Return the text of a kernel on the wires `%a0`, `%b0` and `%c0` with `body`.
///
/// `body` must leave the wires `%a`, `%b` and `%c`. The kernel puts each qubit
/// in an equal superposition first, so that a wrong relative phase shows.
fn program(body: &str) -> String {
    format!(
        "stage @kernel fn @main() -> Int;
specialize @kernel fn @main() -> Int cfg {{
  ^entry() {{
    %x = constant 0.1 -> Float;
    %y = constant 0.35 -> Float;
    %qa = alloc;
    %qb = alloc;
    %qc = alloc;
    %a0, %b0, %c0 = circuit %qa, %qb, %qc digraph ^g0(%qa: Wire, %qb: Wire, %qc: Wire) {{
      %a0 = h %qa;
      %b0 = h %qb;
      %c0 = h %qc;
      yield %a0, %b0, %c0;
    }} -> Wire, Wire, Wire;
{body}
    free %a;
    free %b;
    free %c;
    %n = constant 0 -> Int;
    ret %n;
  }}
}}
"
    )
}

/// Run the pass on the kernel and return the number of removed gates and the new text.
///
/// The test fails if the verifier rejects the result, or if the result
/// prepares another state.
fn fold(body: &str) -> (usize, String) {
    let text = program(body);
    let mut pipeline = common::check(&text).expect("the kernel is valid");
    let before = state(&pipeline);
    let stage = pipeline.stage_by_name("kernel").unwrap();
    let removed = fold_phases(&mut pipeline, stage).expect("the pass succeeds");
    assert!(verify(pipeline.stage(stage).unwrap()).is_ok());
    let folded = pipeline.sprint();
    let after = state(&pipeline);
    assert!(same_up_to_phase(&before, &after), "{folded}");
    (removed, folded)
}

/// Count the statements of the text that apply `name`, such as `t`.
fn count(text: &str, name: &str) -> usize {
    text.matches(&format!("= {name} ")).count() + text.matches(&format!("= {name}(")).count()
}

#[test]
fn two_t_gates_across_a_cx_pair_merge_into_one_s_gate() {
    let (removed, text) = fold(
        "%b, %a, %c = circuit %b0, %a0, %c0 digraph ^g1(%b0: Wire, %a0: Wire, %c0: Wire) {
          %b1 = t %b0;
          %a1, %b2 = cx %a0, %b1;
          %a2, %b3 = cx %a1, %b2;
          %b = t %b3;
          %a = x %a2;
          %c = x %c0;
          yield %b, %a, %c;
        } -> Wire, Wire, Wire;",
    );
    assert_eq!(removed, 1);
    assert_eq!((count(&text, "t"), count(&text, "s")), (0, 1), "{text}");
}

#[test]
fn a_t_gate_on_the_negated_parity_cancels_a_t_gate() {
    let (removed, text) = fold(
        "%a, %b, %c = circuit %a0, %b0, %c0 digraph ^g2(%a0: Wire, %b0: Wire, %c0: Wire) {
          %a1 = t %a0;
          %a2 = x %a1;
          %a = t %a2;
          %b = x %b0;
          %c = x %c0;
          yield %a, %b, %c;
        } -> Wire, Wire, Wire;",
    );
    assert_eq!(removed, 2);
    assert_eq!(count(&text, "t"), 0, "{text}");
}

#[test]
fn t_gates_on_the_parity_of_two_qubits_merge() {
    let (removed, text) = fold(
        "%a, %b, %c = circuit %a0, %b0, %c0 digraph ^g3(%a0: Wire, %b0: Wire, %c0: Wire) {
          %a1, %b1 = cx %a0, %b0;
          %b2 = t %b1;
          %b3, %c1 = cx %b2, %c0;
          %c2, %b4 = cx %c1, %b3;
          %b5, %c3 = cx %b4, %c2;
          %c4 = t %c3;
          %a = x %a1;
          %b = x %b5;
          %c = x %c4;
          yield %a, %b, %c;
        } -> Wire, Wire, Wire;",
    );
    assert_eq!(removed, 1);
    assert_eq!((count(&text, "t"), count(&text, "s")), (0, 1), "{text}");
}

#[test]
fn a_hadamard_between_two_t_gates_keeps_both() {
    let (removed, text) = fold(
        "%a, %b, %c = circuit %a0, %b0, %c0 digraph ^g4(%a0: Wire, %b0: Wire, %c0: Wire) {
          %a1 = t %a0;
          %a2 = h %a1;
          %a = t %a2;
          %b = x %b0;
          %c = x %c0;
          yield %a, %b, %c;
        } -> Wire, Wire, Wire;",
    );
    assert_eq!(removed, 0);
    assert_eq!(count(&text, "t"), 2, "{text}");
}

#[test]
fn rotations_on_one_parity_merge_into_one_rotation_with_the_signed_sum() {
    let (removed, text) = fold(
        "%a, %b, %c = circuit %a0, %b0, %c0, %x, %y digraph ^g5(%a0: Wire, %b0: Wire, %c0: Wire) capture(%x: Float, %y: Float) {
          %a1 = rz(%x) %a0;
          %a2, %b1 = cx %a1, %b0;
          %a3 = x %a2;
          %a = rz(%y) %a3;
          %b = x %b1;
          %c = x %c0;
          yield %a, %b, %c;
        } -> Wire, Wire, Wire;",
    );
    assert_eq!(removed, 1);
    assert_eq!(count(&text, "rz"), 1, "{text}");
    assert_eq!(count(&text, "neg"), 1, "{text}");
}

#[test]
fn a_measurement_ends_the_groups() {
    let (removed, _) = fold(
        "%bit, %a, %b, %c = circuit %a0, %b0, %c0 digraph ^g6(%a0: Wire, %b0: Wire, %c0: Wire) {
          %a1 = t %a0;
          %a2, %bit = measure %a1;
          %a = t %a2;
          %b = x %b0;
          %c = x %c0;
          yield %bit, %a, %b, %c;
        } -> MeasurementResult, Wire, Wire, Wire;",
    );
    assert_eq!(removed, 0);
}

/// Give the same sequence of numbers for the same seed.
struct Random(u64);

impl Random {
    fn below(&mut self, bound: usize) -> usize {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        ((self.0 >> 33) as usize) % bound
    }
}

/// Return a `circuit` region of random gates on the three wires.
fn random_body(seed: u64) -> String {
    let mut random = Random(seed);
    let mut wires = ["%a0".to_string(), "%b0".to_string(), "%c0".to_string()];
    let mut lines = Vec::new();
    for step in 0..40 {
        let first = random.below(3);
        let name = |qubit: usize| format!("%{}{}", ["a", "b", "c"][qubit], step + 1);
        match random.below(10) {
            kind @ 0..=6 => {
                let gate = ["t", "t_dag", "s", "z", "x", "h", "rz(%x)"][kind];
                let next = name(first);
                lines.push(format!("{next} = {gate} {};", wires[first]));
                wires[first] = next;
            }
            kind => {
                let second = (first + 1 + random.below(2)) % 3;
                let gate = ["cx", "cx", "cz"][kind - 7];
                let (control, target) = (name(first), name(second));
                lines.push(format!(
                    "{control}, {target} = {gate} {}, {};",
                    wires[first], wires[second]
                ));
                wires[first] = control;
                wires[second] = target;
            }
        }
    }
    for (qubit, wire) in wires.iter().enumerate() {
        let last = ["%a", "%b", "%c"][qubit];
        lines.push(format!("{last} = x {wire};"));
    }
    let gates = lines.join("\n      ");
    format!(
        "%a, %b, %c = circuit %a0, %b0, %c0, %x digraph ^random(%a0: Wire, %b0: Wire, %c0: Wire) capture(%x: Float) {{
      {gates}
      yield %a, %b, %c;
    }} -> Wire, Wire, Wire;"
    )
}

#[test]
fn random_circuits_keep_their_state_and_lose_gates() {
    let mut removed = 0;
    for seed in 0..300 {
        removed += fold(&random_body(seed)).0;
    }
    assert!(removed > 300, "the pass removed {removed} gates");
}
