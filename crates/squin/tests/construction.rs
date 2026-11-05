use kirin::prelude::*;
use squin::ops::{Alloc, Free, Function, H};
use squin::{Circuit, Type, validate};

#[path = "../examples/bell_pair.rs"]
mod bell_pair;

#[test]
fn construct_bell_pair_with_kirin_builders() {
    bell_pair::main().unwrap();
}

#[test]
fn graph_members_do_not_impose_execution_order() {
    let mut builder = BuilderStageInfo::<Circuit>::default();
    let alloc = Alloc::new(&mut builder);
    let free = Free::new(&mut builder, alloc.wire);
    let body = builder.digraph().node(free.into()).node(alloc.into()).new();
    Function::new(&mut builder, body, Signature::new(vec![], Type::Unit, ()));
    let stage = builder.finalize().unwrap();
    verify_derived(&stage).unwrap();
    validate(&stage).unwrap();
    assert_eq!(stage.cfg_arena().iter().count(), 0);
    assert_eq!(stage.block_arena().iter().count(), 0);
}

#[test]
fn validator_rejects_cross_function_uses() {
    let mut builder = BuilderStageInfo::<Circuit>::default();
    let alloc = Alloc::new(&mut builder);
    let wire = alloc.wire;
    let free = Free::new(&mut builder, wire);
    let body = builder.digraph().node(alloc.into()).node(free.into()).new();
    Function::new(&mut builder, body, Signature::new(vec![], Type::Unit, ()));
    let free = Free::new(&mut builder, wire);
    let body = builder.digraph().node(free.into()).new();
    Function::new(&mut builder, body, Signature::new(vec![], Type::Unit, ()));
    let stage = builder.finalize().unwrap();
    verify_derived(&stage).unwrap();
    let error = validate(&stage).unwrap_err();
    assert!(
        error.message.contains("outside its defining graph"),
        "{error}"
    );
}

#[test]
fn wire_continuations_identify_operand_and_result_positions() {
    let mut builder = BuilderStageInfo::<Circuit>::default();
    let alloc = Alloc::new(&mut builder);
    let input = alloc.wire;
    let h = H::new(&mut builder, input);
    let output = h.wire_out;
    let gate: Statement = h.into();
    let body = builder
        .digraph()
        .node(alloc.into())
        .node(gate)
        .yield_value(output.into())
        .new();
    Function::new(&mut builder, body, Signature::new(vec![], Type::Wire, ()));
    let stage = builder.finalize().unwrap();
    validate(&stage).unwrap();
    assert_eq!(
        match gate.definition(&stage) {
            Circuit::Squin(op) => op.threads(),
            _ => unreachable!(),
        },
        vec![(input.into(), output)]
    );
}

#[test]
fn structural_checks_reject_corrupt_use_metadata() {
    let mut builder = BuilderStageInfo::<Circuit>::default();
    let alloc = Alloc::new(&mut builder);
    let free = Free::new(&mut builder, alloc.wire);
    let body = builder.digraph().node(alloc.into()).node(free.into()).new();
    Function::new(&mut builder, body, Signature::new(vec![], Type::Unit, ()));
    let stage = builder.finalize().unwrap();
    let mut json = serde_json::to_value(&stage).unwrap();
    json["ssas"]["items"][0]["data"]["uses"] = serde_json::json!([]);
    let corrupt: StageInfo<Circuit> = serde_json::from_value(json).unwrap();
    let error = validate(&corrupt).unwrap_err();
    assert!(
        error.message.contains("Kirin rejected the structure"),
        "{error}"
    );
}

