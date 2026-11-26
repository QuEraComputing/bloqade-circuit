use kirin::prelude::*;
use squin::{Stage, Type, validate};

const BELL: &str = include_str!("../examples/bell_pair.kirin");

fn parse(text: &str) -> Pipeline<Stage> {
    let mut pipeline = Pipeline::new();
    pipeline.parse(text).unwrap();
    pipeline
}

fn check(text: &str) -> Result<(), squin::ValidationError> {
    for Stage::Squin(stage) in parse(text).stages() {
        validate(stage)?;
    }
    Ok(())
}

fn program(params: &str, arguments: &str, result: &str, body: &str) -> String {
    format!(
        "stage @squin fn @test({params}) -> {result};\nspecialize @squin fn @test({params}) -> {result} digraph ^circuit({arguments}) {{\n{body}\n}}"
    )
}

fn rejects(text: &str, message: &str) {
    let error = check(text).unwrap_err();
    assert!(
        error.message.contains(message),
        "Expected {message:?}, got {error}"
    );
}

#[test]
fn bell_pair_validates_and_round_trips() {
    let pipeline = parse(BELL);
    for Stage::Squin(stage) in pipeline.stages() {
        validate(stage).unwrap();
        for item in stage.statement_arena().iter() {
            if !matches!(item.definition(), squin::Circuit::Constant(_)) {
                assert!(!item.definition().is_pure());
            }
        }
    }
    let text = pipeline.sprint();
    check(&text).unwrap();
    assert_eq!(text, parse(&text).sprint());
    let json = serde_json::to_string(&pipeline).unwrap();
    let restored: Pipeline<Stage> = serde_json::from_str(&json).unwrap();
    for Stage::Squin(stage) in restored.stages() {
        validate(stage).unwrap();
    }
    assert_eq!(text, restored.sprint());
}

#[test]
fn types_preserve_lengths() {
    for ty in [
        Type::Wire,
        Type::Bit,
        Type::Int,
        Type::Unit,
        Type::register(0),
        Type::register(2),
        Type::register(u64::MAX),
        Type::dynamic_register(),
    ] {
        assert_eq!(parse_ast::<Type>(&ty.to_string()).unwrap(), ty);
        assert_eq!(
            serde_json::from_str::<Type>(&serde_json::to_string(&ty).unwrap()).unwrap(),
            ty
        );
    }
    for text in [
        "Register<-1>",
        "Register<18446744073709551616>",
        "Register<>",
    ] {
        assert!(parse_ast::<Type>(text).is_err(), "{text}");
    }
    assert!(Type::Wire.is_linear());
    assert!(Type::register(0).is_linear());
    assert!(Type::dynamic_register().is_linear());
    assert!(!Type::Bit.is_linear());
    assert!(!Type::Int.is_linear());
    assert!(!Type::Unit.is_linear());
}

#[test]
fn scalar_operations_and_returned_wires_validate() {
    check(&program("", "", "Bit", "%q = alloc -> Wire; %r = reset %q -> Wire; %m, %b = measure %r -> Wire, Bit; free %m; yield %b;")).unwrap();
    check(&program(
        "Wire",
        "%q: Wire",
        "Wire",
        "%h = h %q -> Wire; yield %h;",
    ))
    .unwrap();
    check(&program("Wire", "%q: Wire", "Unit", "free %q; yield;")).unwrap();
}

