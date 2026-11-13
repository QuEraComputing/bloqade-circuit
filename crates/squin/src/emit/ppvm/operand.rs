//! Name the qubit that a circuit instruction acts on.
//!
//! The address analysis fixes the qubit of most wires, so the emitter pushes
//! that index as a constant. A wire that a `borrow` lends at an index known
//! only at run time has its qubit index in a `u64` slot instead.

use kirin::prelude::*;

use super::PpvmEmitter;
use super::PpvmError;
use super::locals::Kind;
use crate::ir::traits::Threads;

/// Name one qubit operand of a circuit instruction.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Operand {
    /// The address analysis fixes the qubit index.
    Fixed(u32),
    /// The `u64` slot with this number holds the qubit index at run time.
    Stored(u32),
}

impl PpvmEmitter<'_> {
    /// Return the operand that names the qubit of `wire`.
    pub(super) fn operand(&self, wire: SSAValue) -> Result<Operand, PpvmError> {
        match self.qubits.index(wire) {
            Ok(index) => Ok(Operand::Fixed(index)),
            Err(unknown) => match self.env.read(self.index, wire)?.as_deref() {
                Some(&[(slot, Kind::U64)]) => Ok(Operand::Stored(slot)),
                _ => Err(unknown.into()),
            },
        }
    }

    /// Return the operand of each wire that `statement` acts on, in operand order.
    pub(super) fn operands(&self, statement: &impl Threads) -> Result<Vec<Operand>, PpvmError> {
        let threads = statement.threads();
        threads
            .iter()
            .map(|(wire, _)| self.operand(*wire))
            .collect()
    }

    /// Push the qubit index of `operand` onto the CPU stack.
    pub(super) fn push(&mut self, operand: Operand) {
        match operand {
            Operand::Fixed(index) => self.line(format!("cpu::cpu.const u64, {index}")),
            Operand::Stored(slot) => self.line(format!("cpu::cpu.load u64, {slot}")),
        }
    }

    /// Let each output wire of `statement` keep the slot of the input wire that it continues.
    ///
    /// A wire with a fixed qubit has no slot, so this only matters for a wire
    /// that a run-time `borrow` lends.
    pub(super) fn continue_wires(&mut self, statement: &impl Threads) -> Result<(), PpvmError> {
        for (wire, wire_out) in statement.threads() {
            self.alias(wire_out.into(), wire)?;
        }
        Ok(())
    }
}