#[test]
fn construct_a_known_register_parameter_and_preserve_its_type() {
    use squin::ops::{Borrow, IntConstant, Length, Release};

    let mut builder = BuilderStageInfo::<Circuit>::default();
    let register = builder.graph_port().index(0);
    let index = IntConstant::new(&mut builder, 0);
    let borrow = Borrow::new(&mut builder, register, index.result);
    let length = Length::new(&mut builder, borrow.register_out);
    let release = Release::new(&mut builder, length.register_out, index.result, borrow.wire);
    for result in [
        borrow.register_out,
        length.register_out,
        release.register_out,
    ] {
        builder
            .ssa_arena_mut()
            .get_mut(SSAValue::from(result))
            .unwrap()
            .set_ty(Type::register(2));
    }
    let result = release.register_out;
    let body = builder
        .digraph()
        .port(Type::register(2))
        .node(index.into())
        .node(borrow.into())
        .node(length.into())
        .node(release.into())
        .yield_value(result.into())
        .new();
    Function::new(
        &mut builder,
        body,
        Signature::new(vec![Type::register(2)], Type::register(2), ()),
    );
    validate(&builder.finalize().unwrap()).unwrap();
}

#[test]
fn phase_gate_builders_preserve_wire_continuations() {
    use squin::ops::{CZ, R, Rz};
    let mut builder = BuilderStageInfo::<Circuit>::default();
    let a = Alloc::new(&mut builder);
    let b = Alloc::new(&mut builder);
    let rz = Rz::new(&mut builder, -std::f64::consts::FRAC_PI_2, a.wire);
    let r = R::new(&mut builder, 0.125, -0.25, b.wire);
    let cz = CZ::new(&mut builder, rz.wire_out, r.wire_out);
    let free_a = Free::new(&mut builder, cz.control_out);
    let free_b = Free::new(&mut builder, cz.target_out);
    let rz_threads = vec![(a.wire.into(), rz.wire_out)];
    let r_threads = vec![(b.wire.into(), r.wire_out)];
    let cz_threads = vec![
        (rz.wire_out.into(), cz.control_out),
        (r.wire_out.into(), cz.target_out),
    ];
    let rz_stmt: Statement = rz.into();
    let cz_stmt: Statement = cz.into();
    let r_stmt: Statement = r.into();
    let body = builder
        .digraph()
        .node(a.into())
        .node(b.into())
        .node(r_stmt)
        .node(rz_stmt)
        .node(cz_stmt)
        .node(free_a.into())
        .node(free_b.into())
        .new();
    Function::new(&mut builder, body, Signature::new(vec![], Type::Unit, ()));
    let stage = builder.finalize().unwrap();
    validate(&stage).unwrap();
    for (statement, expected) in [
        (rz_stmt, rz_threads),
        (r_stmt, r_threads),
        (cz_stmt, cz_threads),
    ] {
        let Circuit::Squin(op) = statement.definition(&stage) else {
            panic!("The statement must be a Squin operation.")
        };
        assert_eq!(op.threads(), expected);
        assert!(!op.is_pure());
    }
}

#[test]
fn nonfinite_rotation_angles_fail() {
    use squin::ops::Rz;
    for angle in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        let mut builder = BuilderStageInfo::<Circuit>::default();
        let a = Alloc::new(&mut builder);
        let rz = Rz::new(&mut builder, angle, a.wire);
        let free = Free::new(&mut builder, rz.wire_out);
        let body = builder
            .digraph()
            .node(a.into())
            .node(rz.into())
            .node(free.into())
            .new();
        Function::new(&mut builder, body, Signature::new(vec![], Type::Unit, ()));
        assert!(
            validate(&builder.finalize().unwrap())
                .unwrap_err()
                .message
                .contains("must be finite")
        );
    }
}

#[test]
fn r_rejects_nonfinite_axis_and_rotation_angles() {
    use squin::ops::R;
    for angle in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        for (axis, rotation, message) in [
            (angle, 0.5, "axis angle must be finite"),
            (0.25, angle, "rotation angle must be finite"),
        ] {
            let mut builder = BuilderStageInfo::<Circuit>::default();
            let a = Alloc::new(&mut builder);
            let r = R::new(&mut builder, axis, rotation, a.wire);
            let free = Free::new(&mut builder, r.wire_out);
            let body = builder
                .digraph()
                .node(a.into())
                .node(r.into())
                .node(free.into())
                .new();
            Function::new(&mut builder, body, Signature::new(vec![], Type::Unit, ()));
            assert!(
                validate(&builder.finalize().unwrap())
                    .unwrap_err()
                    .message
                    .contains(message)
            );
        }
    }
}
