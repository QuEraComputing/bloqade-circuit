//! Walk a function in program order and collect its Stim instructions.

use std::collections::HashMap;

use kirin::prelude::*;
use kirin_scf::StructuredControlFlow;

use super::StimError;
use super::names::{gate_name, unsupported};
use crate::analysis::address::{Address, Addresses, QubitId};
use crate::ir::dialects::qubit::QubitOp;
use crate::ir::dialects::register::RegisterOp;
use crate::ir::traits::Threads;
use crate::ir::{Squin, query};

/// Collect the instructions of a Stim circuit and the Stim index of each qubit.
pub(super) struct Writer<'a> {
    program: &'a StageInfo<Squin>,
    addresses: &'a Addresses<'a>,
    lines: Vec<String>,
    indices: HashMap<QubitId, u32>,
    freed: Vec<u32>,
    next: u32,
}

impl<'a> Writer<'a> {
    pub(super) fn new(program: &'a StageInfo<Squin>, addresses: &'a Addresses<'a>) -> Self {
        Self {
            program,
            addresses,
            lines: Vec::new(),
            indices: HashMap::new(),
            freed: Vec::new(),
            next: 0,
        }
    }

    pub(super) fn finish(self) -> String {
        self.lines.iter().map(|line| format!("{line}\n")).collect()
    }

    pub(super) fn block(&mut self, block: Block) -> Result<(), StimError> {
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
            Squin::Conditional(branch) => {
                let arm = match self.addresses.of(branch.condition) {
                    Address::Bool(true) => branch.then_body,
                    Address::Bool(false) => branch.else_body,
                    _ => {
                        return Err(StimError::Unsupported(
                            "a `conditional` on a run-time condition".into(),
                        ));
                    }
                };
                self.block(arm)?;
            }
            // Any topological order of the graph gives the same circuit,
            // because each gate follows the gates whose wires it reads.
            Squin::Circuit(region) => {
                let order = query::graph_order(self.program, region.body);
                let cycle = || StimError::Unsupported("a `circuit` graph with a cycle".into());
                for node in order.ok_or_else(cycle)? {
                    self.statement(node)?;
                }
            }
            Squin::Repeat(_) => {
                return Err(StimError::Unsupported(
                    "a `repeat` loop, because Stim cannot end a loop on a measurement".into(),
                ));
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
