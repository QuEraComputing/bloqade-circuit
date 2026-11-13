//! Check that a circuit region parses, prints and passes facts through the address analysis.

use kirin::prelude::*;
use squin::Squin;
use squin::analysis::address::{self, Address};

const BELL: &str = "
stage @kernel fn @main() -> MeasurementResult;

specialize @kernel fn @main() -> MeasurementResult cfg {
  ^entry() {
    %a0 = alloc;
    %b0 = alloc;
    %a1, %b1, %m = circuit %a0, %b0 digraph ^dg0(%a: Wire, %b: Wire) {
      %a2 = h %a;
      %a3, %b2 = cx %a2, %b;
      %b3, %bit = measure %b2;
      yield %a3, %b3, %bit;
    } -> Wire, Wire, MeasurementResult;
    free %a1;
    free %b1;
    ret %m;
  }
}
";

/// Prepare a data qubit with an ancilla and correct it when the ancilla measures one.
const CORRECTION: &str = "
stage @kernel fn @main() -> MeasurementResult;

specialize @kernel fn @main() -> MeasurementResult cfg {
  ^entry() {
    %data0 = alloc;
    %anc0 = alloc;
    %data1, %anc1, %m = circuit %data0, %anc0 digraph ^prepare(%d: Wire, %a: Wire) {
      %a1 = h %a;
      %d1, %a2 = cx %d, %a1;
      %a3, %bit = measure %a2;
      yield %d1, %a3, %bit;
    } -> Wire, Wire, MeasurementResult;
    free %anc1;
    %flip = is_one %m;
    %data2 = conditional %flip (%data1) then block ^correct(%t: Wire) {
      %fixed = circuit %t digraph ^flip(%q: Wire) {
        %q1 = x %q;
        yield %q1;
      } -> Wire;
      yield %fixed;
    } else block ^keep(%e: Wire) {
      yield %e;
    } -> Wire;
    %data3, %out = circuit %data2 digraph ^read(%w: Wire) {
      %w1, %bit = measure %w;
      yield %w1, %bit;
    } -> Wire, MeasurementResult;
    free %data3;
    ret %out;
  }
}
";

fn parse(text: &str) -> Pipeline<StageInfo<Squin>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(text).expect("the program parses");
    pipeline
}

/// Return the SSA value that the program text names `name`, such as `%a1`.
fn value(pipeline: &Pipeline<StageInfo<Squin>>, name: &str) -> SSAValue {
    let stage = pipeline
        .stage(pipeline.stage_by_name("kernel").unwrap())
        .unwrap();
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
fn a_circuit_region_prints_and_parses_again() {
    let printed = parse(BELL).sprint();
    assert!(printed.contains("circuit"), "{printed}");
    assert_eq!(parse(&printed).sprint(), printed);
}

#[test]
fn a_circuit_region_keeps_the_qubit_of_each_wire() {
    let pipeline = parse(BELL);
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let fact = |name| addresses.of(value(&pipeline, name));
    assert!(matches!(fact("%a0"), Address::Wire(_)));
    assert_eq!(fact("%a"), fact("%a0"));
    assert_eq!(fact("%a3"), fact("%a0"));
    assert_eq!(fact("%a1"), fact("%a0"));
    assert_eq!(fact("%b1"), fact("%b0"));
    assert_ne!(fact("%a1"), fact("%b1"));
    assert_eq!(fact("%m"), Address::Top);
}

#[test]
fn a_correction_verifies_and_keeps_the_data_qubit() {
    let pipeline = parse(CORRECTION);
    let stage = pipeline.stage(pipeline.stage_by_name("kernel").unwrap());
    assert_eq!(squin::verify(stage.unwrap()), Ok(()));
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let fact = |name| addresses.of(value(&pipeline, name));
    for name in ["%data1", "%t", "%q1", "%fixed", "%e", "%data2", "%data3"] {
        assert_eq!(fact(name), fact("%data0"), "{name}");
    }
    assert_ne!(fact("%anc1"), fact("%data0"));
    assert_eq!(fact("%m"), Address::Top);
}
