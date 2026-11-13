//! Check the ppvm emitter: its `.sst` text, its bytecode, and the behavior of that bytecode.
//!
//! The tests behind the `ppvm` feature encode each program with ppvm's own
//! encoder. They also run the program on ppvm, so a wrong branch or a wrong
//! qubit index shows as a wrong outcome.

mod common;

use squin::emit::ppvm::{self, PpvmError};

/// Prepare a Bell pair on two qubits and measure both.
const BELL: &str = "
    %a0 = alloc;
    %b0 = alloc;
    %a1, %b1, %ma, %mb = circuit %a0, %b0 digraph ^bell(%a: Wire, %b: Wire) {
      %a2 = h %a;
      %a3, %b2 = cx %a2, %b;
      %a4, %ra = measure %a3;
      %b3, %rb = measure %b2;
      yield %a4, %b3, %ra, %rb;
    } -> Wire, Wire, MeasurementResult, MeasurementResult;
    free %a1;
    free %b1;
    %n = constant 0 -> Int;
    ret %n;";

/// Flip a qubit, measure it, and flip a second qubit when the first reads one.
const CORRECTION: &str = "
    %a0 = alloc;
    %b0 = alloc;
    %a1, %m = circuit %a0 digraph ^flip(%a: Wire) {
      %a2 = x %a;
      %a3, %r = measure %a2;
      yield %a3, %r;
    } -> Wire, MeasurementResult;
    %one = is_one %m;
    %b1 = conditional %one (%b0) then block ^fix(%t: Wire) {
      %t1 = circuit %t digraph ^x(%q: Wire) {
        %q1 = x %q;
        yield %q1;
      } -> Wire;
      yield %t1;
    } else block ^keep(%e: Wire) {
      yield %e;
    } -> Wire;
    %b2, %mb = circuit %b1 digraph ^read(%q: Wire) {
      %q1, %r = measure %q;
      yield %q1, %r;
    } -> Wire, MeasurementResult;
    free %a1;
    free %b2;
    %n = constant 0 -> Int;
    ret %n;";

/// Measure `h` on a fresh ancilla until it reads one.
const UNTIL_ONE: &str = "
    %d0 = alloc;
    %d1 = repeat (%d0) do block ^attempt(%d: Wire) {
      %anc = alloc;
      %anc1, %ok = circuit %anc digraph ^try(%p: Wire) {
        %p1 = h %p;
        %p2, %r = measure %p1;
        yield %p2, %r;
      } -> Wire, MeasurementResult;
      free %anc1;
      %done = is_one %ok;
      yield %done, %d;
    } -> Wire;
    free %d1;
    %n = constant 0 -> Int;
    ret %n;";

/// Flip one qubit three times in a counted loop, then measure it.
const THREE_FLIPS: &str = "
    %zero = constant 0 -> Int;
    %one = constant 1 -> Int;
    %three = constant 3 -> Int;
    %q0 = alloc;
    %q1 = for %zero in %zero..%three step %one iter_args(%q0) do block ^body(%k: Int, %q: Wire) {
      %q2 = circuit %q digraph ^x(%w: Wire) {
        %w1 = x %w;
        yield %w1;
      } -> Wire;
      yield %q2;
    } -> Wire;
    %q3, %m = circuit %q1 digraph ^read(%w: Wire) {
      %w1, %r = measure %w;
      yield %w1, %r;
    } -> Wire, MeasurementResult;
    free %q3;
    %n = constant 0 -> Int;
    ret %n;";

/// Emit the kernel `body` and return its instructions without comments.
fn emit(body: &str) -> Result<String, PpvmError> {
    ppvm::emit(&common::kernel("", body), "kernel", "main").map(|text| common::instructions(&text))
}

#[test]
fn each_statement_marks_its_first_instruction() {
    let text = ppvm::emit(&common::kernel("", BELL), "kernel", "main").unwrap();
    assert!(text.contains("circuit::circuit.h\n"), "{text}");
    let marked = text
        .lines()
        .find(|line| line.contains("// %a2 = h %a"))
        .unwrap();
    assert_eq!(
        marked.split("//").next().unwrap().trim(),
        "cpu::cpu.const u64, 0"
    );
    assert!(text.contains("// %a3, %b2 = cx %a2, %b"), "{text}");
    assert!(
        text.contains("cpu::cpu.ret 0") && text.contains("// ret %n"),
        "{text}"
    );
}

