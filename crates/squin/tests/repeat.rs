//! Check the repeat loop in the parser, the verifier, the address analysis and the emitter.

mod common;

use kirin::prelude::*;
use squin::analysis::address::{self, Address};
use squin::emit::stim::{self, StimError};
use squin::{Rule, Squin, verify};

/// Entangle a data qubit with a fresh ancilla until the ancilla measures one.
const UNTIL_SUCCESS: &str = "
    %d0 = alloc;
    %d1 = repeat (%d0) do block ^attempt(%d: Wire) {
      %a0 = alloc;
      %d2, %a1, %ok = circuit %d, %a0 digraph ^try(%q: Wire, %a: Wire) {
        %a2 = h %a;
        %q1, %a3 = cx %q, %a2;
        %a4, %bit = measure %a3;
        yield %q1, %a4, %bit;
      } -> Wire, Wire, Bit;
      free %a1;
      yield %ok, %d2;
    } -> Wire;
    free %d1;
    %n = constant 0 -> Int;
    ret %n;";

/// Verify the kernel and return the rule of each violation.
fn rules(body: &str) -> Vec<Rule> {
    let pipeline = common::kernel("", body);
    let stage: &StageInfo<Squin> = pipeline.stages().next().expect("the kernel has a stage");
    let violations = verify(stage).err().unwrap_or_default();
    violations
        .iter()
        .map(|violation| violation.rule())
        .collect()
}

/// Return the SSA value that the program text names `name`, such as `%d1`.
fn value(pipeline: &Pipeline<StageInfo<Squin>>, name: &str) -> SSAValue {
    let stage = pipeline.stages().next().unwrap();
    let wanted = name.trim_start_matches('%');
    let mut values = stage.ssa_arena().iter().filter_map(|item| item.as_ref());
    let found = values.find(|info| {
        let name = info
            .name()
            .and_then(|symbol| stage.symbol_table().resolve(symbol));
        name.map(String::as_str) == Some(wanted)
    });
    found
        .unwrap_or_else(|| panic!("the program names {name}"))
        .id()
}

#[test]
fn a_repeat_loop_prints_and_parses_again() {
    let printed = common::kernel("", UNTIL_SUCCESS).sprint();
    assert!(printed.contains("repeat"), "{printed}");
    let mut again: Pipeline<StageInfo<Squin>> = Pipeline::new();
    again.parse(&printed).expect("the printed text parses");
    assert_eq!(again.sprint(), printed);
}

#[test]
fn a_repeat_until_success_loop_verifies() {
    assert_eq!(rules(UNTIL_SUCCESS), []);
}

#[test]
fn a_repeat_loop_keeps_the_qubit_that_it_carries() {
    let pipeline = common::kernel("", UNTIL_SUCCESS);
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let fact = |name| addresses.of(value(&pipeline, name));
    assert!(matches!(fact("%d0"), Address::Wire(_)));
    for name in ["%d", "%q", "%q1", "%d2", "%d1"] {
        assert_eq!(fact(name), fact("%d0"), "{name}");
    }
    assert_ne!(fact("%a1"), fact("%d0"));
    assert_eq!(fact("%ok"), Address::Top);
}

#[test]
fn a_repeat_body_that_reads_an_outer_wire_fails() {
    let body = "%d0 = alloc;
                %b = alloc;
                %d1 = repeat (%d0) do block ^attempt(%d: Wire) {
                  free %b;
                  %stop = constant true -> Bool;
                  yield %stop, %d;
                } -> Wire;
                free %d1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules(body), [Rule::Capture]);
}

#[test]
fn a_repeat_body_that_swaps_its_wires_fails() {
    let body = "%a0 = alloc;
                %b0 = alloc;
                %a1, %b1 = repeat (%a0, %b0) do block ^attempt(%a: Wire, %b: Wire) {
                  %stop = constant true -> Bool;
                  yield %stop, %b, %a;
                } -> Wire, Wire;
                free %a1;
                free %b1;
                %n = constant 0 -> Int;
                ret %n;";
    let found = rules(body);
    assert!(!found.is_empty(), "{found:?}");
    assert!(found.iter().all(|rule| *rule == Rule::Origin), "{found:?}");
}

#[test]
fn a_repeat_body_needs_a_stop_flag() {
    let body = "%d0 = alloc;
                %d1 = repeat (%d0) do block ^attempt(%d: Wire) {
                  %stop = constant 1 -> Int;
                  yield %stop, %d;
                } -> Wire;
                free %d1;
                %n = constant 0 -> Int;
                ret %n;";
    assert_eq!(rules(body), [Rule::Type]);
}

#[test]
fn the_emitter_rejects_a_repeat_loop() {
    let pipeline = common::kernel("", UNTIL_SUCCESS);
    let circuit = stim::emit(&pipeline, "kernel", "main");
    assert!(
        matches!(circuit, Err(StimError::Unsupported(_))),
        "{circuit:?}"
    );
}