#[test]
fn duplicate_and_unused_linear_values_fail() {
    rejects(
        &program(
            "",
            "",
            "Unit",
            "%q = alloc -> Wire; free %q; free %q; yield;",
        ),
        "multiple consuming uses",
    );
    rejects(
        &program("Wire", "%q: Wire", "Unit", "yield;"),
        "0 consuming uses",
    );
    rejects(
        &program("", "", "Unit", "%q = alloc -> Wire; yield;"),
        "0 consuming uses",
    );
    rejects(
        &program("Wire", "%q: Wire", "Wire", "%h = h %q -> Wire; yield %q;"),
        "multiple consuming uses",
    );
    rejects(
        &program(
            "Wire",
            "%q: Wire",
            "Unit",
            "%a, %b = cx %q, %q -> Wire, Wire; free %a; free %b; yield;",
        ),
        "multiple consuming uses",
    );
    rejects(
        &program(
            "Register<2>",
            "%r: Register<2>",
            "Unit",
            "free_register %r; free_register %r; yield;",
        ),
        "multiple consuming uses",
    );
    rejects(
        &program("Register<2>", "%r: Register<2>", "Unit", "yield;"),
        "0 consuming uses",
    );
}

#[test]
fn operand_and_result_types_fail() {
    rejects(
        &program(
            "Int",
            "%n: Int",
            "Unit",
            "%q = h %n -> Wire; free %q; yield;",
        ),
        "requires Wire",
    );
    rejects(
        &program("Wire", "%q: Wire", "Unit", "%h = h %q -> Bit; yield;"),
        "requires Wire",
    );
    rejects(
        &program(
            "Wire",
            "%q: Wire",
            "Bit",
            "%m, %b = measure %q -> Wire, Int; free %m; yield %b;",
        ),
        "requires Bit",
    );
    rejects(
        &program(
            "Register<2>",
            "%r: Register<2>",
            "Unit",
            "%r1, %n = length %r -> Register<3>, Int; free_register %r1; yield;",
        ),
        "requires Register<2>",
    );
    rejects(
        &program("", "", "Unit", "%n = constant 2 -> Bit; yield;"),
        "requires Int",
    );
    rejects(&program("Int", "%n: Bit", "Unit", "yield;"), "requires Int");
    rejects(
        &program("Bit", "%b: Bit", "Wire", "yield %b;"),
        "requires Wire",
    );
    rejects(&program("", "", "Wire", "yield;"), "graph yield count");
}

#[test]
fn invalid_register_accesses_fail() {
    for index in [-1, 2, 3] {
        rejects(
            &program(
                "Register<2>",
                "%r: Register<2>",
                "Unit",
                &format!(
                    "%i = constant {index} -> Int; %r1, %q = borrow %r, %i -> Register<2>, Wire; free %q; free_register %r1; yield;"
                ),
            ),
            if index < 0 { "nonnegative" } else { "bounds" },
        );
    }
    rejects(
        &BELL.replace("borrow %r1, %one", "borrow %r1, %zero"),
        "already empty",
    );
    rejects(
        &BELL.replace("release %r3, %one", "release %r3, %zero"),
        "occupied",
    );
    rejects(
        &BELL
            .replace(
                "%r4 = release %r3, %one, %q1m -> Register<2>;",
                "free %q1m;",
            )
            .replace("free_register %r4", "free_register %r3"),
        "empty slots",
    );
    rejects(
        &program(
            "Register<2>, Wire",
            "%r: Register<2>, %q: Wire",
            "Unit",
            "%i = constant 0 -> Int; %r1 = release %r, %i, %q -> Register<2>; free_register %r1; yield;",
        ),
        "occupied",
    );
}

#[test]
fn unknown_indices_and_bounds_fail() {
    rejects(
        &program(
            "Register<2>, Int",
            "%r: Register<2>, %i: Int",
            "Unit",
            "%r1, %q = borrow %r, %i -> Register<2>, Wire; free %q; free_register %r1; yield;",
        ),
        "cannot prove the index",
    );
    rejects(
        &program(
            "Register<?>",
            "%r: Register<?>",
            "Unit",
            "%i = constant 0 -> Int; %r1, %q = borrow %r, %i -> Register<?>, Wire; free %q; free_register %r1; yield;",
        ),
        "unknown length",
    );
    rejects(
        &program(
            "Register<2>, Int",
            "%r: Register<2>, %i: Int",
            "Unit",
            "%z = constant 0 -> Int; %r1, %q = borrow %r, %z -> Register<2>, Wire; %r2 = release %r1, %i, %q -> Register<2>; free_register %r2; yield;",
        ),
        "cannot prove the index",
    );
}

