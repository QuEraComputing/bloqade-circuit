//! Check the verifier rules on small kernels.

mod common;

use kirin::prelude::*;
use squin::{Rule, Squin, Violation, verify};

/// Verify the kernel and return the rule of each violation.
fn rules(parameters: &str, body: &str) -> Vec<Rule> {
    violations(parameters, body)
        .into_iter()
        .map(|violation| violation.rule())
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
        "%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1];
         %a1 = circuit %a0 digraph ^g0(%a0: Wire) {
           %a1 = h %a0;
           yield %a1;
         } -> Wire;
         %r2 = release %r1, %s, %a1 -> Register[2];
         free_register %r2;",
    );
    assert_eq!(violations("", &body), []);
}

#[test]
fn a_wire_with_two_uses_fails() {
    let body = "%a0 = alloc;
                %a1, %a2 = circuit %a0 digraph ^g1(%a0: Wire) {
                  %a1 = h %a0;
                  %a2 = x %a0;
                  yield %a1, %a2;
                } -> Wire, Wire;
                free %a1;
                free %a2;
                %n = constant 0 -> Int;
                ret %n;";
    let found = violations("", body);
    assert_eq!(found.len(), 1, "{found:?}");
    assert_eq!(found[0].rule(), Rule::SingleUse);
    assert!(found[0].to_string().contains("%a0"), "{found:?}");
}

#[test]
fn a_wire_that_nothing_consumes_fails() {
    let body = "%a0 = alloc;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::SingleUse]);
}

#[test]
fn a_whole_register_statement_on_a_lent_register_fails() {
    let body = with_register(
        "%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1];
         %r2, %bits = measure_register %r1 -> Register[2; lent=1], MeasurementResults[2];
         %r3 = release %r2, %s, %a0 -> Register[2];
         free_register %r3;",
    );
    assert_eq!(rules("", &body), [Rule::Type]);
}

#[test]
fn two_borrows_that_exchange_their_qubits_fail() {
    let body = with_register(
        "%r1, %s0, %a = borrow %r0, %i -> Register[2; lent=1];
         %r2, %s1, %b = borrow %r1, %j -> Register[2; lent=2];
         %r3 = release %r2, %s0, %b -> Register[2; lent=1];
         %r4 = release %r3, %s1, %a -> Register[2];
         free_register %r4;",
    );
    assert_eq!(rules("", &body), [Rule::Origin, Rule::Origin]);
}

#[test]
fn a_replace_moves_a_qubit_to_a_new_position() {
    let body = with_register(
        "%a = alloc;
         %r1, %b = replace %r0, %i, %a -> Register[2];
         %r2, %c = replace %r1, %j, %b -> Register[2];
         free %c;
         free_register %r2;",
    );
    assert_eq!(violations("", &body), []);
}

