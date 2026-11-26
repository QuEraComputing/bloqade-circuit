use kirin::prelude::*;
use squin::{
    Circuit, RzStats, Squin, Stage,
    ops::Rz,
    optimize_rz,
    rewrite::{merge_rz, remove_zero_rz},
    validate,
};

fn parse(body: &str) -> Pipeline<Stage> {
    let mut pipeline = Pipeline::new();
    pipeline.parse(&format!(
        "stage @squin fn @test(Wire) -> Wire; specialize @squin fn @test(Wire) -> Wire digraph ^circuit(%q: Wire) {{ {body} }}"
    )).unwrap();
    pipeline
}

fn stage(pipeline: &Pipeline<Stage>) -> &StageInfo<Circuit> {
    let Stage::Squin(stage) = pipeline
        .stage(pipeline.stage_by_name("squin").unwrap())
        .unwrap();
    stage
}

fn gates(pipeline: &Pipeline<Stage>) -> Vec<Rz> {
    stage(pipeline)
        .statement_arena()
        .iter()
        .filter_map(|item| match item.definition() {
            Circuit::Squin(Squin::Rz(op)) => Some(op.clone()),
            _ => None,
        })
        .collect()
}

fn optimize(pipeline: &mut Pipeline<Stage>) -> RzStats {
    let id = pipeline.stage_by_name("squin").unwrap();
    optimize_rz::<Circuit, _>(pipeline, id).unwrap()
}

fn assert_stable_round_trips(pipeline: &mut Pipeline<Stage>) {
    let printed = pipeline.sprint();
    assert_eq!(optimize(pipeline), RzStats::default());
    assert_eq!(pipeline.sprint(), printed);
    let mut parsed = Pipeline::<Stage>::new();
    parsed.parse(&printed).unwrap();
    let mut restored: Pipeline<Stage> =
        serde_json::from_slice(&serde_json::to_vec(pipeline).unwrap()).unwrap();
    for (format, pipeline) in [("text", &mut parsed), ("JSON", &mut restored)] {
        validate(stage(pipeline)).unwrap();
        assert_eq!(optimize(pipeline), RzStats::default());
        assert_eq!(
            pipeline.sprint(),
            printed,
            "The {format} round trip must preserve angles."
        );
    }
}

#[test]
fn zero_rule_redirects_graph_yields_and_preserves_linearity() {
    for angle in [0.0, -0.0] {
        let mut pipeline = parse(&format!("%r = rz({angle}) %q -> Wire; yield %r;"));
        let graph = stage(&pipeline).digraph_arena().iter().next().unwrap();
        let input = SSAValue::from(graph.ports()[0]);
        assert_eq!(
            optimize(&mut pipeline),
            RzStats {
                removed_zero: 1,
                merged: 0
            }
        );
        assert!(gates(&pipeline).is_empty());
        let graph = stage(&pipeline).digraph_arena().iter().next().unwrap();
        assert_eq!(graph.yields(), &[input]);
        assert_eq!(input.expect_info(stage(&pipeline)).uses().len(), 1);
        assert_stable_round_trips(&mut pipeline);
    }
}

#[test]
fn merging_preserves_the_last_result_and_combines_a_chain() {
    let mut pipeline = parse(
        "%a = rz(0.25) %q -> Wire; %b = rz(0.0) %a -> Wire; %c = rz(0.5) %b -> Wire; %d = rz(0.75) %c -> Wire; yield %d;",
    );
    let output = stage(&pipeline)
        .digraph_arena()
        .iter()
        .next()
        .unwrap()
        .yields()[0];
    assert_eq!(
        optimize(&mut pipeline),
        RzStats {
            removed_zero: 1,
            merged: 2
        }
    );
    let gates = gates(&pipeline);
    assert_eq!(gates.len(), 1);
    assert_eq!(gates[0].angle, 1.5);
    assert_eq!(SSAValue::from(gates[0].wire_out), output);
    assert_stable_round_trips(&mut pipeline);
}

#[test]
fn inverse_rotations_trigger_both_rules() {
    let mut pipeline = parse("%a = rz(0.5) %q -> Wire; %b = rz(-0.5) %a -> Wire; yield %b;");
    assert_eq!(
        optimize(&mut pipeline),
        RzStats {
            removed_zero: 1,
            merged: 1
        }
    );
    assert!(gates(&pipeline).is_empty());
    assert_stable_round_trips(&mut pipeline);
}

#[test]
fn dependency_order_handles_reversed_text_and_independent_operations() {
    let mut pipeline = parse(
        "%c = rz(0.5) %b -> Wire; %other = alloc -> Wire; %a = rz(0.25) %q -> Wire; %h = h %other -> Wire; %b = rz(0.75) %a -> Wire; free %h; yield %c;",
    );
    assert_eq!(optimize(&mut pipeline).merged, 2);
    assert_eq!(gates(&pipeline)[0].angle, 1.5);
    assert_stable_round_trips(&mut pipeline);
}