#[test]
fn register_lengths_and_empty_slots_follow_successive_values() {
    check(&BELL.replace("Register<2>", "Register<?>")).unwrap();
    check(&program(
        "Register<?>",
        "%r: Register<?>",
        "Register<?>",
        "%r1, %n = length %r -> Register<?>, Int; yield %r1;",
    ))
    .unwrap();
    rejects(
        &program(
            "Register<2>",
            "%r: Register<2>",
            "Unit",
            "%i = constant 0 -> Int; %r1, %q = borrow %r, %i -> Register<2>, Wire; %r2, %n = length %r1 -> Register<2>, Int; free %q; free_register %r2; yield;",
        ),
        "empty slots",
    );
    rejects(
        &program(
            "Register<2>",
            "%r: Register<2>",
            "Register<2>",
            "%i = constant 0 -> Int; %r1, %q = borrow %r, %i -> Register<2>, Wire; free %q; yield %r1;",
        ),
        "empty slots",
    );
    check(&program("Register<2>", "%r: Register<2>", "Unit", "%r1, %n = length %r -> Register<2>, Int; %new = alloc_register %n -> Register<2>; free_register %new; free_register %r1; yield;")).unwrap();
    check(&program(
        "",
        "",
        "Unit",
        "%n = constant 0 -> Int; %r = alloc_register %n -> Register<0>; free_register %r; yield;",
    ))
    .unwrap();
}

#[test]
fn allocation_sizes_must_match_and_have_proven_bounds() {
    rejects(
        &program(
            "",
            "",
            "Unit",
            "%n = constant 2 -> Int; %r = alloc_register %n -> Register<3>; free_register %r; yield;",
        ),
        "matches its size",
    );
    rejects(
        &program(
            "",
            "",
            "Unit",
            "%n = constant -1 -> Int; %r = alloc_register %n -> Register<?>; free_register %r; yield;",
        ),
        "nonnegative allocation size",
    );
    rejects(
        &program(
            "Int",
            "%n: Int",
            "Unit",
            "%r = alloc_register %n -> Register<?>; free_register %r; yield;",
        ),
        "nonnegative allocation size",
    );
}

#[test]
fn graph_dependencies_allow_forward_references() {
    let text = program("", "", "Unit", "free %q; %q = alloc -> Wire; yield;");
    check(&text).unwrap();
}

#[test]
fn cfg_bodies_and_nested_graphs_fail() {
    let cfg =
        "stage @squin fn @test() -> Unit; specialize @squin fn @test() -> Unit cfg { ^entry() {} }";
    let mut pipeline = Pipeline::<Stage>::new();
    assert!(pipeline.parse(cfg).is_err());
    let nested = program(
        "",
        "",
        "Unit",
        "fn @nested() -> Unit digraph ^inside() { yield; }; yield;",
    );
    rejects(&nested, "does not support nested");
    rejects(&program("", "", "Wire", "yield;"), "graph yield count");
}

#[test]
fn equal_constant_indices_refer_to_the_same_slot() {
    rejects(
        &program(
            "Register<2>",
            "%r: Register<2>",
            "Unit",
            "%a = constant 0 -> Int; %b = constant 0 -> Int; %r1, %q0 = borrow %r, %a -> Register<2>, Wire; %r2, %q1 = borrow %r1, %b -> Register<2>, Wire; free %q0; free %q1; free_register %r2; yield;",
        ),
        "already empty",
    );
    check(&program(
        "Register<2>", "%r: Register<2>", "Unit",
        "%a = constant 0 -> Int; %b = constant 0 -> Int; %r1, %q = borrow %r, %a -> Register<2>, Wire; %r2 = release %r1, %b, %q -> Register<2>; free_register %r2; yield;",
    )).unwrap();
}