#[test]
fn a_slot_of_another_register_fails() {
    let body = with_register(
        "%q0 = alloc_register %n -> Register[2];
         %r1, %s, %a = borrow %r0, %i -> Register[2; lent=1];
         %q1, %t, %b = borrow %q0, %i -> Register[2; lent=1];
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
fn a_gate_in_both_arms_of_a_conditional_passes() {
    let body = with_register(
        "%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1];
         %a1 = conditional %c (%a0) then block ^then(%t: Wire) {
           %flipped = circuit %t digraph ^g2(%t: Wire) {
             %flipped = x %t;
             yield %flipped;
           } -> Wire;
           yield %flipped;
         } else block ^else(%e: Wire) {
           yield %e;
         } -> Wire;
         %r2 = release %r1, %s, %a1 -> Register[2];
         free_register %r2;",
    );
    assert_eq!(violations("%c: Bool", &body), []);
}

#[test]
fn a_conditional_on_a_read_measurement_result_passes() {
    let body = "%a0 = alloc;
                %a1, %bit = circuit %a0 digraph ^g3(%a0: Wire) {
                  %a1, %bit = measure %a0;
                  yield %a1, %bit;
                } -> Wire, MeasurementResult;
                %one = is_one %bit;
                %a2 = conditional %one (%a1) then block ^then(%t: Wire) {
                  %flipped = circuit %t digraph ^g4(%t: Wire) {
                    %flipped = x %t;
                    yield %flipped;
                  } -> Wire;
                  yield %flipped;
                } else block ^else(%e: Wire) {
                  yield %e;
                } -> Wire;
                free %a2;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(violations("", body), []);
}

#[test]
fn an_if_arm_that_reads_a_wire_from_above_fails() {
    let body = "%a = alloc;
                %n = constant 0 -> Int;
                if %c then block ^then() {
                  free %a;
                  yield;
                } else block ^else() {
                  free %a;
                  yield;
                };
                ret %n;";
    assert_eq!(rules("%c: Bool", body), [Rule::Capture]);
}

#[test]
fn a_conditional_arm_that_drops_its_wire_fails() {
    let body = "%a = alloc;
                %n = constant 0 -> Int;
                conditional %c (%a) then block ^then(%t: Wire) {
                  free %t;
                  yield;
                } else block ^else(%e: Wire) {
                  yield;
                };
                ret %n;";
    assert_eq!(rules("%c: Bool", body), [Rule::SingleUse]);
}

#[test]
fn a_wire_that_a_block_and_its_conditional_both_consume_fails() {
    let body = "%a = alloc;
                %n = constant 0 -> Int;
                free %a;
                conditional %c (%a) then block ^then(%t: Wire) {
                  free %t;
                  yield;
                } else block ^else(%e: Wire) {
                  free %e;
                  yield;
                };
                ret %n;";
    assert_eq!(rules("%c: Bool", body), [Rule::SingleUse]);
}

#[test]
fn a_conditional_that_swaps_its_wires_in_one_arm_fails_the_release() {
    let body = with_register(
        "%r1, %s, %a0 = borrow %r0, %i -> Register[2; lent=1];
         %r2, %u, %b0 = borrow %r1, %j -> Register[2; lent=2];
         %a1, %b1 = conditional %c (%a0, %b0) then block ^then(%ta: Wire, %tb: Wire) {
           yield %tb, %ta;
         } else block ^else(%ea: Wire, %eb: Wire) {
           yield %ea, %eb;
         } -> Wire, Wire;
         %r3 = release %r2, %s, %a1 -> Register[2; lent=1];
         %r4 = release %r3, %u, %b1 -> Register[2];
         free_register %r4;",
    );
    let found = rules("%c: Bool", &body);
    assert!(!found.is_empty(), "{found:?}");
    assert!(found.iter().all(|rule| *rule == Rule::Origin), "{found:?}");
}

#[test]
fn a_conditional_on_an_integer_fails() {
    let body = "%a = alloc;
                %n = constant 0 -> Int;
                %b = conditional %n (%a) then block ^then(%t: Wire) {
                  yield %t;
                } else block ^else(%e: Wire) {
                  yield %e;
                } -> Wire;
                free %b;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Type]);
}

#[test]
fn a_release_inside_a_conditional_fails() {
    let body = with_register(
        "%r1, %s, %a = borrow %r0, %i -> Register[2; lent=1];
         %r2 = conditional %c (%r1, %s, %a) then block ^then(%tr: Register[2; lent=1], %ts: Slot, %ta: Wire) {
           %filled = release %tr, %ts, %ta -> Register[2];
           yield %filled;
         } else block ^else(%er: Register[2; lent=1], %es: Slot, %ea: Wire) {
           %same = release %er, %es, %ea -> Register[2];
           yield %same;
         } -> Register[2];
         free_register %r2;",
    );
    let found = rules("%c: Bool", &body);
    assert!(found.contains(&Rule::SlotScope), "{found:?}");
}

#[test]
fn a_loop_that_borrows_and_releases_each_element_passes() {
    let body = with_register(
        "%r3 = for %i in %i..%n step %j iter_args(%r0) do block ^body(%k: Int, %r: Register[2]) {
           %r1, %s, %a0 = borrow %r, %k -> Register[2; lent=1];
           %a1 = circuit %a0 digraph ^g5(%a0: Wire) {
             %a1 = h %a0;
             yield %a1;
           } -> Wire;
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
           %r1, %s, %a = borrow %r, %k -> Register[2; lent=1];
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
        "%a = alloc;
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
         %r1, %s0, %a = borrow %r0, %first -> Register[2; lent=1];
         %r2, %s1, %b = borrow %r1, %second -> Register[2; lent=2];
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
        "%r1, %s0, %a = borrow %r0, %i -> Register[2; lent=1];
         %r2, %s1, %b = borrow %r1, %j -> Register[2; lent=2];
         %r3 = release %r2, %s0, %a -> Register[2; lent=1];
         %r4, %s2, %c = borrow %r3, %i -> Register[2; lent=2];
         %r5 = release %r4, %s2, %c -> Register[2; lent=1];
         %r6 = release %r5, %s1, %b -> Register[2];
         free_register %r6;",
    );
    assert_eq!(violations("", &body), []);
}

