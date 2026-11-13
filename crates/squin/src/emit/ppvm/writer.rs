//! Walk a function in program order and collect its ppvm instructions.

use kirin::prelude::*;

use super::PpvmError;
use super::locals::{Locals, Slot};
use super::names::{angles, gate_name};
use crate::analysis::address::Addresses;
use crate::emit::qubits::Qubits;
use crate::ir::dialects::gate::Gate;
use crate::ir::dialects::qubit::QubitOp;
use crate::ir::dialects::register::RegisterOp;
use crate::ir::traits::Threads;
use crate::ir::Squin;

/// Collect the instructions of a ppvm program, its qubit indices and its local slots.
pub(super) struct Writer<'a> {
    pub(super) program: &'a StageInfo<Squin>,
    pub(super) addresses: &'a Addresses<'a>,
    pub(super) locals: Locals,
    qubits: Qubits<'a>,
    lines: Vec<String>,
    labels: u32,
    /// Count the loops around the current statement.
    loops: u32,
}

impl<'a> Writer<'a> {
    pub(super) fn new(program: &'a StageInfo<Squin>, addresses: &'a Addresses<'a>) -> Self {
        Self {
            program,
            addresses,
            locals: Locals::default(),
            qubits: Qubits::new(program, addresses),
            lines: Vec::new(),
            labels: 0,
            loops: 0,
        }
    }

    /// Return the `.sst` text: the device header, then `@main` with its locals reserved.
    pub(super) fn finish(self) -> String {
        let mut text = format!(
            "device circuit.n_qubits {};\n\nfn @main() {{\n",
            self.qubits.count()
        );
        for _ in 0..self.locals.count() {
            text.push_str("    cpu::cpu.const bool, false\n");
        }
        for line in &self.lines {
            text.push_str(&format!("    {line}\n"));
        }
        text.push_str("}\n");
        text
    }

    pub(super) fn block(&mut self, block: Block) -> Result<(), PpvmError> {
        // The terminator comes last: `ret` ends the function, and a `yield`
        // leaves the owner of the block to copy its values.
        let body: Vec<Statement> = block
            .statements(self.program)
            .chain(block.terminator(self.program))
            .collect();
        for statement in body {
            self.statement(statement)?;
        }
        Ok(())
    }

    pub(super) fn statement(&mut self, statement: Statement) -> Result<(), PpvmError> {
        match statement.definition(self.program) {
            Squin::Gate(gate) => self.gate(gate)?,
            Squin::Qubit(QubitOp::Alloc(alloc)) => self.allocate(alloc.wire.into())?,
            Squin::Qubit(QubitOp::Free(free)) => self.qubits.release(free.wire)?,
            Squin::Qubit(QubitOp::Measure(measure)) => {
                let qubit = self.qubits.index(measure.wire)?;
                let slot = self.define(measure.result.into())[0];
                self.measure(qubit, slot);
            }
            Squin::Qubit(QubitOp::Reset(reset)) => {
                let qubit = self.qubits.index(reset.wire)?;
                self.qubit_instruction("reset", &[qubit]);
            }
            Squin::Register(RegisterOp::AllocRegister(alloc)) => {
                self.allocate(alloc.register.into())?
            }
            Squin::Register(RegisterOp::FreeRegister(free)) => {
                self.qubits.release(free.register)?
            }
            // ppvm names every qubit by a fixed index, so each lent or moved
            // element must be a known qubit, even if no gate acts on it.
            Squin::Register(RegisterOp::Borrow(borrow)) => {
                self.qubits.index(borrow.wire.into())?;
            }
            Squin::Register(RegisterOp::Replace(replace)) => {
                self.qubits.index(replace.wire_out.into())?;
            }
            Squin::Register(RegisterOp::MeasureRegister(measure)) => {
                let qubits = self.qubits.indices_of(measure.register)?;
                let slots = self.define(measure.results.into());
                for (qubit, slot) in qubits.into_iter().zip(slots) {
                    self.measure(qubit, slot);
                }
            }
            Squin::Register(_) | Squin::Function(_) => {}
            Squin::Return(_) => self.line("cpu::cpu.ret 0".to_string()),
            _ => self.control(statement)?,
        }
        Ok(())
    }

    /// Write `gate`: each qubit index, then each angle, then the instruction.
    fn gate(&mut self, gate: &Gate) -> Result<(), PpvmError> {
        let threads = gate.threads();
        let qubits = threads.iter().map(|(wire, _)| self.qubits.index(*wire));
        let qubits = qubits.collect::<Result<Vec<_>, _>>()?;
        let Some(name) = gate_name(gate) else {
            // ppvm has no `cy`, so the writer turns the target's Y axis into X:
            // `cy = s · cnot · s_adj` on the target.
            let target = &qubits[1..];
            self.qubit_instruction("s_adj", target);
            self.qubit_instruction("cnot", &qubits);
            self.qubit_instruction("s", target);
            return Ok(());
        };
        for qubit in &qubits {
            self.line(format!("cpu::cpu.const u64, {qubit}"));
        }
        for angle in angles(gate) {
            self.load(angle)?;
        }
        self.line(format!("circuit::circuit.{name}"));
        Ok(())
    }

    /// Give an index to each qubit of `value`, and reset a qubit that can hold a state.
    ///
    /// A reused index holds the state of a freed qubit. In a loop, a fresh
    /// index holds the state of the previous run.
    fn allocate(&mut self, value: SSAValue) -> Result<(), PpvmError> {
        for (index, reused) in self.qubits.allocate(value)? {
            if reused || self.loops > 0 {
                self.qubit_instruction("reset", &[index]);
            }
        }
        Ok(())
    }

    /// Measure the qubit `qubit` and store the outcome in `slot`.
    fn measure(&mut self, qubit: u32, slot: Slot) {
        self.qubit_instruction("measure", &[qubit]);
        self.line(format!("cpu::cpu.store {}, {}", slot.1, slot.0));
    }

    /// Push each qubit index and run the circuit instruction `name`.
    fn qubit_instruction(&mut self, name: &str, qubits: &[u32]) {
        for qubit in qubits {
            self.line(format!("cpu::cpu.const u64, {qubit}"));
        }
        self.line(format!("circuit::circuit.{name}"));
    }

    /// Return a new label, such as `@l3`.
    pub(super) fn label(&mut self) -> String {
        self.labels += 1;
        format!("@l{}", self.labels - 1)
    }

    /// Run `walk` with the loop count raised by one.
    pub(super) fn in_loop(
        &mut self,
        walk: impl FnOnce(&mut Self) -> Result<(), PpvmError>,
    ) -> Result<(), PpvmError> {
        self.loops += 1;
        let result = walk(self);
        self.loops -= 1;
        result
    }

    pub(super) fn line(&mut self, line: String) {
        self.lines.push(line);
    }
}
