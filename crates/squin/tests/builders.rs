//! Check generated result types and the verifier boundary for Rust-built programs.

mod common;

use kirin::prelude::*;
use kirin_arith::ArithType;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use squin::ir::dialects::gate::*;
use squin::ir::dialects::measurement::{GetResult, PackResults, ResultsLength};
use squin::ir::dialects::qubit::{Alloc, Free, Measure, Reset};
use squin::ir::dialects::register::{FreeRegister, Pack};
use squin::{Length, Rule, Scalar, Squin, SquinType, verify};

fn gate_program(angle: Scalar) -> Pipeline<StageInfo<Squin>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse("stage @kernel fn @main() -> Int;").unwrap();
    let stage = pipeline.stage_by_name("kernel").unwrap();
    let function = pipeline.resolve_staged_function("main", stage).unwrap();
    pipeline.stage_mut(stage).unwrap().with_builder(|builder| {
        let angle = Constant::<Scalar, SquinType>::new(builder, angle);
        let zero = Constant::<Scalar, SquinType>::new(builder, Scalar::from(0_i64));
        let left = Alloc::new(builder);
        let right = Alloc::new(builder);
        let mut statements = vec![angle.id, zero.id, left.id, right.id];
        let (mut a, mut b) = (left.wire, right.wire);

        macro_rules! singles {
            ($($gate:ident),+) => {$(
                let next = $gate::new(builder, a);
                statements.push(next.id);
                a = next.wire_out;
            )+};
        }
        singles!(
            X, Y, Z, H, S, SDag, T, TDag, SqrtX, SqrtXDag, SqrtY, SqrtYDag
        );
        macro_rules! rotations {
            ($($gate:ident),+) => {$(
                let next = $gate::new(builder, angle.result, a);
                statements.push(next.id);
                a = next.wire_out;
            )+};
        }
        rotations!(Rx, Ry, Rz);
        let general = U3::new(builder, angle.result, angle.result, angle.result, a);
        statements.push(general.id);
        a = general.wire_out;
        macro_rules! controlled {
            ($($gate:ident),+) => {$(
                let next = $gate::new(builder, a, b);
                statements.push(next.id);
                (a, b) = (next.control_out, next.target_out);
            )+};
        }
        controlled!(CX, CY, CZ);
        let reset = Reset::new(builder, a);
        let measure = Measure::new(builder, reset.wire_out);
        let bits = PackResults::new(builder, vec![measure.result.into()]);
        let bit = GetResult::new(builder, bits.packed, zero.result);
        let length = ResultsLength::new(builder, bits.packed);
        let register = Pack::new(builder, vec![measure.wire_out.into(), b.into()]);
        let free = FreeRegister::new(builder, register.register);
        statements.extend([
            reset.id,
            measure.id,
            bits.id,
            bit.id,
            length.id,
            register.id,
            free.id,
        ]);
        let ret = Return::<SquinType>::new(builder, vec![length.length.into()]);
        let mut block = builder.block();
        for statement in statements {
            block = block.stmt(statement);
        }
        let entry = block.terminator(ret).new();
        let body = builder.cfg().add_block(entry).new();
        let signature = Signature::new(Vec::new(), SquinType::Number(ArithType::I64), ());
        let definition = Function::<SquinType>::new(builder, body, signature);
        builder
            .specialize()
            .staged_func(function)
            .definition(definition)
            .new()
            .unwrap();
    });
    pipeline
}

// The program puts its gates in a block, because the builders here make no
// `circuit` region. So the verifier reports placement and nothing else.
#[test]
fn generated_gate_builders_and_packing_give_the_result_types() {
    let pipeline = gate_program(Scalar::from(0.25));
    let stage = pipeline.stage_by_name("kernel").unwrap();
    let violations = verify(pipeline.stage(stage).unwrap()).err().unwrap();
    assert!(
        violations
            .iter()
            .all(|violation| violation.rule() == Rule::Placement),
        "{violations:?}"
    );
    let text = pipeline.sprint();
    assert!(!text.contains("Any"), "{text}");
    assert!(text.contains("MeasurementResults[1]"), "{text}");
    assert!(text.contains("Register[2]"), "{text}");
}

#[test]
fn generated_result_types_preserve_operand_type_checks() {
    let pipeline = gate_program(Scalar::from(1_i64));
    let stage = pipeline.stage_by_name("kernel").unwrap();
    let violations = verify(pipeline.stage(stage).unwrap()).err().unwrap();
    assert!(
        violations
            .iter()
            .any(|violation| violation.rule() == Rule::Type)
    );
}

#[test]
fn a_written_type_on_a_fixed_quantum_result_is_a_parse_error() {
    // The operation fixes these result types, so the text format has no place for them.
    for body in [
        "%a = alloc -> Int; free %a;",
        "%a = alloc; %b = h %a -> Int; free %b;",
        "%a = alloc; %b = reset %a -> Int; free %b;",
        "%a = alloc; %b, %bit = measure %a -> Wire, Int; free %b;",
    ] {
        let text = format!(
            "stage @kernel fn @main() -> Int;
             specialize @kernel fn @main() -> Int cfg {{
               ^entry() {{ {body} %zero = constant 0 -> Int; ret %zero; }}
             }}"
        );
        let result = common::check(&text);
        assert!(matches!(result, Err(common::Rejected::Parse(_))), "{text}");
    }
}

#[test]
fn empty_packs_have_known_zero_length() {
    let mut builder = BuilderStageInfo::<Squin>::default();
    let bits = PackResults::new(&mut builder, Vec::new());
    let register = Pack::new(&mut builder, Vec::new());
    let stage = builder.finalize().unwrap();
    assert_eq!(
        *bits.packed.expect_info(&stage).ty(),
        SquinType::MeasurementResults(Length::Known(0))
    );
    assert_eq!(
        *register.register.expect_info(&stage).ty(),
        SquinType::register(Length::Known(0))
    );
}

#[test]
fn gate_projection_uses_kirins_nested_wrapper_support() {
    let mut builder = BuilderStageInfo::<Squin>::default();
    let allocated = Alloc::new(&mut builder);
    let h = H::new(&mut builder, allocated.wire);
    let free = Free::new(&mut builder, h.wire_out);
    builder.block().stmt(allocated).stmt(h.id).stmt(free).new();
    let stage = builder.finalize().unwrap();
    let definition = h.id.definition(&stage).clone();
    let projected: H = definition.try_project_to().unwrap();
    assert_eq!(projected.wire_out, h.wire_out);
}