#[test]
fn a_bottom_wire_cannot_supply_both_operands_of_a_gate() {
    let body = "%b, %c = cx %a, %a;
                free %b;
                free %c;
                %n = constant 0 -> Int;
                ret %n;";
    assert!(rules("%a: Bottom", body).contains(&Rule::Type), "{body}");
}

#[test]
fn packing_wires_cannot_hide_register_ownership_in_any() {
    let body = "%a = alloc;
                %r = pack %a -> Any;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Type]);
}

#[test]
fn an_if_cannot_hide_wire_ownership_in_any() {
    let body = "%a = alloc;
                %r = if %c then block ^then() {
                  yield %a;
                } else block ^else() {
                  yield %a;
                } -> Any;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(
        rules("%c: Bool", body),
        [Rule::Type, Rule::Type, Rule::Capture]
    );
}

fn borrow_inside_loop(index: &str) -> String {
    with_register(&format!(
        "%r1, %s, %a = borrow %r0, %i -> Register[2; lent=1];
         %r2 = for %i in %i..%n step %j iter_args(%r1) do block ^body(%k: Int, %r: Register[2; lent=1]) {{
           %r3, %t, %b = borrow %r, {index} -> Register[2; lent=2];
           %b1 = circuit %b digraph ^g6(%b: Wire) {{
             %b1 = h %b;
             yield %b1;
           }} -> Wire;
           %r4 = release %r3, %t, %b1 -> Register[2; lent=1];
           yield %r4;
         }} -> Register[2; lent=1];
         %r5 = release %r2, %s, %a -> Register[2];
         free_register %r5;"
    ))
}

#[test]
fn a_loop_cannot_borrow_an_element_that_its_input_already_lent() {
    assert_eq!(rules("", &borrow_inside_loop("%i")), [Rule::Distinct]);
}

#[test]
fn a_loop_can_borrow_another_element_while_an_outer_borrow_stays_open() {
    assert_eq!(violations("", &borrow_inside_loop("%j")), []);
}

#[test]
fn a_loop_must_prove_its_index_differs_from_an_outer_borrow() {
    assert_eq!(rules("", &borrow_inside_loop("%k")), [Rule::Distinct]);
}

#[test]
fn a_function_cannot_borrow_when_its_input_has_unknown_open_borrows() {
    let body = "%i = constant 0 -> Int;
                %r1, %s, %a = borrow %r, %i -> Register[2; lent=2];
                %r2 = release %r1, %s, %a -> Register[2; lent=1];
                ret %r2;";
    let text = format!(
        "stage @kernel fn @main(Register[2; lent=1]) -> Register[2; lent=1];
         specialize @kernel fn @main(Register[2; lent=1]) -> Register[2; lent=1] cfg {{
           ^entry(%r: Register[2; lent=1]) {{ {body} }}
         }}"
    );
    let error = common::check(&text).err().expect("The borrow must fail.");
    let common::Rejected::Invalid(found) = error else {
        panic!("{error:?}");
    };
    assert_eq!(
        found.iter().map(Violation::rule).collect::<Vec<_>>(),
        [Rule::Distinct]
    );
}

#[test]
fn a_function_cannot_return_a_wire_as_an_integer() {
    assert_eq!(rules("", "%a = alloc; ret %a;"), [Rule::Type]);
}

#[test]
fn a_function_must_return_the_declared_number_of_values() {
    for body in ["ret;", "%n = constant 0 -> Int; ret %n, %n;"] {
        assert_eq!(rules("", body), [Rule::Type], "{body}");
    }
}

#[test]
fn a_function_entry_must_match_its_declared_parameters() {
    let text = "stage @kernel fn @main(Float) -> Int;
                specialize @kernel fn @main(Float) -> Int cfg {
                  ^entry(%n: Int) { ret %n; }
                }";
    let error = common::check(text).err().expect("The parameter must fail.");
    let common::Rejected::Invalid(found) = error else {
        panic!("{error:?}");
    };
    assert_eq!(
        found.iter().map(Violation::rule).collect::<Vec<_>>(),
        [Rule::Type]
    );
}

#[test]
fn a_gate_in_a_block_fails() {
    let body = "%a0 = alloc;
                %a1 = h %a0;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Placement]);
}

