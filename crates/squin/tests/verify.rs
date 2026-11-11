//! Check the verifier rules on small kernels.

mod common;

use kirin::prelude::*;
use squin::{Rule, Squin, Violation, verify};

/// Verify the kernel and return the rule of each violation.
fn rules(parameters: &str, body: &str) -> Vec<Rule> {
    violations(parameters, body)
        .into_iter()
        .map(|violation| violation.rule)
        .collect()
}

fn violations(parameters: &str, body: &str) -> Vec<Violation> {
    let pipeline = common::kernel(parameters, body);
    let stage: &StageInfo<Squin> = pipeline.stages().next().expect("the kernel has a stage");
    verify(stage).err().unwrap_or_default()
}

/// Wrap `body` in a kernel that owns the register `%r0` of 2 qubits.
fn with_register(body: &str) -> String {
    format!(
        "%n = constant 2 -> Int;
         %i = constant 0 -> Int;
         %j = constant 1 -> Int;
         %r0 = alloc_register %n -> Register[2];
         {body}
         ret %n;"
    )
}

#[test]
fn a_borrow_with_its_release_passes() {
    let body = with_register(
        "%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
         %a1 = h %a0 -> Wire;
         %r2 = release %r1, %s, %a1 -> Register[2];
         free_register %r2;",
    );
    assert_eq!(violations("", &body), []);
}

#[test]
fn a_wire_with_two_uses_fails() {
    let body = "%a0 = alloc -> Wire;
                %a1 = h %a0 -> Wire;
                %a2 = x %a0 -> Wire;
                free %a1;
                free %a2;
                %n = constant 0 -> Int;
                ret %n;";
    let found = violations("", body);
    assert_eq!(found.len(), 1, "{found:?}");
    assert_eq!(found[0].rule, Rule::SingleUse);
    assert!(found[0].message.contains("%a0"), "{found:?}");
}

#[test]
fn a_wire_that_nothing_consumes_fails() {
    let body = "%a0 = alloc -> Wire;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::SingleUse]);
}

#[test]
fn a_whole_register_statement_on_a_lent_register_fails() {
    let body = with_register(
        "%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
         %r2, %bits = measure_register %r1 -> Register[2; lent=1], Bits[2];
         %r3 = release %r2, %s, %a0 -> Register[2];
         free_register %r3;",
    );
    assert_eq!(rules("", &body), [Rule::Type]);
}

#[test]
fn two_borrows_that_exchange_their_qubits_fail() {
    let body = with_register(
        "%r1, %s0, %a = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
         %r2, %s1, %b = borrow %r1, %j -> Register[2; lent=2], Slot, Wire;
         %r3 = release %r2, %s0, %b -> Register[2; lent=1];
         %r4 = release %r3, %s1, %a -> Register[2];
         free_register %r4;",
    );
    assert_eq!(rules("", &body), [Rule::Origin, Rule::Origin]);
}

#[test]
fn a_replace_moves_a_qubit_to_a_new_position() {
    let body = with_register(
        "%a = alloc -> Wire;
         %r1, %b = replace %r0, %i, %a -> Register[2], Wire;
         %r2, %c = replace %r1, %j, %b -> Register[2], Wire;
         free %c;
         free_register %r2;",
    );
    assert_eq!(violations("", &body), []);
}

#[test]
fn a_slot_of_another_register_fails() {
    let body = with_register(
        "%q0 = alloc_register %n -> Register[2];
         %r1, %s, %a = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
         %q1, %t, %b = borrow %q0, %i -> Register[2; lent=1], Slot, Wire;
         %r2 = release %r1, %t, %a -> Register[2];
         %q2 = release %q1, %s, %b -> Register[2];
         free_register %r2;
         free_register %q2;",
    );
    let found = rules("", &body);
    assert!(found.iter().all(|rule| *rule == Rule::Origin), "{found:?}");
    assert_eq!(found.len(), 4, "{found:?}");
}

#[test]
fn a_gate_in_both_arms_of_an_if_passes() {
    let body = with_register(
        "%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
         %a1 = if %c then block ^then() {
           %flipped = x %a0 -> Wire;
           yield %flipped;
         } else block ^else() {
           yield %a0;
         } -> Wire;
         %r2 = release %r1, %s, %a1 -> Register[2];
         free_register %r2;",
    );
    assert_eq!(violations("%c: Bool", &body), []);
}

#[test]
fn a_wire_that_one_arm_of_an_if_consumes_fails() {
    let body = "%a = alloc -> Wire;
                %n = constant 0 -> Int;
                if %c then block ^then() {
                  free %a;
                  yield;
                } else block ^else() {
                  yield;
                };
                ret %n;";
    assert_eq!(rules("%c: Bool", body), [Rule::Capture]);
}

#[test]
fn a_wire_that_a_block_and_its_if_both_consume_fails() {
    let body = "%a = alloc -> Wire;
                %n = constant 0 -> Int;
                free %a;
                if %c then block ^then() {
                  free %a;
                  yield;
                } else block ^else() {
                  free %a;
                  yield;
                };
                ret %n;";
    assert_eq!(rules("%c: Bool", body), [Rule::SingleUse]);
}