#[test]
fn gates_on_different_wires_stay_separate() {
    let mut pipeline = parse(
        "%other = alloc -> Wire; %a = rz(0.25) %q -> Wire; %b = rz(0.5) %other -> Wire; free %b; yield %a;",
    );
    assert_eq!(optimize(&mut pipeline), RzStats::default());
    assert_eq!(gates(&pipeline).len(), 2);
    assert_stable_round_trips(&mut pipeline);
}

#[test]
fn other_quantum_operations_end_a_consecutive_chain() {
    for middle in [
        "%mid = h %a -> Wire;",
        "%mid = reset %a -> Wire;",
        "%mid = r(0.25, 0.5) %a -> Wire;",
        "%mid, %bit = measure %a -> Wire, Bit;",
        "%other = alloc -> Wire; %mid, %target = cz %a, %other -> Wire, Wire; free %target;",
        "%other = alloc -> Wire; %mid, %target = cx %a, %other -> Wire, Wire; free %target;",
    ] {
        let mut pipeline = parse(&format!(
            "%a = rz(0.25) %q -> Wire; {middle} %b = rz(0.5) %mid -> Wire; yield %b;"
        ));
        assert_eq!(optimize(&mut pipeline), RzStats::default());
        assert_eq!(gates(&pipeline).len(), 2);
        assert_stable_round_trips(&mut pipeline);
    }
}

#[test]
fn exact_zero_policy_preserves_small_angles_and_global_phase() {
    for angle in [
        f64::from_bits(1),
        f64::MIN_POSITIVE,
        1e-15,
        std::f64::consts::TAU,
    ] {
        let mut pipeline = parse(&format!("%a = rz({angle}) %q -> Wire; yield %a;"));
        assert_eq!(optimize(&mut pipeline), RzStats::default());
        assert_eq!(gates(&pipeline)[0].angle.to_bits(), angle.to_bits());
    }
    let pi = std::f64::consts::PI;
    let mut pipeline = parse(&format!(
        "%a = rz({pi}) %q -> Wire; %b = rz({pi}) %a -> Wire; yield %b;"
    ));
    assert_eq!(
        optimize(&mut pipeline),
        RzStats {
            removed_zero: 0,
            merged: 1
        }
    );
    assert_eq!(gates(&pipeline)[0].angle, std::f64::consts::TAU);
}

#[test]
fn merging_uses_ordinary_f64_addition() {
    let max = f64::MAX;
    let mut pipeline = parse(&format!(
        "%a = rz({max}) %q -> Wire; %b = rz({max}) %a -> Wire; yield %b;"
    ));
    assert_eq!(optimize(&mut pipeline).merged, 1);
    assert_eq!(gates(&pipeline)[0].angle, f64::INFINITY);
    assert!(validate(stage(&pipeline)).is_err());
}

#[test]
fn both_rules_can_run_as_individual_kirin_passes() {
    let mut pipeline = parse("%a = rz(0.25) %q -> Wire; %b = rz(-0.25) %a -> Wire; yield %b;");
    let id = pipeline.stage_by_name("squin").unwrap();
    let output = gates(&pipeline)[1].wire_out;
    let SSAKind::Result(statement, _) = *output.expect_info(stage(&pipeline)).kind() else {
        unreachable!()
    };
    assert!(
        pipeline
            .run_pass::<Circuit, _, _, _>(id, |rw| merge_rz(rw, statement))
            .unwrap()
    );
    validate(stage(&pipeline)).unwrap();
    assert_eq!(gates(&pipeline)[0].angle, 0.0);
    assert!(
        pipeline
            .run_pass::<Circuit, _, _, _>(id, |rw| remove_zero_rz(rw, statement))
            .unwrap()
    );
    validate(stage(&pipeline)).unwrap();
    assert!(gates(&pipeline).is_empty());
}

#[test]
fn merging_preserves_rotation_matrices_with_f64_rounding() {
    for (a, b) in [
        (0.3, 0.7),
        (-2.5, 1.125),
        (3.0, -3.0),
        (1.0, std::f64::consts::TAU),
    ] {
        let mut pipeline = parse(&format!(
            "%a = rz({a}) %q -> Wire; %b = rz({b}) %a -> Wire; yield %b;"
        ));
        optimize(&mut pipeline);
        let combined = gates(&pipeline).first().map_or(0.0, |gate| gate.angle);
        for sign in [-1.0_f64, 1.0] {
            let (s1, c1) = (sign * a / 2.0).sin_cos();
            let (s2, c2) = (sign * b / 2.0).sin_cos();
            let (s, c) = (sign * combined / 2.0).sin_cos();
            assert!((c - (c1 * c2 - s1 * s2)).abs() < 1e-14);
            assert!((s - (s1 * c2 + c1 * s2)).abs() < 1e-14);
        }
    }
}