#[test]
fn a_bell_kernel_emits_its_gates_on_two_qubits() {
    let text = emit(BELL).unwrap();
    assert!(text.starts_with("device circuit.n_qubits 2;"), "{text}");
    for expected in [
        "cpu::cpu.const u64, 0\n    circuit::circuit.h",
        "cpu::cpu.const u64, 0\n    cpu::cpu.const u64, 1\n    circuit::circuit.cnot",
        "circuit::circuit.measure\n    cpu::cpu.store u32,",
        "cpu::cpu.ret 0",
    ] {
        assert!(text.contains(expected), "{expected}\n{text}");
    }
}

#[test]
fn a_conditional_becomes_a_conditional_branch() {
    let text = emit(CORRECTION).unwrap();
    assert!(
        text.contains("cpu::cpu.const u32, 1\n    cpu::cpu.eq u32"),
        "{text}"
    );
    assert!(text.contains("cpu::cpu.cond_br @l0, @l1"), "{text}");
}

#[test]
fn a_repeat_loop_branches_back_until_its_flag_holds() {
    let text = emit(UNTIL_ONE).unwrap();
    assert!(text.contains("cpu::cpu.label @l0"), "{text}");
    assert!(text.contains("cpu::cpu.cond_br @l1, @l0"), "{text}");
    // The ancilla index holds the state of the previous run, so each run resets it.
    assert!(text.contains("circuit::circuit.reset"), "{text}");
}

#[test]
fn a_counted_loop_compares_its_index_with_the_end() {
    let text = emit(THREE_FLIPS).unwrap();
    assert!(text.contains("cpu::cpu.lt i64"), "{text}");
    assert!(text.contains("cpu::cpu.add i64"), "{text}");
}

#[test]
fn a_cy_gate_becomes_a_cnot_between_phase_gates() {
    let body = "%c0 = alloc;
                %t0 = alloc;
                %c1, %t1 = circuit %c0, %t0 digraph ^g(%c: Wire, %t: Wire) {
                  %c2, %t2 = cy %c, %t;
                  yield %c2, %t2;
                } -> Wire, Wire;
                free %c1;
                free %t1;
                %n = constant 0 -> Int;
                ret %n;";
    let text = emit(body).unwrap();
    let order = ["circuit.s_adj", "circuit.cnot", "circuit.s\n"];
    let positions: Vec<usize> = order.iter().map(|name| text.find(name).unwrap()).collect();
    assert!(positions.windows(2).all(|pair| pair[0] < pair[1]), "{text}");
}

#[test]
fn an_invalid_program_is_an_error() {
    let body = "%a0 = alloc;
                %n = constant 0 -> Int;
                ret %n;";
    assert!(matches!(emit(body), Err(PpvmError::Invalid(_))));
}

#[cfg(feature = "ppvm")]
mod bytecode {
    use ppvm_vihaco::measurements::MeasurementOutcome;

    use super::common;

    /// Parse the kernel `body`, run it on ppvm once, and return the outcomes in order.
    fn run(body: &str) -> Vec<MeasurementOutcome> {
        common::ppvm::run(&common::kernel("", body))
    }

    #[test]
    fn a_bell_pair_measures_two_equal_outcomes() {
        for _ in 0..20 {
            let outcomes = run(super::BELL);
            assert_eq!(outcomes.len(), 2);
            assert_eq!(outcomes[0], outcomes[1]);
        }
    }

    #[test]
    fn a_correction_flips_the_second_qubit() {
        let outcomes = run(super::CORRECTION);
        assert_eq!(outcomes, [MeasurementOutcome::One, MeasurementOutcome::One]);
    }

    #[test]
    fn a_repeat_loop_stops_at_the_first_one() {
        for _ in 0..20 {
            let outcomes = run(super::UNTIL_ONE);
            let (last, earlier) = outcomes.split_last().unwrap();
            assert_eq!(*last, MeasurementOutcome::One);
            assert!(
                earlier
                    .iter()
                    .all(|outcome| *outcome == MeasurementOutcome::Zero)
            );
        }
    }

    #[test]
    fn a_counted_loop_runs_its_body_three_times() {
        assert_eq!(run(super::THREE_FLIPS), [MeasurementOutcome::One]);
    }
}
