//! Write a squin function as a Stim circuit.
//!
//! The emitter verifies the stage and runs the address analysis. It then walks
//! the function in program order. Each wire must carry a known qubit, so the
//! function needs constant register sizes and constant indices. Stim has no
//! loops over squin values and no branches, so a `for` is an error, and an `if`
//! needs a condition that the analysis knows.
//!
//! The emitter gives each qubit a Stim index. A qubit after a `free` gives its
//! index to the next allocation, which resets it first.

use std::collections::HashMap;

use kirin::prelude::*;
use kirin_scf::StructuredControlFlow;

use crate::analysis::address::{self, Address, AddressError, Addresses, QubitId};
use crate::ir::ops::{Gate, QubitOp, RegisterOp};
use crate::ir::traits::Threads;
use crate::ir::{Squin, query};
use crate::verify::{Violation, verify};

/// Tell why the emitter cannot write a function as a Stim circuit.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum StimError {
    #[error("The pipeline has no stage named {0}.")]
    UnknownStage(String),
    #[error("{}", lines(.0))]
    Invalid(Vec<Violation>),
    #[error(transparent)]
    Analysis(#[from] AddressError),
    #[error("The wire {0} carries no known qubit.")]
    UnknownQubit(String),
    #[error("Stim has no instruction for {0}.")]
    Unsupported(String),
}

fn lines(violations: &[Violation]) -> String {
    let lines: Vec<String> = violations.iter().map(Violation::to_string).collect();
    lines.join("\n")
}

/// Write the function `function` of the stage `stage` as a Stim circuit.
///
/// The result holds one instruction on each line.
pub fn emit(
    pipeline: &Pipeline<StageInfo<Squin>>,
    stage: &str,
    function: &str,
) -> Result<String, StimError> {
    let unknown = || StimError::UnknownStage(stage.to_string());
    let program = pipeline.stage(pipeline.stage_by_name(stage).ok_or_else(unknown)?);
    let program = program.ok_or_else(unknown)?;
    verify(program).map_err(StimError::Invalid)?;
    let addresses = address::analyze(pipeline, stage, function)?;
    let mut circuit = Circuit::new(program, &addresses);
    if let Some(entry) = query::body_blocks(program, addresses.definition()).first() {
        circuit.block(*entry)?;
    }
    Ok(circuit.finish())
}

/// Collect the instructions of a circuit and the Stim index of each qubit.
struct Circuit<'a> {
    program: &'a StageInfo<Squin>,
    addresses: &'a Addresses<'a>,
    lines: Vec<String>,
    indices: HashMap<QubitId, u32>,
    freed: Vec<u32>,
    next: u32,
}

impl<'a> Circuit<'a> {
    fn new(program: &'a StageInfo<Squin>, addresses: &'a Addresses<'a>) -> Self {
        Self {
            program,
            addresses,
            lines: Vec::new(),
            indices: HashMap::new(),
            freed: Vec::new(),
            next: 0,
        }
    }

    fn finish(self) -> String {
        self.lines.iter().map(|line| format!("{line}\n")).collect()
    }

    fn block(&mut self, block: Block) -> Result<(), StimError> {
        for statement in block.statements(self.program) {
            self.statement(statement)?;
        }
        Ok(())
    }