#[test]
fn disposal_allows_replacement_and_rejects_empty_register_access() {
    check(&program(
        "Register<2>", "%r: Register<2>", "Register<2>",
        "%i = constant 0 -> Int; %r1, %q = borrow %r, %i -> Register<2>, Wire; free %q; %replacement = alloc -> Wire; %r2 = release %r1, %i, %replacement -> Register<2>; yield %r2;",
    )).unwrap();
    rejects(
        &program(
            "Register<0>",
            "%r: Register<0>",
            "Unit",
            "%i = constant 0 -> Int; %r1, %q = borrow %r, %i -> Register<0>, Wire; free %q; free_register %r1; yield;",
        ),
        "bounds",
    );
}

#[test]
fn every_operation_survives_text_and_serialization_round_trips() {
    for text in [
        BELL.to_owned(),
        include_str!("../examples/phase.kirin").to_owned(),
        program(
            "",
            "",
            "Unit",
            "%q = alloc -> Wire; %r = reset %q -> Wire; free %r; yield;",
        ),
        program(
            "Register<2>",
            "%r: Register<2>",
            "Int",
            "%r1, %n = length %r -> Register<2>, Int; free_register %r1; yield %n;",
        ),
        program("Register<?>", "%r: Register<?>", "Register<?>", "yield %r;"),
    ] {
        check(&text).unwrap();
        let pipeline = parse(&text);
        let printed = pipeline.sprint();
        assert_eq!(printed, parse(&printed).sprint());
        let restored: Pipeline<Stage> =
            serde_json::from_slice(&serde_json::to_vec(&pipeline).unwrap()).unwrap();
        for Stage::Squin(stage) in restored.stages() {
            validate(stage).unwrap();
        }
        assert_eq!(printed, restored.sprint());
    }
}

#[test]
fn register_lengths_must_fit_the_classical_integer_type() {
    rejects(
        &program(
            "Register<9223372036854775808>",
            "%r: Register<9223372036854775808>",
            "Unit",
            "free_register %r; yield;",
        ),
        "must fit Int",
    );
    check(&program(
        "Register<9223372036854775807>",
        "%r: Register<9223372036854775807>",
        "Int",
        "%r1, %n = length %r -> Register<9223372036854775807>, Int; free_register %r1; yield %n;",
    ))
    .unwrap();
}

#[test]
fn graph_cycles_fail_even_when_each_wire_has_one_use() {
    for body in [
        "%q = h %q -> Wire; yield;",
        "%a = h %b -> Wire; %b = h %a -> Wire; yield;",
    ] {
        rejects(&program("", "", "Unit", body), "has a cycle");
    }
}

#[test]
fn graph_yields_consume_values_and_preserve_parameter_types() {
    for (ty, argument) in [
        ("Wire", "%q: Wire"),
        ("Register<2>", "%q: Register<2>"),
        ("Register<?>", "%q: Register<?>"),
    ] {
        let pipeline = parse(&program(ty, argument, ty, "yield %q;"));
        for Stage::Squin(stage) in pipeline.stages() {
            validate(stage).unwrap();
            let graph = stage.digraph_arena().iter().next().unwrap();
            let value = graph.ports()[0].expect_info(stage);
            assert_eq!(
                value.uses().as_slice(),
                &[Use::DiGraphYield {
                    graph: graph.id(),
                    index: 0
                }]
            );
        }
        check(&pipeline.sprint()).unwrap();
    }
    rejects(
        &program("Wire", "%q: Wire", "Wire", "yield %q, %q;"),
        "multiple consuming uses",
    );
    rejects(
        &program("Wire", "%q: Wire", "Wire", "free %q; yield %q;"),
        "multiple consuming uses",
    );
    rejects(
        &program("", "", "Unit", "%q = alloc -> Wire; yield %q;"),
        "graph yield count",
    );
}

