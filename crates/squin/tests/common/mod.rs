//! Share the kernel parser of the squin tests.

use kirin::prelude::*;
use squin::Squin;

/// Parse a kernel with the parameters `parameters` and the statements `body`.
///
/// `parameters` is a list such as `"%c: Bool, %a: Float"`. The kernel has one
/// function, which returns an `Int`.
#[allow(dead_code)]
pub fn kernel(parameters: &str, body: &str) -> Pipeline<StageInfo<Squin>> {
    let types: Vec<&str> = parameters
        .split(',')
        .filter_map(|parameter| parameter.split(':').nth(1))
        .map(str::trim)
        .collect();
    let signature = format!("fn @main({}) -> Int", types.join(", "));
    let program = format!(
        "stage @kernel {signature};\n\
         specialize @kernel {signature} cfg {{\n  ^entry({parameters}) {{\n{body}\n  }}\n}}\n"
    );
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    if let Err(error) = pipeline.parse(&program) {
        panic!("the kernel must parse: {error:?}\n{program}");
    }
    pipeline
}

/// Tell why a program text does not give a verified program.
#[derive(Debug)]
#[allow(dead_code)]
pub enum Rejected {
    Parse(kirin::parsers::FunctionParseError),
    Invalid(Vec<squin::Violation>),
}

/// Parse `text` and verify every function of its stage `@kernel`.
#[allow(dead_code)]
pub fn check(text: &str) -> Result<Pipeline<StageInfo<Squin>>, Rejected> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(text).map_err(Rejected::Parse)?;
    let stage = pipeline
        .stage_by_name("kernel")
        .expect("the text declares @kernel");
    squin::verify(pipeline.stage(stage).unwrap()).map_err(Rejected::Invalid)?;
    Ok(pipeline)
}

/// Name one gate that a kernel applies, with the Stim-style indices of its qubits.
#[derive(Clone, Debug, PartialEq)]
#[allow(dead_code)]
pub struct Applied {
    pub gate: String,
    pub qubits: Vec<u32>,
    pub angles: Vec<f64>,
}

/// Return the gates that the straight-line function `@main` of the stage `@kernel` applies.
///
/// The address analysis names the qubit of each wire. Each `alloc` gets the
/// next index. An angle must be a float constant or a sum, a difference, a
/// product or a negation of such constants.
#[allow(dead_code)]
pub fn applied(pipeline: &Pipeline<StageInfo<Squin>>) -> Vec<Applied> {
    use squin::Threads;
    use squin::analysis::address;
    use squin::ir::ops::{Gate, QubitOp};
    use squin::ir::query;

    let addresses = address::analyze(pipeline, "kernel", "main").expect("the analysis runs");
    let stage = pipeline
        .stage(pipeline.stage_by_name("kernel").unwrap())
        .unwrap();
    let entry = query::body_blocks(stage, addresses.definition())[0];
    let mut indices = std::collections::HashMap::new();
    let mut gates = Vec::new();
    for statement in entry.statements(stage) {
        match statement.definition(stage) {
            Squin::Qubit(QubitOp::Alloc(alloc)) => {
                let qubit = addresses.of(alloc.wire).qubit().expect("a fresh qubit");
                let next = indices.len() as u32;
                indices.insert(qubit, next);
            }
            Squin::Gate(gate) => {
                let name = format!("{gate:?}");
                let angles = match gate {
                    Gate::Rx(rx) => vec![rx.angle],
                    Gate::Ry(ry) => vec![ry.angle],
                    Gate::Rz(rz) => vec![rz.angle],
                    Gate::U3(u3) => vec![u3.theta, u3.phi, u3.lam],
                    _ => Vec::new(),
                };
                let qubits = gate.threads().into_iter().map(|(wire, _)| {
                    let qubit = addresses.of(wire).qubit().expect("a known qubit");
                    indices[&qubit]
                });
                gates.push(Applied {
                    gate: name.split('(').next().unwrap().to_string(),
                    qubits: qubits.collect(),
                    angles: angles
                        .into_iter()
                        .map(|angle| float(stage, angle))
                        .collect(),
                });
            }
            _ => {}
        }
    }
    gates
}

/// Evaluate the float that the constant statements and the arithmetic before `value` compute.
fn float(stage: &StageInfo<Squin>, value: SSAValue) -> f64 {
    use kirin_arith::Arith;
    use squin::{ArithValue, Scalar};

    let SSAKind::Result(statement, _) = *value.expect_info(stage).kind() else {
        panic!("an angle must come from a statement");
    };
    match statement.definition(stage) {
        Squin::Constant(constant) => match constant.value {
            Scalar::Number(ArithValue::F64(angle)) => angle,
            ref other => panic!("{other:?} is no float"),
        },
        Squin::Arith(Arith::Add { lhs, rhs, .. }) => float(stage, *lhs) + float(stage, *rhs),
        Squin::Arith(Arith::Sub { lhs, rhs, .. }) => float(stage, *lhs) - float(stage, *rhs),
        Squin::Arith(Arith::Mul { lhs, rhs, .. }) => float(stage, *lhs) * float(stage, *rhs),
        Squin::Arith(Arith::Neg { operand, .. }) => -float(stage, *operand),
        other => panic!("the angle comes from {other:?}"),
    }
}