    fn statement(&mut self, statement: Statement) -> Result<(), StimError> {
        match statement.definition(self.program) {
            Squin::Gate(gate) => {
                let name = gate_name(gate).ok_or_else(|| unsupported(gate))?;
                let qubits = gate.threads().into_iter().map(|(wire, _)| self.index(wire));
                let qubits = qubits.collect::<Result<Vec<_>, _>>()?;
                self.instruction(name, &qubits);
            }
            Squin::Qubit(QubitOp::Alloc(alloc)) => self.allocate(alloc.wire.into())?,
            Squin::Qubit(QubitOp::Free(free)) => self.release(free.wire)?,
            Squin::Qubit(QubitOp::Measure(measure)) => {
                let qubit = self.index(measure.wire)?;
                self.instruction("M", &[qubit]);
            }
            Squin::Qubit(QubitOp::Reset(reset)) => {
                let qubit = self.index(reset.wire)?;
                self.instruction("R", &[qubit]);
            }
            Squin::Register(RegisterOp::AllocRegister(alloc)) => {
                self.allocate(alloc.register.into())?
            }
            Squin::Register(RegisterOp::FreeRegister(free)) => self.release(free.register)?,
            // Stim names every qubit by a fixed index, so each lent or moved
            // element must be a known qubit, even if no gate acts on it.
            Squin::Register(RegisterOp::Borrow(borrow)) => {
                self.index(borrow.wire.into())?;
            }
            Squin::Register(RegisterOp::Replace(replace)) => {
                self.index(replace.wire_out.into())?;
            }
            Squin::Register(RegisterOp::MeasureRegister(measure)) => {
                let qubits = self.indices_of(measure.register)?;
                self.instruction("M", &qubits);
            }
            Squin::Structured(StructuredControlFlow::If(branch)) => {
                let arm = match self.addresses.of(branch.condition()) {
                    Address::Bool(true) => branch.then_block(),
                    Address::Bool(false) => branch.else_block(),
                    _ => {
                        return Err(StimError::Unsupported(
                            "an `if` on a run-time condition".into(),
                        ));
                    }
                };
                self.block(arm)?;
            }
            Squin::Structured(StructuredControlFlow::For(_)) => {
                return Err(StimError::Unsupported(
                    "a `for` loop. Unroll the loop first".into(),
                ));
            }
            _ => {}
        }
        Ok(())
    }

    /// Give a Stim index to each qubit of the new wire or register `value`.
    fn allocate(&mut self, value: SSAValue) -> Result<(), StimError> {
        let qubits = self.qubits(value)?;
        for qubit in qubits {
            let index = match self.freed.pop() {
                Some(index) => {
                    self.instruction("R", &[index]);
                    index
                }
                None => {
                    self.next += 1;
                    self.next - 1
                }
            };
            self.indices.insert(qubit, index);
        }
        Ok(())
    }

    /// Return the Stim index of each qubit of the wire or register `value` to the free list.
    fn release(&mut self, value: SSAValue) -> Result<(), StimError> {
        let indices = self.indices_of(value)?;
        self.freed.extend(indices);
        Ok(())
    }

    /// Return the qubits of the wire or register `value`.
    fn qubits(&self, value: SSAValue) -> Result<Vec<QubitId>, StimError> {
        match self.addresses.of(value) {
            Address::Wire(qubit) => Ok(vec![qubit]),
            Address::Register(qubits) => Ok(qubits),
            _ => Err(StimError::UnknownQubit(query::name(self.program, value))),
        }
    }

    /// Return the Stim index of each qubit of the wire or register `value`.
    fn indices_of(&self, value: SSAValue) -> Result<Vec<u32>, StimError> {
        let qubits = self.qubits(value)?;
        let unknown = || StimError::UnknownQubit(query::name(self.program, value));
        qubits
            .iter()
            .map(|qubit| self.indices.get(qubit).copied().ok_or_else(unknown))
            .collect()
    }

    /// Return the Stim index of the qubit of the wire `wire`.
    fn index(&self, wire: SSAValue) -> Result<u32, StimError> {
        let indices = self.indices_of(wire)?;
        let unknown = || StimError::UnknownQubit(query::name(self.program, wire));
        indices.first().copied().ok_or_else(unknown)
    }

    fn instruction(&mut self, name: &str, qubits: &[u32]) {
        let targets: Vec<String> = qubits.iter().map(u32::to_string).collect();
        self.lines.push(format!("{name} {}", targets.join(" ")));
    }
}

/// Return the Stim name of a Clifford gate.
///
/// Stim holds Clifford gates only, so `t`, the rotations and `u3` have no name.
fn gate_name(gate: &Gate) -> Option<&'static str> {
    Some(match gate {
        Gate::X(_) => "X",
        Gate::Y(_) => "Y",
        Gate::Z(_) => "Z",
        Gate::H(_) => "H",
        Gate::S(_) => "S",
        Gate::SDag(_) => "S_DAG",
        Gate::SqrtX(_) => "SQRT_X",
        Gate::SqrtXDag(_) => "SQRT_X_DAG",
        Gate::SqrtY(_) => "SQRT_Y",
        Gate::SqrtYDag(_) => "SQRT_Y_DAG",
        Gate::CX(_) => "CX",
        Gate::CY(_) => "CY",
        Gate::CZ(_) => "CZ",
        _ => return None,
    })
}

fn unsupported(gate: &Gate) -> StimError {
    let name = format!("{gate:?}");
    let name = name.split('(').next().unwrap_or("this gate").to_string();
    StimError::Unsupported(format!("the gate {name}"))
}
