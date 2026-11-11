//! Check the Stim circuits that kernels emit.

use squin::runtime::Value;
use squin::runtime::stim::{Record, Stim};
use squin::{Kernel, KernelError};

/// Return the text of a kernel whose function `@main` holds `body`.
fn program(body: &str) -> String {
    format!(
        "stage @kernel fn @main() -> Int;\n\
         specialize @kernel fn @main() -> Int cfg {{\n  ^entry() {{\n{body}\n  }}\n}}\n"
    )
}

fn stim(body: &str) -> Result<String, KernelError> {
    Kernel::parse(&program(body))?.to_stim("main")
}

const BELL: &str = include_str!("../examples/bell.kirin");

#[test]
fn a_bell_kernel_emits_its_gates_on_the_register_qubits() {
    let circuit = Kernel::parse(BELL).unwrap().to_stim("main").unwrap();
    assert_eq!(circuit, "X 0\nX 0\nH 0\nCX 0 1\nM 0 1\n");
}

#[test]
fn the_optimized_bell_kernel_emits_no_cancelled_gates() {
    let mut kernel = Kernel::parse(BELL).unwrap();
    assert_eq!(kernel.optimize().unwrap(), 1);
    assert_eq!(kernel.to_stim("main").unwrap(), "H 0\nCX 0 1\nM 0 1\n");
}

#[test]
fn a_kernel_returns_the_record_positions_of_its_measurements() {
    let kernel = Kernel::parse(BELL).unwrap();
    let mut backend = Stim::default();
    let returned = kernel.run("main", Vec::new(), &mut backend).unwrap();
    assert_eq!(returned, [Value::Bits(vec![Record(0), Record(1)])]);
}

#[test]
fn a_loop_emits_one_gate_for_each_register_element() {
    let circuit = stim(
        "%n = constant 3 -> Int;
         %zero = constant 0 -> Int;
         %one = constant 1 -> Int;
         %r0 = alloc_register %n -> Register[3];
         %r3 = for %zero in %zero..%n step %one iter_args(%r0) do block ^body(%k: Int, %r: Register[3]) {
           %r1, %s, %a0 = borrow %r, %k -> Register[3; lent=1], Slot, Wire;
           %a1 = h %a0 -> Wire;
           %r2 = release %r1, %s, %a1 -> Register[3];
           yield %r2;
         } -> Register[3];
         free_register %r3;
         ret %n;",
    );
    assert_eq!(circuit.unwrap(), "H 0\nH 1\nH 2\n");
}

#[test]
fn an_allocation_after_a_free_takes_the_freed_qubit_and_resets_it() {
    let circuit = stim(
        "%a0 = alloc -> Wire;
         %a1 = h %a0 -> Wire;
         %a2, %bit = measure %a1 -> Wire, Bit;
         free %a2;
         %b0 = alloc -> Wire;
         %b1 = x %b0 -> Wire;
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
         %fresh = alloc -> Wire;
         %r1, %old = replace %r0, %one, %fresh -> Register[2], Wire;
         %old1 = x %old -> Wire;
         free %old1;
         %r2, %bits = measure_register %r1 -> Register[2], Bits[2];
         free_register %r2;
         ret %n;",
    );
    assert_eq!(circuit.unwrap(), "X 1\nM 0 2\n");
}

#[test]
fn a_gate_outside_of_the_clifford_group_is_an_error() {
    let error = stim(
        "%a0 = alloc -> Wire;
         %a1 = t %a0 -> Wire;
         free %a1;
         %n = constant 0 -> Int;
         ret %n;",
    )
    .unwrap_err();
    assert!(error.to_string().contains("Stim backend"), "{error}");
}

#[test]
fn an_index_outside_of_the_register_is_an_error() {
    let error = stim(
        "%n = constant 2 -> Int;
         %r0 = alloc_register %n -> Register[2];
         %r1, %s, %a = borrow %r0, %n -> Register[2; lent=1], Slot, Wire;
         %r2 = release %r1, %s, %a -> Register[2];
         free_register %r2;
         ret %n;",
    )
    .unwrap_err();
    assert_eq!(
        error.to_string(),
        "The index 2 is outside of a length of 2."
    );
}

#[test]
fn a_program_that_breaks_a_rule_does_not_parse_into_a_kernel() {
    let text = program(
        "%a0 = alloc -> Wire;
         %n = constant 0 -> Int;
         ret %n;",
    );
    let error = Kernel::parse(&text).err().expect("the wire has no use");
    assert!(matches!(error, KernelError::Invalid(_)), "{error}");
}

#[test]
fn a_computed_index_selects_the_register_element() {
    let circuit = stim(
        "%n = constant 3 -> Int;
         %one = constant 1 -> Int;
         %last = sub %n, %one -> Int;
         %r0 = alloc_register %n -> Register[3];
         %r1, %s, %a0 = borrow %r0, %last -> Register[3; lent=1], Slot, Wire;
         %a1 = x %a0 -> Wire;
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
         %a0 = alloc -> Wire;
         %a1 = if %small then block ^then() {
           %flipped = x %a0 -> Wire;
           yield %flipped;
         } else block ^else() {
           %turned = h %a0 -> Wire;
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
    assert!(error.to_string().contains("divides by zero"), "{error}");
}

#[test]
fn each_clifford_gate_has_its_stim_name() {
    let circuit = stim(
        "%a0 = alloc -> Wire;
         %b0 = alloc -> Wire;
         %a1 = s %a0 -> Wire;
         %a2 = s_dag %a1 -> Wire;
         %a3 = sqrt_x %a2 -> Wire;
         %a4 = sqrt_y_dag %a3 -> Wire;
         %a5, %b1 = cz %a4, %b0 -> Wire, Wire;
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