#[test]
fn graph_captures_fail() {
    rejects(
        "stage @squin fn @test() -> Wire; specialize @squin fn @test() -> Wire digraph ^circuit() capture(%q: Wire) { yield %q; }",
        "does not support graph captures",
    );
}

#[test]
fn register_analysis_follows_dependencies_in_reversed_text_order() {
    let mut lines: Vec<_> = BELL.lines().collect();
    let last_operation = lines.len() - 2;
    lines[2..last_operation].reverse();
    let reversed = lines.join("\n");
    check(&reversed).unwrap();
    let pipeline = parse(&reversed);
    check(&pipeline.sprint()).unwrap();
    let restored: Pipeline<Stage> =
        serde_json::from_slice(&serde_json::to_vec(&pipeline).unwrap()).unwrap();
    for Stage::Squin(stage) in restored.stages() {
        validate(stage).unwrap();
    }
}

#[test]
fn phase_gates_check_types_and_linear_uses() {
    check(include_str!("../examples/phase.kirin")).unwrap();
    rejects(
        &program(
            "Int",
            "%n: Int",
            "Unit",
            "%q = rz(0.5) %n -> Wire; free %q; yield;",
        ),
        "requires Wire",
    );
    rejects(
        &program("Wire", "%q: Wire", "Unit", "%r = rz(0.5) %q -> Bit; yield;"),
        "requires Wire",
    );
    rejects(
        &program(
            "Wire",
            "%q: Wire",
            "Unit",
            "%a, %b = cz %q, %q -> Wire, Wire; free %a; free %b; yield;",
        ),
        "multiple consuming uses",
    );
    rejects(
        &program(
            "Wire, Int",
            "%q: Wire, %n: Int",
            "Unit",
            "%a, %b = cz %q, %n -> Wire, Wire; free %a; free %b; yield;",
        ),
        "requires Wire",
    );
    rejects(
        &program(
            "Wire, Wire",
            "%q: Wire, %r: Wire",
            "Unit",
            "%a, %b = cz %q, %r -> Bit, Wire; free %b; yield;",
        ),
        "requires Wire",
    );
}

#[test]
fn r_preserves_native_parameters_in_text_and_serialization() {
    let text = program(
        "Wire",
        "%q: Wire",
        "Wire",
        "%r = r(0.125, -0.25) %q -> Wire; yield %r;",
    );
    let pipeline = parse(&text);
    let printed = pipeline.sprint();
    let restored: Pipeline<Stage> =
        serde_json::from_str(&serde_json::to_string(&pipeline).unwrap()).unwrap();
    for pipeline in [pipeline, parse(&printed), restored] {
        for Stage::Squin(stage) in pipeline.stages() {
            validate(stage).unwrap();
            let r = stage
                .statement_arena()
                .iter()
                .find_map(|item| match item.definition() {
                    squin::Circuit::Squin(squin::Squin::R(op)) => Some(op),
                    _ => None,
                })
                .unwrap();
            assert_eq!(r.axis_angle, 0.125);
            assert_eq!(r.rotation_angle, -0.25);
        }
        assert_eq!(pipeline.sprint(), printed);
    }
}

#[test]
fn r_checks_wire_types_and_linear_uses() {
    for (body, params, args, error) in [
        (
            "%r = r(0.25, 0.5) %q -> Wire; free %r; yield;",
            "Int",
            "%q: Int",
            "requires Wire",
        ),
        (
            "%r = r(0.25, 0.5) %q -> Bit; yield;",
            "Wire",
            "%q: Wire",
            "requires Wire",
        ),
        (
            "%r = r(0.25, 0.5) %q -> Wire; free %q; free %r; yield;",
            "Wire",
            "%q: Wire",
            "multiple consuming uses",
        ),
        (
            "%r = r(0.25, 0.5) %q -> Wire; yield;",
            "Wire",
            "%q: Wire",
            "0 consuming uses",
        ),
    ] {
        rejects(&program(params, args, "Unit", body), error);
    }
}
