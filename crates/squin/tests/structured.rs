use kirin::prelude::*;
use kirin_scf::StructuredControlFlow;
use squin::{Squin, Type};

#[path = "../examples/structured.rs"]
mod example;

use example::{StructuredCircuit, StructuredStage};

fn parse(source: &str) -> Pipeline<StructuredStage> {
    let mut pipeline = Pipeline::new();
    pipeline.parse(source).unwrap();
    pipeline
}

fn check_bodies(pipeline: &Pipeline<StructuredStage>, graph_function: bool) {
    let StructuredStage::Structured(stage) = pipeline.stages().next().unwrap();
    verify_derived(stage).unwrap();
    assert_eq!(stage.cfg_arena().iter().count(), 0);
    assert_eq!(
        stage.digraph_arena().iter().count(),
        usize::from(graph_function)
    );
    assert_eq!(
        stage.block_arena().iter().count(),
        if graph_function { 3 } else { 4 }
    );

    let mut loops = 0;
    let mut branches = 0;
    let mut gates = 0;
    for statement in stage.statement_arena().iter() {
        match statement.definition() {
            StructuredCircuit::Function(function) => {
                assert!(!graph_function);
                assert_eq!(function.callable_body(), Some(Body::Block(function.body)));
            }
            StructuredCircuit::GraphFunction(function) => {
                assert!(graph_function);
                assert_eq!(function.callable_body(), Some(Body::DiGraph(function.body)));
            }
            StructuredCircuit::Scf(StructuredControlFlow::For(op)) => {
                loops += 1;
                assert_eq!(op.init_args().len(), 1);
                assert_eq!(op.results().len(), 1);
                assert_eq!(*op.init_args()[0].expect_info(stage).ty(), Type::Wire);
                assert_eq!(*op.results()[0].expect_info(stage).ty(), Type::Wire);
            }
            StructuredCircuit::Scf(StructuredControlFlow::If(op)) => {
                branches += 1;
                assert_eq!(*op.condition().expect_info(stage).ty(), Type::Bit);
                assert_eq!(*op.results()[0].expect_info(stage).ty(), Type::Wire);
            }
            StructuredCircuit::Squin(Squin::H(_) | Squin::Rz(_)) => gates += 1,
            _ => {}
        }
    }
    assert_eq!((loops, branches, gates), (1, 1, 3));
}

#[test]
fn quantum_gates_and_scf_share_nested_blocks() {
    check_bodies(&parse(include_str!("../examples/structured.kirin")), false);
}

#[test]
fn structured_circuit_preserves_bodies_in_round_trips() {
    for (source, graph_function) in [
        (include_str!("../examples/structured.kirin"), false),
        (include_str!("../examples/structured_digraph.kirin"), true),
    ] {
        let pipeline = parse(source);
        let text = pipeline.sprint();
        let from_text = parse(&text);
        let from_json = serde_json::from_str::<Pipeline<StructuredStage>>(
            &serde_json::to_string(&pipeline).unwrap(),
        )
        .unwrap();
        for restored in [from_text, from_json] {
            check_bodies(&restored, graph_function);
            assert_eq!(restored.sprint(), text);
        }
    }
}

#[test]
fn digraph_keeps_loop_dependencies_when_text_order_changes() {
    let source = include_str!("../examples/structured_digraph.kirin")
        .replace("  %initial = h %wire -> Wire;\n", "")
        .replace(
            "  free %out;",
            "  %initial = h %wire -> Wire;\n  free %out;",
        );
    let pipeline = parse(&source);
    check_bodies(&pipeline, true);
    let StructuredStage::Structured(stage) = pipeline.stages().next().unwrap();
    let graph = stage.digraph_arena().iter().next().unwrap();
    let loop_statement = graph
        .nodes()
        .find(|stmt| {
            matches!(
                stmt.definition(stage),
                StructuredCircuit::Scf(StructuredControlFlow::For(_))
            )
        })
        .unwrap();
    let StructuredCircuit::Scf(StructuredControlFlow::For(op)) = loop_statement.definition(stage)
    else {
        unreachable!()
    };
    let SSAKind::Result(producer, _) = *op.init_args()[0].expect_info(stage).kind() else {
        unreachable!()
    };
    assert!(
        graph
            .graph()
            .find_edge(
                graph.node_idx_of(producer).unwrap(),
                graph.node_idx_of(loop_statement).unwrap(),
            )
            .is_some()
    );
}

#[test]
fn digraph_dependencies_require_explicit_loop_inputs() {
    let captured = include_str!("../examples/structured_digraph.kirin")
        .replace("    %next = if %condition", "    %next = if %flag")
        .replace("  %out = for", "  %probe = alloc -> Wire;\n  %measured, %flag = measure %probe -> Wire, Bit;\n  free %measured;\n  %out = for");
    let explicit = captured
        .replace("%out = for", "%out, %condition_out = for")
        .replace("iter_args(%initial)", "iter_args(%initial, %flag)")
        .replace("%q: Wire)", "%q: Wire, %loop_condition: Bit)")
        .replace("if %flag then", "if %loop_condition then")
        .replace("yield %next;", "yield %next, %loop_condition;")
        .replace("  } -> Wire;\n  free", "  } -> Wire, Bit;\n  free");

    for (source, has_dependency) in [(captured, false), (explicit, true)] {
        let pipeline = parse(&source);
        let StructuredStage::Structured(stage) = pipeline.stages().next().unwrap();
        verify_derived(stage).unwrap();
        let graph = stage.digraph_arena().iter().next().unwrap();
        let measurement = graph
            .nodes()
            .find(|stmt| {
                matches!(
                    stmt.definition(stage),
                    StructuredCircuit::Squin(Squin::Measure(_))
                )
            })
            .unwrap();
        let loop_statement = graph
            .nodes()
            .find(|stmt| {
                matches!(
                    stmt.definition(stage),
                    StructuredCircuit::Scf(StructuredControlFlow::For(_))
                )
            })
            .unwrap();
        assert_eq!(
            graph
                .graph()
                .find_edge(
                    graph.node_idx_of(measurement).unwrap(),
                    graph.node_idx_of(loop_statement).unwrap(),
                )
                .is_some(),
            has_dependency
        );
    }
}

#[test]
fn scf_yield_conflicts_with_digraph_return_parsing() {
    let source = include_str!("../examples/structured_digraph.kirin")
        .replace("-> Unit", "-> Wire")
        .replace("free %out;", "yield %out;");
    let mut pipeline = Pipeline::<StructuredStage>::new();
    let error = pipeline.parse(&source).unwrap_err();
    assert!(
        error
            .to_string()
            .contains("digraph body cannot contain a terminator")
    );
}
