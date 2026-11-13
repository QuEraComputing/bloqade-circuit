//! Check that the ppvm emitter rotates by the squin angle, which is in turns.
//!
//! ppvm reads angles in radians. The tests behind the `ppvm` feature run
//! rotations with a known result, so a wrong unit shows as a wrong outcome.

mod common;

/// Rotate one qubit by `rx(0.5)`, a half turn, and measure it.
const HALF_TURN: &str = "
    %half = constant 0.5 -> Float;
    %a0 = alloc;
    %a1, %m = circuit %a0, %half digraph ^g(%q: Wire) capture(%t: Float) {
      %q1 = rx(%t) %q;
      %q2, %r = measure %q1;
      yield %q2, %r;
    } -> Wire, MeasurementResult;
    free %a1;
    %n = constant 0 -> Int;
    ret %n;";

#[test]
fn an_angle_becomes_radians_before_its_rotation() {
    let text = squin::emit::ppvm::emit(&common::kernel("", HALF_TURN), "kernel", "main").unwrap();
    let text = common::instructions(&text);
    let tau = format!("cpu::cpu.const f64, {:?}", std::f64::consts::TAU);
    let expected = format!("{tau}\n    cpu::cpu.mul f64\n    circuit::circuit.rx");
    assert!(text.contains(&expected), "{text}");
}

#[cfg(feature = "ppvm")]
mod bytecode {
    use kirin::prelude::*;
    use ppvm_vihaco::measurements::MeasurementOutcome;
    use squin::Squin;

    use super::common;

    #[test]
    fn a_half_turn_about_x_flips_the_qubit() {
        let outcomes = common::ppvm::run(&common::kernel("", super::HALF_TURN));
        assert_eq!(outcomes, [MeasurementOutcome::One]);
    }

    /// The kernel injects a quarter turn into `|+>` and maps the result `|+i>` to `|0>`.
    ///
    /// Every ancilla outcome before the last one reads 1, the last ancilla
    /// outcome reads 0, and the data qubit reads 0.
    #[test]
    fn an_injected_rotation_leaves_the_expected_state() {
        let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
        pipeline
            .parse(include_str!("../examples/rz_injection.kirin"))
            .unwrap();
        for _ in 0..30 {
            let outcomes = common::ppvm::run(&pipeline);
            let (data, tries) = outcomes.split_last().unwrap();
            assert_eq!(*data, MeasurementOutcome::Zero, "{outcomes:?}");
            let (success, failures) = tries.split_last().unwrap();
            assert_eq!(*success, MeasurementOutcome::Zero, "{outcomes:?}");
            assert!(
                failures
                    .iter()
                    .all(|outcome| *outcome == MeasurementOutcome::One)
            );
        }
    }
}