#[test]
fn a_release_inside_an_if_fails() {
    let body = with_register(
        "%r1, %s, %a = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
         %r2 = if %c then block ^then() {
           %filled = release %r1, %s, %a -> Register[2];
           yield %filled;
         } else block ^else() {
           %same = release %r1, %s, %a -> Register[2];
           yield %same;
         } -> Register[2];
         free_register %r2;",
    );
    assert_eq!(rules("%c: Bool", &body), [Rule::SlotScope]);
}

#[test]
fn a_loop_that_borrows_and_releases_each_element_passes() {
    let body = with_register(
        "%r3 = for %i in %i..%n step %j iter_args(%r0) do block ^body(%k: Int, %r: Register[2]) {
           %r1, %s, %a0 = borrow %r, %k -> Register[2; lent=1], Slot, Wire;
           %a1 = h %a0 -> Wire;
           %r2 = release %r1, %s, %a1 -> Register[2];
           yield %r2;
         } -> Register[2];
         free_register %r3;",
    );
    assert_eq!(violations("", &body), []);
}

#[test]
fn a_loop_body_that_keeps_a_borrow_open_fails() {
    let body = with_register(
        "%r3 = for %i in %i..%n step %j iter_args(%r0) do block ^body(%k: Int, %r: Register[2]) {
           %r1, %s, %a = borrow %r, %k -> Register[2; lent=1], Slot, Wire;
           free %a;
           yield %r1;
         } -> Register[2];
         free_register %r3;",
    );
    let found = rules("", &body);
    assert!(found.contains(&Rule::Type), "{found:?}");
    assert!(found.contains(&Rule::SingleUse), "{found:?}");
}

#[test]
fn a_loop_body_that_consumes_an_outer_wire_fails() {
    let body = with_register(
        "%a = alloc -> Wire;
         for %i in %i..%n step %j iter_args() do block ^body(%k: Int) {
           free %a;
           yield;
         };
         free_register %r0;",
    );
    assert_eq!(rules("", &body), [Rule::Capture]);
}

#[test]
fn a_loop_body_that_exchanges_two_registers_fails() {
    let body = with_register(
        "%q0 = alloc_register %n -> Register[2];
         %r1, %q1 = for %i in %i..%n step %j iter_args(%r0, %q0) do block ^body(%k: Int, %r: Register[2], %q: Register[2]) {
           yield %q, %r;
         } -> Register[2], Register[2];
         free_register %r1;
         free_register %q1;",
    );
    assert_eq!(rules("", &body), [Rule::Origin, Rule::Origin]);
}

#[test]
fn a_sum_of_an_integer_and_a_float_fails() {
    let body = "%n = constant 1 -> Int;
                %sum = add %n, %x -> Int;
                ret %sum;";
    assert_eq!(rules("%x: Float", body), [Rule::Type]);
}

#[test]
fn a_comparison_with_an_integer_result_fails() {
    let body = "%n = constant 1 -> Int;
                %less = lt %n, %n -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Type]);
}

/// Borrow the elements at `%first` and `%second` of the register `%r0` at once.
fn two_borrows(indices: &str) -> String {
    with_register(&format!(
        "{indices}
         %r1, %s0, %a = borrow %r0, %first -> Register[2; lent=1], Slot, Wire;
         %r2, %s1, %b = borrow %r1, %second -> Register[2; lent=2], Slot, Wire;
         %r3 = release %r2, %s1, %b -> Register[2; lent=1];
         %r4 = release %r3, %s0, %a -> Register[2];
         free_register %r4;"
    ))
}

#[test]
fn two_open_borrows_at_one_constant_index_fail() {
    let body = two_borrows("%first = constant 1 -> Int;\n%second = constant 1 -> Int;");
    assert_eq!(rules("", &body), [Rule::Distinct]);
}

#[test]
fn two_open_borrows_at_an_index_and_its_successor_pass() {
    let body = two_borrows("%first = add %k, %i -> Int;\n%second = add %first, %j -> Int;");
    assert_eq!(violations("%k: Int", &body), []);
}

#[test]
fn two_open_borrows_at_unrelated_indices_fail() {
    let body = two_borrows("%first = add %k, %i -> Int;\n%second = add %m, %i -> Int;");
    assert_eq!(rules("%k: Int, %m: Int", &body), [Rule::Distinct]);
}

#[test]
fn a_borrow_after_a_release_of_the_same_index_passes() {
    let body = with_register(
        "%r1, %s0, %a = borrow %r0, %i -> Register[2; lent=1], Slot, Wire;
         %r2, %s1, %b = borrow %r1, %j -> Register[2; lent=2], Slot, Wire;
         %r3 = release %r2, %s0, %a -> Register[2; lent=1];
         %r4, %s2, %c = borrow %r3, %i -> Register[2; lent=2], Slot, Wire;
         %r5 = release %r4, %s2, %c -> Register[2; lent=1];
         %r6 = release %r5, %s1, %b -> Register[2];
         free_register %r6;",
    );
    assert_eq!(violations("", &body), []);
}