#[test]
fn a_register_statement_in_a_graph_fails() {
    let body = "%n = constant 1 -> Int;
                %r0 = alloc_register %n -> Register[1];
                %r1 = circuit %r0 digraph ^g(%r: Register[1]) {
                  %m = constant 1 -> Int;
                  %fresh = alloc_register %m -> Register[1];
                  free_register %r;
                  yield %fresh;
                } -> Register[1];
                free_register %r1;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Placement, Rule::Placement]);
}

#[test]
fn an_allocation_and_a_free_in_a_graph_pass() {
    let body = "%a0 = alloc;
                %a1 = circuit %a0 digraph ^g(%a: Wire) {
                  %b = alloc;
                  %a2, %b1 = cx %a, %b;
                  free %b1;
                  yield %a2;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(violations("", body), []);
}

#[test]
fn a_graph_that_reads_an_outer_wire_fails() {
    let body = "%a0 = alloc;
                %b0 = alloc;
                %a1 = circuit %a0 digraph ^g(%a: Wire) {
                  %a2, %b1 = cx %a, %b0;
                  free %b1;
                  yield %a2;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Capture]);
}

#[test]
fn a_graph_port_with_two_uses_fails() {
    let body = "%a0 = alloc;
                %a1, %a2 = circuit %a0 digraph ^g(%a: Wire) {
                  %b = h %a;
                  %c = x %a;
                  yield %b, %c;
                } -> Wire, Wire;
                free %a1;
                free %a2;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::SingleUse]);
}

#[test]
fn a_region_result_of_the_wrong_type_fails() {
    let body = "%a0 = alloc;
                %a1 = circuit %a0 digraph ^g(%a: Wire) {
                  %b = h %a;
                  yield %b;
                } -> MeasurementResult;
                %n = constant 0 -> Int;
                ret %n;";
    assert!(rules("", body).contains(&Rule::Type));
}

#[test]
fn a_graph_with_a_cycle_fails() {
    // Kirin accepts a cyclic digraph as IR, so the verifier must reject it.
    let body = "%a0 = alloc;
                %a1 = circuit %a0 digraph ^g(%a: Wire) {
                  %x, %y = cx %a, %z;
                  %z = h %y;
                  yield %x;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Scope]);
}

#[test]
fn a_graph_that_reads_an_outer_angle_without_a_capture_fails() {
    let body = "%x = constant 0.5 -> Float;
                %a0 = alloc;
                %a1 = circuit %a0 digraph ^g(%a: Wire) {
                  %b = rz(%x) %a;
                  yield %b;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Capture]);
}

#[test]
fn a_graph_with_a_captured_angle_passes() {
    let body = "%x = constant 0.5 -> Float;
                %a0 = alloc;
                %a1 = circuit %a0, %x digraph ^g(%a: Wire) capture(%t: Float) {
                  %b = rz(%t) %a;
                  yield %b;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(violations("", body), []);
}

#[test]
fn a_wire_in_the_capture_list_fails() {
    let body = "%a0 = alloc;
                %a1 = circuit %a0 digraph ^g() capture(%a: Wire) {
                  %b = h %a;
                  yield %b;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Capture]);
}

#[test]
fn a_conditional_on_a_raw_measurement_result_fails() {
    // A result can also report a lost atom, so the program must read it first.
    let body = "%a0 = alloc;
                %a1, %m = circuit %a0 digraph ^g(%a: Wire) {
                  %a2, %r = measure %a;
                  yield %a2, %r;
                } -> Wire, MeasurementResult;
                %a3 = conditional %m (%a1) then block ^then(%t: Wire) {
                  yield %t;
                } else block ^else(%e: Wire) {
                  yield %e;
                } -> Wire;
                free %a3;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Type]);
}

#[test]
fn each_read_of_a_measurement_result_gives_a_bool() {
    let body = "%a0 = alloc;
                %a1, %m = circuit %a0 digraph ^g(%a: Wire) {
                  %a2, %r = measure %a;
                  yield %a2, %r;
                } -> Wire, MeasurementResult;
                %zero = is_zero %m;
                %one = is_one %m;
                %lost = is_lost %m;
                %either = or %zero, %one -> Bool;
                %kept = not %lost -> Bool;
                %sure = and %either, %kept -> Bool;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(violations("", body), []);
}

#[test]
fn a_bitwise_statement_on_mixed_types_fails() {
    let body = "%t = constant true -> Bool;
                %n = constant 0 -> Int;
                %x = and %t, %n -> Bool;
                ret %n;";
    assert_eq!(rules("", body), [Rule::Type]);
}
